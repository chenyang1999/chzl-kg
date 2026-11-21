"""R1 independent contracts: scratch closure only; no broker or real ledger.

Legacy writer must be copied at paper/pre/app/trading/paper/ledger.py beside
paper/post or paper/migrated. It writes real old-shape orders, not edited JSON.
"""
from __future__ import annotations
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sqlite3
import pytest
from trading.paper import PaperLedger
from scripts.execute import run_paper_plan_once as driver
from test_canghai_paper_plan_driver_20261023 import guards, env, fixtures, cycle, NOW, NEXT, AUTH, SYMBOL

LATER='2099-01-06T10:00:03+08:00'
THIRD='2099-01-07T10:00:01+08:00'
ROOT=Path(__file__).resolve().parents[1]


def data(now=NEXT, *, depth=100000, stop=False):
    p,q,c=fixtures(now)
    p['execution_pool']=[];p['no_trade']=True
    p['risk_limits']['target_total_position_pct']=0
    p['meta'].pop('research_summary');p['meta'].pop('r6_devil_advocate')
    p['meta']['production_ready']=False
    q['quotes'][0].update(last_price=9.4 if stop else 11.6,
        bid_price=9.39 if stop else 11.59,ask_price=9.4 if stop else 11.6,bid_size=depth)
    if now==LATER:
        q['quotes'][0].update(observed_at='2099-01-06T10:00:02+08:00',received_at='2099-01-06T10:00:02+08:00')
    p['meta']['paper_authorization_id']=AUTH
    return p,q,c


def direct(ledger, bundle, *, now=NEXT, oid='r1-ratio', side='sell', idx=0, qty=10000):
    p,q,c=deepcopy(bundle);p['meta']['paper_authorization_id']=AUTH
    intent=dict(order_id=oid,symbol=SYMBOL,side=side,quantity=qty,
        limit_price=q['quotes'][0]['bid_price' if side=='sell' else 'ask_price'],rule_index=idx)
    return ledger.execute(account_id='synthetic',authorization_id=AUTH,intent=intent,
        plan=p,quotes=q,calendar=c,quote_max_age='5',now=now)


def tables(ledger):
    with ledger.transaction() as db:
        return {name:[dict(row) for row in db.execute('SELECT * FROM '+name+' ORDER BY rowid')]
                for name in ['accounts','orders','fills','lots','liquidity','exit_plans']}


@pytest.fixture
def old_writer(env):
    assert ROOT.is_relative_to(Path('/Users/chenyang/.hermes/cache/scratch'))
    path=ROOT.parents[1]/'pre/app/trading/paper/ledger.py'
    assert path.is_file(), 'copy the frozen S2 pre ledger, never import production'
    spec=importlib.util.spec_from_file_location('r1_before_ledger',path)
    assert spec is not None and spec.loader is not None
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.PaperLedger(env[0].path,fixture=True)


@pytest.mark.parametrize('depth',[100000,1000,50])
def test_genuine_old_writer_orders_resume_or_complete_without_rewrite(env,old_writer,depth):
    assert cycle(env)[1]['fills'][0]['quantity']==10000
    first=direct(old_writer,data(depth=depth))
    assert first['status']==('pending' if depth==50 else 'partial')
    assert 'target_quantity' not in first and 'exit_stage_key' not in first
    previous=tables(env[0])
    rule=env[0].snapshot('synthetic',now=NEXT)['managed_exit_plans'][SYMBOL]['stock']['exit_rules'][0]
    restart=PaperLedger(env[0].path,fixture=True)
    progress=restart.sell_progress('synthetic',SYMBOL,rule,now=NEXT)
    assert progress['target_quantity']==5000
    assert progress['complete'] is (depth>=5000)
    assert tables(env[0])==previous  # Resolution is read-only, including last_at.
    result=cycle((restart,env[1]),data(THIRD),now=THIRD)[1]
    assert result['snapshot_after']['positions'][SYMBOL]['quantity']==5000
    if depth>=5000:
        assert result['fills']==[] and tables(env[0])==previous
        assert any(x['reason']=='fractional_exit_stage_completed' for x in result['rejections'])
    else:
        assert result['fills'][0]['quantity']==5000-first['fill_quantity']
        assert result['orders'][0]['order_id']=='r1-ratio'
        assert result['orders'][0]['target_quantity']==5000
        assert result['orders'][0]['status']=='filled'


@pytest.mark.parametrize('depth',[100000,1000,50])
def test_genuine_old_order_never_reserves_stock_from_priority_stop(env,old_writer,depth):
    assert cycle(env)[1]['fills'][0]['quantity']==10000
    old=direct(old_writer,data(depth=depth))
    restart=PaperLedger(env[0].path,fixture=True)
    out=cycle((restart,env[1]),data(LATER,stop=True),now=LATER)[1]
    assert out['fills'][0]['quantity']==10000-old['fill_quantity']
    assert out['snapshot_after']['positions']=={}
    assert not cycle((restart,env[1]),data(LATER,stop=True),now=LATER)[1]['fills']


def test_genuine_old_fill_without_rule_proof_fails_closed_but_independent_stop_works(env,old_writer):
    cycle(env)
    first=direct(old_writer,data(depth=1000))
    assert first['fill_quantity']==1000
    with env[0].transaction() as db:
        row=db.execute("SELECT fill_id,evidence_json FROM fills WHERE order_id='r1-ratio'").fetchone()
        proof=json.loads(row['evidence_json']);proof.pop('rule')
        db.execute('UPDATE fills SET evidence_json=? WHERE fill_id=?',(json.dumps(proof),row['fill_id']))
    out=cycle(env,data(LATER),now=LATER)[1]
    assert not out['fills'] and out['snapshot_after']['positions'][SYMBOL]['quantity']==9000
    assert any(x['reason']=='legacy_exit_rule_evidence_required' for x in out['rejections'])
    out=cycle(env,data(THIRD,stop=True),now=THIRD)[1]
    assert out['fills'][0]['quantity']==9000 and out['snapshot_after']['positions']=={}


def test_completed_stage_identity_survives_description_priority_and_pool_edits(env):
    assert cycle(env)[1]['fills'][0]['quantity']==10000
    first=cycle(env,data(),now=NEXT)[1]
    assert first['orders'][0]['target_quantity']==5000
    before=tables(env[0])
    p,q,c=fixtures(THIRD)
    s=p['execution_pool'].pop();p['watch_pool']=[s];p['no_trade']=True
    p['risk_limits']['target_total_position_pct']=0
    s['exit_rules'][0].update(reason='different explanation',priority=3)
    s['exit_rules'].reverse()  # Same numerical tranche despite reordering.
    q['quotes'][0].update(last_price=11.6,bid_price=11.59,ask_price=11.6)
    out=cycle((PaperLedger(env[0].path,fixture=True),env[1]),(p,q,c),now=THIRD)[1]
    assert out['fills']==[] and out['intents']==[]
    assert any(x['reason']=='fractional_exit_stage_completed' for x in out['rejections'])
    assert tables(env[0])==before


def test_adding_stock_does_not_reset_consumed_stage_or_use_today_t1_lots(env):
    assert cycle(env)[1]['fills'][0]['quantity']==10000
    assert cycle(env,data(),now=NEXT)[1]['fills'][0]['quantity']==5000
    # Buy an explicit small addition through the real ledger (not lot injection).
    p,q,c=fixtures(LATER)
    q['quotes'][0].update(observed_at='2099-01-06T10:00:02+08:00',received_at='2099-01-06T10:00:02+08:00')
    add=direct(env[0],(p,q,c),now=LATER,oid='r1-add',side='buy',qty=100)
    assert add['fill_quantity']==100,add
    held=env[0].snapshot('synthetic',now=LATER)['positions'][SYMBOL]
    assert (held['quantity'],held['sellable_quantity'])==(5100,5000)
    out=cycle((PaperLedger(env[0].path,fixture=True),env[1]),data(THIRD),now=THIRD)[1]
    assert out['fills']==[] and out['snapshot_after']['positions'][SYMBOL]['quantity']==5100


def test_atomic_takeover_failure_restores_every_table_including_liquidity(env):
    cycle(env);first=cycle(env,data(depth=1000),now=NEXT)[1]
    assert first['orders'][0]['status']=='partial'
    with env[0].transaction() as db:
        db.execute("CREATE TRIGGER r1_abort BEFORE INSERT ON fills BEGIN SELECT RAISE(ABORT,'R1_ATOMIC_ABORT'); END")
    before=tables(env[0]);code,out=cycle(env,data(LATER,stop=True),now=LATER)
    assert code==2 and 'R1_ATOMIC_ABORT' in out['reason']
    assert tables(env[0])==before
    with env[0].transaction() as db:db.execute('DROP TRIGGER r1_abort')
    out=cycle(env,data(LATER,stop=True),now=LATER)[1]
    assert out['snapshot_after']['positions']=={}
    old=next(x for x in out['snapshot_after']['orders'] if x['order_id']==first['orders'][0]['order_id'])
    assert old['status']=='superseded' and old['filled_quantity']==1000


def test_low_boundary_active_flag_is_not_downgraded_by_absent_file(env):
    p,q,c=fixtures();p['risk_limits']['kill_switch_active']=True
    assert not (driver.ROOT/'data/runtime/KILL_SWITCH').exists()
    out=direct(env[0],(p,q,c),now=NOW,side='buy',qty=100)
    assert out['fill_quantity']==0 and out['status']=='rejected'
    assert out['kill_switch_snapshot']['exists'] is False
    assert env[0].snapshot('synthetic',now=NOW)['fills']==[]


def test_low_boundary_sell_uses_saved_rule_not_buy_readiness_or_kill_path(env):
    cycle(env)
    p,q,c=data(stop=True)
    p['risk_limits'].update(kill_switch_active=True,kill_switch_file='.env')
    out=direct(env[0],(p,q,c),idx=1)
    assert out['fill_quantity']==10000 and out['status']=='filled',out
    assert env[0].snapshot('synthetic',now=NEXT)['positions']=={}
