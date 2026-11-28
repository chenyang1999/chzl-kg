"""S3 safety regression: copied source, synthetic evidence, no broker/accounts.

Run this file alone with -B, PYTEST_DISABLE_PLUGIN_AUTOLOAD=1, --noconftest,
-p no:cacheprovider and --basetemp beneath Hermes scratch. It deliberately
imports no project modules during collection. Fixture stubs replace settings,
collectors, broker construction, account state and journal IO before imports.
Order observations below are synthetic intents, never fills.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from decimal import Decimal, InvalidOperation
import builtins
import importlib
import importlib.abc
import importlib.util
import io
import json
from math import floor, isfinite
from numbers import Real
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pydantic
import pytest

REPO = Path(__file__).resolve().parents[1]
SCRATCH = Path.home() / ".hermes/cache/scratch"
SYMBOL = "600000.SH"
OTHER = "600001.SH"
DATE = "20990105"
SOURCES = [
    "trading/entry_selector.py", "trading/watcher/session_context.py",
    "trading/executors/base.py", "trading/executors/_buy_common.py",
    "trading/order/qmt_context.py", "trading/executors/_sell_common.py",
    "trading/schema/watchlist_plan.py", "src/plan/buy_eligibility.py",
    "trading/execution_authorization.py", "src/trading_agent/models.py", "src/trading_agent/journal.py",
    "trading/watcher/dispatch.py", "trading/executors/registry.py",
] + [f"trading/executors/execute_{kind}.py" for kind in (
    "leader_breakout", "daban_confirm", "trend_pullback_buy", "low_absorption_intraday", "t_add_pullback",
    "exit_at_open", "exit_if_no_new_high", "intraday_break_exit", "sector_switch_exit", "stop_loss_break",
    "t_reduce_resistance", "take_profit_hit", "volume_price_divergence")]


@pytest.fixture(scope="module")
def code(tmp_path_factory, request):
    root = tmp_path_factory.mktemp("s3-code")
    assert root.resolve().is_relative_to(SCRATCH.resolve()), "use a scratch --basetemp"
    for rel in SOURCES:
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / rel, dest)
    saved = {k: v for k, v in sys.modules.items() if k.split(".")[0] in {"src", "trading"}}
    for key in saved:
        del sys.modules[key]
    mp = pytest.MonkeyPatch()
    mp.delenv("CHZL_JUDGMENT_NODE", raising=False)
    mp.syspath_prepend(str(root))
    mp.chdir(root)
    violations = []
    journal = []

    def deny(*args, **kwargs):
        violations.append("external_effect")
        raise AssertionError("broker/network/process/database forbidden")

    def module(name, **values):
        m = ModuleType(name)
        m.__dict__.update(values)
        mp.setitem(sys.modules, name, m)
        return m

    for package in ("src", "src.plan", "src.execute", "src.trading_agent", "trading",
                    "trading.schema", "trading.order", "trading.executors", "trading.watcher"):
        module(package, __path__=[str(root / package.replace(".", "/"))])
    module("src.settings", ROOT=root, DATA_DIR=root / "data")
    (root / "data/runtime").mkdir(parents=True)
    module("src.trading_agent.qmt_client", QMTMCPClient=type("ForbiddenClient", (), {"__init__": deny}))
    # Pure real model predicates are now needed by final bound authorization.
    # Settings and transport remain synthetic; no authorization function is mocked.
    importlib.import_module("src.trading_agent.models")
    module("src.trading_agent.journal", append_jsonl=lambda path, row: journal.append((path, deepcopy(row))))

    class FixtureAmygdala:
        def check_buy_order(self, **kw):
            return SimpleNamespace(allowed=True, reason="fixture_only", code="fixture_only")

        def check_sell_order(self, **kw):
            return SimpleNamespace(allowed=0 < kw["quantity"] <= kw["available_qty"],
                                   reason="fixture_sell_availability", code="fixture_only")

    module("src.execute.amygdala", Amygdala=FixtureAmygdala)
    module("trading.positions_state", PositionState=object, PositionsStateStore=object)
    candidate = module("trading.candidate_pool", Candidate=SimpleNamespace,
                       build_candidate_pool=deny, save_candidate_pool=deny)
    daily = module("trading.daily_levels", candles_from_xtick_rows=deny, compute_daily_levels=deny)
    pattern = module("trading.intraday_pattern", analyze_intraday_pattern=deny, fetch_xtick_minute_bars=deny)
    sise = module("trading.sise_filter", evaluate_sise_gate=deny)

    class BlockImports(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if (fullname == "src.settings" or fullname.startswith(("src.collectors", "dotenv", "ibapi", "ib_insync"))
                    or "qmt_client" in fullname):
                violations.append("forbidden_import:" + fullname)
                raise AssertionError("unexpected real dependency: " + fullname)

    blocker = BlockImports()
    sys.meta_path.insert(0, blocker)
    mp.setattr(socket, "create_connection", deny)
    mp.setattr(socket.socket, "connect", deny)
    mp.setattr(subprocess, "Popen", deny)
    mp.setattr(sqlite3, "connect", deny)
    for container in (builtins, io):
        original = container.open

        def guarded(file, mode="r", *args, _original=original, **kwargs):
            if not isinstance(file, int):
                path = Path(file).resolve()
                write = any(c in mode for c in "wax+")
                production = path.is_relative_to(REPO.resolve()) and not path.is_relative_to(root)
                library = path.is_relative_to(Path(sys.prefix).resolve()) and not write
                if path.name.startswith(".env") or "credentials" in str(path).lower() or (production and not library):
                    violations.append("forbidden_file:" + str(path))
                    raise AssertionError("production/credential access forbidden")
                if write and not path.is_relative_to(root):
                    violations.append("out_of_fixture_write:" + str(path))
                    raise AssertionError("write outside isolated module fixture")
            return _original(file, mode, *args, **kwargs)
        mp.setattr(container, "open", guarded)

    def cleanup():
        sys.meta_path.remove(blocker)
        mp.undo()
        for key in list(sys.modules):
            if key.split(".")[0] in {"src", "trading"}:
                del sys.modules[key]
        sys.modules.update(saved)
    request.addfinalizer(cleanup)
    qmt = importlib.import_module("trading.order.qmt_context")
    base = importlib.import_module("trading.executors.base")
    buy = importlib.import_module("trading.executors._buy_common")
    sell = importlib.import_module("trading.executors._sell_common")
    session = importlib.import_module("trading.watcher.session_context")
    selector = importlib.import_module("trading.entry_selector")
    schema = importlib.import_module("trading.schema.watchlist_plan")
    dispatch = importlib.import_module("trading.watcher.dispatch")
    registry = importlib.import_module("trading.executors.registry")
    yield SimpleNamespace(root=root, qmt=qmt, base=base, buy=buy, sell=sell, session=session,
                          selector=selector, schema=schema, journal=journal, dispatch=dispatch, registry=registry)
    assert not violations, violations


@pytest.fixture(autouse=True)
def reset_session(code):
    code.session.clear_session()
    code.journal.clear()
    yield
    code.session.clear_session()


def stock(kind="leader_breakout"):
    return {"ts_code": SYMBOL, "name": "SYNTHETIC_ONLY", "score": 90,
            "auto_trade_enabled": True, "requires_user_confirmation": False,
            "plan_status": "execution_pool_hold_add_on_pullback",
            "max_position_pct": .2, "stop_loss": 9., "take_profit": 14.,
            "entry_rules": [{"type": kind, "trigger_price": 10., "max_acceptable_ask": 10.3,
                             "position_pct": .1}]}


def fixture_authorization(code, stocks):
    """Explicit synthetic plan/account consent, not an order-gate override.

    Keep each stock's rule/zero/invalid quote/scan inputs unchanged. This supplies
    only the missing I1 binding contract; final authorization remains real.
    """
    plan = code.schema.WatchlistPlan.model_validate({
        "trade_date": DATE, "mode": "dry_run", "autonomous_trading_enabled": True,
        "requires_user_confirmation": False, "execution_pool": stocks,
        "risk_limits": {"target_total_position_pct": .4, "max_positions": 4,
                        "max_buy_orders_per_day": 4, "max_orders_per_symbol_per_day": 2,
                        "block_prefixes": [], "block_st": True,
                        "kill_switch_file": "unused_synthetic_kill"}})
    account = SimpleNamespace(mode="dry_run", autonomous_trading_enabled=True,
                              requires_user_confirmation=False, risk_limits={})
    auth = importlib.import_module("trading.execution_authorization")
    return auth.bind_execution_authorization(plan, account, effective_mode="dry_run")


def ctx(code, *, cash=100000., last=10., ask=10., holdings=None):
    # Direct dispatcher tests supply all five supported types with the same
    # explicit 10.0 cap. Executor tests below bind their exact supplied stock.
    s = stock()
    s["entry_rules"] = [{**stock(kind)["entry_rules"][0], "max_acceptable_ask": 10.}
                        for kind in ("leader_breakout", "daban_confirm", "trend_pullback_buy",
                                     "low_absorption_intraday", "t_add_pullback")]
    s["exit_rules"] = [{"type": "stop_loss_break", "trigger_price": 9., "quantity_pct": 1.}]
    q = code.qmt.QMTContext(DATE, True, "unused_synthetic_kill", runtime_dir=code.root / "data/runtime",
                            authorization=fixture_authorization(code, [s]))
    q.total_asset = 100000.
    q.cash = cash
    q.holdings = deepcopy(holdings) if holdings is not None else {}
    for row in q.holdings.values():
        # Only fill a previously absent valuation; retain anomalous quantities.
        if "market_value" not in row and type(row.get("total_qty")) in (int, float):
            row["market_value"] = row["total_qty"] * 10.
    q.quotes = {SYMBOL: SimpleNamespace(last=last, ask=ask, bid=9.9),
                OTHER: SimpleNamespace(last=100., ask=100., bid=99.)}
    return q


def scan(code, *, action="buy_breakout", sise=True):
    code.session.set_scan_result({"trade_date": DATE, "opportunities": [
        {"ts_code": SYMBOL, "action": action, "sise_pass": sise, "reasons": ["synthetic_confirmed"]}]})


def execute(code, q, s=None, **flags):
    s = s or stock()
    q.authorization = fixture_authorization(code, [s])
    return code.buy.run_buy_executor(s, s["entry_rules"][0], q, SimpleNamespace(positions={}),
                                     expected_type=s["entry_rules"][0]["type"], **flags)


def test_missing_scan_is_not_permission(code):
    q = ctx(code)
    result = execute(code, q)
    assert result.skip_reason == "intraday_scan_gate"
    assert code.journal == []


@pytest.mark.parametrize("flags", [{}, {"simulate": True}, {"simulate": True, "force_trigger": True}])
def test_scan_exception_fails_closed_even_simulation(code, monkeypatch, flags):
    def failed(*a, **kw):
        raise ValueError("synthetic_scanner_failure")
    monkeypatch.setattr(code.session, "buy_allowed", failed)
    result = execute(code, ctx(code), **flags)
    assert result.skip_reason == "intraday_scan_gate"
    assert "scan_evidence_unavailable" in result.reasons
    assert code.journal == []


@pytest.mark.parametrize("replacement", [{}, {"opportunities": []}, {"opportunities": None},
                                          {"errors": [{"ts_code": SYMBOL, "error": "fixture"}]}])
def test_scan_replacement_does_not_keep_old_success(code, replacement):
    scan(code)
    assert code.session.buy_allowed(SYMBOL, entry_style="leader_breakout", trade_date=DATE)[0]
    code.session.set_scan_result(replacement)
    assert not code.session.buy_allowed(SYMBOL, entry_style="leader_breakout", trade_date=DATE)[0]


@pytest.mark.parametrize("sise", [False, None, 1, "true"])
def test_scan_sise_requires_explicit_true(code, sise):
    scan(code, sise=sise)
    assert not code.session.buy_allowed(SYMBOL, entry_style="leader_breakout", trade_date=DATE)[0]


@pytest.mark.parametrize("style,action,expected", [
    ("low_absorption_intraday", "buy_pullback", True), ("trend_pullback_buy", "buy_pullback", True),
    ("leader_breakout", "buy_breakout", True), ("daban_confirm", "buy_breakout", True),
    ("leader_breakout", "buy_pullback", False), ("pullback", "buy_breakout", False),
    ("pullback", "buy_magic", False), ("future_unknown", "buy_breakout", False),
    ("leader_breakout", "watch", False), ("leader_breakout", "skip", False)])
def test_scan_only_known_matched_signal_passes(code, style, action, expected):
    scan(code, action=action)
    assert code.session.buy_allowed(SYMBOL, entry_style=style, trade_date=DATE)[0] is expected


def test_scan_errors_are_local_and_duplicate_evidence_rejected(code):
    good = {"ts_code": OTHER, "action": "buy_breakout", "sise_pass": True}
    bad = {**good, "ts_code": SYMBOL}
    code.session.set_scan_result({"trade_date": DATE, "opportunities": [bad, good], "errors": [{"ts_code": SYMBOL}]})
    assert not code.session.buy_allowed(SYMBOL, entry_style="leader_breakout", trade_date=DATE)[0]
    assert code.session.buy_allowed(OTHER, entry_style="leader_breakout", trade_date=DATE)[0]
    code.session.set_scan_result({"trade_date": DATE, "opportunities": [good, good, good]})
    assert not code.session.buy_allowed(OTHER, entry_style="leader_breakout", trade_date=DATE)[0]


@pytest.mark.parametrize("last,ask,confirm,expected", [
    (9.8, 9.9, None, False), (10., 10., None, True), (10.1, 10.2, 10.2, False),
    (10.2, 10.2, 10.2, True), (10.3, 10.31, None, False), (10.3, 10.3, None, True)])
def test_breakout_reaches_trigger_and_confirm_with_ask_cap(code, last, ask, confirm, expected):
    rule = stock()["entry_rules"][0]
    rule["confirm_price"] = confirm
    ok, _ = code.base.evaluate_buy_trigger(rule=rule, quote_last=last, quote_ask=ask)
    assert ok is expected


@pytest.mark.parametrize("key,value", [("trigger_price", 0), ("trigger_price", True),
    ("confirm_price", float("nan")), ("max_acceptable_ask", 0), ("max_acceptable_ask", False),
    ("max_acceptable_ask", float("inf")), ("trigger_price", "10")])
def test_trigger_invalid_numeric_is_not_defaulted(code, key, value):
    rule = stock()["entry_rules"][0]
    rule[key] = value
    assert not code.base.evaluate_buy_trigger(rule=rule, quote_last=10., quote_ask=10.)[0]


@pytest.mark.parametrize("key,value", [("sealed_bid_threshold", 0), ("only_first_seal", False),
    ("max_break_count_today", 1), ("unknown_predicate", {}), ("confirmation_conditions", []),
    ("time_window", "09:30-10:00"), ("t_round_limit", 1), ("max_premium_pct", .01)])
def test_active_complex_predicate_explicitly_unsupported(code, key, value):
    rule = stock()["entry_rules"][0]
    rule[key] = value
    ok, reasons = code.base.evaluate_buy_trigger(rule=rule, quote_last=10., quote_ask=10.)
    assert not ok
    assert "unsupported" in " ".join(reasons)


@pytest.mark.parametrize("kind", ["leader_breakout", "trend_pullback_buy", "low_absorption_intraday", "t_add_pullback"])
def test_full_schema_normal_positive_buy_intent_chain(code, kind):
    s = stock(kind)
    s["entry_rules"][0]["max_acceptable_ask"] = 10.
    # A real model dump contributes null inactive constraints and max_premium=0.
    plan = code.schema.WatchlistPlan.model_validate({"trade_date": DATE, "execution_pool": [s]})
    payload = json.loads(plan.model_dump_json())
    s = payload["execution_pool"][0]
    scan(code, action="buy_breakout" if kind == "leader_breakout" else "buy_pullback")
    q = ctx(code)
    result = execute(code, q, s)
    assert result.status == "dry_run"
    assert result.quantity == 1000
    assert result.limit_price == 10.
    orders = [r for path, r in code.journal if path == q.orders_path]
    assert len(orders) == 1
    assert orders[0]["quantity"] == 1000
    assert orders[0]["status"] == "dry_run"
    assert orders[0]["order_id"] is None  # intent, NOT a fill


@pytest.mark.parametrize("kind", ["leader_breakout", "daban_confirm", "trend_pullback_buy",
                                    "low_absorption_intraday", "t_add_pullback"])
def test_serialized_plan_through_real_dispatch_registry_to_valid_intent(code, kind):
    s = stock(kind)
    s["entry_rules"][0]["max_acceptable_ask"] = 10.
    plan = code.schema.WatchlistPlan.model_validate({"trade_date": DATE, "execution_pool": [s],
                                                   "risk_limits": {"target_total_position_pct": .5}})
    plan = code.schema.WatchlistPlan.model_validate_json(plan.model_dump_json())
    scan(code, action="buy_breakout" if kind in {"leader_breakout", "daban_confirm"} else "buy_pullback")
    q = ctx(code, holdings={SYMBOL: {"total_qty": 100}} if kind == "t_add_pullback" else None)
    report = code.dispatch.dispatch_plan(plan, q, SimpleNamespace(positions={}))
    assert len(report.entry_results) == 1
    assert report.entry_results[0]["status"] == "dry_run"
    assert report.entry_results[0]["quantity"] == 1000
    assert not report.skipped


def test_dispatch_preserves_legal_sell_with_missing_scan(code):
    s = stock()
    s["exit_rules"] = [{"type": "stop_loss_break", "trigger_price": 9., "quantity_pct": 1.}]
    plan = code.schema.WatchlistPlan.model_validate({"trade_date": DATE, "execution_pool": [s]})
    q = ctx(code, last=8.9, ask=9., holdings={SYMBOL: {"total_qty": 1000, "available_qty": 1000}})
    q.quotes[SYMBOL].bid = 8.89
    report = code.dispatch.dispatch_plan(plan, q, SimpleNamespace(positions={}))
    assert report.exit_results[0]["status"] == "dry_run"
    assert report.exit_results[0]["quantity"] == 1000
    assert report.entry_results[0]["status"] == "skipped"
    assert report.entry_results[0]["skip_reason"] == "intraday_scan_gate"


def test_buy_zone_normal_reclaim_is_not_globally_blocked(code):
    s = stock("trend_pullback_buy")
    s["entry_rules"][0].update(trigger_price=9.8, buy_zone=[9.8, 10.2], confirm_price=10.)
    scan(code, action="buy_pullback")
    assert execute(code, ctx(code, last=10.1, ask=10.1), s).status == "dry_run"
    assert execute(code, ctx(code, last=9.9, ask=10.1), s).skip_reason == "trigger_not_met"
    assert execute(code, ctx(code, last=10.1, ask=9.7), s).skip_reason == "trigger_not_met"


def test_submitted_intent_uses_exact_proposed_limit_for_sizing(code):
    scan(code)
    q = ctx(code, last=10.1, ask=10.1)
    q.quotes[OTHER].last = 9999.
    result = execute(code, q)
    assert result.limit_price == 10.3  # Existing explicit submitted-limit contract.
    assert result.quantity == 900
    s = stock()
    s["entry_rules"][0]["max_acceptable_ask"] = None
    assert execute(code, q, s).limit_price == 10.1


@pytest.mark.parametrize("ask", [None, 0, True, float("nan"), float("inf")])
def test_missing_ask_never_uses_last_or_plan_cap(code, ask):
    scan(code)
    q = ctx(code, ask=ask)
    result = execute(code, q)
    assert result.status == "skipped"
    assert not code.journal


@pytest.mark.parametrize("field,value", [("cash", None), ("cash", 0), ("cash", 999.),
    ("cash", True), ("cash", float("nan")), ("total_asset", 0), ("total_asset", float("inf")),
    ("position_pct", 0), ("position_pct", False), ("position_pct", float("nan")),
    ("position_pct", .001), ("limit_price", 0), ("limit_price", True),
    ("max_position_pct", 0), ("max_position_pct", .001)])
def test_insufficient_or_invalid_buy_budget_has_no_minimum_lot(code, field, value):
    q = ctx(code)
    args = dict(ts_code=SYMBOL, limit_price=10., position_pct=.1, max_position_pct=.2)
    if field in ("cash", "total_asset"):
        setattr(q, field, value)
    else:
        args[field] = value
    assert code.base.compute_buy_qty(q, **args) == 0


def test_sizing_is_bound_to_target_symbol_cash_and_remaining_position_room(code):
    q = ctx(code, cash=3500.)
    assert code.base.compute_buy_qty(q, ts_code=SYMBOL, limit_price=10., position_pct=.1) == 300
    q.cash = 100000.
    q.holdings = {SYMBOL: {"total_qty": 1950}, OTHER: {"total_qty": 9999}}
    assert code.base.compute_buy_qty(q, ts_code=SYMBOL, limit_price=10., position_pct=.1, max_position_pct=.2) == 0
    q.holdings[SYMBOL]["total_qty"] = 1800
    assert code.base.compute_buy_qty(q, ts_code=SYMBOL, limit_price=10., position_pct=.1, max_position_pct=.2) == 200
    assert code.base.compute_buy_qty(q, ts_code="missing", limit_price=10., position_pct=.1) == 0


def test_executor_zero_quantity_never_calls_order_boundary(code):
    scan(code)
    assert execute(code, ctx(code, cash=999.)).skip_reason == "zero_buy_qty"
    assert not code.journal


@pytest.mark.parametrize("value,expected", [(None, 0), (0, 0), (0., 0), ("0", 0),
    (True, 0), (False, 0), (float("nan"), 0), (float("inf"), 0), (-1, 0), (1.5, 0),
    ("bad", 0), ([], 0), ("NaN", 0), ("1.5", 0), (1000, 1000), (1000., 1000), ("1000", 1000)])
def test_available_qty_never_uses_total_and_rejects_bool_nan(code, value, expected):
    q = ctx(code, holdings={SYMBOL: {"total_qty": 9999, "available_qty": value}})
    assert q.available_qty(SYMBOL) == expected


def test_missing_available_qty_returns_zero(code):
    assert ctx(code, holdings={SYMBOL: {"total_qty": 1000}}).available_qty(SYMBOL) == 0


@pytest.mark.parametrize("dry_run", [True, False])
def test_quote_refresh_does_not_invent_book_from_holdings(code, dry_run):
    q = ctx(code, holdings={SYMBOL: {"total_qty": 1000, "last_price": 10.}})
    q.dry_run = dry_run
    if dry_run:
        del q.quotes[SYMBOL]  # No explicitly supplied book: do not invent one.
    class FailedClient:
        def get_quotes(self, symbols):
            raise ValueError("synthetic_quote_failure")
    q._client = FailedClient()
    q.refresh_quotes([SYMBOL])
    assert SYMBOL not in q.quotes
    assert OTHER in q.quotes


def test_valid_quote_refresh_preserves_explicit_book(code):
    q = ctx(code)
    q.dry_run = False
    book = SimpleNamespace(last=10., ask=10.01, bid=9.99)
    q._client = SimpleNamespace(get_quotes=lambda symbols: {SYMBOL: book})
    q.refresh_quotes([SYMBOL])
    assert q.quotes[SYMBOL] is book


@pytest.mark.parametrize("flags", [{}, {"simulate": True}, {"simulate": True, "force_trigger": True}])
def test_confirmed_scan_cannot_bypass_missing_breakout_even_with_force(code, flags):
    scan(code)
    result = execute(code, ctx(code, last=9.8, ask=9.9), **flags)
    assert result.skip_reason == "trigger_not_met"
    assert not code.journal


@pytest.mark.parametrize("value", [None, 0, False, float("nan")])
def test_unknown_or_zero_available_qty_cannot_generate_sell_intent(code, value):
    q = ctx(code, last=8.9, ask=9., holdings={SYMBOL: {"total_qty": 1000, "available_qty": value}})
    q.quotes[SYMBOL].bid = 8.89
    result = code.sell.run_sell_executor(stock(), {"type": "stop_loss_break", "trigger_price": 9.,
        "quantity_pct": 1.}, q, SimpleNamespace(positions={}), expected_type="stop_loss_break")
    assert result.skip_reason == "zero_sell_qty"
    assert not code.journal


@pytest.mark.parametrize("side", ["buy", "sell"])
@pytest.mark.parametrize("book", [None, 0, True, float("nan"), float("inf")])
def test_final_context_refuses_missing_or_invalid_executable_book(code, monkeypatch, side, book):
    q = ctx(code, holdings={SYMBOL: {"total_qty": 1000, "available_qty": 1000}})
    scan(code)
    # Keep the original ten case identities, but use the plan's real rules.
    # Authorization is not patched: invalid ask fails its buy trigger first;
    # sell passes its independent exit permission before the final bid check.
    spec = importlib.util.spec_from_file_location("s3_real_journal", code.root / "src/trading_agent/journal.py")
    assert spec is not None and spec.loader is not None
    real_journal = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(real_journal)
    monkeypatch.setattr(code.qmt, "append_jsonl", real_journal.append_jsonl)
    q.runtime_dir = code.root / "book-refusal" / side / str(book)
    client_calls = []
    def forbidden_client():
        client_calls.append("unexpected_client")
        raise AssertionError("invalid book must never reach a client")
    monkeypatch.setattr(q, "_ensure_client", forbidden_client)
    setattr(q.quotes[SYMBOL], "ask" if side == "buy" else "bid", book)
    result = q.place_order(ts_code=SYMBOL, side=side, quantity=100, limit_price=10.,
                           rule_type="leader_breakout" if side == "buy" else "stop_loss_break", reasons=[])
    assert result["status"] == "rejected"
    assert result["reason"] == ("buy_trigger_not_met" if side == "buy" else "missing_or_invalid_executable_quote")
    assert client_calls == [] and q._client is None
    assert real_journal.read_jsonl(q.orders_path) == [result]
    assert not real_journal.read_jsonl(q.decisions_path)


def test_missing_book_sell_fallback_cannot_become_order_intent(code):
    q = ctx(code, holdings={SYMBOL: {"total_qty": 1000, "available_qty": 1000}})
    del q.quotes[SYMBOL]
    result = code.sell.run_sell_executor(stock(), {"type": "stop_loss_break", "trigger_price": 9.,
        "quantity_pct": 1.}, q, SimpleNamespace(positions={}), expected_type="stop_loss_break")
    assert result.status == "rejected"
    assert code.journal[0][1]["reason"] == "missing_or_invalid_executable_quote"


def test_legal_sell_intent_not_blocked_by_missing_scan(code):
    q = ctx(code, last=8.9, ask=9., holdings={SYMBOL: {"total_qty": 1000, "available_qty": 1000}})
    q.quotes[SYMBOL].bid = 8.89
    s = stock()
    result = code.sell.run_sell_executor(s, {"type": "stop_loss_break", "trigger_price": 9.,
        "quantity_pct": 1.}, q, SimpleNamespace(positions={}), expected_type="stop_loss_break")
    assert result.status == "dry_run"
    assert result.quantity == 1000
    assert result.limit_price == 8.89


def pattern(**kw):
    return SimpleNamespace(last=10., bars_5m=5, washout_score=.7, bull_trap_score=.1,
                           slow_bleed_score=.1, meta={"in_support": True, "in_resistance": False}, **kw)


def candidate(style="pullback", code=SYMBOL):
    return SimpleNamespace(ts_code=code, name="SYNTHETIC_ONLY", pool="execution_pool", entry_style=style,
        score=80., trigger_low=10., trigger_confirm=10.1, trigger_breakout=10., raw={})


@pytest.mark.parametrize("changes,expected", [({}, "buy_pullback"),
    ({"slow_bleed_score": .6}, "skip"), ({"bull_trap_score": .6}, "skip"),
    ({"washout_score": .1, "meta": {"in_support": False}}, "watch"),
    ({"last": 0., "bars_5m": 0}, "skip"), ({"last": float("nan")}, "skip")])
def test_selector_cheap_price_not_enough_but_confirmed_setup_passes(code, changes, expected):
    p = pattern()
    p.__dict__.update(changes)
    _, action, _ = code.selector._rank_score(candidate(), p, None, cash=10000.)
    assert action == expected


@pytest.mark.parametrize("failure", ["daily_empty", "minute_empty", "fetch_exception", "sise_exception", None])
def test_scan_fetch_failure_is_per_symbol_and_positive_neighbor_survives(code, monkeypatch, failure):
    sel = code.selector
    c1, c2 = candidate("breakout"), candidate("breakout", OTHER)
    monkeypatch.setattr(sel, "build_candidate_pool", lambda *a, **k: [c1, c2])
    monkeypatch.setattr(sel, "save_candidate_pool", lambda *a: None)
    def daily(symbol):
        if symbol == SYMBOL:
            if failure == "fetch_exception":
                raise ValueError("synthetic_fetch_failure")
            if failure == "daily_empty":
                return []
        return [{"synthetic": True}]
    monkeypatch.setattr(sel, "_fetch_daily_candles", daily)
    monkeypatch.setattr(sel, "compute_daily_levels", lambda *a, **k: SimpleNamespace())
    monkeypatch.setattr(sel, "fetch_xtick_minute_bars", lambda symbol, **k:
                        [] if symbol == SYMBOL and failure == "minute_empty" else [{"synthetic": True}])
    monkeypatch.setattr(sel, "analyze_intraday_pattern", lambda *a, **k: pattern())
    def gate(symbol, **k):
        if symbol == SYMBOL and failure == "sise_exception":
            raise ValueError("synthetic_sise_failure")
        return SimpleNamespace(pass_new_buy=True, vol_red=4, reason="synthetic_confirmed")
    monkeypatch.setattr(sel, "evaluate_sise_gate", gate)
    payload = sel.scan_entry_opportunities({}, trade_date=DATE, cash=10000.)
    code.session.set_scan_result(payload)
    assert code.session.buy_allowed(OTHER, entry_style="leader_breakout", trade_date=DATE)[0]
    assert code.session.buy_allowed(SYMBOL, entry_style="leader_breakout", trade_date=DATE)[0] is (failure is None)
    assert len(payload["errors"]) == (0 if failure is None else 1)
    # Full scanner -> session -> actual executor with the same real schema.
    result = execute(code, ctx(code))
    assert (result.status == "dry_run") is (failure is None)
