"""New audit assertions: failures are findings, NOT post-fix acceptance.
All prices, permission ids, positions and clocks are synthetic. Legacy modules
are never imported; only inspected pure definitions are extracted with AST.
"""
from __future__ import annotations
import ast
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from math import floor
import pytest
from trading.paper import PaperLedger
from test_canghai_paper_plan_driver_20261023 import fixtures, cycle, NOW, NEXT, AUTH, SYMBOL

BASE = Path(__file__).resolve().parents[2]
APP = BASE / 'app'


def definition(path, name, deps=None, class_name=None):
    module = ast.parse((BASE/'inspected'/path).read_text())
    nodes = module.body
    if class_name:
        nodes = next(n.body for n in nodes if isinstance(n,ast.ClassDef) and n.name==class_name)
    function = next(n for n in nodes if isinstance(n,ast.FunctionDef) and n.name==name)
    tree = ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),function], type_ignores=[])
    ast.fix_missing_locations(tree)
    namespace = dict(deps or {})
    exec(compile(tree, 'isolated_ast:'+path, 'exec'), namespace)
    return namespace[name]


@pytest.fixture
def env(tmp_path):
    ledger=PaperLedger(tmp_path/'audit_synthetic.sqlite3',fixture=True)
    ledger.initialize(account_id='synthetic',init_cash='1000000',authorization_id=AUTH,
        seed_source='D_AUDIT_SYNTHETIC_ONLY',fee_model={'model':'zero_fee_assumption'},now=NOW)
    return ledger,tmp_path


def test_pending_fractional_profit_exit_must_not_block_new_hard_stop(env):
    assert cycle(env)[1]['event']=='paper_filled'
    p,q,c=fixtures(NEXT)
    p['execution_pool']=[];p['no_trade']=True
    q['quotes'][0].update(last_price=11.6,bid_price=11.59,ask_price=11.6)
    code,r=cycle(env,(p,q,c),now=NEXT)
    assert r['fills'][0]['quantity']==5000
    # New valid observation now triggers the stored priority-1 stop, while
    # yesterday's half-profit order remains partial only because requested=base.
    q['quotes'][0].update(last_price=9.4,bid_price=9.39,ask_price=9.4,
        observed_at='2099-01-06T10:00:02+08:00',received_at='2099-01-06T10:00:02+08:00')
    code,r=cycle(env,(p,q,c),now='2099-01-06T10:00:03+08:00')
    assert r['snapshot_after']['positions'].get(SYMBOL,{}).get('quantity',0)==0, {
        'remaining':r['snapshot_after']['positions'], 'fills':r['fills'],
        'observations':r['observations'],'rejections':r['rejections']}


def test_lowlevel_paper_execute_must_honor_same_default_kill_file(env):
    p,q,c=fixtures()
    p['meta']['paper_authorization_id']=AUTH
    kill=APP/'data/runtime/KILL_SWITCH'
    kill.parent.mkdir(parents=True,exist_ok=True)
    assert not kill.exists()
    kill.write_text('AUDIT SYNTHETIC STOP; NOT PRODUCTION')
    try:
        r=env[0].execute(account_id='synthetic',authorization_id=AUTH,
            intent=dict(order_id='audit-kill',symbol=SYMBOL,side='buy',quantity=100,limit_price=10.,rule_index=0),
            plan=p,quotes=q,calendar=c,quote_max_age='5',now=NOW)
        assert r['fill_quantity']==0, {'status':r['status'],'event':r['event'],'fill_quantity':r['fill_quantity']}
    finally:
        kill.unlink()


def test_account_overlay_must_not_raise_formal_zero_budget():
    spec=importlib.util.spec_from_file_location('d_audit_schema',APP/'trading/schema/watchlist_plan.py')
    schema=importlib.util.module_from_spec(spec);sys.modules[spec.name]=schema;spec.loader.exec_module(schema)
    apply=definition('trading/load_plan.py','apply_account_overrides',{'WatchlistPlan':schema.WatchlistPlan})
    plan=schema.WatchlistPlan(trade_date='20990105',mode='dry_run',autonomous_trading_enabled=False,
        requires_user_confirmation=True,no_trade=False,risk_limits={'target_total_position_pct':0})
    account=SimpleNamespace(mode='live',autonomous_trading_enabled=True,requires_user_confirmation=False,
        risk_limits={'target_total_position_pct':.75})
    out=apply(plan,account)
    assert out.risk_limits.target_total_position_pct==0, out.risk_limits.target_total_position_pct


def test_unknown_sellable_must_not_fall_back_to_total_qty():
    available=definition('trading/order/qmt_context.py','available_qty',class_name='QMTContext')
    ctx=SimpleNamespace(holdings={SYMBOL:{'total_qty':1000}})
    assert available(ctx,SYMBOL)==0, available(ctx,SYMBOL)


def test_order_sizing_must_use_intended_symbol_price_not_universe_max():
    lot=definition('trading/executors/base.py','floor_lot',{'floor':floor,'LOT_SIZE':100})
    sizing=definition('trading/executors/base.py','compute_buy_qty',{'floor_lot':lot,'LOT_SIZE':100})
    ctx=SimpleNamespace(total_asset=100000,quotes={SYMBOL:SimpleNamespace(last=10.),'600001.SH':SimpleNamespace(last=100.)})
    result=sizing(ctx,position_pct=.1)
    assert result==1000, {'intended_symbol':SYMBOL,'intended_price':10,'other_price':100,'actual_quantity':result}


def test_legacy_breakout_must_reach_trigger_not_only_ask_cap():
    trigger=definition('trading/executors/base.py','evaluate_buy_trigger')
    ok,reasons=trigger(rule={'type':'leader_breakout','trigger_price':10.,'max_acceptable_ask':10.3},
        quote_last=9.8,quote_ask=9.9)
    assert ok is False, reasons
