"""A-group regressions: real contracts, synthetic data, no production imports.

Run ONLY this file with --basetemp beneath HERMES scratch and cache disabled.
Copy Python sources before imports; do not copy .env, data, config, DB or reports.
External effects are denied (and recorded even when a fallback swallows errors).
"""
from __future__ import annotations

import builtins
import importlib
import io
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRATCH = Path.home() / ".hermes/cache/scratch"
DATE = "20261023"
EARLY = "2026-10-23T06:00:00+08:00"


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False), encoding="utf-8")


def _plan(**updates):
    return {
        "schema_version": "watchlist_plan_v1", "trade_date": DATE,
        "generated_at": EARLY, "decision_source": "llm", "mode": "dry_run",
        "autonomous_trading_enabled": False, "requires_user_confirmation": True,
        "execution_pool": [], "watch_pool": [], "no_trade": True,
        "risk_limits": {"target_total_position_pct": 0.0}, **updates,
    }


@pytest.fixture(scope="module")
def code(tmp_path_factory):
    root = tmp_path_factory.mktemp("plan-contract-code")
    assert root.resolve().is_relative_to(SCRATCH.resolve()), "use --basetemp under Hermes scratch"
    # Filesystem inspection found settings' .env loader and d1_algorithm's
    # stock-character cache build at import time. Relocation prevents both from
    # ever seeing production inputs; do not symlink these packages.
    for directory in ("src", "trading"):
        for source in (REPO / directory).rglob("*.py"):
            target = root / source.relative_to(REPO)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    for rel in ("scripts/research/pipeline_artifacts.py", "scripts/research/build_research_summary.py",
                "scripts/plan/ensure_watchlist_plan.py"):
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / rel, target)
    for package in ("scripts", "scripts/research", "scripts/plan"):
        (root / package / "__init__.py").write_text("")

    prefixes = ("src", "trading", "scripts")
    saved = {k: v for k, v in sys.modules.items() if k.split(".")[0] in prefixes}
    for key in saved:
        del sys.modules[key]
    mp = pytest.MonkeyPatch()
    mp.syspath_prepend(str(root))
    violations = []
    lib_roots = {Path(sys.base_prefix).resolve(), Path(sys.prefix).resolve()}
    # CPython's macOS sysconfig reads the OS version while importing pydantic.
    # This is library initialization, not permission to read project data.
    library_files = {Path("/System/Library/CoreServices/SystemVersion.plist"), Path(__file__).resolve()}

    def check_file(path, *, write=False):
        if isinstance(path, int):
            return
        p = Path(os.fsdecode(path)).absolute().resolve()
        if p.is_relative_to(SCRATCH.resolve()):
            return
        if not write and any(p.is_relative_to(base) for base in lib_roots):
            return
        if not write and p in library_files:
            return
        violations.append(("write" if write else "read", str(p)))
        raise AssertionError(f"outside isolated scratch: {p}")

    def wrap_open(original):
        def guarded(file, mode="r", *args, **kwargs):
            check_file(file, write=any(c in mode for c in "wax+"))
            return original(file, mode, *args, **kwargs)
        return guarded

    mp.setattr(builtins, "open", wrap_open(builtins.open))
    mp.setattr(io, "open", wrap_open(io.open))
    real_os_open = os.open

    def os_open(path, flags, *args, **kwargs):
        check_file(path, write=bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)))
        return real_os_open(path, flags, *args, **kwargs)

    mp.setattr(os, "open", os_open)

    def wrap_mutation(original, both_paths=False):
        def guarded(path, *args, **kwargs):
            check_file(path, write=True)
            if both_paths:
                check_file(args[0], write=True)
            return original(path, *args, **kwargs)
        return guarded

    for name in ("mkdir", "unlink", "remove", "rmdir"):
        mp.setattr(os, name, wrap_mutation(getattr(os, name)))
    for name in ("rename", "replace"):
        mp.setattr(os, name, wrap_mutation(getattr(os, name), both_paths=True))

    def denied(kind):
        def call(*args, **kwargs):
            violations.append((kind, "external effect"))
            raise AssertionError(f"forbidden {kind}")
        return call

    for obj, attr, kind in ((socket.socket, "connect", "network"), (socket, "create_connection", "network"),
                            (subprocess, "Popen", "process"), (os, "system", "process"),
                            (sqlite3, "connect", "database")):
        mp.setattr(obj, attr, denied(kind))
    try:
        artifacts = importlib.import_module("scripts.research.pipeline_artifacts")
        ensure = importlib.import_module("scripts.plan.ensure_watchlist_plan")
        builder = importlib.import_module("scripts.research.build_research_summary")
        orchestrator = importlib.import_module("src.research.orchestrator")
        algorithm = importlib.import_module("src.plan.d1_algorithm")
        resolver = importlib.import_module("src.plan.plan_resolver")
        loader = importlib.import_module("trading.load_plan")
        main_decision = importlib.import_module("src.plan.main_decision")
        mp.setattr(loader, "QMTContext", denied("QMT constructor"))
        mp.setattr(importlib.import_module("src.trading_agent.qmt_client"), "QMTMCPClient", denied("QMT client"))
        mp.setattr(importlib.import_module("src.plan.qmt_holdings"), "fetch_holdings_map", denied("QMT holdings"))
        mp.setattr(algorithm, "fetch_holdings_map", denied("QMT holdings"))
        yield SimpleNamespace(artifacts=artifacts, ensure=ensure, builder=builder,
                              orchestrator=orchestrator, algorithm=algorithm,
                              resolver=resolver, loader=loader, main=main_decision,
                              violations=violations)
    finally:
        mp.undo()
        for key in list(sys.modules):
            if key.split(".")[0] in prefixes:
                del sys.modules[key]
        sys.modules.update(saved)
        assert not violations, violations


@pytest.fixture
def env(code, tmp_path, monkeypatch):
    assert tmp_path.resolve().is_relative_to(SCRATCH.resolve())
    for module in (code.ensure, code.builder, code.orchestrator, code.algorithm, code.resolver, code.loader, code.main):
        monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(code.loader, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(code.loader, "RUNTIME_DIR", tmp_path / "data/runtime")
    return SimpleNamespace(**vars(code), root=tmp_path, monkeypatch=monkeypatch,
                           canonical=tmp_path / f"data/plans/{DATE}/watchlist_plan.json",
                           runtime=tmp_path / f"data/runtime/watchlist_plan_{DATE}.json")


def _deliver(env, plan):
    _write(env.canonical, plan)
    md = env.root / f"chzl_kg/投研交易/盘前预案/{DATE}.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("# synthetic contract\n" + "fixture only\n" * 6)


def _research(env):
    fields = {
        "R1": {"style": "fixture", "position_cap_suggestion": 0.0},
        "R2": {"main_lines": [], "consensus_themes": [], "empty_pool_reason": "fixture no mainline"},
        "R3": {"resonance_top_themes": []}, "R4": {"top_events": []},
        "R5": {"profiles": []}, "R6": {"counter_arguments": [], "hard_rejects": []},
        "R7": {"main_force": {}, "northbound": {}, "staleness_status": "ok", "resolved_trade_date": "20261022"},
    }
    paths = {}
    for unit, filename in env.artifacts.UNIT_FILES.items():
        rel = f"data/research/{DATE}/{filename}"
        _write(env.root / rel, {"trade_date": DATE, "status": "complete", "confidence": None if unit == "R5" else 0,
                                "generated_at": EARLY, **fields[unit]})
        paths[unit] = rel
    _write(env.root / f"data/raw/{DATE}/manifest.json", {"date": DATE, "global_severity": 0, "sources": {}})
    # Real saved-summary preflight requires the producer's versioned handoff,
    # not a handcrafted legacy artifacts-only object. Partial/zero inputs stay
    # legal; this fixture does not invent complete research or MD delivery.
    summary, missing = env.builder.make_summary(DATE)
    assert missing == []
    _write(env.root / f"data/research/{DATE}/research_summary.json", summary)
    return paths


def _fake_llm(env, *, still_unready=False):
    calls = []
    env.monkeypatch.setattr(env.ensure, "_hermes_bin", lambda: "/offline/hermes")

    def run(cmd, **kwargs):
        calls.append(cmd)
        assert cmd[cmd.index("-p") + 1] == "canghai-plan"
        assert cmd[cmd.index("-s") + 1] == "main_decision_v1"
        assert Path(kwargs["cwd"]) == env.root
        generated = "2026-10-23T09:00:00+08:00"
        _deliver(env, _plan(generated_at=generated, production_ready=not still_unready,
                            meta={"research_completion_passed": not still_unready}))
        return SimpleNamespace(returncode=0)

    env.monkeypatch.setattr(env.ensure.subprocess, "run", run)
    return calls


def test_bug01_interim_can_publish_but_is_not_completed(env, capsys):
    plan = _plan(production_ready=False, meta={"research_completion_passed": False})
    _deliver(env, plan)
    calls = _fake_llm(env)
    seen = []
    original = env.ensure._upstream_ready
    env.monkeypatch.setattr(env.ensure, "_upstream_ready", lambda date: (seen.append(date), original(date))[1])
    before = env.canonical.read_bytes()
    assert env.ensure.ensure_plan(DATE, force=True) == 1
    assert seen == [DATE] and calls == []
    assert env.canonical.read_bytes() == before
    assert env.artifacts.read_object(env.runtime) == plan
    assert env.artifacts.plan_reassessment_reasons(plan)
    assert "reassessment required" in capsys.readouterr().err


@pytest.mark.parametrize("no_llm", [False, True])
def test_bug01_complete_llm_no_trade_is_protected_even_force(env, no_llm):
    _deliver(env, _plan(production_ready=True, meta={"research_completion_passed": True}))
    calls = _fake_llm(env)
    before = env.canonical.read_bytes()
    assert env.ensure.ensure_plan(DATE, force=True, no_llm=no_llm) == 0
    assert env.canonical.read_bytes() == before and calls == []
    assert env.artifacts.read_object(env.runtime)["risk_limits"]["target_total_position_pct"] == 0.0


@pytest.mark.parametrize("still_unready,expected", [(False, 0), (True, 1)])
def test_bug01_fresh_batch_reassesses_via_real_retry_not_python(env, still_unready, expected):
    _deliver(env, _plan(production_ready=False))
    _research(env)
    calls = _fake_llm(env, still_unready=still_unready)
    assert env.ensure.ensure_plan(DATE) == expected
    assert len(calls) == 1
    result = env.artifacts.read_object(env.runtime)
    assert result == env.artifacts.read_object(env.canonical)
    assert result["production_ready"] is not still_unready
    assert result["mode"] == "dry_run" and result["autonomous_trading_enabled"] is False
    assert result["requires_user_confirmation"] is True
    assert result["risk_limits"]["target_total_position_pct"] == 0.0


def test_bug01_failed_reassessment_cannot_fall_through_to_rule_overwrite(env):
    interim = _plan(production_ready=False)
    _deliver(env, interim)
    _research(env)
    env.monkeypatch.setattr(env.ensure, "_hermes_bin", lambda: "/offline/hermes")

    def failed_llm(cmd, **kwargs):
        env.canonical.write_text("incomplete LLM JSON")
        return SimpleNamespace(returncode=17)

    env.monkeypatch.setattr(env.ensure.subprocess, "run", failed_llm)
    assert env.ensure.ensure_plan(DATE) == 1
    assert env.canonical.read_text() == "incomplete LLM JSON"  # no fabricated rule replacement
    assert env.artifacts.read_object(env.runtime) == interim


@pytest.mark.parametrize("fault", ["old_summary", "old_r1", "wrong_date", "bad_pointer", "unready_summary", "unready_r1", "different_run", "newer_run", "no_llm"])
def test_bug01_interim_never_reuses_old_or_unowned_research(env, fault):
    _deliver(env, _plan(production_ready=False))
    paths = _research(env)
    summary_path = env.root / f"data/research/{DATE}/research_summary.json"
    summary = env.artifacts.read_object(summary_path)
    if fault == "old_summary":
        os.utime(summary_path, ns=(1, 1))
    elif fault == "old_r1":
        os.utime(env.root / paths["R1"], ns=(1, 1))
    elif fault == "wrong_date":
        summary["trade_date"] = "20261022"
        _write(summary_path, summary)
    elif fault == "bad_pointer":
        summary["artifacts"]["R1"] = "data/research/20261022/R1_style.json"
        _write(summary_path, summary)
    elif fault == "unready_summary":
        summary["production_ready"] = False
        _write(summary_path, summary)
    elif fault == "unready_r1":
        r1_path = env.root / paths["R1"]
        _write(r1_path, {**env.artifacts.read_object(r1_path), "production_ready": False})
    elif fault in {"different_run", "newer_run"}:
        _write(env.root / f"data/health/research_pipeline_{DATE}.json",
               {"run_id": "current-run", "started_ns": 1 if fault == "different_run" else 9_999_999_999_999_999_999})
    calls = _fake_llm(env)
    before = env.canonical.read_bytes()
    assert env.ensure.ensure_plan(DATE, no_llm=fault == "no_llm") == 1
    assert calls == [] and env.canonical.read_bytes() == before


@pytest.mark.parametrize("changes", [
    {"mode": "live"}, {"autonomous_trading_enabled": True}, {"requires_user_confirmation": False},
])
def test_bug01_readiness_never_grants_authorization(env, changes):
    bad = _plan(production_ready=False, no_trade=False, **changes)
    _deliver(env, bad)
    with pytest.raises(ValueError, match="unready"):
        env.loader.validate_plan_for_date(bad, DATE)
    with pytest.raises(ValueError, match="unready"):
        env.artifacts.publish_runtime_plan(env.root, DATE)
    assert not env.runtime.exists()


def test_bug01_ready_flag_cannot_promote_existing_restricted_runtime(env):
    _deliver(env, _plan(production_ready=False))
    env.artifacts.publish_runtime_plan(env.root, DATE)
    old = env.runtime.read_bytes()
    _deliver(env, _plan(production_ready=True, no_trade=False, mode="live",
                        autonomous_trading_enabled=True, requires_user_confirmation=False))
    with pytest.raises(ValueError, match="cannot expand live authorization"):
        env.artifacts.publish_runtime_plan(env.root, DATE)
    assert env.runtime.read_bytes() == old


def test_bug01_root_ready_does_not_override_meta_unfinished(env):
    plan = _plan(production_ready=True, meta={"research_completion_passed": False})
    _deliver(env, plan)
    assert env.ensure.ensure_plan(DATE, force=True, no_llm=True) == 1
    assert env.artifacts.read_object(env.runtime) == plan
    bad = {**plan, "no_trade": False, "mode": "live"}
    with pytest.raises(ValueError, match="unready"):
        env.loader.validate_plan_for_date(bad, DATE)


@pytest.mark.parametrize("status", ["complete", "degraded", "partial", "failed", None])
def test_bug02_explicit_zero_budget_never_becomes_fifty_percent(env, status):
    assert env.algorithm.step1_position_cap({"status": status, "position_cap_suggestion": 0}, {}) == 0.0


@pytest.mark.parametrize("cap,expected", [(0.2, 0.2), (0.8, 0.5), (None, 0.5)])
def test_bug02_degradation_never_increases_supplied_budget(env, cap, expected):
    assert env.algorithm.step1_position_cap({"status": "degraded", "position_cap_suggestion": cap}, {}) == expected


@pytest.mark.parametrize("cap", [float("nan"), float("inf"), -0.1, 1.1, "0", False])
def test_bug02_invalid_budget_fails_closed(env, cap):
    assert env.algorithm.step1_position_cap({"status": "complete", "position_cap_suggestion": cap}, {}) == 0.0


def test_bug02_existing_caps_and_severity_protection_survive(env):
    fn = env.algorithm.step1_position_cap
    assert fn({"status": "complete", "position_cap_suggestion": 0.75}, {}) == 0.75
    assert fn({"status": "complete", "position_cap_suggestion": 0.75}, {"fetch_global_severity": 1}) == 0.6
    assert fn({"status": "complete", "position_cap_suggestion": 0.75}, {"fetch_global_severity": 3}) == 0.0
    assert fn({"status": "complete", "position_cap_suggestion": 0.75}, {"fetch_global_severity": None}) == 0.0
    assert fn(None, {}) == 0.5


@pytest.mark.parametrize("sync", [True, False])
@pytest.mark.parametrize("canonical", ["absent", "fallback", "wrong_date", "invalid_json", "valid"])
def test_bug03_resolver_is_read_only_canonical_authority(env, sync, canonical):
    _write(env.runtime, _plan(trade_date="20261022", no_trade=False, mode="live",
                              autonomous_trading_enabled=True, requires_user_confirmation=False))
    if canonical != "absent":
        _deliver(env, _plan(**({"mode": "fallback", "meta": {"python_fallback": True}} if canonical == "fallback"
                               else {"trade_date": "20261022"} if canonical == "wrong_date" else {})))
        if canonical == "invalid_json":
            env.canonical.write_text("not JSON")
    before = env.canonical.read_bytes() if env.canonical.exists() else None
    runtime_before = env.runtime.read_bytes()
    result = env.resolver.resolve_authoritative_plan("2026-10-23", sync=sync)
    assert (result is not None) is (canonical == "valid")
    if result:
        assert result["trade_date"] == DATE and result["mode"] == "dry_run"
    assert (env.canonical.read_bytes() if env.canonical.exists() else None) == before
    assert env.runtime.read_bytes() == runtime_before


@pytest.mark.parametrize("date", ["../20261023", "202610230", "20261323", None])
def test_bug03_malformed_requested_date_is_not_repaired(env, date):
    assert env.resolver.resolve_authoritative_plan(date) is None
    assert not env.canonical.exists()


@pytest.mark.parametrize("value,expected", [(None, None), (0, 0.0), (0.7, 0.7), (1, 1.0),
                                           (True, None), (False, None), ("0", None),
                                           (float("nan"), None), (float("inf"), None), (-0.1, None), (1.1, None)])
def test_bug11_null_and_measured_zero_remain_distinct(env, value, expected):
    assert env.artifacts.confidence({"confidence": value}) == expected
    assert env.artifacts.confidence({}) is None


def test_bug11_real_summary_and_d1_consumer_preserve_null(env):
    paths = _research(env)
    summary, missing = env.builder.make_summary(DATE)
    assert missing == []
    assert summary["confidence"]["R5"] is None
    assert summary["confidence"]["R6"] == 0.0
    roundtrip = json.loads(json.dumps(summary, allow_nan=False))
    assert roundtrip["confidence"]["R5"] is None
    assert roundtrip["confidence"]["R6"] == 0.0
    # Exercise the real D1 consumer. Only external QMT and empty-price collector
    # boundaries are substituted; pool/summary/metadata implementations are real.
    env.monkeypatch.setattr(env.algorithm, "fetch_holdings_map", lambda: {})
    xtick = SimpleNamespace(XTickCollector=lambda: SimpleNamespace())
    env.monkeypatch.setitem(sys.modules, "src.collectors.xtick_collector", xtick)
    plan = env.main.build_watchlist_plan(DATE, summary, {}, fallback=True)
    assert plan["meta"]["research_confidence"]["R5"] is None
    assert plan["meta"]["research_confidence"]["R6"] == 0.0
    assert plan["risk_limits"]["target_total_position_pct"] == 0.0
    assert plan["autonomous_trading_enabled"] is False
    (env.root / paths["R5"]).unlink()
    _, unit_meta, missing = env.builder.collect_artifacts(DATE)
    assert missing == ["R5"] and unit_meta["R5"]["confidence"] is None


def test_bug01_missing_human_delivery_does_not_replace_llm(env):
    _write(env.canonical, _plan(production_ready=True))
    before = env.canonical.read_bytes()
    calls = _fake_llm(env)
    assert env.ensure.ensure_plan(DATE, force=True, no_llm=True) == 1
    assert env.canonical.read_bytes() == before and calls == []
    assert not env.runtime.exists()
