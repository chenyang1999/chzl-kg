"""Scratch-only, synthetic plan-driver acceptance against the real SQLite backend.

Copy this test and the listed source closure to scratch before running pytest.
There is no real account, real market observation, broker, process, credential IO
or production artifact access during tests. A synthetic calendar is not evidence
of an actual trading day. PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 and --noconftest.
"""
from __future__ import annotations

import builtins
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import importlib
import importlib.abc
import io
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path('/Users/chenyang/.hermes/cache/scratch')
PRODUCTION = Path('/Users/chenyang/Downloads/demo/沧海巨浪')
sys.path.insert(0, str(ROOT))
from scripts.execute import run_paper_plan_once as driver
from trading.paper import PaperLedger

NOW = '2099-01-05T10:00:01+08:00'
NEXT = '2099-01-06T10:00:01+08:00'
AUTH = 'SYNTHETIC_ONLY_NOT_USER_PRODUCTION_AUTHORIZATION'
SYMBOL = '600000.SH'
UNITS = ['R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7']


def fixtures(now=NOW) -> tuple[dict, dict, dict]:
    date = now[:10]
    summary = dict(trade_date=date, generated_at=date+'T08:40:00+08:00',
        orchestrator_status='complete', contract_checks_passed=True, contract_failures={}, timeouts=[],
        fetch_global_severity=0, artifacts={u: 'SYNTHETIC/'+u+'.json' for u in UNITS},
        units={u: {'status':'complete'} for u in UNITS},
        contract_results={u: {'status':'passed', 'research_status':'complete'} for u in UNITS})
    r6 = dict(trade_date=date, generated_at=date+'T08:30:00+08:00', status='complete', candidates_evaluated=1,
        upstream_usable={u: True for u in UNITS if u!='R6'}, hard_rejects=[], counter_arguments=[])
    stock = dict(ts_code=SYMBOL, name='SYNTHETIC_NOT_MARKET', is_st=False, role='leader',
        max_position_pct=.1, stop_loss=9.5, take_profit=11.5,
        entry_rules=[dict(type='trend_pullback_buy', trigger_price=10.1, position_pct=.1)],
        exit_rules=[dict(type='take_profit_hit', trigger_price=11.5, quantity_pct=.5, priority=2),
                    dict(type='stop_loss_break', trigger_price=9.5, quantity_pct=1, priority=1)])
    plan = dict(schema_version='watchlist_plan_v1', mode='dry_run', autonomous_trading_enabled=False,
        trade_date=date, generated_at=date+'T09:00:00+08:00', status='ok', no_trade=False,
        requires_user_confirmation=True, execution_pool=[stock], watch_pool=[],
        risk_limits=dict(target_total_position_pct=.5, max_positions=3, max_buy_orders_per_day=10,
                         max_orders_per_symbol_per_day=10, block_prefixes=[]),
        meta=dict(paper_trading_authorized=True, production_ready=True, research_completion_passed=True,
                  research_summary=summary, r6_devil_advocate=r6))
    quotes = {'quotes': [dict(symbol=SYMBOL, source='SYNTHETIC_ONLY_NOT_MARKET', trade_date=date,
        observed_at=date+'T10:00:00+08:00', received_at=date+'T10:00:00.500000+08:00', board='main',
        security_type='common_stock', is_st=False, quantity_unit='shares', lot_size=100, tick_size=.01,
        bid_price=9.99, bid_size=100000, ask_price=10., ask_size=100000, last_price=10.,
        lower_limit=8., upper_limit=12., suspended=False, at_upper_limit=False, at_lower_limit=False)]}
    calendar = dict(source='SYNTHETIC_ONLY_NOT_EXCHANGE_CALENDAR', reliable=True,
        published_at='2099-01-01T00:00:00+08:00', coverage_start='2099-01-01', coverage_end='2099-01-10',
        trading_days=['2099-01-05','2099-01-06','2099-01-07'])
    return plan, quotes, calendar


@pytest.fixture(autouse=True)
def guards(monkeypatch):
    assert ROOT.resolve().is_relative_to(SCRATCH.resolve()), 'copy code and tests to scratch before pytest'
    def deny(*args, **kwargs):
        raise AssertionError('NETWORK_SUBPROCESS_FORBIDDEN')
    monkeypatch.setattr(socket, 'create_connection', deny)
    monkeypatch.setattr(socket.socket, 'connect', deny)
    monkeypatch.setattr(subprocess, 'Popen', deny)
    original_import = builtins.__import__
    def imports(name, *args, **kwargs):
        if name == 'src.settings' or 'qmt' in name.lower() or name.startswith(('dotenv','ib_insync','ibapi')):
            raise AssertionError('BROKER_SETTINGS_IMPORT_FORBIDDEN:' + name)
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, '__import__', imports)
    for container in (builtins, io):
        original = container.open
        def guard(path, mode='r', *args, _original=original, **kwargs):
            if not isinstance(path, int):
                resolved = Path(path).resolve()
                assert resolved.name != '.env' and not resolved.is_relative_to(PRODUCTION), 'PRODUCTION_CREDENTIAL_IO_FORBIDDEN'
                if any(m in mode for m in 'wax+'):
                    assert resolved.is_relative_to(SCRATCH), 'WRITE_OUTSIDE_SCRATCH_FORBIDDEN'
            return _original(path, mode, *args, **kwargs)
        monkeypatch.setattr(container, 'open', guard)
    original_connect = sqlite3.connect
    def connect(path, *args, **kwargs):
        assert str(path).startswith((str(SCRATCH), SCRATCH.as_uri())), 'PRODUCTION_DB_FORBIDDEN'
        return original_connect(path, *args, **kwargs)
    monkeypatch.setattr(sqlite3, 'connect', connect)


@pytest.fixture
def env(tmp_path):
    assert tmp_path.resolve().is_relative_to(SCRATCH)
    ledger = PaperLedger(tmp_path/'fixture.sqlite3', fixture=True)
    ledger.initialize(account_id='synthetic', init_cash='1000000', authorization_id=AUTH,
        seed_source='SYNTHETIC_ACCEPTANCE_ONLY', fee_model={'model':'zero_fee_assumption'}, now=NOW)
    return ledger, tmp_path


def cycle(env, data=None, *, now=NOW, omit=(), extra=()):
    ledger, directory = env
    p, q, c = data or fixtures(now)
    args = ['--once', '--database', str(ledger.path), '--account-id', 'synthetic',
            '--authorization-id', AUTH, '--fixture', '--now', now]
    for key, obj in [('plan', p), ('quotes', q), ('calendar', c)]:
        path = directory/(key+'.json')
        path.write_text(json.dumps(obj, allow_nan=False))
        if key not in omit:
            args += ['--'+key, str(path)]
    if 'quote_max_age' not in omit:
        args += ['--quote-max-age','5']
    args += list(extra)
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        code = driver.main(args)
    return code, json.loads(stdout.getvalue())


def test_positive_real_buy_with_account_based_size_and_immutable_plan(env):
    p, q, c = fixtures()
    original = deepcopy(p)
    code, r = cycle(env, (p,q,c))
    assert code == 0 and r['event']=='paper_filled', r
    assert len(r['fills'])==1 and r['fills'][0]['side']=='buy'
    assert r['fills'][0]['quantity']==10000  # Equity * explicit 10%, not fixed 100.
    assert r['snapshot_after']['cash_cents']==90000000
    assert r['authorization']['source']=='canonical_permission_cli_id'
    assert r['canonical_sha256']==hashlib.sha256((env[1]/'plan.json').read_bytes()).hexdigest()
    assert json.loads((env[1]/'plan.json').read_text())==original==p
    assert 'src.settings' not in sys.modules
    with env[0].transaction() as db:
        assert db.execute('SELECT COUNT(*) FROM fills').fetchone()[0]==1


def test_empty_forbidden_is_honest_idle_without_market_inputs(env):
    p,q,c=fixtures();p['no_trade']=True
    code,r=cycle(env,(p,q,c),omit=('quotes','calendar','quote_max_age'))
    assert code==0 and r['event']=='paper_idle' and r['fills']==[] and r['intents']==[],r
    assert r['snapshot_after']['positions']=={} and 'inputs' not in r


def test_empty_pool_not_watch_or_b_plan_execution(env):
    p,q,c=fixtures();p['watch_pool']=p['execution_pool'];p['B_plan']=p['execution_pool'];p['execution_pool']=[]
    code,r=cycle(env,(p,q,c),omit=('quotes','calendar','quote_max_age'))
    assert code==0 and r['event']=='paper_idle' and not r['fills'],r


@pytest.mark.parametrize('missing', ['quotes','calendar','quote_max_age'])
def test_potential_action_missing_input_blocked_not_idle(env,missing):
    code,r=cycle(env,omit=(missing,))
    assert code==2 and r['event']=='paper_blocked' and not r['fills'] and not r['orders'],r
    assert 'required_input_missing:'+missing in r['reasons']


def test_missing_symbol_quote_blocked(env):
    p,q,c=fixtures();q['quotes']=[]
    code,r=cycle(env,(p,q,c))
    assert code==2 and r['rejections'] and not r['fills'],r
    assert not env[0].snapshot('synthetic',now=NOW)['fills']


def test_same_quote_never_second_order_or_fill_even_after_size_changes(env):
    assert cycle(env)[1]['event']=='paper_filled'
    code,r=cycle(env)
    assert code==0 and r['event']=='paper_no_new_fill' and not r['fills'],r
    assert len(r['snapshot_after']['orders'])==len(r['snapshot_after']['fills'])==1
    assert r['orders'][0]['event']=='paper_observation_already_processed'


def test_unknown_kill_path_never_read_and_refuses_new(env):
    p,q,c=fixtures();p['risk_limits']['kill_switch_file']='/private/credentials/secret.env'
    code,r=cycle(env,(p,q,c),omit=('quotes','calendar','quote_max_age'))
    assert code==2 and r['event']=='paper_blocked' and not r['fills'],r
    assert r['kill_switch_snapshot']['status']=='unknown_path'


def test_approved_kill_exists_only_snapshot(env,monkeypatch):
    p,q,c=fixtures();p['risk_limits']['kill_switch_file']='data/runtime/KILL_SWITCH'
    path=ROOT/'data/runtime/KILL_SWITCH'
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text('DO NOT READ')
    original=Path.read_bytes
    def no_kill_read(self):
        assert self != path,'KILL_CONTENTS_FORBIDDEN'
        return original(self)
    monkeypatch.setattr(Path,'read_bytes',no_kill_read)
    code,r=cycle(env,(p,q,c),omit=('quotes','calendar','quote_max_age'))
    path.unlink()
    assert code==0 and r['event']=='paper_idle' and r['kill_switch_snapshot']['exists'] is True,r


@pytest.mark.parametrize('active', [True, False])
def test_missing_kill_field_still_honors_existing_schema_default(env, active):
    p,q,c=fixtures();p['risk_limits'].pop('kill_switch_file',None)
    path=ROOT/'data/runtime/KILL_SWITCH'
    assert not path.exists()
    if active:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('SYNTHETIC STOP - EXISTS ONLY')
    try:
        code,r=cycle(env,(p,q,c))
        if active:
            assert code==0 and r['event']=='paper_idle' and not r['fills'],r
        else:
            assert code==0 and len(r['fills'])==1,r
        assert r['kill_switch_snapshot']['configuration_source']=='schema_default'
        assert r['kill_switch_snapshot']['exists'] is active
    finally:
        if active:
            path.unlink()


def test_explicit_null_kill_path_does_not_silently_use_default(env):
    p,q,c=fixtures();p['risk_limits']['kill_switch_file']=None
    code,r=cycle(env,(p,q,c))
    assert code==2 and not r['fills'] and 'unknown_kill_switch_path' in r['reasons']


@pytest.mark.parametrize('field,value', [('auction_confirm', True),('volume_ratio',2),
    ('trigger_condition','volume > yesterday'),('max_premium_pct',.03),('only_first_seal',False)])
def test_unsupported_confirmation_is_explicit_blocked(env,field,value):
    p,q,c=fixtures();p['execution_pool'][0]['entry_rules'][0][field]=value
    code,r=cycle(env,(p,q,c))
    assert code==2 and not r['fills'] and any('unsupported' in x['reason'] for x in r['rejections']),r


def test_new_buys_forbidden_but_saved_paper_exit_sells_half_once(env):
    assert cycle(env)[1]['event']=='paper_filled'
    p,q,c=fixtures(NEXT);p['execution_pool']=[];p['no_trade']=True
    p['risk_limits']['target_total_position_pct']=0;p['meta']['production_ready']=False
    p['meta'].pop('research_summary');p['meta'].pop('r6_devil_advocate')
    q['quotes'][0].update(last_price=11.6,bid_price=11.59,ask_price=11.6)
    code,r=cycle(env,(p,q,c),now=NEXT)
    assert code==0 and len(r['fills'])==1 and r['fills'][0]['side']=='sell',r
    assert r['fills'][0]['quantity']==5000  # NOT .5 squared.
    assert r['snapshot_after']['positions'][SYMBOL]['quantity']==5000
    code,r=cycle(env,(p,q,c),now=NEXT)
    assert not r['fills'] and r['snapshot_after']['positions'][SYMBOL]['quantity']==5000,r


def test_no_rule_hit_does_not_liquidate_absent_pool(env):
    assert cycle(env)[1]['event']=='paper_filled'
    p,q,c=fixtures(NEXT);p['execution_pool']=[];p['no_trade']=True
    code,r=cycle(env,(p,q,c),now=NEXT)
    assert not r['fills'] and r['snapshot_after']['positions'][SYMBOL]['quantity']==10000,r


def test_exit_priority_and_no_same_cycle_rebuy(env):
    assert cycle(env)[1]['event']=='paper_filled'
    p,q,c=fixtures(NEXT)
    p['execution_pool'][0]['exit_rules']=[
        dict(type='take_profit_hit',trigger_price=9.,quantity_pct=.5,priority=20),
        dict(type='stop_loss_break',trigger_price=11.,quantity_pct=1,priority=1)]
    code,r=cycle(env,(p,q,c),now=NEXT)
    assert len(r['fills'])==1 and r['fills'][0]['side']=='sell' and r['fills'][0]['quantity']==10000,r
    assert r['intents'][0]['rule_index']==1


def test_one_stock_bad_rr_does_not_block_other_stock(env):
    p,q,c=fixtures();other=deepcopy(p['execution_pool'][0]);other['ts_code']='600001.SH'
    p['execution_pool'][0]['take_profit']=10.1
    p['execution_pool'].append(other)
    oq=deepcopy(q['quotes'][0]);oq['symbol']=other['ts_code'];q['quotes'].append(oq)
    code,r=cycle(env,(p,q,c))
    assert len(r['fills'])==1 and r['fills'][0]['symbol']==other['ts_code'],r
    assert any(x['symbol']==SYMBOL and 'stock_buy_ineligible' in x['reason'] for x in r['rejections'])


def test_tiny_budget_no_fabricated_minimum_lot(env):
    p,q,c=fixtures();p['execution_pool'][0]['max_position_pct']=.00001
    code,r=cycle(env,(p,q,c));assert code==2 and not r['fills'] and not r['intents'],r
    assert 'below_one_lot' in r['rejections'][0]['reason']


def test_explicit_cli_authorization_not_live_upgrade(env):
    p,q,c=fixtures();p['meta'].pop('paper_trading_authorized')
    assert cycle(env,(p,q,c))[0]==2
    code,r=cycle(env,(p,q,c),extra=('--paper-trading-authorized',))
    assert code==0 and r['event']=='paper_filled' and r['authorization']['source']=='explicit_cli',r
    assert json.loads((env[1]/'plan.json').read_text())['autonomous_trading_enabled'] is False


def test_authorization_mismatch_and_live_flag_reject_without_fill(env):
    p,q,c=fixtures();p['meta']['paper_authorization_id']='OTHER'
    code,r=cycle(env,(p,q,c));assert code==2 and not r['fills'],r
    p['meta'].pop('paper_authorization_id');p['autonomous_trading_enabled']=True
    code,r=cycle(env,(p,q,c));assert code==2 and not r['fills'],r


def test_report_atomic_strict_json_and_refuse_input_collision(env):
    target=env[1]/'report.json'
    code,r=cycle(env,extra=('--report',str(target)))
    assert code==0 and json.loads(target.read_text())==r
    code,r=cycle(env,extra=('--report',str(env[1]/'plan.json')))
    assert code==2 and r['reason']=='report_cannot_replace_input_or_ledger',r
    code,r=cycle(env,extra=('--report',str(ROOT/'not_allowed.json')))
    # ROOT is scratch and is intentionally allowed; production paths are not.
    assert code==0
    with pytest.raises(driver.PaperError):
        driver.report_path(PRODUCTION/'config/report.json')


@pytest.mark.parametrize('change', ['stale','calendar','r6','ready'])
def test_invalid_inputs_fail_closed_no_fill(env,change):
    p,q,c=fixtures()
    if change=='stale':q['quotes'][0]['observed_at']='2099-01-05T09:30:00+08:00'
    if change=='calendar':c['reliable']=False
    if change=='r6':p['meta']['r6_devil_advocate']['hard_rejects']=[SYMBOL]
    if change=='ready':p['meta']['production_ready']=False
    code,r=cycle(env,(p,q,c));assert code==2 and not r['fills'],r


def test_stock_scoped_veto_never_becomes_global_for_other_stock(env):
    p,q,c=fixtures();p['no_trade_conditions']=[dict(scope='stock',ts_code='600001.SH',active=True,code='RR_FAIL')]
    code,r=cycle(env,(p,q,c))
    assert code==0 and len(r['fills'])==1 and r['fills'][0]['symbol']==SYMBOL,r


def test_bad_optional_research_does_not_block_existing_sell(env):
    assert cycle(env)[1]['event']=='paper_filled'
    p,q,c=fixtures(NEXT);p['execution_pool']=[];p['no_trade']=True
    q['quotes'][0].update(last_price=11.6,bid_price=11.59,ask_price=11.6)
    code,r=cycle(env,(p,q,c),now=NEXT,extra=('--r6-research',str(env[1]/'not_present.json')))
    assert code==0 and len(r['fills'])==1 and r['fills'][0]['side']=='sell',r


def test_unknown_kill_path_does_not_block_legal_paper_sell(env):
    assert cycle(env)[1]['event']=='paper_filled'
    p,q,c=fixtures(NEXT);p['execution_pool']=[];p['risk_limits']['kill_switch_file']='.env'
    q['quotes'][0].update(last_price=11.6,bid_price=11.59,ask_price=11.6)
    code,r=cycle(env,(p,q,c),now=NEXT)
    assert code==0 and len(r['fills'])==1 and r['fills'][0]['side']=='sell',r
    assert 'unknown_kill_switch_path' in r['reasons']


def test_missing_saved_exit_is_explicit_block_not_liquidation(env):
    assert cycle(env)[1]['event']=='paper_filled'
    with env[0].transaction() as db:
        db.execute('DELETE FROM exit_plans')
    p,q,c=fixtures(NEXT);p['execution_pool']=[];p['no_trade']=True
    code,r=cycle(env,(p,q,c),now=NEXT)
    assert code==2 and not r['fills'] and any('exit_source_missing' in x['reason'] for x in r['rejections']),r
    assert r['snapshot_after']['positions'][SYMBOL]['quantity']==10000


def test_fractional_pending_retry_does_not_square_or_compound_percentage(env):
    assert cycle(env)[1]['event']=='paper_filled'
    p,q,c=fixtures(NEXT);p['execution_pool']=[];p['no_trade']=True
    q['quotes'][0].update(last_price=11.6,bid_price=11.59,ask_price=11.6)
    assert cycle(env,(p,q,c),now=NEXT)[1]['fills'][0]['quantity']==5000
    q['quotes'][0].update(observed_at='2099-01-06T10:00:02+08:00',received_at='2099-01-06T10:00:02+08:00')
    code,r=cycle(env,(p,q,c),now='2099-01-06T10:00:03+08:00')
    assert code==2 and not r['fills'] and r['snapshot_after']['positions'][SYMBOL]['quantity']==5000,r
    assert any('fractional_partial_sell_retry_unsupported' in x['reason'] for x in r['rejections'])


def test_report_failure_cannot_conceal_committed_fill(env,monkeypatch):
    def failed(*args):
        raise OSError('SYNTHETIC_REPORT_DISK_FAILURE')
    monkeypatch.setattr(driver,'write_report',failed)
    code,r=cycle(env,extra=('--report',str(env[1]/'failed_report.json')))
    assert code==2 and r['event']=='paper_filled' and len(r['fills'])==1,r
    assert r['report_error']=='SYNTHETIC_REPORT_DISK_FAILURE'


def test_empty_missing_ledger_never_initialized(env):
    ledger,directory=env;missing=PaperLedger(directory/'missing.sqlite3',fixture=True)
    code,r=cycle((missing,directory))
    assert code==2 and not r['fills'] and not missing.path.exists(),r
