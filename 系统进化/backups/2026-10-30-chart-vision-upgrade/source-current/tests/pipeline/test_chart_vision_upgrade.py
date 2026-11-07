"""Isolated chart upgrade contracts: no credentials, live data or API calls."""
from __future__ import annotations
import asyncio
import copy
from datetime import datetime, timedelta
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import threading
import time
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
FILES = ['src/analytics/chart_input.py', 'src/analytics/chart_batch.py', 'src/analytics/lwc_chart_renderer.py', 'src/agents/chart_vision_agent.py', 'src/research/candidate_pool.py']


@pytest.fixture
def app(tmp_path, monkeypatch):
    assert tmp_path.resolve().is_relative_to(Path.home() / '.hermes/cache/scratch')
    root = tmp_path / 'app'
    for rel in FILES:
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, dst)
    saved = {k: v for k, v in sys.modules.items() if k == 'src' or k.startswith('src.')}
    for k in saved:
        monkeypatch.delitem(sys.modules, k)
    for name in ['src', 'src.analytics', 'src.agents', 'src.research']:
        m = ModuleType(name)
        m.__path__ = [str(root / name.replace('.', '/'))]
        monkeypatch.setitem(sys.modules, name, m)
    loaded = {}
    for short, rel in [('inputs', FILES[0]), ('vision', FILES[3]), ('renderer', FILES[2]), ('batch', FILES[1]), ('pool', FILES[4])]:
        name = rel[:-3].replace('/', '.')
        spec = importlib.util.spec_from_file_location(name, root / rel)
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, mod)
        spec.loader.exec_module(mod)
        loaded[short] = mod
    monkeypatch.delenv('CHART_VISION_MODEL', raising=False)
    yield SimpleNamespace(root=root, **loaded)


def bars():
    first = datetime(2026, 7, 1)
    return [{'time': (first + timedelta(days=i)).strftime('%Y-%m-%d'), 'open': 10+i/10, 'high': 11+i/10, 'low': 9+i/10, 'close': 10.5+i/10} for i in range(100)]


def test_shared_input_fetches_each_period_once_and_clips_future(app):
    calls = []
    def fetch(code, **kw):
        calls.append(kw)
        data = bars() + [{'time': '2026-11-01', 'open': 99, 'high': 999, 'low': 98, 'close': 99}]
        return {'candles': data, 'volumes': [{'time': b['time'], 'value': 100} for b in data], 'source': 'synthetic'}
    p = app.inputs.prepare_chart_input('000001.SZ', as_of='20261029', fetcher=fetch)
    assert len(calls) == len(app.inputs.DEFAULT_PERIODS)
    assert all(c['end_date'] == '2026-10-30' for c in calls)
    assert all(len(x['candles']) == 100 for x in p['panels'])
    assert all(c['close'] == panel['candles'][-1]['close'] for c, panel in zip(p['period_context'], p['panels']))
    assert all(c['high20'] < 999 for c in p['period_context'])


def test_model_is_chart_specific_and_frozen_context_prevents_refetch(app, monkeypatch):
    monkeypatch.setenv('VISION_MODEL', 'seed-old-legacy-setting')
    assert app.vision._vision_model() == 'deepseek-v4.1-flash-1017'
    def deny(*args, **kwargs):
        pytest.fail('must not refetch the image input for its model summary')
    monkeypatch.setattr(app.vision, 'build_multi_period_context', deny)
    requests = []
    def complete(**kwargs):
        requests.append(kwargs)
        return SimpleNamespace(model='deepseek-flash', choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({'summary':'offline fixture', 'signals':[{'type':'观望','price_hint':None}]})))])
    monkeypatch.setattr(app.vision, '_complete', complete)
    context = [{'period':'1d','close':12.34}]
    result = app.vision.analyze_chart_vision(b'fixture-image', 'image/png', '000001.SZ', period_context=context)
    assert result['period_context'] is context
    assert result['model'] == 'deepseek-v4.1-flash-1017' and result['response_model'] == 'deepseek-flash'
    assert requests[0]['response_format'] == {'type':'json_object'}
    assert requests[0]['messages'][1]['content'][1]['image_url']['url'].startswith('data:image/png;base64,')
    assert result['price_hint_role'] == 'technical_reference_not_execution_authorization'


def test_chart_universe_is_uncapped_union_without_changing_trade_permission(app):
    date = '20261029'
    research = {'trade_date':date, 'status':'partial', 'no_trade':True,
                'main_lines':[{'leaders':[{'ts_code':f'{i:06d}.SZ','name':'synthetic'} for i in range(1,41)]}],
                'secondary_lines':[{'leaders':[{'ts_code':f'{i:06d}.SZ'} for i in range(35,61)]}]}
    plan = {'trade_date':date, 'no_trade':True, 'execution_pool':[], 'watch_pool':[{'ts_code':f'{i:06d}.SZ'} for i in range(50,81)]}
    rp = app.root / f'data/research/{date}/R2_main_sectors.json'
    pp = app.root / f'data/plans/{date}/watchlist_plan.json'
    for p, value in [(rp,research),(pp,plan)]:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value))
    before = (rp.read_bytes(), pp.read_bytes())
    pool, metadata = app.pool.chart_universe(date)
    assert len(pool) == 80 and len(dict(pool)) == 80
    assert 'plan.watch_pool' in metadata['provenance']['000060.SZ']
    assert (rp.read_bytes(), pp.read_bytes()) == before
    assert plan['no_trade'] and not plan['execution_pool']
    plan['trade_date'] = '20261028'
    pp.write_text(json.dumps(plan))
    assert len(app.pool.chart_universe(date)[0]) == 60


@pytest.fixture
def engine(app, tmp_path, monkeypatch):
    state = SimpleNamespace(prepared=0, rendered=0, modeled=0, sessions=[], active_render=0, active_model=0, peak_render=0, peak_model=0, changed=set(), failures=set(), transient=set(), attempts={})
    lock = threading.Lock()
    class Session:
        def __init__(self):
            self.closed = False
            state.sessions.append(self)
        def close(self):
            self.closed = True
    def prepare(code, **kwargs):
        with lock: state.prepared += 1
        if code in state.failures:
            raise ValueError('synthetic input failure')
        return {'input_digest':code + ('changed' if code in state.changed else ''), 'as_of':'2026-10-29T15:00:00+08:00', 'period_context':[{'period':'1d','close':12.3}], 'panels':[]}
    def render(code, **kwargs):
        with lock:
            state.rendered += 1
            state.active_render += 1
            state.peak_render = max(state.peak_render, state.active_render)
        time.sleep(.004)
        p = tmp_path / (code + '.png')
        p.write_bytes(b'explicit-offline-render-fixture')
        with lock: state.active_render -= 1
        return {'path':str(p), 'render_ms':4, 'fetch_ms':1}
    def analyze(**kwargs):
        code = kwargs['ts_code']
        with lock:
            state.modeled += 1
            state.attempts[code] = state.attempts.get(code,0) + 1
            state.active_model += 1
            state.peak_model = max(state.peak_model, state.active_model)
        time.sleep(.008)
        with lock: state.active_model -= 1
        if code in state.transient and state.attempts[code] == 1:
            exc = type('Synthetic503', (RuntimeError,), {'status_code':503})('synthetic transient 503')
            raise exc
        return {'summary':'offline fixture', 'signals':[{'type':'观望','price_hint':None}], 'model':app.vision._vision_model()}
    monkeypatch.setattr(app.batch, 'LwcRenderSession', Session)
    monkeypatch.setattr(app.batch, 'prepare_chart_input', prepare)
    monkeypatch.setattr(app.batch, 'render_lwc_multi_period_kline', render)
    monkeypatch.setattr(app.batch, 'analyze_chart_vision', analyze)
    return state


def test_fifty_symbols_separate_pools_and_verified_input_cache(app, engine):
    universe = [(f'{i:06d}.SZ','synthetic') for i in range(1,51)]
    first = asyncio.run(app.batch.run_chart_batch(universe,6,render_workers=2))
    assert len(first) == 50 and not any(r.get('error') for r in first)
    assert engine.rendered == engine.modeled == 50
    assert 1 < engine.peak_render <= 2 and 1 < engine.peak_model <= 6
    assert len(engine.sessions) <= 2 and all(x.closed for x in engine.sessions)
    cached = {x['ts_code']:x for x in first}
    second = asyncio.run(app.batch.run_chart_batch(universe,6,render_workers=2,cached=cached))
    assert all(x['reused_analysis'] for x in second)
    assert engine.rendered == engine.modeled == 50
    assert engine.prepared == 100  # Input validation is not repeated image/model work.
    engine.changed.add('000003.SZ')
    third = asyncio.run(app.batch.run_chart_batch(universe,6,render_workers=2,cached=cached))
    assert len(third) == 50 and engine.rendered == engine.modeled == 51
    assert not third[2]['reused_analysis']


@pytest.mark.parametrize('change', ['model','prompt','render'])
def test_cache_segregates_model_prompt_and_renderer(app, engine, monkeypatch, change):
    universe = [('000001.SZ','synthetic')]
    first = asyncio.run(app.batch.run_chart_batch(universe))
    kwargs = {}
    if change == 'model': monkeypatch.setenv('CHART_VISION_MODEL','synthetic-other-model')
    elif change == 'prompt': monkeypatch.setattr(app.vision,'VISION_PROMPT',app.vision.VISION_PROMPT+'\nnew fixture prompt')
    else: kwargs['macd'] = True
    second = asyncio.run(app.batch.run_chart_batch(universe,cached={'000001.SZ':first[0]},**kwargs))
    assert engine.modeled == 2 and not second[0]['reused_analysis']
    assert engine.rendered == (2 if change == 'render' else 1)


def test_failed_object_is_not_replaced_and_transient_only_retries_model(app, engine):
    engine.failures.add('000001.SZ')
    engine.transient.add('000002.SZ')
    rows = asyncio.run(app.batch.run_chart_batch([('000001.SZ','one'),('000002.SZ','two')]))
    assert [r['ts_code'] for r in rows] == ['000001.SZ','000002.SZ']
    assert rows[0]['error_stage'] == 'input_or_render'
    assert rows[1]['error'] is None and rows[1]['model_attempts'] == 2
    assert engine.rendered == 1 and engine.modeled == 2


def test_empty_batch_never_touches_market_or_model(app, engine):
    assert asyncio.run(app.batch.run_chart_batch([])) == []
    assert engine.prepared == engine.rendered == engine.modeled == 0


def test_invalid_worker_counts_are_explicit(app):
    with pytest.raises(ValueError): asyncio.run(app.batch.run_chart_batch([('000001.SZ','')],0))


def test_missing_png_is_regenerated_without_repeating_valid_model_analysis(app, engine):
    universe = [('000001.SZ','synthetic')]
    first = asyncio.run(app.batch.run_chart_batch(universe))[0]
    Path(first['chart_path']).unlink()
    second = asyncio.run(app.batch.run_chart_batch(universe,cached={'000001.SZ':first}))[0]
    assert Path(second['chart_path']).is_file()
    assert engine.rendered == 2 and engine.modeled == 1
    assert second['reused_analysis']


def test_previous_plan_supplies_membership_not_research_or_trade_permission(app):
    path = app.root / 'data/plans/20261028/watchlist_plan.json'
    path.parent.mkdir(parents=True)
    payload = {'trade_date':'20261028','no_trade':True,'execution_pool':[], 'watch_pool':[{'ts_code':'000002.SZ','name':'prior watch'}]}
    path.write_text(json.dumps(payload))
    before = path.read_bytes()
    future = app.root / 'data/plans/20261030/watchlist_plan.json'
    future.parent.mkdir(parents=True)
    future.write_text(json.dumps({'trade_date':'20261030','watch_pool':[{'ts_code':'000003.SZ'}]}))
    universe, meta = app.pool.chart_universe('20261029')
    assert universe == [('000002.SZ','prior watch')]
    assert meta['plan_date'] == '20261028' and meta['prior_plan_used_for_membership_only']
    assert path.read_bytes() == before and payload['no_trade'] and not payload['execution_pool']
