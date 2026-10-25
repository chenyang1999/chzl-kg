"""S1 boundary regression: copied real loader/watcher/daemon/schema/dispatcher.

Run only with --basetemp under Hermes scratch, --noconftest and no cacheprovider.
QMT, market scanner and rule execution are recording fakes. No real account,
positions DB, credentials, settings module, network or task process is used.
"""
from __future__ import annotations

import ast
import importlib
import importlib.abc
import json
from pathlib import Path
import shutil
import sys
from types import ModuleType, SimpleNamespace

import pydantic
import pytest

REPO = Path(__file__).resolve().parents[1]
SCRATCH = Path.home() / ".hermes/cache/scratch"
DATE = "20990101"
FILES = (
    "trading/load_plan.py", "trading/execution_authorization.py",
    "trading/watcher/run_once.py", "trading/watcher/dispatch.py",
    "trading/watcher/session_context.py", "trading/account_config.py",
    "trading/positions_state.py", "trading/schema/watchlist_plan.py",
    "trading/schema/normalize.py", "src/trading_agent/models.py",
    "src/plan/buy_eligibility.py", "scripts/research/pipeline_artifacts.py",
    "src/execute/watcher_daemon.py",
)


@pytest.fixture(scope="module")
def code(tmp_path_factory, request):
    root = tmp_path_factory.mktemp("s1-code")
    assert root.resolve().is_relative_to(SCRATCH.resolve())
    for rel in FILES:
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / rel, dest)
    for directory in ("src", "src/execute", "src/plan", "src/trading_agent", "scripts",
                      "scripts/research", "trading", "trading/schema", "trading/order",
                      "trading/watcher", "trading/executors"):
        (root / directory).mkdir(parents=True, exist_ok=True)
        (root / directory / "__init__.py").write_text("")
    saved = {k: v for k, v in sys.modules.items() if k.split(".")[0] in ("src", "trading", "scripts")}
    for key in saved:
        del sys.modules[key]
    mp = pytest.MonkeyPatch()
    mp.syspath_prepend(str(root))
    mp.chdir(root)
    violations = []

    def deny(*args, **kwargs):
        violations.append("external dependency called")
        raise AssertionError("real external dependency forbidden")

    class BlockImports(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "src.settings" or "qmt_client" in fullname or fullname.startswith(("dotenv", "ibapi", "ib_insync")):
                violations.append(fullname)
                raise AssertionError("forbidden import: " + fullname)

    blocker = BlockImports()
    sys.meta_path.insert(0, blocker)

    def stub(name, **attrs):
        module = ModuleType(name)
        module.__dict__.update(attrs)
        mp.setitem(sys.modules, name, module)
        return module

    stub("src.settings", ROOT=root, DATA_DIR=root / "data")
    stub("trading.order.qmt_context", QMTContext=deny)
    stub("trading.entry_selector", scan_entry_opportunities=deny)
    stub("src.execute.amygdala", Amygdala=deny)
    stub("src.execute.market_snapshot", build_snapshot=deny)
    stub("src.execute.sector_stats", compute_sector_stats=deny, output_path=deny)
    stub("src.execute.plan_context", load_sector_map=deny)
    # Registry keys are extracted from actual source; rule execution itself is
    # replaced, not tested here (S2 owns the executor predicates and sizing).
    tree = ast.parse((REPO / "trading/executors/registry.py").read_text())
    keys = {}
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and isinstance(node.value, ast.Dict):
            keys[node.target.id] = [ast.literal_eval(k) for k in node.value.keys if k is not None]
    stub("trading.executors.registry", all_entry_types=lambda: keys["ENTRY_EXECUTORS"],
         all_exit_types=lambda: keys["EXIT_EXECUTORS"], get_entry_executor=deny, get_exit_executor=deny)

    def cleanup():
        sys.meta_path.remove(blocker)
        mp.undo()
        for key in list(sys.modules):
            if key.split(".")[0] in ("src", "trading", "scripts"):
                del sys.modules[key]
        sys.modules.update(saved)
    request.addfinalizer(cleanup)
    modules = {name: importlib.import_module(module) for name, module in (
        ("loader", "trading.load_plan"), ("consumer", "trading.watcher.run_once"),
        ("daemon", "src.execute.watcher_daemon"), ("schema", "trading.schema.watchlist_plan"),
        ("auth", "trading.execution_authorization"), ("account", "trading.account_config"),
        ("dispatcher", "trading.watcher.dispatch"), ("positions", "trading.positions_state"))}
    yield SimpleNamespace(root=root, violations=violations, **modules)
    assert not violations, violations


def risk(**changes):
    return {"target_total_position_pct": 0.4, "max_positions": 4,
            "max_buy_orders_per_day": 4, "max_orders_per_symbol_per_day": 2,
            "block_prefixes": [], "block_st": True,
            "kill_switch_file": "data/runtime/KILL_SWITCH", **changes}


def stock(**changes):
    return {"ts_code": "600000.SH", "name": "SYNTHETIC_NOT_REAL", "score": 80,
            "plan_status": "execution_pool_hold_add_on_pullback", "auto_trade_enabled": True,
            "requires_user_confirmation": False, "max_position_pct": 0.1,
            "entry_rules": [{"type": "trend_pullback_buy", "trigger_price": 10.0, "position_pct": 0.1}],
            "exit_rules": [{"type": "stop_loss_break", "trigger_price": 9.0}], **changes}


def raw_plan(**changes):
    return {"schema_version": "watchlist_plan_v1", "trade_date": DATE, "mode": "live",
            "autonomous_trading_enabled": True, "requires_user_confirmation": False,
            "no_trade": False, "execution_pool": [stock()], "watch_pool": [],
            "risk_limits": risk(), **changes}


def account(code, **changes):
    return code.account.AccountConfig(**{
        "mode": "live", "autonomous_trading_enabled": True, "requires_user_confirmation": False,
        "risk_limits": {}, "default_base_mobile_ratio": 0.7,
        "daban_max_symbols_per_day": 2, "daban_default_sealed_bid_threshold": 50000, **changes})


@pytest.fixture()
def sandbox(code, tmp_path, monkeypatch):
    runtime = tmp_path / "data/runtime"
    runtime.mkdir(parents=True)
    calls, orders = [], []
    state = SimpleNamespace(holdings={}, account=account(code), dispatches=0)
    for module in (code.loader, code.consumer, code.daemon):
        monkeypatch.setattr(module, "ROOT", tmp_path)
        monkeypatch.setattr(module, "DATA_DIR", tmp_path / "data")
    for module in (code.loader, code.consumer, code.positions):
        monkeypatch.setattr(module, "RUNTIME_DIR", runtime)
    for module in (code.loader, code.consumer):
        monkeypatch.setattr(module, "load_account_config", lambda: state.account, raising=False)
    monkeypatch.setattr(code.daemon, "Amygdala", lambda: SimpleNamespace(
        check_kill_switch=lambda _: SimpleNamespace(allowed=True)))
    canonical = tmp_path / "data/plans" / DATE / "watchlist_plan.json"
    loaded = runtime / f"watchlist_plan_{DATE}.loaded.json"

    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    class Context:
        def __init__(self, **kw):
            calls.append(("context", kw))
            self.holdings = state.holdings
            self.cash, self.total_asset = 100000.0, 100000.0
            self.quotes = {}
            self.orders_path, self.events_path = runtime / "fake-orders", runtime / "fake-events"
        def refresh_holdings(self, **kw):
            calls.append(("holdings", kw))
        def refresh_quotes(self, symbols):
            calls.append(("quotes", symbols))
        def log_event(self, event):
            calls.append(("event", event))

    def executor(side):
        def run(row, rule, ctx, positions, **kw):
            if side == "sell" and ctx.holdings.get(row["ts_code"], {}).get("available_qty", 0) < 100:
                return SimpleNamespace(status="skipped", ts_code=row["ts_code"], side=side)
            orders.append((side, row["ts_code"], row, rule))
            return SimpleNamespace(status="synthetic_intent", ts_code=row["ts_code"], side=side)
        return run

    def dispatch(*args, **kw):
        state.dispatches += 1
        return code.dispatcher.dispatch_plan(*args, **kw)

    for module in (code.loader, code.consumer):
        monkeypatch.setattr(module, "QMTContext", Context)
        monkeypatch.setattr(module, "dispatch_plan", dispatch)
    monkeypatch.setattr(code.dispatcher, "get_entry_executor", lambda _: executor("buy"))
    monkeypatch.setattr(code.dispatcher, "get_exit_executor", lambda _: executor("sell"))
    monkeypatch.setattr(code.consumer, "scan_entry_opportunities", lambda *a, **kw: {
        "pool_size": len(a[0].execution_pool) + len(a[0].watch_pool), "buy_ready_count": 1,
        "opportunities": [], "errors": []})
    return SimpleNamespace(code=code, runtime=runtime, canonical=canonical, loaded=loaded,
                           write=write, calls=calls, orders=orders, state=state)


@pytest.mark.parametrize("field", ["target_total_position_pct", "max_positions", "max_buy_orders_per_day", "max_orders_per_symbol_per_day"])
@pytest.mark.parametrize("plan_value,account_value,expected", [(0, 1, 0), (1, 0, 0), (0.4, 0.2, 0.2), (0.2, 0.4, 0.2)])
def test_formal_caps_are_intersections(code, field, plan_value, account_value, expected):
    if field != "target_total_position_pct":
        plan_value, account_value, expected = (int(v * 10) for v in (plan_value, account_value, expected))
    p = code.loader.validate_plan_for_date(raw_plan(risk_limits=risk(**{field: plan_value})), DATE)
    result = code.loader.apply_account_overrides(p, account(code, risk_limits={field: account_value}))
    assert getattr(result.risk_limits, field) == expected


def test_restriction_union_and_tighter_stop(code):
    p = code.loader.validate_plan_for_date(raw_plan(risk_limits=risk(
        block_prefixes=["300"], block_st=True, account_hard_stop_loss_pct=0.03)), DATE)
    out = code.loader.apply_account_overrides(p, account(code, risk_limits={
        "block_prefixes": ["688", "300"], "block_st": False, "account_hard_stop_loss_pct": 0.08}))
    assert out.risk_limits.block_prefixes == ["300", "688"]
    assert out.risk_limits.block_st is True
    assert out.risk_limits.account_hard_stop_loss_pct == 0.03


@pytest.mark.parametrize("plan_stop,account_stop", [(0, 0.03), (0.03, 0), (None, 0.03), (0.03, None)])
def test_disabled_optional_stop_cannot_erase_active_stop(code, plan_stop, account_stop):
    out = code.auth.merge_risk_limits({"account_hard_stop_loss_pct": plan_stop},
                                      {"account_hard_stop_loss_pct": account_stop})
    assert out["account_hard_stop_loss_pct"] == 0.03


@pytest.mark.parametrize("bad", [True, "0.5", None, float("nan"), float("inf"), -0.1, 1.1])
@pytest.mark.parametrize("source", ["plan", "account"])
def test_invalid_budget_rejected_before_broker(sandbox, bad, source):
    p = raw_plan()
    if source == "plan":
        p["risk_limits"]["target_total_position_pct"] = bad
    else:
        sandbox.state.account = account(sandbox.code, risk_limits={"target_total_position_pct": bad})
    sandbox.write(sandbox.canonical, p)
    with pytest.raises(ValueError):
        sandbox.code.loader.run_load_plan(DATE)
    assert sandbox.calls == sandbox.orders == []


@pytest.mark.parametrize("value", [True, 1.5, -1, None, "4"])
def test_counts_do_not_coerce(code, value):
    with pytest.raises(ValueError):
        code.auth.merge_risk_limits({"max_positions": value}, {})


@pytest.mark.parametrize("source", ["plan", "account"])
def test_unknown_risk_predicate_is_explicit_refusal(sandbox, source):
    p = raw_plan()
    if source == "plan":
        p["risk_limits"]["unimplemented_risk"] = False
    else:
        sandbox.state.account = account(sandbox.code, risk_limits={"unimplemented_risk": False})
    sandbox.write(sandbox.canonical, p)
    with pytest.raises(ValueError, match="unsupported risk_limits"):
        sandbox.code.loader.run_load_plan(DATE)
    assert sandbox.calls == []


def test_conflicting_kill_paths_cannot_remove_protection(sandbox):
    sandbox.write(sandbox.canonical, raw_plan())
    sandbox.state.account = account(sandbox.code, risk_limits={"kill_switch_file": "different-switch"})
    with pytest.raises(ValueError, match="conflicting"):
        sandbox.code.loader.run_load_plan(DATE)
    assert sandbox.calls == []


@pytest.mark.parametrize("key", ["target_total_position_pct", "max_positions", "max_buy_orders_per_day", "max_orders_per_symbol_per_day"])
def test_missing_plan_budget_stays_missing_despite_positive_account_and_roundtrip(sandbox, key):
    r = risk()
    del r[key]
    sandbox.state.holdings = {"600000.SH": {"total_qty": 1000, "available_qty": 1000}}
    sandbox.write(sandbox.canonical, raw_plan(risk_limits=r))
    sandbox.state.account = account(sandbox.code, risk_limits=risk())
    sandbox.code.loader.run_load_plan(DATE, dispatch=False)
    saved = json.loads(sandbox.loaded.read_text())
    assert key not in saved["risk_limits"]
    assert key + ":missing" in saved["execution_authorization"]["buy_budget_blockers"]
    sandbox.code.consumer.run_intraday_once(DATE)
    assert not any(side == "buy" for side, *_ in sandbox.orders)
    assert any(side == "sell" for side, *_ in sandbox.orders)


@pytest.mark.parametrize("restriction", [
    {"mode": "dry_run"}, {"autonomous_trading_enabled": False}, {"requires_user_confirmation": True}])
@pytest.mark.parametrize("source", ["plan", "account"])
@pytest.mark.parametrize("reload", [False, True])
def test_live_request_never_supplies_consent(sandbox, source, restriction, reload):
    p = raw_plan(**(restriction if source == "plan" else {}))
    if source == "account":
        sandbox.state.account = account(sandbox.code, **restriction)
    sandbox.write(sandbox.canonical if reload else sandbox.loaded, p)
    with pytest.raises(ValueError, match="live"):
        sandbox.code.consumer.run_intraday_once(DATE, mode="live", reload=reload)
    assert sandbox.calls == sandbox.orders == []


@pytest.mark.parametrize("mode", ["other", "", 1])
def test_invalid_runtime_mode_cannot_mean_live(sandbox, mode):
    sandbox.write(sandbox.loaded, raw_plan())
    with pytest.raises(ValueError):
        sandbox.code.consumer.run_intraday_once(DATE, mode=mode)
    assert sandbox.calls == []


@pytest.mark.parametrize("reload", [False, True])
@pytest.mark.parametrize("mode", [None, "live", "dry_run"])
def test_authorized_positive_schema_roundtrip_dispatches_once(sandbox, reload, mode):
    # Exercise the actual schema serialization used by producers, not only a
    # hand-written narrow dict. Preserve all optional/default model fields.
    p = sandbox.code.schema.WatchlistPlan.model_validate(raw_plan()).model_dump(mode="json")
    sandbox.state.holdings = {"600000.SH": {"total_qty": 1000, "available_qty": 1000}}
    sandbox.write(sandbox.canonical if reload else sandbox.loaded, p)
    result = sandbox.code.consumer.run_intraday_once(DATE, mode=mode, reload=reload)
    assert result["ok"]
    assert sandbox.state.dispatches == 1
    assert [row[0] for row in sandbox.orders] == ["sell", "buy"]
    contexts = [row[1] for row in sandbox.calls if row[0] == "context"]
    assert len(contexts) == 1
    assert contexts[0]["dry_run"] is (mode == "dry_run")


@pytest.mark.parametrize("restriction", [{"auto_trade_enabled": False}, {"requires_user_confirmation": True}])
def test_stock_consent_cannot_be_granted_by_holdings_or_global_flags(sandbox, restriction):
    p = raw_plan(execution_pool=[stock(**restriction)])
    sandbox.state.holdings = {"600000.SH": {"total_qty": 1000, "available_qty": 1000}}
    sandbox.write(sandbox.canonical, p)
    sandbox.code.loader.run_load_plan(DATE)
    assert [row[0] for row in sandbox.orders] == ["sell"]
    saved = json.loads(sandbox.loaded.read_text())
    assert saved["execution_pool"][0]["auto_trade_enabled"] is False


@pytest.mark.parametrize("cap", ["target_total_position_pct", "max_positions", "max_buy_orders_per_day", "max_orders_per_symbol_per_day"])
@pytest.mark.parametrize("pool", ["execution_pool", "watch_pool"])
def test_zero_new_buy_budget_preserves_legal_exit_and_watch(sandbox, cap, pool):
    row = stock()
    p = raw_plan(risk_limits=risk(**{cap: 0}), execution_pool=[], watch_pool=[])
    p[pool] = [row]
    sandbox.state.holdings = {row["ts_code"]: {"total_qty": 1000, "available_qty": 1000}}
    sandbox.write(sandbox.canonical, p)
    sandbox.code.consumer.run_intraday_once(DATE, mode="live", reload=True)
    assert [row[0] for row in sandbox.orders] == ["sell"]
    assert sandbox.state.dispatches == 1
    manifest = json.loads((sandbox.runtime / f"intraday_manifest_{DATE}.json").read_text())
    if pool == "watch_pool":
        assert manifest["watch_started"] == [row["ts_code"]]


@pytest.mark.parametrize("pool", ["execution_pool", "watch_pool"])
def test_symbol_buy_compliance_does_not_erase_held_exit(sandbox, pool):
    p = raw_plan(risk_limits=risk(block_prefixes=["300"]), execution_pool=[], watch_pool=[])
    p[pool] = [stock(ts_code="300001.SZ")]
    sandbox.state.holdings = {"300001.SZ": {"total_qty": 1000, "available_qty": 1000}}
    sandbox.write(sandbox.canonical, p)
    sandbox.code.consumer.run_intraday_once(DATE, reload=True)
    assert [row[0] for row in sandbox.orders] == ["sell"]
    assert sandbox.orders[0][2]["entry_rules"] == []


def test_unheld_watch_row_never_becomes_execution_permission(sandbox):
    sandbox.write(sandbox.canonical, raw_plan(execution_pool=[], watch_pool=[stock()]))
    sandbox.code.consumer.run_intraday_once(DATE, reload=True)
    assert sandbox.orders == []


def test_no_trade_preserves_research_and_exit_without_live_upgrade(sandbox):
    sandbox.state.holdings = {"600000.SH": {"total_qty": 1000, "available_qty": 1000}}
    sandbox.write(sandbox.canonical, raw_plan(mode="dry_run", no_trade=True))
    result = sandbox.code.consumer.run_intraday_once(DATE, reload=True)
    assert result["candidate_pool_size"] == 1
    assert [row[0] for row in sandbox.orders] == ["sell"]
    assert [kw for kind, kw in sandbox.calls if kind == "context"][0]["dry_run"] is True


def test_preparation_has_no_broker_positions_or_dispatch_effects(sandbox):
    sandbox.write(sandbox.canonical, raw_plan())
    result = sandbox.code.loader.run_load_plan(DATE, dispatch=False)
    assert result["dispatched"] is False
    assert sandbox.calls == sandbox.orders == []
    assert sandbox.state.dispatches == 0
    assert sandbox.loaded.is_file()
    assert not list(sandbox.runtime.glob("*positions*"))
    assert not list(sandbox.runtime.glob("pipeline_state*"))


def test_legacy_loader_default_still_dispatches_exactly_once(sandbox):
    sandbox.write(sandbox.canonical, raw_plan())
    result = sandbox.code.loader.run_load_plan(DATE)
    assert result["dispatched"] is True
    assert sandbox.state.dispatches == 1
    assert result["dispatch"].entry_results and result["dispatch"].exit_results


def test_daemon_two_passes_have_two_total_dispatches_and_refresh_source(sandbox, monkeypatch):
    sandbox.write(sandbox.canonical, raw_plan(generated_at="first"))
    def sleep(_):
        sandbox.write(sandbox.canonical, raw_plan(generated_at="second"))
    monkeypatch.setattr(sandbox.code.daemon.time, "sleep", sleep)
    assert sandbox.code.daemon.run_loop(DATE, mode="live", outside_session=True, max_passes=2) == 0
    assert sandbox.state.dispatches == 2
    assert len([c for c in sandbox.calls if c[0] == "context"]) == 2
    assert json.loads(sandbox.loaded.read_text())["generated_at"] == "second"


def test_daemon_invalid_new_source_never_executes_old_loaded(sandbox):
    sandbox.write(sandbox.loaded, raw_plan())
    sandbox.write(sandbox.canonical, raw_plan(trade_date="20990102"))
    assert sandbox.code.daemon.run_loop(DATE, once=True, mode="live") == 1
    assert sandbox.state.dispatches == 0
    assert sandbox.calls == []


def test_direct_watcher_canonical_zero_outranks_old_positive_loaded(sandbox):
    sandbox.state.holdings = {"600000.SH": {"total_qty": 1000, "available_qty": 1000}}
    sandbox.write(sandbox.loaded, raw_plan())
    sandbox.write(sandbox.canonical, raw_plan(risk_limits=risk(target_total_position_pct=0)))
    sandbox.code.consumer.run_intraday_once(DATE, mode="live", reload=False)
    assert [row[0] for row in sandbox.orders] == ["sell"]
    assert json.loads(sandbox.loaded.read_text())["risk_limits"]["target_total_position_pct"] == 0


def test_direct_watcher_canonical_dry_cannot_borrow_stale_loaded_live(sandbox):
    sandbox.write(sandbox.loaded, raw_plan())
    sandbox.write(sandbox.canonical, raw_plan(mode="dry_run"))
    with pytest.raises(ValueError, match="live"):
        sandbox.code.consumer.run_intraday_once(DATE, mode="live", reload=False)
    assert sandbox.calls == []


def test_same_day_loader_does_not_reset_t_state(sandbox):
    code = sandbox.code
    store = code.positions.PositionsStateStore.for_mode(trade_date=DATE, dry_run=False)
    store.positions["600000.SH"] = code.positions.PositionState(
        ts_code="600000.SH", t_state=code.positions.TState(date=DATE, t_add_done=True, t_add_qty=100))
    store.save()
    sandbox.write(sandbox.canonical, raw_plan())
    code.loader.run_load_plan(DATE)
    store.load()
    assert store.positions["600000.SH"].t_state.t_add_done
    assert store.positions["600000.SH"].t_state.t_add_qty == 100


@pytest.mark.parametrize("flag,value", [("autonomous_trading_enabled", "false"),
    ("autonomous_trading_enabled", 1), ("requires_user_confirmation", "false")])
def test_raw_account_consent_not_truthiness_coerced(code, tmp_path, monkeypatch, flag, value):
    p = tmp_path / "synthetic-account.yaml"
    raw = {"mode": "live", "autonomous_trading_enabled": True, "requires_user_confirmation": False,
           "risk_limits": {}}
    raw[flag] = value
    p.write_text(json.dumps(raw))
    monkeypatch.setattr(code.loader, "DEFAULT_CONFIG_PATH", p, raising=False)
    monkeypatch.setattr(code.account, "DEFAULT_CONFIG_PATH", p)
    with pytest.raises(ValueError, match="explicit boolean"):
        code.loader.load_account_config()


def test_valid_raw_account_config_is_accepted(code, tmp_path, monkeypatch):
    p = tmp_path / "synthetic-account.yaml"
    p.write_text(json.dumps({"mode": "live", "autonomous_trading_enabled": True,
        "requires_user_confirmation": False, "risk_limits": risk()}))
    monkeypatch.setattr(code.loader, "DEFAULT_CONFIG_PATH", p, raising=False)
    monkeypatch.setattr(code.account, "DEFAULT_CONFIG_PATH", p)
    cfg = code.loader.load_account_config()
    assert cfg.mode == "live" and cfg.autonomous_trading_enabled is True
    assert cfg.risk_limits == risk()
