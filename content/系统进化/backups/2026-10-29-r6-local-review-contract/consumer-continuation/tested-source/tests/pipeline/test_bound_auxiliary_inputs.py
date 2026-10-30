"""Synthetic-only INPUT-01: reviewed-code authority and actual bound reads.

No live data/settings/account/network imports. Production helpers are copied
into scratch before import; only make_summary's unrelated orchestrator I/O is
substituted. Run under a collection-before-import audit guard.
"""
from __future__ import annotations

from copy import deepcopy
import importlib
import json
import os
from pathlib import Path
import shutil
import sys
from types import ModuleType, SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
DATE = "20990106"
RUN = "synthetic-bound-auxiliary"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def resign(b, summary):
    manifest = summary["input_manifest"]
    manifest["sha256"] = b._digest({k: v for k, v in manifest.items() if k != "sha256"})


@pytest.fixture
def native(tmp_path):
    root = tmp_path / "isolated-application"
    for name in ("scripts", "scripts/research"):
        path = root / name
        path.mkdir(parents=True, exist_ok=True)
        (path / "__init__.py").write_text("")
    for name in ("pipeline_artifacts.py", "build_research_summary.py"):
        shutil.copyfile(REPO / "scripts/research" / name, root / "scripts/research" / name)
    prefixes = ("scripts", "src")
    saved_modules = {k: v for k, v in sys.modules.items()
                     if any(k == p or k.startswith(p + ".") for p in prefixes)}
    old_path = list(sys.path)
    for key in saved_modules:
        del sys.modules[key]
    sys.path.insert(0, str(root))
    try:
        b = importlib.import_module("scripts.research.build_research_summary")
        a = importlib.import_module("scripts.research.pipeline_artifacts")
        fields = {
            "R1": {"style": "synthetic", "position_cap_suggestion": 0},
            "R2": {"main_lines": [], "empty_pool_reason": "synthetic zero budget", "consensus_themes": []},
            "R3": {"resonance_top_themes": []}, "R4": {"top_events": []},
            "R5": {"profiles": []},
            "R6": {"counter_arguments": [], "hard_rejects": [{"ts_code": "000001.SZ", "reason": "synthetic veto"}]},
            "R7": {"main_force": {}},
        }
        state = {"trade_date": DATE, "run_id": RUN, "stages": {}, "contract_results": {}}
        for unit, filename in a.UNIT_FILES.items():
            path = root / f"data/research/{DATE}/{filename}"
            save(path, {"trade_date": DATE, "run_id": RUN, "attempt": 1,
                        "status": "partial" if unit == "R2" else "complete", **fields[unit]})
            fp = a.file_version(root, path)
            state["stages"][unit] = {"attempt": 1, "attempt_started_ns": fp["mtime_ns"] - 1}
            state["contract_results"][unit] = {"json": {**fp, "passed": True, "run_id": RUN, "attempt": 1}}
        state_path = root / f"data/health/research_pipeline_{DATE}.json"
        save(state_path, state)
        payloads = {
            "attention": {"trade_date": DATE, "persistent": [], "surge": [], "zero": 0, "unknown": None},
            "emotion_cycle": {"trade_date": DATE, "confidence": 0, "phase": None,
                              "captured_at": "2099-01-06T07:15:00+08:00", "metrics_date": "20990105"},
        }
        scope = b.approved_d1_auxiliary_paths(DATE)
        for name, value in payloads.items():
            save(root / scope[name][0], value)
        # Stub only unrelated application imports; _collect, snapshots, binding,
        # receipts, consumers, make_summary and verify_saved_inputs stay real.
        src = ModuleType("src"); src.__path__ = []
        research = ModuleType("src.research"); research.__path__ = []
        orchestrator = ModuleType("src.research.orchestrator")
        orchestrator.__dict__["load_fetch_manifest"] = lambda date: {}
        orchestrator.__dict__["build_research_summary"] = lambda date, fetch, artifacts, meta: {
            "schema_version": "research_summary_v1", "trade_date": date, "artifacts": artifacts,
            "confidence": {"R1": 0}, "no_trade": True, "position_cap": 0}
        checks = ModuleType("src.research.contract_checks")
        checks.__dict__["run_research_checks"] = lambda data, date: {}
        research.__dict__["contract_checks"] = checks
        sys.modules.update({"src": src, "src.research": research,
                            "src.research.orchestrator": orchestrator,
                            "src.research.contract_checks": checks})
        yield SimpleNamespace(b=b, a=a, root=root, state=state, state_path=state_path,
                              scope=scope, payloads=payloads)
    finally:
        sys.path[:] = old_path
        for key in list(sys.modules):
            if any(key == p or key.startswith(p + ".") for p in prefixes):
                del sys.modules[key]
        sys.modules.update(saved_modules)


def make(n, approved=True):
    summary, _ = n.b.make_summary(DATE, run_id=RUN, auxiliary_paths=n.scope if approved else None)
    return summary


def consume(n, summary):
    return n.b.consume_bound_auxiliary_inputs(summary, root=n.root, approved_paths=n.scope)


def test_actual_summary_and_consumers_preserve_main_and_auxiliary_identity(native):
    n = native
    summary = make(n)
    before = deepcopy(summary)
    main = n.b.consume_authorized_inputs(summary, root=n.root)
    aux = consume(n, summary)
    assert set(main) == set(n.a.UNIT_FILES) == set(summary["artifacts"])
    assert {k: v["payload"] for k, v in aux.items()} == n.payloads
    assert main["R1"]["position_cap_suggestion"] == summary["position_cap"] == 0
    assert summary["no_trade"] is True and summary["confidence"]["R1"] == 0
    assert main["R2"]["status"] == "partial"
    assert main["R6"]["hard_rejects"] == summary["hard_rejects"]
    bound = summary["input_manifest"]["bound_auxiliary_inputs"]
    assert bound["run_id"] == RUN and bound["trade_date"] == DATE
    assert bound["main_version_sha256"] == n.b._main_version(summary["input_manifest"])
    assert bound["trading_authorization_granted"] is False
    assert aux["emotion_cycle"]["payload"]["metrics_date"] == "20990105"
    assert summary == before


def test_only_reviewed_paths_read_and_default_never_promotes_adapter(native, monkeypatch):
    n = native
    seen = []
    original = n.b._snapshot
    def track(root, path):
        seen.append(str(path.relative_to(root)))
        return original(root, path)
    monkeypatch.setattr(n.b, "_snapshot", track)
    summary = make(n)
    candidates = summary["input_manifest"]["auxiliary_candidates"]
    assert all(not r["authorized"] and r["status"] == "pending_approval" for r in candidates.values())
    seen.clear()
    assert n.b.consume_bound_auxiliary_inputs(summary, root=n.root) == {}
    assert not set(seen) & {p[0] for p in n.scope.values()}
    seen.clear()
    consume(n, summary)
    assert set(seen) == set(summary["artifacts"].values()) | {p[0] for p in n.scope.values()}
    # Old adapter approval stays only evidence, even if a report self-signs it.
    legacy = make(n, approved=False)
    legacy["input_manifest"]["auxiliary_candidates"] = n.b.auxiliary_input_manifest(
        DATE, root=n.root, approved_paths={"attention": n.scope["attention"]})
    legacy["authorized"] = True
    resign(n.b, legacy)
    with pytest.raises(ValueError, match="binding missing"):
        consume(n, legacy)


@pytest.mark.parametrize("fault", ["missing", "wrong_date", "missing_date", "not_object", "bad_json", "symlink"])
def test_invalid_or_missing_snapshots_are_explicit_gaps_not_zeros(native, fault):
    n = native
    path = n.root / n.scope["attention"][0]
    if fault == "missing":
        path.unlink()
    elif fault == "wrong_date":
        save(path, {"trade_date": "20990105", "zero": 0})
    elif fault == "missing_date":
        save(path, {"zero": 0})
    elif fault == "not_object":
        save(path, [])
    elif fault == "bad_json":
        path.write_text("{")
    else:
        path.unlink()
        path.symlink_to("emotion_cycle.json")
    summary = make(n)
    result = consume(n, summary)
    assert result["attention"]["status"] == "unavailable"
    assert "payload" not in result["attention"] and "version" not in result["attention"]
    assert result["emotion_cycle"]["payload"] == n.payloads["emotion_cycle"]
    assert summary["hard_rejects"] and summary["position_cap"] == 0
    assert set(summary["artifacts"]) == set(n.a.UNIT_FILES)
    if fault == "missing":
        assert not path.exists()  # No fetch/reconstruction side effect.
        save(path, n.payloads["attention"])
        assert consume(n, summary)["attention"]["status"] == "unavailable"


@pytest.mark.parametrize("fault", ["bytes", "mtime", "deleted", "date", "path", "hash", "size",
                                  "schema", "run", "main_version", "main_attempt", "receipt", "projection"])
def test_drift_rejected_even_with_rehashed_manifest(native, fault):
    n = native
    summary = make(n)
    manifest = summary["input_manifest"]
    bound = manifest["bound_auxiliary_inputs"]
    record = bound["records"]["attention"]
    path = n.root / n.scope["attention"][0]
    if fault == "bytes":
        save(path, {**n.payloads["attention"], "zero": 1})
    elif fault == "mtime":
        os.utime(path, ns=(path.stat().st_atime_ns, path.stat().st_mtime_ns + 1000000))
    elif fault == "deleted":
        path.unlink()
    elif fault == "date":
        bound["trade_date"] = "20990105"
    elif fault == "path":
        record["path"] = "data/research/20990105/attention_signals.json"
    elif fault == "hash":
        record["sha256"] = "0" * 64
    elif fault == "size":
        record["bytes"] += 1
    elif fault == "schema":
        bound["schema_version"] = "other"
    elif fault == "run":
        bound["run_id"] = "other"
    elif fault == "main_version":
        bound["main_version_sha256"] = "0" * 64
    elif fault in {"main_attempt", "receipt"}:
        if fault == "main_attempt":
            n.state["stages"]["R1"]["attempt"] = 2
        else:
            n.state["contract_results"]["R1"]["json"]["sha256"] = "0" * 64
        save(n.state_path, n.state)
    else:
        summary["hard_rejects"] = []
    resign(n.b, summary)
    with pytest.raises((ValueError, OSError)):
        consume(n, summary)


@pytest.mark.parametrize("fault", ["extra", "wrong_date", "traversal", "absolute", "wildcard"])
def test_reviewed_caller_cannot_expand_approved_scope(native, fault):
    n = native
    scope = deepcopy(n.scope)
    if fault == "extra":
        scope["corrections"] = ["data/corrections/2099/error_case_1.md"]
    else:
        scope["attention"] = [{"wrong_date": "data/research/20990105/attention_signals.json",
                                "traversal": "../.env", "absolute": "/outside/attention_signals.json",
                                "wildcard": f"data/research/{DATE}/*.json"}[fault]]
    with pytest.raises(ValueError, match="exact approved"):
        n.b.make_summary(DATE, run_id=RUN, auxiliary_paths=scope)


def test_saved_summary_pre_and_post_delivery_rechecks_bound_versions(native):
    n = native
    summary = make(n)
    path = n.root / f"data/research/{DATE}/research_summary.json"
    save(path, summary)
    fp = n.a.file_version(n.root, path)
    n.state["stages"]["summary"] = {"attempt": 1, "attempt_started_ns": fp["mtime_ns"] - 1}
    n.state["contract_results"]["summary"] = {**fp, "passed": True, "run_id": RUN, "attempt": 1}
    save(n.state_path, n.state)
    first, saved = n.b.verify_saved_inputs(DATE, root=n.root, run_id=RUN, auxiliary_paths=n.scope)
    assert saved == summary and first == fp
    assert n.b.verify_saved_inputs(DATE, root=n.root, run_id=RUN, auxiliary_paths=n.scope)[0] == first
    save(n.root / n.scope["emotion_cycle"][0], {"trade_date": DATE, "confidence": 1})
    with pytest.raises(ValueError, match="version changed"):
        n.b.verify_saved_inputs(DATE, root=n.root, run_id=RUN, auxiliary_paths=n.scope)


def test_cli_uses_reviewed_code_for_actual_binding_and_preflight(native, monkeypatch):
    n = native
    monkeypatch.setattr(sys, "argv", ["build_research_summary.py", "--date", DATE])
    assert n.b.main() == 0
    path = n.root / f"data/research/{DATE}/research_summary.json"
    summary = json.loads(path.read_text())
    assert set(summary["input_manifest"]["bound_auxiliary_inputs"]["records"]) == set(n.scope)
    monkeypatch.setattr(sys, "argv", ["build_research_summary.py", "--date", DATE, "--verify-inputs"])
    assert n.b.main() == 0
    save(n.root / n.scope["attention"][0], {"trade_date": DATE, "zero": 1})
    with pytest.raises(ValueError, match="version changed"):
        n.b.main()
