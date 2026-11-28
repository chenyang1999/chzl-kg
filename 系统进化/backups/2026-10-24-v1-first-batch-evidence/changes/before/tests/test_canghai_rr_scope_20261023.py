"""Isolated RR-scope regression; synthetic fixtures, never broker/production IO.

Run with --basetemp beneath ~/.hermes/cache/scratch and -p no:cacheprovider.
Copy only required Python sources. Never import src.settings or broker code.
"""
from __future__ import annotations

import builtins
from copy import deepcopy
import importlib
import importlib.abc
import io
import json
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pydantic  # initialize library before installing the no-process guard
import pytest

REPO = Path(__file__).resolve().parents[1]
SCRATCH = Path.home() / ".hermes/cache/scratch"
DATE = "20990101"  # synthetic only; never today's production plan


@pytest.fixture(scope="module")
def code(tmp_path_factory, request):
    root = tmp_path_factory.mktemp("rr-scope-code")
    assert root.resolve().is_relative_to(SCRATCH.resolve()), "--basetemp must be Hermes scratch"
    files = ["src/__init__.py", "src/plan/__init__.py", "src/plan/buy_eligibility.py",
             "src/plan/price_levels.py", "src/plan/risk_reward.py",
             "scripts/plan/apply_price_levels.py", "trading/__init__.py",
             "trading/schema/watchlist_plan.py", "trading/watcher/dispatch.py",
             "trading/watcher/session_context.py"]
    files += [str(p.relative_to(REPO)) for p in (REPO / "trading/executors").glob("*.py")]
    for rel in files:
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / rel, dest)
    for package in ("scripts", "scripts/plan", "trading/order", "trading/schema", "trading/watcher"):
        path = root / package / "__init__.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")
    prefixes = ("src", "trading", "scripts")
    saved = {k: v for k, v in sys.modules.items() if k.split(".")[0] in prefixes}
    for key in saved:
        del sys.modules[key]
    mp = pytest.MonkeyPatch()
    mp.syspath_prepend(str(root))
    mp.chdir(root)
    violations = []

    class BlockImports(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if (fullname == "src.settings" or "qmt_client" in fullname
                    or fullname.startswith(("dotenv", "ib_insync", "ibapi"))):
                violations.append(fullname)
                raise AssertionError(f"forbidden import: {fullname}")

    blocker = BlockImports()
    sys.meta_path.insert(0, blocker)

    def deny(*args, **kwargs):
        violations.append("external_effect")
        raise AssertionError("network/process/DB access forbidden")

    mp.setattr(socket, "create_connection", deny)
    mp.setattr(socket.socket, "connect", deny)
    mp.setattr(subprocess, "Popen", deny)
    mp.setattr(sqlite3, "connect", deny)
    for container in (builtins, io):
        original = container.open

        def guarded(file, mode="r", *args, _original=original, **kwargs):
            if not isinstance(file, int):
                path = Path(file).absolute().resolve()
                test_source = path == Path(__file__).resolve() and not any(c in mode for c in "wax+")
                library_read = path.is_relative_to(Path(sys.prefix).resolve()) and not any(c in mode for c in "wax+")
                if path.name == ".env" or (path.is_relative_to(REPO.resolve()) and not (test_source or library_read)):
                    violations.append(str(path))
                    raise AssertionError(f"production read/write forbidden: {path}")
                if any(c in mode for c in "wax+") and not path.is_relative_to(SCRATCH.resolve()):
                    violations.append(str(path))
                    raise AssertionError(f"write outside isolated repo: {path}")
            return _original(file, mode, *args, **kwargs)
        mp.setattr(container, "open", guarded)

    # Type-only dependencies: zero broker-source imports or account objects.
    qmt = ModuleType("trading.order.qmt_context")
    setattr(qmt, "QMTContext", type("ForbiddenBrokerContext", (), {"__init__": deny}))
    ps = ModuleType("trading.positions_state")
    setattr(ps, "PositionsStateStore", object)
    setattr(ps, "PositionState", object)
    mp.setitem(sys.modules, qmt.__name__, qmt)
    mp.setitem(sys.modules, ps.__name__, ps)
    def cleanup():
        sys.meta_path.remove(blocker)
        mp.undo()
        for key in list(sys.modules):
            if key.split(".")[0] in prefixes:
                del sys.modules[key]
        sys.modules.update(saved)
    request.addfinalizer(cleanup)
    helper = importlib.import_module("src.plan.buy_eligibility")
    levels = importlib.import_module("src.plan.price_levels")
    sizing = importlib.import_module("src.plan.risk_reward")
    apply = importlib.import_module("scripts.plan.apply_price_levels")
    buy = importlib.import_module("trading.executors._buy_common")
    sell = importlib.import_module("trading.executors._sell_common")
    dispatch = importlib.import_module("trading.watcher.dispatch")
    schema = importlib.import_module("trading.schema.watchlist_plan")
    yield SimpleNamespace(root=root, helper=helper, levels=levels, sizing=sizing,
                          apply=apply, buy=buy, sell=sell, dispatch=dispatch, schema=schema)
    assert "src.settings" not in sys.modules
    assert not violations, f"blocked effects were attempted: {violations}"


def stock(code="000001.SZ", take=120.0, **updates):
    return {"ts_code": code, "name": "SYNTHETIC_NOT_REAL", "score": 90,
            "reference_close": 100.0, "stop_loss": 90.0, "take_profit": take,
            "plan_status": "execution_pool_hold_add_on_pullback", "auto_trade_enabled": True,
            "max_position_pct": 0.1,
            "entry_rules": [{"type": "trend_pullback_buy", "buy_zone": [99.0, 100.0],
                             "trigger_price": 100.0, "max_acceptable_ask": 100.0,
                             "position_pct": 0.05}],
            "exit_rules": [{"type": "stop_loss_break", "trigger_price": 90.0,
                            "quantity_pct": 1.0, "priority": 1}], **updates}


def plan(**updates):
    return {"trade_date": DATE, "mode": "dry_run", "execution_pool": [], "watch_pool": [],
            "risk_limits": {"target_total_position_pct": 0.5}, "no_trade_conditions": [], **updates}


def watch_stock(code="000002.SZ", **updates):
    s = stock(code, entry_rules=[], auto_trade_enabled=False, **updates)
    s.pop("stop_loss")
    s.pop("take_profit")
    s["exit_rules"] = []
    return s


class FixtureContext:
    """Only in-memory call observations, not simulated fills or account equity."""
    def __init__(self, stocks):
        self.quotes = {s["ts_code"]: SimpleNamespace(last=100.0, ask=100.0, bid=99.9) for s in stocks}
        self.total_asset = 100000.0  # synthetic sizing fixture, not paper seed
        self.calls = []
        self.events = []

    def refresh_quotes(self, symbols):
        assert set(symbols) <= set(self.quotes)

    def place_order(self, **kwargs):
        self.calls.append(kwargs)
        return {"status": "fixture_order_intent"}

    def log_event(self, row):
        self.events.append(row)

    def has_position(self, code):
        return True

    def available_qty(self, code):
        return 200  # synthetic legally sellable fixture


def tech(monkeypatch, code, *, fail=False):
    # Real derive formulas against deterministic injected technical levels.
    def load(symbol, date):
        assert date == DATE
        if symbol == "000003.SZ":
            raise RuntimeError("fixture refresh failed")
        return {"close": 100.0, "ma50": 100.0, "hi20": 108.0 if fail else 120.0}
    monkeypatch.setattr(code.levels, "load_tech", load)


def test_import_is_pure_and_relocated(code):
    assert code.apply.ROOT == code.root
    assert "src.settings" not in sys.modules
    assert code.helper.RR_MIN == 1.8


@pytest.mark.parametrize("take,status", [(109.9, "blocked"), (110.0, "blocked"),
                                         (117.94, "blocked"), (117.95, "eligible"),
                                         (118.0, "eligible"), (120.0, "eligible"), (130.0, "eligible")])
def test_rr_engine_rounding_boundary(code, take, status):
    result = code.helper.evaluate_stock_buy_eligibility(stock(take=take))
    assert result["status"] == status
    assert result["risk_reward_ratio"] == round((take - 100.0) / 10.0, 2)


@pytest.mark.parametrize("value", [None, True, False, float("nan"), float("inf"),
                                   -float("inf"), 0, -1, "100"])
@pytest.mark.parametrize("field", ["buy", "stop", "take"])
def test_invalid_numerics_never_authorize(code, value, field):
    s = stock()
    if field == "buy":
        s["entry_rules"][0]["buy_zone"][1] = value
    else:
        s["stop_loss" if field == "stop" else "take_profit"] = value
    assert code.helper.evaluate_stock_buy_eligibility(s)["status"] != "eligible"


@pytest.mark.parametrize("quote", [{"ask": None, "last": 100}, {"ask": True},
                                   {"ask": float("nan")}, {"ask": float("inf")},
                                   {"ask": 0}, {"last": 100}, True, "100"])
def test_quote_cannot_fallback_to_last(code, quote):
    assert code.helper.evaluate_stock_buy_eligibility(stock(), quote)["status"] == "unknown"


def test_exact_buy_price_recomputed_not_engine_rr(code):
    s = stock()
    s["engine_levels"] = {"ok": True, "buy_zone": [99, 100], "stop_loss": 90,
                          "take_profit": 120, "risk_reward_ratio": 999, "rr_grade": "pass"}
    r = code.helper.evaluate_stock_buy_eligibility(s, {"ask": 110})
    assert r["status"] == "blocked" and r["risk_reward_ratio"] == 0.5
    assert r["price_source"] == "D1"


def test_d1_disagreement_is_audit_not_zero_deviation_gate(code):
    # Parent review: new RR-scope test originally encoded an unauthorized
    # zero-deviation gate. Original D1 prices are complete and consistent.
    s = stock()
    s["engine_levels"] = {"ok": True, "buy_zone": [90, 95], "stop_loss": 85, "take_profit": 130,
                          "risk_reward_ratio": 3.5}
    original = deepcopy(s)
    r = code.helper.evaluate_stock_buy_eligibility(s)
    assert r["status"] == "eligible" and r["review_required"] is False
    assert r["price_comparison"]["differs"] is True
    assert (r["buy_price"], r["stop_loss"], r["take_profit"], r["risk_reward_ratio"]) == (100, 90, 120, 2)
    assert s == original
    s.pop("stop_loss")
    s["exit_rules"] = []
    assert code.helper.evaluate_stock_buy_eligibility(s)["status"] == "unknown"


def test_multi_rule_must_select_then_each_rule_checked(code):
    s = stock()
    second = {**s["entry_rules"][0], "buy_zone": [110, 115]}
    s["entry_rules"].append(second)
    assert code.helper.evaluate_stock_buy_eligibility(s)["status"] == "unknown"
    assert code.helper.evaluate_stock_buy_eligibility(s, entry_rule=second)["status"] == "blocked"
    assert code.helper.evaluate_stock_buy_eligibility(s, entry_rule=s["entry_rules"][0])["status"] == "eligible"


def test_scope_and_research_membership_survive_enrichment(code, monkeypatch):
    tech(monkeypatch, code, fail=True)
    a = stock(stop_loss=95.95, take_profit=111.1)
    a["entry_rules"][0]["buy_zone"] = [99, 101]
    # Original top-level stop (95.95) conflicts with actual exit stop (90):
    # preserve both and require evidence review, not a zero-deviation veto.
    w = watch_stock(plan_status="watch_pool_only")
    b = {"ts_code": "000004.SZ", "name": "SYNTHETIC_B", "reference_close": 100}
    p = plan(execution_pool=[a], watch_pool=[w],
             seesaw_plan={"seesaw_directions": [{"candidates": [b]}]})
    exits = deepcopy(a["exit_rules"])
    code.apply.apply_to_plan(p, DATE)
    assert p["no_trade_conditions"] == []
    assert a["buy_eligibility"]["status"] != "eligible"
    assert w["buy_eligibility"]["status"] == "blocked"
    assert b["buy_eligibility"]["status"] == "blocked"
    assert p["execution_pool"] == [a] and p["watch_pool"] == [w]
    assert not w["auto_trade_enabled"] and w["plan_status"] == "watch_pool_only"
    assert a["exit_rules"] == exits
    assert code.helper.evaluate_plan_buy_gate(p)["status"] == "eligible"


def test_legacy_migration_exact_source_and_idempotence(code, monkeypatch):
    tech(monkeypatch, code)
    owned = {"code": "RR_FAIL", "source": "price_levels_engine", "active": True, "description": "old"}
    foreign = [{"code": "RR_FAIL", "source": x, "active": True} for x in (None, "user", "risk")]
    foreign += [{"code": "RR_FAIL", "active": True}, {"code": "R7_STALE", "source": "price_levels_engine", "active": True}]
    w = watch_stock()
    p = plan(watch_pool=[w], no_trade_conditions=[owned] + deepcopy(foreign))
    code.apply.apply_to_plan(p, DATE)
    assert p["no_trade_conditions"] == foreign
    assert p["price_levels_rr_migration"] == [owned]
    first = deepcopy(p)
    code.apply.apply_to_plan(p, DATE)
    assert p == first
    assert code.helper.evaluate_plan_buy_gate(p)["status"] == "blocked"


def test_fail_then_pass_then_missing_refresh_is_not_sticky(code, monkeypatch):
    w = watch_stock()
    p = plan(watch_pool=[w], no_trade_conditions=[{"code": "RR_FAIL", "source": "price_levels_engine", "active": True}])
    tech(monkeypatch, code, fail=True)
    code.apply.apply_to_plan(p, DATE)
    assert w["buy_eligibility"]["status"] == "blocked"
    tech(monkeypatch, code, fail=False)
    code.apply.apply_to_plan(p, DATE)
    assert w["buy_eligibility"]["status"] == "eligible"
    assert p["no_trade_conditions"] == []
    w["ts_code"] = "000003.SZ"
    code.apply.apply_to_plan(p, DATE)
    assert w["buy_eligibility"]["status"] == "unknown"
    assert w["engine_levels"]["ok"] is False
    assert w["engine_levels"]["risk_reward_ratio"] is None


@pytest.mark.parametrize("source", [None, "user", "other_engine"])
@pytest.mark.parametrize("status", ["blocked", "unknown"])
def test_external_qualification_survives_repeated_refresh(code, monkeypatch, source, status):
    tech(monkeypatch, code)
    w = watch_stock(buy_eligibility={"source": source, "status": status})
    p = plan(watch_pool=[w])
    for _ in range(3):
        code.apply.apply_to_plan(p, DATE)
        assert w["buy_eligibility"]["status"] == status
        assert w["buy_eligibility"]["external_qualification"] == {"source": source, "status": status}


@pytest.mark.parametrize("extra", [{"no_trade": True}, {"no_trade": "false"},
                                     {"decision_status": "no_trade"},
                                     {"no_trade_conditions": [{"code": "MAIN_DOWN", "active": True}]},
                                     {"no_trade_conditions": [{"code": "RR_FAIL", "source": "user", "active": True}]},
                                     {"no_trade_conditions": [{"code": "R7_STALE", "active": None}]},
                                     {"risk_limits": {"target_total_position_pct": 0}},
                                     {"meta": {"position_cap_pct": 0}},
                                     {"position_cap_derivation": {"final_position_cap_pct": 0}}])
def test_real_global_blockers_and_zero_budgets_preserved(code, monkeypatch, extra):
    tech(monkeypatch, code)
    p = plan(**extra)
    before = deepcopy(p)
    code.apply.apply_to_plan(p, DATE)
    assert p == before
    assert code.helper.evaluate_plan_buy_gate(p)["status"] == "blocked"


def test_actual_common_buy_blocks_only_bad_stock_and_sell_still_runs(code):
    good, bad = stock(), stock("000002.SZ", take=110)
    ctx = FixtureContext([good, bad])
    positions = SimpleNamespace(positions={})
    for s in (good, bad):
        result = code.buy.run_buy_executor(s, s["entry_rules"][0], ctx, positions,
                                          expected_type="trend_pullback_buy", simulate=True, force_trigger=True)
        assert (result.status == "fixture_order_intent") is (s is good)
    result = code.sell.run_sell_executor(bad, {"type": "exit_at_open", "quantity_pct": 1},
                                         ctx, positions, expected_type="exit_at_open")
    assert result.side == "sell" and result.quantity == 200
    assert [(c["ts_code"], c["side"]) for c in ctx.calls] == [(good["ts_code"], "buy"), (bad["ts_code"], "sell")]


@pytest.mark.parametrize("status", ["watch_pool_only", "watch_pool_wait_for_entry", None])
def test_other_entry_cannot_promote_watch_or_b(code, status):
    s = stock(plan_status=status)
    ctx = FixtureContext([s])
    r = code.buy.run_buy_executor(s, s["entry_rules"][0], ctx, SimpleNamespace(positions={}),
                                 expected_type="trend_pullback_buy", simulate=True, force_trigger=True)
    assert r.skip_reason == "stock_buy_not_authorized" and not ctx.calls


@pytest.mark.parametrize("key", ["position_pct", "max_position_pct"])
def test_actual_common_buy_preserves_zero_budget(code, key):
    s = stock()
    (s["entry_rules"][0] if key == "position_pct" else s)[key] = 0
    ctx = FixtureContext([s])
    r = code.buy.run_buy_executor(s, s["entry_rules"][0], ctx, SimpleNamespace(positions={}),
                                 expected_type="trend_pullback_buy", simulate=True)
    assert r.skip_reason == "zero_or_invalid_stock_buy_budget" and not ctx.calls


def test_dispatch_global_gate_does_not_stop_legal_sell_or_research(code):
    s = stock()
    s["exit_rules"] = [{"type": "exit_at_open", "quantity_pct": 1.0}]
    w = stock("000002.SZ", plan_status="watch_pool_only", auto_trade_enabled=False)
    p = code.schema.WatchlistPlan.model_validate(plan(execution_pool=[s], watch_pool=[w],
        no_trade_conditions=[{"code": "R7_STALE", "active": True}]))
    ctx = FixtureContext([s, w])
    report = code.dispatch.dispatch_plan(p, ctx, SimpleNamespace(positions={}))
    assert len(ctx.calls) == 1 and ctx.calls[0]["side"] == "sell"
    assert report.entry_results == [] and report.exit_results[0]["side"] == "sell"
    assert report.watch_started == [w["ts_code"]]
    assert report.skipped[0]["reason"] == "global_buy_gate"


def test_actual_dispatch_mixed_rr_has_no_global_contagion(code):
    good, bad = stock(), stock("000002.SZ", take=110)
    for s in (good, bad):
        s["exit_rules"] = []
    p = code.schema.WatchlistPlan.model_validate(plan(execution_pool=[good, bad]))
    ctx = FixtureContext([good, bad])
    report = code.dispatch.dispatch_plan(p, ctx, SimpleNamespace(positions={}), simulate=True)
    assert len(ctx.calls) == 1 and ctx.calls[0]["ts_code"] == good["ts_code"]
    assert report.entry_results[1]["skip_reason"] == "stock_buy_eligibility"


def test_d1_actual_limit_not_cached_buy_zone_rr(code):
    s = stock()
    s["entry_rules"][0]["max_acceptable_ask"] = 110.0
    ctx = FixtureContext([s])
    r = code.buy.run_buy_executor(s, s["entry_rules"][0], ctx, SimpleNamespace(positions={}),
                                 expected_type="trend_pullback_buy", simulate=True, force_trigger=True)
    assert r.skip_reason == "stock_buy_eligibility"
    assert r.meta["buy_eligibility"]["risk_reward_ratio"] == 0.5
    assert not ctx.calls


@pytest.mark.parametrize("rr,tier", [(0.99, "none"), (1.0, "trial"), (1.8, "trial"),
                                     (1.99, "trial"), (2.0, "core"), (2.99, "core"), (3.0, "core_main")])
def test_original_sizing_1_2_3_not_changed(code, rr, tier):
    r = code.sizing.judge_risk_reward(DATE, "SYNTHETIC", "FIXTURE", 100, 100 + rr * 10, 90,
                                     emotion_phase="main_up")
    assert r.position_tier == tier
    assert (code.sizing.MIN_RR_TRIAL, code.sizing.MIN_RR_NORMAL, code.sizing.MIN_RR_MAIN) == (1, 2, 3)


def test_real_engine_formula_2r_and_1_8_threshold(code, monkeypatch):
    tech(monkeypatch, code)
    r = code.levels.derive("000001.SZ", DATE, ref_close=100)
    assert r["buy_zone"] == [99, 101] and r["stop_loss"] == 95.95
    assert r["take_profit"] == 111.1 and r["risk_reward_ratio"] == 2.0 and r["rr_grade"] == "pass"
    tech(monkeypatch, code, fail=True)
    r = code.levels.derive("000001.SZ", DATE, ref_close=100)
    assert r["take_profit"] == 108 and r["risk_reward_ratio"] == 1.39 and r["rr_grade"] == "RR_FAIL"


def test_main_writes_only_relocated_synthetic_plan_and_report(code, monkeypatch):
    tech(monkeypatch, code, fail=True)
    p = plan(watch_pool=[watch_stock()])
    path = code.root / f"data/plans/{DATE}/watchlist_plan.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(p))
    monkeypatch.setattr(sys, "argv", ["apply_price_levels.py", "--date", DATE, "--write-json"])
    code.apply.main()
    result = json.loads(path.read_text())
    assert result["watch_pool"][0]["buy_eligibility"]["status"] == "blocked"
    assert result["no_trade_conditions"] == []
    text = (code.root / f"chzl_kg/投研交易/盘前预案/{DATE}_价位推导.md").read_text()
    assert "不污染全局" in text and "D1/引擎差异留审计" in text
    assert "买区偏离>10%须 derivation_reason" in text


def test_d1_watch_trigger_only_and_b_prices_are_not_overwritten(code, monkeypatch):
    tech(monkeypatch, code)
    w = stock("000002.SZ", plan_status="watch_pool_only", auto_trade_enabled=False)
    w["entry_rules"][0].pop("buy_zone")
    b = {"ts_code": "000004.SZ", "name": "SYNTHETIC_B", "reference_close": 100,
         "buy_zone": [98, 100], "trigger_price": 100, "stop_loss": 90, "take_profit": 120}
    original_w, original_b = deepcopy(w), deepcopy(b)
    p = plan(watch_pool=[w], seesaw_plan={"seesaw_directions": [{"candidates": [b]}]})
    code.apply.apply_to_plan(p, DATE)
    assert w["entry_rules"] == original_w["entry_rules"]
    assert all(b[k] == v for k, v in original_b.items())
    # Parent review: retain original prices and audit differences, but neither
    # research membership nor a lawful difference is an RR rejection.
    for candidate in (w, b):
        assert candidate["buy_eligibility"]["review_required"] is False
        assert candidate["buy_eligibility"]["status"] == "eligible"
        assert candidate["buy_eligibility"]["price_comparison"]["differs"] is True


@pytest.mark.parametrize("bad_zone", [[99, None], [99, True], [99, float("nan")],
                                        [99, float("inf")], [100], [], "invalid"])
def test_enrichment_preserves_invalid_d1_as_unknown_not_auto_repaired(code, monkeypatch, bad_zone):
    tech(monkeypatch, code)
    s = stock()
    s["entry_rules"][0]["buy_zone"] = bad_zone
    p = plan(execution_pool=[s])
    code.apply.apply_to_plan(p, DATE)
    assert s["buy_eligibility"]["status"] == "unknown"
    assert s["entry_rules"][0]["buy_zone"] is bad_zone


@pytest.mark.parametrize("rule_type", ["trend_pullback_buy", "leader_breakout", "daban_confirm",
                                      "low_absorption_intraday", "t_add_pullback"])
def test_all_registered_buy_entries_use_same_stock_gate(code, rule_type):
    bad = stock(take=110)
    bad["entry_rules"][0]["type"] = rule_type
    ctx = FixtureContext([bad])
    executor = code.dispatch.get_entry_executor(rule_type)
    result = executor(bad, bad["entry_rules"][0], ctx, SimpleNamespace(positions={}), simulate=True)
    assert result.skip_reason == "stock_buy_eligibility" and not ctx.calls


def test_generated_entry_does_not_borrow_engine_rr_for_d1_exits(code):
    s = stock()
    s["entry_rules"][0]["price_src"] = "engine"
    s["engine_levels"] = {"ok": True, "buy_zone": [99, 100], "stop_loss": 95, "take_profit": 110}
    r = code.helper.evaluate_stock_buy_eligibility(s)
    # Parent review: sourced original exits may differ from the entry engine;
    # recompute their RR rather than borrowing engine RR or vetoing all changes.
    assert r["status"] == "eligible" and not r["review_required"]
    assert r["price_comparison"]["differs"] is True
    assert r["risk_reward_ratio"] == 2.0
    assert r["risk_price_source"] == "D1_exits"
    assert (r["stop_loss"], r["take_profit"]) == (90, 120)


@pytest.mark.parametrize("status", ["blocked", "unknown"])
def test_unverified_stock_cannot_bypass_by_just_changing_pool(code, status):
    s = stock(buy_eligibility={"source": "price_levels_engine", "status": status},
              engine_levels={"ok": False, "reason": "missing"})
    ctx = FixtureContext([s])
    result = code.buy.run_buy_executor(s, s["entry_rules"][0], ctx, SimpleNamespace(positions={}),
                                      expected_type="trend_pullback_buy", simulate=True, force_trigger=True)
    assert result.skip_reason == "stock_buy_eligibility" and not ctx.calls


@pytest.mark.parametrize("status", ["eligible", "blocked", "unknown"])
def test_stripped_engine_evidence_never_authorizes(code, status):
    s = stock(buy_eligibility={"source": "price_levels_engine", "status": status})
    assert code.helper.evaluate_stock_buy_eligibility(s, 100)["status"] == "unknown"


@pytest.mark.parametrize("scope", ["stock", "symbol"])
def test_explicit_stock_condition_only_blocks_its_target(code, scope):
    p = plan(no_trade_conditions=[{"scope": scope, "ts_code": "000002.SZ",
                                  "active": True, "code": "STOCK_REVIEW"}])
    assert code.helper.evaluate_plan_buy_gate(p)["status"] == "eligible"
    assert code.helper.evaluate_plan_buy_gate(p, ts_code="000001.SZ")["status"] == "eligible"
    assert code.helper.evaluate_plan_buy_gate(p, ts_code="000002.SZ")["status"] == "blocked"


@pytest.mark.parametrize("condition", [
    {"scope": "stock", "active": True},
    {"scope": "symbol", "ts_code": "002.SZ", "active": True},
    {"scope": "typo", "ts_code": "000002.SZ", "active": True},
    {"scope": None, "active": True},
    {"active": True, "code": "USER_GLOBAL_STOP"},
])
def test_invalid_or_global_condition_is_not_silently_ignored(code, condition):
    p = plan(no_trade_conditions=[condition])
    assert code.helper.evaluate_plan_buy_gate(p)["status"] == "blocked"
    assert code.helper.evaluate_plan_buy_gate(p, ts_code="000001.SZ")["status"] == "blocked"


def test_scoped_dispatch_keeps_good_buy_bad_sell_and_watch(code):
    good, bad, observed = stock(), stock("000002.SZ"), stock("000003.SZ", auto_trade_enabled=False)
    good["exit_rules"] = []
    bad["exit_rules"] = [{"type": "exit_at_open", "quantity_pct": 1.0}]
    p = code.schema.WatchlistPlan.model_validate(plan(execution_pool=[good, bad], watch_pool=[observed],
        no_trade_conditions=[{"scope": "stock", "ts_code": bad["ts_code"], "active": True,
                              "code": "STOCK_REVIEW"}]))
    ctx = FixtureContext([good, bad, observed])
    report = code.dispatch.dispatch_plan(p, ctx, SimpleNamespace(positions={}), simulate=True)
    assert [(x["ts_code"], x["side"]) for x in ctx.calls] == [(good["ts_code"], "buy"), (bad["ts_code"], "sell")]
    assert any(x["reason"] == "stock_buy_gate" for x in report.skipped)
    assert report.watch_started == [observed["ts_code"]]
