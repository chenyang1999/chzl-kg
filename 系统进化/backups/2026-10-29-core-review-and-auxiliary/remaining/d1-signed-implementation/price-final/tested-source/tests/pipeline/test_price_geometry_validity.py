"""Reject self-contradictory engine prices without inventing new risk policy.

Use a pre-collection guard and scratch basetemp. Only synthetic technical data;
actual derive -> apply_to_plan -> buy-eligibility functions are exercised.
"""
from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
from types import ModuleType, SimpleNamespace

import pytest

REPO = Path(os.environ.get("PRICE_GEOMETRY_SOURCE_ROOT", Path(__file__).resolve().parents[2]))
SCRATCH = Path.home() / ".hermes/cache/scratch"
DATE = "20990101"
FILES = ("src/plan/price_levels.py", "src/plan/buy_eligibility.py", "scripts/plan/apply_price_levels.py")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def env(tmp_path, monkeypatch):
    assert tmp_path.resolve().is_relative_to(SCRATCH.resolve())
    root = tmp_path / "app"
    for rel in FILES:
        dest = root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / rel, dest)
    prefixes = ("src", "scripts")
    saved = {k: v for k, v in sys.modules.items() if k.split(".")[0] in prefixes}
    for key in saved:
        sys.modules.pop(key)
    for name, directory in (("src", "src"), ("src.plan", "src/plan"),
                            ("scripts", "scripts"), ("scripts.plan", "scripts/plan")):
        package = ModuleType(name)
        package.__file__ = "<synthetic namespace>"
        package.__path__ = [str(root / directory)]
        monkeypatch.setitem(sys.modules, name, package)
    try:
        levels = load("src.plan.price_levels", root / FILES[0])
        helper = load("src.plan.buy_eligibility", root / FILES[1])
        apply = load("scripts.plan.apply_price_levels", root / FILES[2])
        def deny(*args, **kwargs):
            pytest.fail("synthetic geometry must not access the technical database")
        monkeypatch.setattr(levels, "load_tech", deny)
        yield SimpleNamespace(levels=levels, helper=helper, apply=apply)
    finally:
        for key in list(sys.modules):
            if key.split(".")[0] in prefixes:
                sys.modules.pop(key)
        sys.modules.update(saved)


def derive(env, monkeypatch, *, ref=18.94, code="000001.SZ", channel="divergence_pullback", tech=None):
    monkeypatch.setattr(env.levels, "load_tech", lambda *a: deepcopy(tech or {"close": ref, "ma10": ref * .8, "ma50": ref}))
    return env.levels.derive(code, DATE, ref_close=ref, channel=channel)


@pytest.mark.parametrize("ref", [18.94, 7.08, 100.0])
def test_divergence_base_stop_inside_zone_is_not_marked_usable(env, monkeypatch, ref):
    row = derive(env, monkeypatch, ref=ref)
    assert row["ok"] is False
    assert "invalid_stop_geometry" in row["reason"]
    assert row.get("trigger_price") is None
    assert row.get("risk_reward_ratio") is None


def test_quote_rounding_cannot_move_valid_raw_stop_onto_zone_edge(env, monkeypatch):
    row = derive(env, monkeypatch, ref=.1, channel="trend_pullback_buy", tech={"close": .1, "ma50": .1})
    assert row["ok"] is False
    assert "invalid_stop_geometry" in row["reason"]


@pytest.mark.parametrize("code,channel,ref,tech", [
    ("000001.SZ", "trend_pullback_buy", 100.0, {"close": 100.0, "ma50": 100.0, "hi20": 120.0}),
    ("000001.SZ", "leader_breakout", 100.0, {"close": 100.0, "hi20": 100.0}),
    ("300001.SZ", "divergence_pullback", 100.0, {"close": 100.0, "ma10": 80.0}),
    ("920001.BJ", "divergence_pullback", 100.0, {"close": 100.0, "ma10": 80.0}),
])
def test_existing_valid_channels_still_produce_geometry_and_rr(env, monkeypatch, code, channel, ref, tech):
    row = derive(env, monkeypatch, code=code, channel=channel, ref=ref, tech=tech)
    assert row["ok"] is True
    assert 0 < row["stop_loss"] < row["buy_zone"][0] <= row["buy_zone"][1] < row["take_profit"]
    assert row["risk_reward_ratio"] >= 1.8
    assert env.helper.RR_MIN == 1.8


def stock(code="000001.SZ", ref=18.94, **updates):
    return {"ts_code": code, "name": "synthetic-only", "reference_close": ref,
            "entry_rules": [], "exit_rules": [{"type": "stop_loss_break", "trigger_price": 15.0,
                                                "quantity_pct": 1.0, "priority": 1}],
            "auto_trade_enabled": False, "requires_user_confirmation": True,
            "max_position_pct": 0.0, **updates}


def plan(stocks, **updates):
    return {"trade_date": DATE, "mode": "dry_run", "execution_pool": [], "watch_pool": stocks,
            "autonomous_trading_enabled": False, "requires_user_confirmation": True,
            "risk_limits": {"target_total_position_pct": 0.0}, "no_trade": True, **updates}


def test_apply_invalid_geometry_does_not_create_an_entry_or_remove_exits(env, monkeypatch):
    s = stock()
    p = plan([s])
    exits = deepcopy(s["exit_rules"])
    monkeypatch.setattr(env.levels, "load_tech", lambda *a: {"close": 18.94, "ma10": 15.0})
    rows = env.apply.apply_to_plan(p, DATE)
    assert rows[0]["ok"] is False
    assert s["engine_levels"]["ok"] is False
    assert s["entry_rules"] == [] and s["exit_rules"] == exits
    assert s["buy_eligibility"]["status"] != "eligible"
    assert p["no_trade"] is True and p["risk_limits"]["target_total_position_pct"] == 0.0
    assert not p["autonomous_trading_enabled"] and not s["auto_trade_enabled"]
    assert env.helper.evaluate_plan_buy_gate(p)["status"] == "blocked"


def test_bad_geometry_replaces_stale_success_evidence(env, monkeypatch):
    s = stock(buy_eligibility={"source": "price_levels_engine", "status": "eligible"})
    p = plan([s])
    monkeypatch.setattr(env.levels, "load_tech", lambda *a: {"close": 18.94, "ma10": 15.0})
    env.apply.apply_to_plan(p, DATE)
    assert s["engine_levels"]["ok"] is False
    assert s["buy_eligibility"]["status"] != "eligible"


def test_single_invalid_stock_does_not_block_a_valid_sibling_or_make_a_global_ban(env, monkeypatch):
    bad, good = stock(), stock("000002.SZ", 100.0, exit_rules=[], max_position_pct=.1)
    # The positive scenario is explicitly selected, not an empty-entry default.
    good["entry_rules"] = [{"type": "trend_pullback_buy"}]
    p = plan([bad, good], no_trade=False, risk_limits={"target_total_position_pct": .5})
    def tech(code, _date):
        return {"close": 18.94, "ma10": 15.0} if code == "000001.SZ" else {"close": 100.0, "ma10": 100.0, "ma50": 100.0}
    monkeypatch.setattr(env.levels, "load_tech", tech)
    env.apply.apply_to_plan(p, DATE)
    assert bad["engine_levels"]["ok"] is False
    assert bad["entry_rules"] == []
    assert good["engine_levels"]["ok"] is True
    assert good["buy_eligibility"]["status"] == "eligible"
    assert not good["auto_trade_enabled"] and good["requires_user_confirmation"]
    assert env.helper.evaluate_plan_buy_gate(p)["status"] == "eligible"
    assert "no_trade_conditions" not in p


def test_external_owner_refusal_survives_geometry_failure(env, monkeypatch):
    refusal = {"source": "D1", "status": "blocked", "reasons": ["ORIGINAL_NO_TRADE"]}
    s = stock(buy_eligibility=deepcopy(refusal))
    monkeypatch.setattr(env.levels, "load_tech", lambda *a: {"close": 18.94, "ma10": 15.0})
    env.apply.apply_to_plan(plan([s]), DATE)
    assert s["buy_eligibility"]["status"] == "blocked"
    assert s["buy_eligibility"]["external_qualification"] == refusal


def test_invalid_b_plan_candidate_stays_unpriced_without_global_permission_changes(env, monkeypatch):
    candidate = stock()
    candidate.pop("exit_rules")
    p = plan([], seesaw_plan={"seesaw_directions": [{"candidates": [candidate]}]})
    monkeypatch.setattr(env.levels, "load_tech", lambda *a: {"close": 18.94, "ma10": 15.0})
    env.apply.apply_to_plan(p, DATE)
    assert candidate["engine_levels"]["ok"] is False
    assert candidate["entry_rules"] == []
    assert "buy_zone" not in candidate
    assert env.helper.evaluate_plan_buy_gate(p)["status"] == "blocked"
