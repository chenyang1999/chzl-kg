"""I1: isolated real schema/loader/watcher/dispatcher/executor/context chain.

Run only in the audited scratch snapshot. Settings, market scan input and the
last broker transport are synthetic; authorization, risk, state and journal
implementations are real copied source. No real account/holdings are read.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import importlib
import json
from pathlib import Path
import shutil
import sys
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

DATE = "20990105"
SYMBOL = "600000.SH"
OTHER = "600001.SH"
APP = Path(__file__).resolve().parents[1]


def plan_dict() -> dict[str, Any]:
    return dict(schema_version="1.0", trade_date=DATE, mode="live",
                autonomous_trading_enabled=True, requires_user_confirmation=False,
                risk_limits=dict(target_total_position_pct=.4, max_positions=4,
                                 max_buy_orders_per_day=4, max_orders_per_symbol_per_day=2,
                                 block_prefixes=[], block_st=True,
                                 kill_switch_file="data/runtime/SYNTHETIC_KILL"),
                execution_pool=[dict(ts_code=SYMBOL, name="SYNTHETIC_ONLY", score=90,
                    auto_trade_enabled=True, requires_user_confirmation=False,
                    plan_status="execution_pool_hold_add_on_pullback", max_position_pct=.15,
                    stop_loss=9., take_profit=14.,
                    entry_rules=[dict(type="leader_breakout", trigger_price=10.,
                                      max_acceptable_ask=10., position_pct=.01)],
                    exit_rules=[dict(type="stop_loss_break", trigger_price=9., quantity_pct=1.)])],
                watch_pool=[])


@pytest.fixture(scope="module")
def code(tmp_path_factory):
    root = tmp_path_factory.mktemp("i1-real-chain")
    assert root.is_relative_to(Path.home() / ".hermes/cache/scratch")
    # Never import from the production tree. The outer runner supplies reviewed
    # copies; fixture gives every I/O dependency a synthetic root before import.
    saved = {k: v for k, v in sys.modules.items() if k.split(".")[0] in {"src", "trading", "scripts"}}
    for k in saved:
        del sys.modules[k]
    mp = pytest.MonkeyPatch()
    mp.delenv("CHZL_JUDGMENT_NODE", raising=False)
    def module(name, **kw):
        m = ModuleType(name)
        m.__dict__.update(kw)
        mp.setitem(sys.modules, name, m)
    for name in ("src", "src.plan", "src.execute", "src.trading_agent", "trading", "trading.schema",
                 "trading.order", "trading.watcher", "trading.executors", "scripts", "scripts.research"):
        module(name, __path__=[str(APP / name.replace(".", "/"))])
    module("src.settings", ROOT=root, DATA_DIR=root / "data")
    state = SimpleNamespace(clients=0, calls=[], holdings={}, last=10., ask=10., bid=9.9, scan=True,
                            dispatches=0, contexts=[])
    class SyntheticTransport:
        def __init__(self):
            state.clients += 1
        def get_holdings(self, **kw):
            state.calls.append(("holdings", kw))
            return dict(summary=dict(total_asset=100000., cash=100000.), positions=list(deepcopy(state.holdings).values()))
        def get_quotes(self, symbols):
            state.calls.append(("quotes", symbols))
            return {c: SimpleNamespace(ts_code=c, last=state.last, ask=state.ask, bid=state.bid) for c in symbols}
        def place_limit_order(self, **kw):
            state.calls.append(("order", kw))
            return dict(synthetic_only=True, order_id="SYNTHETIC_NOT_A_BROKER_ORDER")
    module("src.trading_agent.qmt_client", QMTMCPClient=SyntheticTransport)
    def scan(plan, **kw):
        return dict(trade_date=DATE, pool_size=len(plan.execution_pool), buy_ready_count=int(state.scan),
                    opportunities=[dict(ts_code=SYMBOL, action="buy_breakout", sise_pass=True,
                                        reasons=["synthetic_market_evidence"])] if state.scan else [])
    module("trading.entry_selector", scan_entry_opportunities=scan)
    mods = {k: importlib.import_module(v) for k, v in dict(
        schema="trading.schema.watchlist_plan", auth="trading.execution_authorization",
        qmt="trading.order.qmt_context", loader="trading.load_plan", watcher="trading.watcher.run_once",
        session="trading.watcher.session_context", positions="trading.positions_state",
        journal="src.trading_agent.journal", after="trading.after_close").items()}
    original_init = mods["qmt"].QMTContext.__init__
    def observed_init(self, *a, **kw):
        original_init(self, *a, **kw)
        state.contexts.append(self)
    mp.setattr(mods["qmt"].QMTContext, "__init__", observed_init)
    original_dispatch = mods["watcher"].dispatch_plan
    def observed_dispatch(*a, **kw):
        state.dispatches += 1
        return original_dispatch(*a, **kw)
    mp.setattr(mods["watcher"], "dispatch_plan", observed_dispatch)
    mp.setattr(mods["loader"], "dispatch_plan", observed_dispatch)
    yield SimpleNamespace(root=root, state=state, **mods)
    mp.undo()
    for k in list(sys.modules):
        if k.split(".")[0] in {"src", "trading", "scripts"}:
            del sys.modules[k]
    sys.modules.update(saved)


@pytest.fixture(autouse=True)
def reset(code):
    for name in ("data", "config"):
        path = code.root / name
        if path.exists():
            shutil.rmtree(path)
    (code.root / "data/runtime").mkdir(parents=True)
    (code.root / "config").mkdir()
    # Explicit synthetic hard preferences use existing semantics, not production
    # thresholds. Positive tests buy only 1% and do not depend on raising caps.
    (code.root / "data/user_preferences.yaml").write_text("{}")
    account = dict(mode="live", autonomous_trading_enabled=True, requires_user_confirmation=False,
                   risk_limits=deepcopy(plan_dict()["risk_limits"]))
    (code.root / "config/trading_account.yaml").write_text(json.dumps(account))
    code.session.clear_session()
    code.state.__dict__.update(clients=0, calls=[], holdings={}, last=10., ask=10., bid=9.9,
                               scan=True, dispatches=0, contexts=[])


def serialize(code, payload=None):
    # The actual schema serializer, not a hand-written simplified loaded plan.
    model = code.schema.WatchlistPlan.model_validate(payload or plan_dict())
    path = code.root / f"data/plans/{DATE}/watchlist_plan.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(code.loader._plan_payload(model)))
    return model


def orders(code):
    return [v for k, v in code.state.calls if k == "order"]


def direct(code, payload=None, *, mode="live", account_changes=None):
    model = serialize(code, payload)
    account = code.loader.load_account_config()
    if account_changes:
        account = replace(account, **account_changes)
    auth = code.auth.bind_execution_authorization(model, account, effective_mode=mode)
    q = code.qmt.QMTContext(DATE, mode == "dry_run", model.risk_limits.kill_switch_file,
                            runtime_dir=code.root / "data/runtime", authorization=auth)
    q.total_asset = q.cash = 100000.
    q.quotes = {SYMBOL: SimpleNamespace(last=10., ask=10., bid=9.9)}
    code.session.set_scan_result(dict(trade_date=DATE, opportunities=[
        dict(ts_code=SYMBOL, action="buy_breakout", sise_pass=True)]))
    return q


def buy(q, **kw):
    return q.place_order(**(dict(ts_code=SYMBOL, side="buy", quantity=100, limit_price=10.,
                                rule_type="leader_breakout", reasons=["synthetic_only"]) | kw))


def sell(q, **kw):
    return buy(q, **(dict(side="sell", rule_type="stop_loss_break", limit_price=9.9) | kw))


@pytest.mark.parametrize("reload", [False, True])
def test_schema_loader_watcher_dispatch_executor_context_positive_buy(code, reload):
    serialize(code)
    out = code.watcher.run_intraday_once(DATE, mode="live", reload=reload)
    assert out["entry_count"] == 1
    assert code.state.dispatches == 1
    assert len(code.state.contexts) == 1
    q = code.state.contexts[0]
    assert isinstance(q.authorization, code.auth.ExecutionAuthorization)
    assert len(orders(code)) == 1
    assert orders(code)[0]["quantity"] == 100
    persisted = code.journal.read_jsonl(q.orders_path)
    assert [r["status"] for r in persisted] == ["submitted"]
    assert persisted[0]["order"]["synthetic_only"] is True


def test_loader_default_single_dispatch_with_real_context(code):
    serialize(code)
    code.session.set_scan_result(dict(trade_date=DATE, opportunities=[dict(ts_code=SYMBOL, action="buy_breakout", sise_pass=True)]))
    code.loader.run_load_plan(DATE, mode="live")
    assert code.state.dispatches == 1
    assert len(orders(code)) == 1


def test_preparation_does_not_construct_or_dispatch(code):
    serialize(code)
    code.loader.run_load_plan(DATE, mode="live", dispatch=False)
    assert code.state.clients == code.state.dispatches == len(code.state.contexts) == 0


def test_two_watcher_rounds_each_dispatch_once_and_respect_count(code):
    payload = plan_dict()
    payload["risk_limits"]["max_buy_orders_per_day"] = 1
    serialize(code, payload)
    for _ in range(2):
        code.watcher.run_intraday_once(DATE, mode="live", reload=True)
    assert code.state.dispatches == 2
    assert len(orders(code)) == 1
    assert code.journal.read_jsonl(code.state.contexts[-1].orders_path)[-1]["reason"] == "daily_buy_order_cap_reached"


@pytest.mark.parametrize("target,key,value", [
    ("plan", "mode", "dry_run"), ("plan", "autonomous_trading_enabled", False),
    ("plan", "requires_user_confirmation", True), ("account", "mode", "dry_run"),
    ("account", "autonomous_trading_enabled", False), ("account", "requires_user_confirmation", True)])
def test_requested_live_cannot_supply_plan_or_account_permission(code, target, key, value):
    payload = plan_dict()
    if target == "plan":
        payload[key] = value
    else:
        path = code.root / "config/trading_account.yaml"
        raw = json.loads(path.read_text()); raw[key] = value; path.write_text(json.dumps(raw))
    serialize(code, payload)
    with pytest.raises(ValueError):
        code.watcher.run_intraday_once(DATE, mode="live", reload=True)
    assert code.state.clients == code.state.dispatches == 0
    assert not orders(code)


@pytest.mark.parametrize("key,value", [("auto_trade_enabled", False), ("requires_user_confirmation", True)])
def test_stock_permission_not_filled_by_live_request_or_holdings(code, key, value):
    payload = plan_dict(); payload["execution_pool"][0][key] = value
    serialize(code, payload)
    code.watcher.run_intraday_once(DATE, mode="live")
    assert not orders(code)
    q = code.state.contexts[-1]
    assert buy(q)["reason"] == "stock_buy_not_authorized"
    assert not orders(code)


@pytest.mark.parametrize("invalid", [None, {}, "live", object()])
@pytest.mark.parametrize("side", ["buy", "sell"])
def test_unbound_invalid_live_context_has_zero_client_calls(code, invalid, side):
    q = code.qmt.QMTContext(DATE, False, "data/runtime/SYNTHETIC_KILL", authorization=invalid)
    result = buy(q, side=side)
    assert result["status"] == "rejected"
    assert result["reason"] == "execution_authorization_missing_or_invalid"
    assert code.state.clients == 0 and code.state.calls == []


@pytest.mark.parametrize("scope,key,value", [
    ("plan", "autonomous_trading_enabled", False), ("account", "requires_user_confirmation", True),
    ("plan", "mode", "dry_run"), ("account", "mode", "dry_run")])
def test_final_boundary_revalidates_invalid_authorization_snapshots(code, scope, key, value):
    q = direct(code)
    a = q.authorization
    payload = json.loads(a.plan_json if scope == "plan" else a.account_json)
    payload[key] = value
    q.authorization = replace(a, **{scope + "_json": json.dumps(payload)})
    assert buy(q)["status"] == "rejected"
    assert code.state.clients == 0


@pytest.mark.parametrize("key", ["target_total_position_pct", "max_positions", "max_buy_orders_per_day", "max_orders_per_symbol_per_day"])
@pytest.mark.parametrize("value", [0, None])
def test_zero_missing_budget_cannot_buy_via_watcher_or_low_level(code, key, value):
    payload = plan_dict()
    if value is None:
        del payload["risk_limits"][key]
    else:
        payload["risk_limits"][key] = value
    serialize(code, payload)
    code.watcher.run_intraday_once(DATE, mode="live")
    assert not orders(code)
    q = direct(code, payload)
    assert buy(q)["status"] == "rejected"
    assert not orders(code)


@pytest.mark.parametrize("value", [0, None])
def test_missing_zero_stock_budget_does_not_get_schema_positive_default(code, value):
    payload = plan_dict()
    if value is None:
        del payload["execution_pool"][0]["max_position_pct"]
    else:
        payload["execution_pool"][0]["max_position_pct"] = value
    q = direct(code, payload)
    assert buy(q)["status"] == "rejected"
    assert code.state.clients == 0


@pytest.mark.parametrize("gate", ["missing_scan", "not_broken_out", "bad_rr", "watch_pool"])
def test_real_chain_and_direct_buy_gates(code, gate):
    payload = plan_dict()
    if gate == "watch_pool":
        payload["watch_pool"] = payload.pop("execution_pool"); payload["execution_pool"] = []
    if gate == "bad_rr":
        payload["execution_pool"][0]["take_profit"] = 10.5
    serialize(code, payload)
    if gate == "missing_scan": code.state.scan = False
    if gate == "not_broken_out": code.state.last = 9.8
    code.watcher.run_intraday_once(DATE, mode="live")
    assert not orders(code)
    q = direct(code, payload)
    if gate == "missing_scan": code.session.clear_session()
    if gate == "not_broken_out": q.quotes[SYMBOL].last = 9.8
    assert buy(q)["status"] == "rejected"
    assert not orders(code)


@pytest.mark.parametrize("watch", [False, True])
def test_legal_explicit_sell_survives_zero_budget_and_missing_scan(code, watch):
    payload = plan_dict()
    payload["risk_limits"] = {k: 0 if k in code.auth.BUY_CAPS else v for k, v in payload["risk_limits"].items()}
    payload["execution_pool"][0]["auto_trade_enabled"] = False
    if watch:
        payload["watch_pool"] = payload["execution_pool"]; payload["execution_pool"] = []
    serialize(code, payload)
    code.state.holdings = {SYMBOL: dict(ts_code=SYMBOL, total_qty=1000, available_qty=1000, market_value=8000., cost_price=8.)}
    code.state.last = 8.; code.state.bid = 8.; code.state.scan = False
    code.watcher.run_intraday_once(DATE, mode="live")
    assert len(orders(code)) == 1 and orders(code)[0]["side"] == "sell"
    assert code.state.dispatches == 1


@pytest.mark.parametrize("gate", ["kill", "available", "quote", "consent", "exit_rule"])
def test_sell_skips_only_buy_gates_not_final_safety(code, gate):
    q = direct(code)
    q.holdings = {SYMBOL: dict(total_qty=1000, available_qty=100)}
    code.session.clear_session()
    if gate == "kill": (code.root / q.kill_switch_file).write_text("synthetic_only")
    if gate == "available": q.holdings[SYMBOL]["available_qty"] = 0
    if gate == "quote": q.quotes[SYMBOL].bid = None
    if gate == "consent": q.authorization = None
    if gate == "exit_rule": return_value = sell(q, rule_type="take_profit_hit")
    else: return_value = sell(q)
    assert return_value["status"] == "rejected"
    assert code.state.clients == 0


@pytest.mark.parametrize("key,cap,second", [("max_buy_orders_per_day", 1, "daily_buy_order_cap_reached"),
    ("max_orders_per_symbol_per_day", 1, "symbol_buy_order_cap_reached")])
def test_positive_actual_order_counts_survive_new_context(code, key, cap, second):
    payload = plan_dict(); payload["risk_limits"][key] = cap
    q = direct(code, payload)
    assert buy(q)["status"] == "submitted"
    restarted = direct(code, payload)
    assert buy(restarted)["reason"] == second
    assert len(orders(code)) == 1


@pytest.mark.parametrize("capacity,reason", [("total", "total_position_cap_exceeded"),
    ("stock", "stock_position_cap_exceeded"), ("cash", "cash_budget_exceeded"),
    ("positions", "max_positions_reached"), ("rule", "rule_buy_budget_exceeded"),
    ("unknown", "buy_capacity_evidence_invalid")])
def test_actual_positive_capacity_limits(code, capacity, reason):
    payload = plan_dict()
    if capacity == "total": payload["risk_limits"]["target_total_position_pct"] = .005
    if capacity == "stock": payload["execution_pool"][0]["max_position_pct"] = .005
    if capacity == "positions": payload["risk_limits"]["max_positions"] = 1
    q = direct(code, payload)
    if capacity == "cash": q.cash = 500.
    if capacity == "positions": q.holdings = {OTHER: dict(total_qty=100, market_value=1000.)}
    if capacity == "unknown": q.holdings = {OTHER: dict(total_qty=100)}
    result = buy(q, quantity=200 if capacity == "rule" else 100)
    assert result["reason"] == reason
    assert code.state.clients == 0


def test_dry_run_is_not_promotion_or_force_authority(code):
    q = direct(code, mode="dry_run")
    q.dry_run = False
    assert buy(q)["status"] == "rejected"
    assert code.state.clients == 0
    q.dry_run = True
    assert buy(q)["status"] == "dry_run"
    assert code.state.clients == 0
    code.session.clear_session()
    assert buy(q)["status"] == "rejected"


def test_readonly_context_and_actual_after_close_not_misclassified_as_orders(code):
    code.state.holdings = {SYMBOL: dict(ts_code=SYMBOL, total_qty=1000, available_qty=1000, cost_price=8.)}
    out = code.after.run_after_close(DATE)
    assert out["positions_updated"] == [SYMBOL]
    assert code.state.clients == 1
    assert not orders(code)
    assert code.state.contexts[-1].authorization is None


def test_bad_canonical_not_old_loaded_and_restricted_not_promoted(code):
    serialize(code)
    code.loader.run_load_plan(DATE, mode="live", dispatch=False)
    canonical = code.root / f"data/plans/{DATE}/watchlist_plan.json"
    canonical.write_text("{bad")
    with pytest.raises(ValueError): code.watcher.run_intraday_once(DATE, mode="live")
    assert code.state.clients == 0
    canonical.unlink()
    runtime = code.root / f"data/runtime/watchlist_plan_{DATE}.json"
    prior = plan_dict(); prior.update(mode="dry_run", autonomous_trading_enabled=False, requires_user_confirmation=True)
    runtime.write_text(json.dumps(prior))
    serialize(code)
    with pytest.raises(ValueError, match="cannot expand live authorization"):
        code.watcher.run_intraday_once(DATE, mode="live")
    assert code.state.clients == 0


@pytest.mark.parametrize("gate", ["missing_scan", "not_broken_out"])
def test_force_simulate_cannot_add_authority_in_actual_executor(code, gate):
    q = direct(code, mode="dry_run")
    entry = plan_dict()["execution_pool"][0]
    if gate == "missing_scan": code.session.clear_session()
    if gate == "not_broken_out": q.quotes[SYMBOL].last = 9.8
    executor = importlib.import_module("trading.executors._buy_common").run_buy_executor
    result = executor(entry, entry["entry_rules"][0], q, SimpleNamespace(positions={}),
                      expected_type="leader_breakout", simulate=True, force_trigger=True)
    assert result.status == "skipped"
    assert code.state.clients == 0
    assert not q.orders_path.exists()


@pytest.mark.parametrize("gate", ["date", "mode", "kill_path", "unready"])
def test_bound_context_must_match_current_request(code, gate):
    q = direct(code)
    if gate == "date": q.trade_date = "20990106"
    if gate == "mode": q.dry_run = True
    if gate == "kill_path": q.kill_switch_file = "data/runtime/OTHER_KILL"
    if gate == "unready":
        payload = json.loads(q.authorization.plan_json); payload["research_completion_passed"] = False
        q.authorization = replace(q.authorization, plan_json=json.dumps(payload))
    assert buy(q)["status"] == "rejected"
    assert code.state.clients == 0


@pytest.mark.parametrize("capacity", ["stock", "total", "cash"])
def test_accepted_notional_reserves_capacity_across_context_restart(code, capacity):
    payload = plan_dict()
    payload["risk_limits"]["max_orders_per_symbol_per_day"] = 4
    if capacity == "stock": payload["execution_pool"][0]["max_position_pct"] = .01
    if capacity == "total": payload["risk_limits"]["target_total_position_pct"] = .01
    q = direct(code, payload)
    if capacity == "cash": q.cash = 1000.
    assert buy(q)["status"] == "submitted"
    q = direct(code, payload)
    if capacity == "cash": q.cash = 1000.
    assert buy(q)["reason"] == dict(stock="stock_position_cap_exceeded", total="total_position_cap_exceeded", cash="cash_budget_exceeded")[capacity]
    assert len(orders(code)) == 1


def test_modes_and_rejections_do_not_consume_live_order_count(code):
    payload = plan_dict(); payload["risk_limits"]["max_buy_orders_per_day"] = 1
    q = direct(code, payload, mode="dry_run")
    assert buy(q)["status"] == "dry_run"
    live = direct(code, payload)
    assert buy(live, quantity=200)["status"] == "rejected"
    assert buy(live)["status"] == "submitted"
    assert len(orders(code)) == 1


def test_malformed_journal_fails_buy_closed_but_not_explicit_exit(code):
    q = direct(code)
    q.orders_path.write_text("{invalid\n")
    assert buy(q)["reason"] == "buy_capacity_evidence_invalid"
    q.holdings = {SYMBOL: dict(total_qty=1000, available_qty=100)}
    code.session.clear_session()
    assert sell(q)["status"] == "submitted"
    assert len(orders(code)) == 1


@pytest.mark.parametrize("scope", ["plan", "account"])
def test_dry_run_does_not_create_buy_permission(code, scope):
    q = direct(code, mode="dry_run")
    auth = q.authorization
    payload = json.loads(auth.plan_json if scope == "plan" else auth.account_json)
    payload["autonomous_trading_enabled"] = False
    q.authorization = replace(auth, **{scope + "_json": json.dumps(payload)})
    assert buy(q)["reason"] == "plan_account_buy_not_authorized"
    assert code.state.clients == 0


def test_loader_preserves_same_day_real_t_state(code):
    serialize(code)
    store = code.positions.PositionsStateStore.for_mode(trade_date=DATE, dry_run=False)
    store.positions[SYMBOL] = code.positions.PositionState(ts_code=SYMBOL, total_qty=1000,
        t_state=code.positions.TState(date=DATE, t_add_done=True, t_add_qty=100))
    store.save()
    code.loader.run_load_plan(DATE, mode="live")
    store.load()
    assert store.positions[SYMBOL].t_state.t_add_done is True
    assert store.positions[SYMBOL].t_state.t_add_qty == 100
