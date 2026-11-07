"""S2 offline regressions; copy reviewed closure to scratch before collection.

Synthetic permission, calendar, inventory and quotes only. No production DB,
initial-capital reset, broker, HTTP or subprocess. Historic assertions stay intact.
"""
from __future__ import annotations
from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
from pathlib import Path

import pytest
from trading.paper import PaperLedger
from trading.paper.ledger import canonical
from scripts.execute import run_paper_plan_once as driver
from scripts.execute.run_paper_trading import main as low_cli
from test_canghai_paper_plan_driver_20261023 import (
    guards, env, fixtures, cycle, NOW, NEXT, AUTH, SYMBOL,
)

LATER = '2099-01-06T10:00:03+08:00'
THIRD = '2099-01-07T10:00:01+08:00'


def exit_data(now=NEXT, *, stop=False, depth=100000):
    p,q,c=fixtures(now)
    p['execution_pool']=[];p['no_trade']=True
    p['risk_limits']['target_total_position_pct']=0
    p['meta'].pop('research_summary');p['meta'].pop('r6_devil_advocate')
    p['meta']['production_ready']=False
    raw=q['quotes'][0]
    raw.update(last_price=9.4 if stop else 11.6,bid_price=9.39 if stop else 11.59,
               ask_price=9.4 if stop else 11.6,bid_size=depth)
    if now==LATER:
        raw.update(observed_at='2099-01-06T10:00:02+08:00',received_at='2099-01-06T10:00:02+08:00')
    return p,q,c


def seed_buy(env):
    r=cycle(env)[1]
    assert r['fills'][0]['quantity']==10000,r
    return r


def state(env, now=NEXT):
    return PaperLedger(env[0].path,fixture=True).snapshot('synthetic',now=now)


def low_order(env, data, *, now=NEXT, oid='low-ratio', idx=0, qty=10000, auth=AUTH):
    p,q,c=deepcopy(data)
    p['meta']['paper_authorization_id']=AUTH
    intent=dict(order_id=oid,symbol=SYMBOL,side='sell',quantity=qty,
                limit_price=q['quotes'][0]['bid_price'],rule_index=idx)
    r=env[0].execute(account_id='synthetic',authorization_id=auth,intent=intent,plan=p,quotes=q,
                     calendar=c,quote_max_age='5',now=now)
    return r,intent


def test_ratio_target_completion_is_not_remaining_position(env):
    seed_buy(env)
    r=cycle(env,exit_data(),now=NEXT)[1]
    assert r['orders'][0]['status']=='filled',r
    assert r['orders'][0]['target_quantity']==r['orders'][0]['filled_quantity']==5000
    assert r['snapshot_after']['positions'][SYMBOL]['sellable_quantity']==5000
    assert r['snapshot_after']['initial_cash_cents']==100000000


@pytest.mark.parametrize('depth', [100000,1000])
def test_ratio_then_higher_priority_hard_stop_even_when_partial(env,depth):
    seed_buy(env)
    first=cycle(env,exit_data(depth=depth),now=NEXT)[1]
    first_qty=min(5000,depth)
    assert first['fills'][0]['quantity']==first_qty,first
    oid=first['orders'][0]['order_id']
    restarted=(PaperLedger(env[0].path,fixture=True),env[1])
    stop=cycle(restarted,exit_data(LATER,stop=True),now=LATER)[1]
    assert stop['fills'][0]['quantity']==10000-first_qty,stop
    assert stop['snapshot_after']['positions']=={}
    if depth<5000:
        old=next(o for o in stop['snapshot_after']['orders'] if o['order_id']==oid)
        assert old['status']=='superseded' and old['filled_quantity']==first_qty
        assert old['superseded_by']==stop['orders'][0]['order_id']
    replay=cycle(restarted,exit_data(LATER,stop=True),now=LATER)[1]
    assert replay['fills']==[] and state(env,LATER)['positions']=={}


@pytest.mark.parametrize('now',[LATER,THIRD])
def test_ratio_target_retries_original_remainder_not_compounded_pct(env,now):
    seed_buy(env)
    first=cycle(env,exit_data(depth=1000),now=NEXT)[1]
    assert first['orders'][0]['status']=='partial'
    same=cycle(env,exit_data(depth=1000),now=NEXT)[1]
    assert not same['fills']
    last=cycle((PaperLedger(env[0].path,fixture=True),env[1]),exit_data(now),now=now)[1]
    assert last['orders'][0]['order_id']==first['orders'][0]['order_id'],last
    assert last['fills'][0]['quantity']==4000
    assert last['orders'][0]['status']=='filled'
    assert state(env,now)['positions'][SYMBOL]['quantity']==5000


@pytest.mark.parametrize('now',[NEXT,LATER,THIRD])
def test_completed_ratio_not_resold_on_new_observation_plan_or_day(env,now):
    seed_buy(env)
    assert cycle(env,exit_data(),now=NEXT)[1]['fills'][0]['quantity']==5000
    before=state(env,NEXT)
    after=cycle((PaperLedger(env[0].path,fixture=True),env[1]),exit_data(now),now=now)[1]
    assert after['fills']==[] and after['snapshot_after']['positions'][SYMBOL]['quantity']==5000,after
    assert len(after['snapshot_after']['fills'])==len(before['fills'])==2


def test_low_level_new_order_id_cannot_repeat_ratio_stage(env):
    seed_buy(env)
    d=fixtures(NEXT);d[1]['quotes'][0].update(last_price=11.6,bid_price=11.59,ask_price=11.6)
    first,_=low_order(env,d)
    assert first['fill_quantity']==5000 and first['status']=='filled',first
    d=fixtures(THIRD);d[1]['quotes'][0].update(last_price=11.6,bid_price=11.59,ask_price=11.6)
    second,_=low_order(env,d,now=THIRD,oid='new-key-same-stage',qty=5000)
    assert not second['fill_quantity'] and 'stage_already_started' in second['reason'],second
    assert state(env,THIRD)['positions'][SYMBOL]['quantity']==5000


def legacy_result(env, *, depth):
    seed_buy(env)
    r=cycle(env,exit_data(depth=depth),now=NEXT)[1]
    oid=r['orders'][0]['order_id']
    # Fixture-only legacy JSON shape: no target/stage/exit_rule, old partial
    # status even if it already fulfilled the ratio. No cash/lots/fills changes.
    with env[0].transaction() as db:
        saved=json.loads(db.execute('SELECT result_json FROM orders WHERE order_id=?',(oid,)).fetchone()[0])
        for k in ['target_quantity','exit_stage_key','exit_rule']:saved.pop(k,None)
        saved['status']='partial'
        db.execute('UPDATE orders SET result_json=?,status=? WHERE order_id=?',(canonical(saved),'partial',oid))
    return oid,saved


@pytest.mark.parametrize('depth',[100000,1000])
def test_legacy_partial_readonly_target_recovery_and_stop(env,depth):
    oid,saved=legacy_result(env,depth=depth)
    before=state(env,NEXT)
    rule=before['managed_exit_plans'][SYMBOL]['stock']['exit_rules'][0]
    progress=env[0].sell_progress('synthetic',SYMBOL,rule,now=NEXT)
    assert progress['target_quantity']==5000
    assert progress['complete'] is (depth>=5000)
    assert state(env,NEXT)==before  # Resolver must not rewrite old orders.
    stop=cycle(env,exit_data(LATER,stop=True),now=LATER)[1]
    assert stop['snapshot_after']['positions']=={} and stop['fills'],stop


def test_legacy_depth_partial_can_resume_to_original_target(env):
    oid,_=legacy_result(env,depth=1000)
    r=cycle(env,exit_data(LATER),now=LATER)[1]
    assert r['orders'][0]['order_id']==oid and r['fills'][0]['quantity']==4000,r
    assert r['orders'][0]['target_quantity']==5000 and r['orders'][0]['status']=='filled'


def test_legacy_zero_fill_pending_retains_original_order_and_target(env):
    oid,_=legacy_result(env,depth=50)
    r=cycle(env,exit_data(LATER),now=LATER)[1]
    assert r['orders'][0]['order_id']==oid and r['fills'][0]['quantity']==5000,r
    assert r['orders'][0]['target_quantity']==5000 and r['orders'][0]['status']=='filled'


def test_missing_legacy_rule_evidence_blocks_ratio_but_not_hard_stop(env):
    oid,_=legacy_result(env,depth=1000)
    with env[0].transaction() as db:
        row=db.execute('SELECT fill_id,evidence_json FROM fills WHERE order_id=?',(oid,)).fetchone()
        evidence=json.loads(row[1]);evidence.pop('rule')
        db.execute('UPDATE fills SET evidence_json=? WHERE fill_id=?',(canonical(evidence),row[0]))
    ratio=cycle(env,exit_data(LATER),now=LATER)[1]
    assert not ratio['fills'] and any('legacy_exit_rule_evidence_required' in x['reason'] for x in ratio['rejections']),ratio
    stop=cycle(env,exit_data(LATER,stop=True),now=LATER)[1]
    assert stop['snapshot_after']['positions']=={} and stop['fills'][0]['quantity']==9000,stop


def test_higher_priority_takeover_rolls_back_with_failed_fill(env):
    seed_buy(env)
    first=cycle(env,exit_data(depth=1000),now=NEXT)[1]
    original=state(env,NEXT)
    with env[0].transaction() as db:
        db.execute("CREATE TRIGGER s2_synthetic_fail BEFORE INSERT ON fills BEGIN SELECT RAISE(ABORT,'S2_SYNTHETIC_ABORT'); END")
    code,r=cycle(env,exit_data(LATER,stop=True),now=LATER)
    assert code==2 and 'S2_SYNTHETIC_ABORT' in r['reason'],r
    after=state(env,LATER)
    for key in ['cash_cents','lots','fills','orders','positions']:
        assert after[key]==original[key],key
    with env[0].transaction() as db:db.execute('DROP TRIGGER s2_synthetic_fail')
    assert cycle(env,exit_data(LATER,stop=True),now=LATER)[1]['snapshot_after']['positions']=={}


def test_invalid_exit_priority_never_consumes_depth_or_a_tranche(env):
    seed_buy(env)
    p,q,c=fixtures(NEXT);q['quotes'][0].update(last_price=11.6,bid_price=11.59,ask_price=11.6)
    p['execution_pool'][0]['exit_rules'][0]['priority']=True
    r,_=low_order(env,(p,q,c))
    assert r['fill_quantity']==0 and r['reason']=='invalid_exit_priority',r
    with env[0].transaction() as db:
        assert db.execute('SELECT COALESCE(SUM(sell_used),0) FROM liquidity').fetchone()[0]==0
    p['execution_pool'][0]['exit_rules'][0]['priority']=2
    fixed,_=low_order(env,(p,q,c),oid='corrected-priority')
    assert fixed['status']=='filled' and fixed['fill_quantity']==5000,fixed


def test_new_position_cycle_can_use_ratio_but_old_partial_cannot_revive(env):
    oid,saved=legacy_result(env,depth=100000)
    with env[0].transaction() as db:
        intent=json.loads(db.execute('SELECT intent_json FROM orders WHERE order_id=?',(oid,)).fetchone()[0])
    assert cycle(env,exit_data(LATER,stop=True),now=LATER)[1]['snapshot_after']['positions']=={}
    # Restore only the legacy terminal-mislabel fixture so an old order retry
    # is possible; never alter cash, lots or fills to seed the next lifecycle.
    with env[0].transaction() as db:
        db.execute('UPDATE orders SET status=?,result_json=? WHERE order_id=?',('partial',canonical(saved),oid))
    buy_data=fixtures(THIRD);buy_data[2]['trading_days'].append('2099-01-08')
    buy=cycle(env,buy_data,now=THIRD)[1]
    assert buy['fills'][0]['side']=='buy',buy
    fourth='2099-01-08T10:00:01+08:00'
    p,q,c=exit_data(fourth);c['trading_days'].append('2099-01-08')
    p['meta']['paper_authorization_id']=AUTH
    old=env[0].execute(account_id='synthetic',authorization_id=AUTH,intent=intent,plan=p,quotes=q,
        calendar=c,quote_max_age='5',now=fourth)
    assert old['fill_quantity']==0 and 'position_cycle_changed' in old['reason'],old
    fresh=cycle(env,(p,q,c),now=fourth)[1]
    assert fresh['fills'][0]['side']=='sell' and fresh['orders'][0]['target_quantity']>0,fresh


def test_legacy_completed_stage_cross_day_no_history_rewrite(env):
    oid,saved=legacy_result(env,depth=100000)
    r=cycle(env,exit_data(THIRD),now=THIRD)[1]
    assert r['fills']==[] and r['snapshot_after']['positions'][SYMBOL]['quantity']==5000
    with env[0].transaction() as db:
        row=db.execute('SELECT result_json,status FROM orders WHERE order_id=?',(oid,)).fetchone()
        assert json.loads(row[0])==saved and row[1]=='partial'


def test_changed_rule_cannot_reinterpret_a_partial_order(env):
    seed_buy(env)
    p,q,c=fixtures(NEXT);q['quotes'][0].update(last_price=11.6,bid_price=11.59,ask_price=11.6,bid_size=1000)
    first,intent=low_order(env,(p,q,c))
    assert first['fill_quantity']==1000
    p['execution_pool'][0]['exit_rules'][0]['quantity_pct']=.8
    q['quotes'][0].update(observed_at='2099-01-06T10:00:02+08:00',received_at='2099-01-06T10:00:02+08:00')
    p['meta']['paper_authorization_id']=AUTH
    r=env[0].execute(account_id='synthetic',authorization_id=AUTH,intent=intent,plan=p,quotes=q,
        calendar=c,quote_max_age='5',now=LATER)
    assert r['fill_quantity']==0 and 'rule_changed' in r['reason'],r
    assert state(env,LATER)['positions'][SYMBOL]['quantity']==9000


@pytest.mark.parametrize('entry', ['ledger','cli'])
@pytest.mark.parametrize('token', ['missing','canonical'])
def test_lowlevel_default_kill_exists_ignores_forged_false_and_never_reads(env,monkeypatch,entry,token):
    p,q,c=fixtures();p['meta']['paper_authorization_id']=AUTH
    p['risk_limits']['kill_switch_active']=False
    if token=='canonical':p['risk_limits']['kill_switch_file']='data/runtime/KILL_SWITCH'
    kill=driver.ROOT/'data/runtime/KILL_SWITCH'
    kill.parent.mkdir(parents=True,exist_ok=True);kill.write_text('SYNTHETIC STOP - NO CONTENT READER')
    old_read=Path.read_bytes
    def guarded_read(path):
        assert path!=kill,'KILL_CONTENTS_MUST_NOT_BE_READ'
        return old_read(path)
    monkeypatch.setattr(Path,'read_bytes',guarded_read)
    intent=dict(order_id='kill',symbol=SYMBOL,side='buy',quantity=100,limit_price=10.,rule_index=0)
    try:
        if entry=='ledger':
            r=env[0].execute(account_id='synthetic',authorization_id=AUTH,intent=intent,plan=p,quotes=q,
                calendar=c,quote_max_age='5',now=NOW)
        else:
            args=['execute','--database',str(env[0].path),'--account-id','synthetic','--authorization-id',AUTH,
                  '--fixture','--now',NOW,'--quote-max-age','5']
            for name,obj in [('plan',p),('quotes',q),('calendar',c),('order',intent)]:
                path=env[1]/(name+'.json');path.write_text(json.dumps(obj));args+=['--'+name,str(path)]
            out=io.StringIO()
            with redirect_stdout(out):code=low_cli(args)
            r=json.loads(out.getvalue());assert code==2,r
        assert r['fill_quantity']==0 and r['kill_switch_snapshot']['exists'] is True,r
        assert state(env,NOW)['cash_cents']==100000000 and not state(env,NOW)['fills']
    finally:kill.unlink()


@pytest.mark.parametrize('token',[None,'.env','/private/unapproved','data/runtime/../runtime/KILL_SWITCH'])
def test_lowlevel_unapproved_kill_token_refuses_without_read(env,token):
    p,q,c=fixtures();p['meta']['paper_authorization_id']=AUTH
    p['risk_limits'].update(kill_switch_file=token,kill_switch_active=False)
    r=env[0].execute(account_id='synthetic',authorization_id=AUTH,
        intent=dict(order_id='bad-token',symbol=SYMBOL,side='buy',quantity=100,limit_price=10.,rule_index=0),
        plan=p,quotes=q,calendar=c,quote_max_age='5',now=NOW)
    assert not r['fill_quantity'] and r['reason']=='unknown_kill_switch_path',r


def test_lowlevel_kill_symlink_is_unsafe_even_when_dangling(env):
    p,q,c=fixtures();p['meta']['paper_authorization_id']=AUTH
    kill=driver.ROOT/'data/runtime/KILL_SWITCH';kill.parent.mkdir(parents=True,exist_ok=True)
    kill.symlink_to(env[1]/'nonexistent-stop')
    try:
        r=env[0].execute(account_id='synthetic',authorization_id=AUTH,
            intent=dict(order_id='symlink-kill',symbol=SYMBOL,side='buy',quantity=100,limit_price=10.,rule_index=0),
            plan=p,quotes=q,calendar=c,quote_max_age='5',now=NOW)
        assert not r['fill_quantity'] and r['reason']=='unsafe_kill_switch_path',r
    finally:kill.unlink()


def test_low_boundary_rechecks_stop_created_after_driver_snapshot(env,monkeypatch):
    kill=driver.ROOT/'data/runtime/KILL_SWITCH';kill.parent.mkdir(parents=True,exist_ok=True)
    original=driver.shared_kill_snapshot
    def observed_then_stopped(plan,at,root):
        snap,errors=original(plan,at,root)
        assert not snap['exists'] and not errors
        kill.write_text('SYNTHETIC STOP AFTER HIGH-LEVEL SNAPSHOT')
        return snap,errors
    monkeypatch.setattr(driver,'shared_kill_snapshot',observed_then_stopped)
    try:
        code,r=cycle(env)
        assert code==2 and not r['fills'] and r['snapshot_after']['positions']=={},r
        assert r['kill_switch_snapshot']['exists'] is False
        assert r['orders'][0]['kill_switch_snapshot']['exists'] is True
    finally:kill.unlink()


def test_kill_file_does_not_block_existing_legal_exit(env):
    seed_buy(env)
    kill=driver.ROOT/'data/runtime/KILL_SWITCH';kill.parent.mkdir(parents=True,exist_ok=True)
    kill.write_text('SYNTHETIC STOP')
    try:
        r=cycle(env,exit_data(stop=True),now=NEXT)[1]
        assert r['fills'][0]['quantity']==10000 and r['snapshot_after']['positions']=={},r
    finally:kill.unlink()


@pytest.mark.parametrize('case',['unauthorized','wrong_auth','missing_research','zero_budget'])
def test_new_buy_gates_still_refuse_without_mutating_inventory(env,case):
    p,q,c=fixtures();p['meta']['paper_authorization_id']=AUTH
    auth=AUTH
    if case=='unauthorized':p['meta']['paper_trading_authorized']=False
    if case=='wrong_auth':auth='NOT_AUTHORIZED'
    if case=='missing_research':p['meta'].pop('research_summary')
    if case=='zero_budget':p['risk_limits']['target_total_position_pct']=0
    intent=dict(order_id='blocked-'+case,symbol=SYMBOL,side='buy',quantity=100,limit_price=10.,rule_index=0)
    if case=='wrong_auth':
        with pytest.raises(ValueError,match='authorization_mismatch'):
            env[0].execute(account_id='synthetic',authorization_id=auth,intent=intent,plan=p,quotes=q,
                calendar=c,quote_max_age='5',now=NOW)
    else:
        r=env[0].execute(account_id='synthetic',authorization_id=auth,intent=intent,plan=p,quotes=q,
            calendar=c,quote_max_age='5',now=NOW)
        assert r['status']=='rejected' and r['fill_quantity']==0,r
    snap=state(env,NOW)
    assert not snap['positions'] and not snap['fills'] and snap['cash_cents']==100000000
