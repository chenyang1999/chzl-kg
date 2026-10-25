"""Four historical AST counterexamples plus the missing-scan joint example.
The before sizing contract predates explicit symbol+limit. Select the actual
signature rather than editing any old audit test or passing invented outputs.
D04 belongs to S1 and is diagnostic-only, never counted as S3-owned repair.
"""
from __future__ import annotations
import ast
import importlib.util
from decimal import Decimal, InvalidOperation
from math import floor, isfinite
from numbers import Real
from pathlib import Path
from types import SimpleNamespace
import sys

APP=Path(__file__).resolve().parents[1]
SYMBOL='600000.SH'

def definition(rel,name,deps=None,klass=None):
    tree=ast.parse((APP/rel).read_text())
    nodes=tree.body
    if klass:
        nodes=next(n.body for n in nodes if isinstance(n,ast.ClassDef) and n.name==klass)
    fn=next(n for n in nodes if isinstance(n,ast.FunctionDef) and n.name==name)
    module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),fn],type_ignores=[])
    ast.fix_missing_locations(module)
    ns=dict(deps or {})
    exec(compile(module,'S3_AST:'+rel,'exec'),ns)
    return ns[name]

def pure_module(rel,name):
    spec=importlib.util.spec_from_file_location(name,APP/rel)
    mod=importlib.util.module_from_spec(spec)
    sys.modules[name]=mod
    spec.loader.exec_module(mod)
    return mod

def deps():
    ns={'floor':floor,'LOT_SIZE':100,'Real':Real,'isfinite':isfinite}
    for name in ('floor_lot','_number','_positive'):
        try:
            ns[name]=definition('trading/executors/base.py',name,ns)
        except StopIteration:
            pass
    return ns

def test_D04_account_overlay_preserves_formal_zero_S1_owned():
    schema=pure_module('trading/schema/watchlist_plan.py','s3_diag_schema')
    ns={'WatchlistPlan':schema.WatchlistPlan}
    if (APP/'trading/execution_authorization.py').exists():
        helper=pure_module('trading/execution_authorization.py','s3_diag_authorization')
        ns.update({k:getattr(helper,k) for k in ('merge_risk_limits','resolve_execution_mode','buy_budget_reasons')})
        ns['_plan_payload']=definition('trading/load_plan.py','_plan_payload',ns)
    apply=definition('trading/load_plan.py','apply_account_overrides',ns)
    p=schema.WatchlistPlan(trade_date='20990105',mode='dry_run',autonomous_trading_enabled=False,
        requires_user_confirmation=True,no_trade=False,risk_limits={'target_total_position_pct':0})
    a=SimpleNamespace(mode='live',autonomous_trading_enabled=True,requires_user_confirmation=False,
        risk_limits={'target_total_position_pct':.75})
    assert apply(p,a).risk_limits.target_total_position_pct==0

def test_D06_unknown_sellable_not_total():
    fn=definition('trading/order/qmt_context.py','available_qty',
                  {'Decimal':Decimal,'InvalidOperation':InvalidOperation},klass='QMTContext')
    q=SimpleNamespace(holdings={SYMBOL:{'total_qty':1000}})
    assert fn(q,SYMBOL)==0

def test_D07_size_target_not_quote_universe():
    fn=definition('trading/executors/base.py','compute_buy_qty',deps())
    q=SimpleNamespace(total_asset=100000.,cash=100000.,holdings={},quotes={
        SYMBOL:SimpleNamespace(last=10.),'600001.SH':SimpleNamespace(last=100.)})
    import inspect
    args={'position_pct':.1}
    if 'ts_code' in inspect.signature(fn).parameters:
        args.update(ts_code=SYMBOL,limit_price=10.)
    assert fn(q,**args)==1000

def test_D08_breakout_must_reach_trigger():
    fn=definition('trading/executors/base.py','evaluate_buy_trigger',deps())
    assert fn(rule={'type':'leader_breakout','trigger_price':10.,'max_acceptable_ask':10.3},
              quote_last=9.8,quote_ask=9.9)[0] is False

def test_C05_missing_scan_must_not_combine_with_price_cap_to_allow():
    mod=pure_module('trading/watcher/session_context.py','s3_diag_session')
    mod.clear_session()
    fn=definition('trading/executors/base.py','evaluate_buy_trigger',deps())
    triggered=fn(rule={'type':'leader_breakout','trigger_price':10.,'max_acceptable_ask':10.3},
                 quote_last=9.8,quote_ask=9.9)[0]
    allowed=mod.buy_allowed(SYMBOL,entry_style='leader_breakout')[0]
    assert allowed is False
    assert not (triggered and allowed)
