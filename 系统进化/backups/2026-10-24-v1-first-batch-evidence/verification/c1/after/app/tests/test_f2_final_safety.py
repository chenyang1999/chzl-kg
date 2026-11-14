"""Independent F2 assertions over frozen real source; synthetic transport only.

The original I1 fixture is reused for isolation/bootstrap, NOT its conclusions.
Safety expectations intentionally fail where a scoped counterexample exists.
"""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import importlib
import json
import pytest
from test_v1_integration_authorization_20261024 import (
    code, reset, plan_dict, serialize, direct, buy, sell, orders, DATE, SYMBOL, OTHER)


def persisted(code,q,result):
    from pathlib import Path
    import os,hashlib
    rows=code.journal.read_jsonl(q.orders_path)
    assert rows[-1]==result
    case=os.environ.get('PYTEST_CURRENT_TEST','unknown')
    folder=Path(__file__).resolve().parents[2]/'observations';folder.mkdir(exist_ok=True)
    (folder/(hashlib.sha256(case.encode()).hexdigest()+'.json')).write_text(json.dumps(dict(case=case,result=result,journal_readback=rows,transport=orders(code)),ensure_ascii=False,indent=2)+'\n')
    return rows


@pytest.mark.parametrize('kind',['leader_breakout','daban_confirm','trend_pullback_buy','low_absorption_intraday','t_add_pullback'])
def test_positive_all_five_wrappers_reach_real_live_boundary(code,kind):
    p=plan_dict(); p['execution_pool'][0]['entry_rules'][0]['type']=kind
    q=direct(code,p)
    if kind=='t_add_pullback':
        q.holdings={SYMBOL:dict(total_qty=100,available_qty=100,market_value=1000.)}
    action='buy_breakout' if kind in ('leader_breakout','daban_confirm') else 'buy_pullback'
    code.session.set_scan_result(dict(trade_date=DATE,opportunities=[dict(ts_code=SYMBOL,action=action,sise_pass=True)]))
    reg=importlib.import_module('trading.executors.registry')
    model=code.schema.WatchlistPlan.model_validate(p)
    entry=model.execution_pool[0].model_dump(mode='json')
    store=code.positions.PositionsStateStore.for_mode(trade_date=DATE,dry_run=False)
    store.ensure_from_holdings(q.holdings,base_mobile_ratio=.7)
    out=reg.get_entry_executor(kind)(entry,entry['entry_rules'][0],q,store,simulate=False)
    assert out.status=='submitted' and out.quantity==100
    assert len(orders(code))==1 and orders(code)[0]['side']=='buy'
    assert code.journal.read_jsonl(q.orders_path)[-1]['order']['synthetic_only'] is True
    if kind=='t_add_pullback': assert store.positions[SYMBOL].t_state.t_add_done


@pytest.mark.parametrize('kind',['exit_at_open','exit_if_no_new_high','t_reduce_resistance','stop_loss_break','take_profit_hit','sector_switch_exit','intraday_break_exit','volume_price_divergence'])
def test_positive_existing_exit_wrappers_live_transport(code,kind):
    p=plan_dict(); p['execution_pool'][0].update(auto_trade_enabled=False,entry_rules=[],exit_rules=[dict(type=kind,trigger_price=9.,quantity_pct=1.)])
    q=direct(code,p)
    q.holdings={SYMBOL:dict(total_qty=1000,available_qty=1000)}
    q.quotes[SYMBOL].last=q.quotes[SYMBOL].bid=9.
    code.session.clear_session()
    reg=importlib.import_module('trading.executors.registry')
    entry=code.schema.WatchlistPlan.model_validate(p).execution_pool[0].model_dump(mode='json')
    out=reg.get_exit_executor(kind)(entry,entry['exit_rules'][0],q,SimpleNamespace(positions={}),simulate=False)
    assert out.status=='submitted'
    assert orders(code)[0]['side']=='sell'
    assert code.journal.read_jsonl(q.orders_path)[-1]['dry_run'] is False


@pytest.mark.parametrize('gate',['zero_budget','missing_budget','global_buy_condition','missing_research_legacy'])
@pytest.mark.parametrize('watch',[False,True])
def test_live_legal_exit_not_dry_run_for_buy_only_blockers(code,gate,watch):
    p=plan_dict()
    if gate=='zero_budget':
        for k in code.auth.BUY_CAPS:p['risk_limits'][k]=0
    elif gate=='missing_budget':
        for k in code.auth.BUY_CAPS:p['risk_limits'].pop(k)
    elif gate=='global_buy_condition':p['no_trade_conditions']=[dict(scope='global',code='RESEARCH_SOURCE_STALE',active=True)]
    # absent readiness fields are explicitly legacy in the source contract.
    p['execution_pool'][0]['auto_trade_enabled']=False
    if watch:p['watch_pool']=p.pop('execution_pool');p['execution_pool']=[]
    serialize(code,p)
    code.state.holdings={SYMBOL:dict(ts_code=SYMBOL,total_qty=1000,available_qty=1000,market_value=8000.,cost_price=8.)}
    code.state.last=code.state.bid=8.;code.state.scan=False
    code.watcher.run_intraday_once(DATE,mode='live')
    assert len(orders(code))==1 and orders(code)[0]['side']=='sell'
    q=code.state.contexts[-1]
    rows=code.journal.read_jsonl(q.orders_path)
    assert rows[-1]['status']=='submitted' and rows[-1]['dry_run'] is False


@pytest.mark.parametrize('marker',['no_trade','decision_status','production_ready','research_completion_passed','meta_research'])
def test_explicit_whole_plan_not_live_contract_denies_before_sell(code,marker):
    p=plan_dict()
    if marker=='no_trade':p['no_trade']=True
    elif marker=='decision_status':p['decision_status']='no_trade'
    elif marker=='meta_research':p['meta']={'research_completion_passed':False}
    else:p[marker]=False
    # A live-looking flag combination is not accepted by existing loader contract.
    with pytest.raises(ValueError):code.loader.validate_plan_for_date(p,DATE)
    with pytest.raises(ValueError):direct(code,p)
    serialize(code,p)
    code.state.holdings={SYMBOL:dict(ts_code=SYMBOL,total_qty=1000,available_qty=1000,market_value=8000.,cost_price=8.)}
    code.state.last=code.state.bid=8.
    with pytest.raises(ValueError):code.watcher.run_intraday_once(DATE,mode='live',reload=True)
    assert code.state.clients==0 and not orders(code)


@pytest.mark.parametrize('marker',['no_trade','decision_status','production_ready','research_completion_passed'])
def test_final_boundary_independently_denies_non_live_plan_for_sell(code,marker):
    q=direct(code);p=json.loads(q.authorization.plan_json)
    p[marker]='no_trade' if marker=='decision_status' else (True if marker=='no_trade' else False)
    q.authorization=replace(q.authorization,plan_json=json.dumps(p))
    q.holdings={SYMBOL:dict(total_qty=1000,available_qty=1000)}
    q.quotes[SYMBOL].last=q.quotes[SYMBOL].bid=8.
    out=sell(q,limit_price=8.)
    assert out['status']=='rejected';persisted(code,q,out)
    assert not orders(code)


def test_detached_snapshot_and_context_date_mismatch(code):
    q=direct(code);original=q.authorization
    parsed=json.loads(original.plan_json);parsed['autonomous_trading_enabled']=False
    assert buy(q)['status']=='submitted' # parsing/modifying a detached copy grants/removes nothing
    q.trade_date='20990106'
    out=buy(q);assert out['status']=='rejected';persisted(code,q,out)
    assert len(orders(code))==1


@pytest.mark.parametrize('scope',['plan','account'])
@pytest.mark.parametrize('key,value',[('autonomous_trading_enabled',False),('requires_user_confirmation',True),('mode','dry_run')])
def test_live_consent_revalidated_for_sells_and_buys(code,scope,key,value):
    q=direct(code);a=q.authorization;p=json.loads(a.plan_json if scope=='plan' else a.account_json);p[key]=value
    q.authorization=replace(a,**{scope+'_json':json.dumps(p)})
    q.holdings={SYMBOL:dict(total_qty=1000,available_qty=1000)}
    assert buy(q)['status']=='rejected' and sell(q)['status']=='rejected'
    assert code.state.clients==0


@pytest.mark.parametrize('available',[None,False,-1,1.5,'nan','unknown',0])
def test_no_guess_sellable_quantity(code,available):
    q=direct(code);q.holdings={SYMBOL:dict(total_qty=1000,available_qty=available)}
    out=sell(q);assert out['status']=='rejected';persisted(code,q,out)
    assert code.state.clients==0


@pytest.mark.parametrize('key,reason',[('max_buy_orders_per_day','daily_buy_order_cap_reached'),('max_orders_per_symbol_per_day','symbol_buy_order_cap_reached')])
def test_positive_capacity_order_counts_actual_journal_readback(code,key,reason):
    p=plan_dict();p['risk_limits'][key]=1
    q=direct(code,p);assert buy(q)['status']=='submitted'
    assert len(code.journal.read_jsonl(q.orders_path))==1
    q=direct(code,p);out=buy(q);assert out['reason']==reason;persisted(code,q,out)
    assert len(orders(code))==1


@pytest.mark.parametrize('gate',['no_scan','trigger','rr','limit'])
def test_final_buy_existing_price_rr_scan_protection(code,gate):
    p=plan_dict()
    if gate=='rr':p['execution_pool'][0]['take_profit']=10.5
    q=direct(code,p)
    if gate=='no_scan':code.session.clear_session()
    if gate=='trigger':q.quotes[SYMBOL].last=9.8
    out=buy(q,limit_price=9.9 if gate=='limit' else 10.)
    assert out['status']=='rejected';persisted(code,q,out)
    assert not orders(code)


@pytest.mark.parametrize('evidence_date',['20990104',None])
def test_counterexample_scan_date_must_match_authorized_plan(code,evidence_date):
    q=direct(code)
    scan=dict(opportunities=[dict(ts_code=SYMBOL,action='buy_breakout',sise_pass=True)])
    if evidence_date is not None:scan['trade_date']=evidence_date
    code.session.set_scan_result(scan)
    out=buy(q);persisted(code,q,out)
    assert out['status']=='rejected',json.dumps(dict(actual=out,transport=orders(code),scan=scan),ensure_ascii=False)


@pytest.mark.parametrize('violation',['untriggered','limit','quantity'])
def test_counterexample_low_level_sell_rule_presence_not_full_authority(code,violation):
    p=plan_dict();p['execution_pool'][0]['exit_rules'][0]['quantity_pct']=.1
    q=direct(code,p);q.holdings={SYMBOL:dict(total_qty=1000,available_qty=1000)}
    q.quotes[SYMBOL].last=q.quotes[SYMBOL].bid=8.
    kw=dict(quantity=100,limit_price=8.)
    if violation=='untriggered':q.quotes[SYMBOL].last=q.quotes[SYMBOL].bid=10.;kw['limit_price']=10.
    if violation=='limit':kw['limit_price']=.01
    if violation=='quantity':kw['quantity']=1000
    out=sell(q,**kw);persisted(code,q,out)
    assert out['status']=='rejected',json.dumps(dict(actual=out,transport=orders(code),bound_rule=p['execution_pool'][0]['exit_rules'][0]),ensure_ascii=False)


def test_real_live_sell_wrapper_still_checks_simple_untriggered_stop(code):
    q=direct(code);q.holdings={SYMBOL:dict(total_qty=1000,available_qty=1000)}
    entry=code.schema.WatchlistPlan.model_validate(plan_dict()).execution_pool[0].model_dump(mode='json')
    wrapper=importlib.import_module('trading.executors.execute_stop_loss_break')
    out=wrapper.execute(entry,entry['exit_rules'][0],q,SimpleNamespace(positions={}),simulate=False)
    assert out.status=='skipped' and out.skip_reason=='trigger_not_met'
    assert not orders(code)


@pytest.mark.parametrize('key',['target_total_position_pct','max_positions','max_buy_orders_per_day','max_orders_per_symbol_per_day','stock'])
@pytest.mark.parametrize('missing',[False,True])
def test_zero_or_missing_buy_budgets_are_not_default_authority(code,key,missing):
    p=plan_dict();container=p['execution_pool'][0] if key=='stock' else p['risk_limits'];field='max_position_pct' if key=='stock' else key
    if missing:container.pop(field)
    else:container[field]=0
    q=direct(code,p);out=buy(q)
    assert out['status']=='rejected';persisted(code,q,out)
    assert code.state.clients==0


@pytest.mark.parametrize('capacity,reason',[('total','total_position_cap_exceeded'),('stock','stock_position_cap_exceeded'),('cash','cash_budget_exceeded'),('positions','max_positions_reached'),('rule','rule_buy_budget_exceeded'),('unknown','buy_capacity_evidence_invalid')])
def test_positive_capacity_amounts_fail_closed_at_real_boundary(code,capacity,reason):
    p=plan_dict()
    if capacity=='total':p['risk_limits']['target_total_position_pct']=.005
    if capacity=='stock':p['execution_pool'][0]['max_position_pct']=.005
    if capacity=='positions':p['risk_limits']['max_positions']=1
    q=direct(code,p)
    if capacity=='cash':q.cash=500.
    if capacity=='positions':q.holdings={OTHER:dict(total_qty=100,market_value=1000.)}
    if capacity=='unknown':q.holdings={OTHER:dict(total_qty=100)}
    out=buy(q,quantity=200 if capacity=='rule' else 100)
    assert out['reason']==reason;persisted(code,q,out)
    assert code.state.clients==0


@pytest.mark.parametrize('side',['buy','sell'])
@pytest.mark.parametrize('binding',[None,'arbitrary_dict'])
def test_final_missing_binding_is_not_permission(code,side,binding):
    q=direct(code);q.authorization={} if binding else None
    out=buy(q,side=side)
    assert out['reason']=='execution_authorization_missing_or_invalid';persisted(code,q,out)
    assert code.state.clients==0


def test_kill_has_priority_over_binding_and_sell_not_guessed_from_last(code):
    q=direct(code);q.holdings={SYMBOL:dict(total_qty=1000,available_qty=1000)}
    q.quotes[SYMBOL].bid=None
    out=sell(q);assert out['status']=='rejected';persisted(code,q,out)
    (code.root/q.kill_switch_file).write_text('synthetic_only')
    q.authorization=None
    out=sell(q);assert out['reason']=='kill_switch_active';persisted(code,q,out)
    assert code.state.clients==0


def test_counterexample_loader_dispatch_cannot_reuse_other_day_scan(code):
    serialize(code)
    code.session.set_scan_result(dict(trade_date='20990104',opportunities=[dict(ts_code=SYMBOL,action='buy_breakout',sise_pass=True)]))
    code.loader.run_load_plan(DATE,mode='live')
    q=code.state.contexts[-1]
    rows=code.journal.read_jsonl(q.orders_path)
    if rows:persisted(code,q,rows[-1])
    assert not orders(code),json.dumps(dict(transport=orders(code),journal=rows),ensure_ascii=False)


def test_two_watcher_rounds_unique_dispatch_and_prepare_has_no_context(code):
    serialize(code)
    code.loader.run_load_plan(DATE,mode='live',dispatch=False)
    assert code.state.clients==code.state.dispatches==len(code.state.contexts)==0
    for _ in range(2):code.watcher.run_intraday_once(DATE,mode='live',reload=True)
    assert code.state.dispatches==2 and len(code.state.contexts)==2
    assert len(orders(code))==2


def test_real_daemon_two_rounds_prepare_then_single_dispatch(code,monkeypatch):
    import sys
    from types import ModuleType
    for name,attrs in (
        ('src.execute.market_snapshot',dict(build_snapshot=lambda *a,**k: (_ for _ in ()).throw(AssertionError('no snapshot execution')))),
        ('src.execute.sector_stats',dict(compute_sector_stats=lambda *a,**k: None,output_path=lambda *a,**k: None)),
        ('src.execute.plan_context',dict(load_sector_map=lambda *a,**k: {}))):
        module=ModuleType(name);module.__dict__.update(attrs);monkeypatch.setitem(sys.modules,name,module)
    daemon=importlib.import_module('src.execute.watcher_daemon')
    monkeypatch.setattr(daemon,'_in_session',lambda now:True)
    monkeypatch.setattr(daemon.time,'sleep',lambda n:None)
    serialize(code)
    out=daemon.run_loop(DATE,mode='live',max_passes=2,refresh_snapshot_every=0)
    assert out==0 and code.state.dispatches==2 and len(code.state.contexts)==2
    assert len(orders(code))==2
    log=code.journal.read_jsonl(code.root/f'data/execution/{DATE}/watcher_daemon.jsonl')
    assert len(log)==2 and all(r['ok'] for r in log)


@pytest.mark.parametrize('kind',['leader_breakout','daban_confirm','trend_pullback_buy','low_absorption_intraday','t_add_pullback'])
def test_watcher_full_chain_positive_for_each_entry_wrapper(code,kind,monkeypatch):
    p=plan_dict();p['execution_pool'][0]['entry_rules'][0]['type']=kind
    serialize(code,p)
    if kind=='t_add_pullback':code.state.holdings={SYMBOL:dict(ts_code=SYMBOL,total_qty=100,available_qty=100,market_value=1000.,cost_price=10.)}
    action='buy_breakout' if kind in ('leader_breakout','daban_confirm') else 'buy_pullback'
    def scan(plan,**kw):
        return dict(trade_date=kw['trade_date'],pool_size=1,buy_ready_count=1,opportunities=[dict(ts_code=SYMBOL,action=action,sise_pass=True)])
    monkeypatch.setattr(code.watcher,'scan_entry_opportunities',scan)
    code.watcher.run_intraday_once(DATE,mode='live',reload=True)
    assert code.state.dispatches==1 and len(orders(code))==1
    assert orders(code)[0]['quantity']==100
    q=code.state.contexts[-1]
    assert code.journal.read_jsonl(q.orders_path)[-1]['status']=='submitted' and not q.dry_run


def test_observation_live_date_only_not_wall_clock_expiry(code):
    # Characterization, not a newly imposed calendar/session requirement.
    q=direct(code)
    out=buy(q);assert out['status']=='submitted'
    persisted(code,q,out)
    assert q.trade_date==DATE=='20990105'
