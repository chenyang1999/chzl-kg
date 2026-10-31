"""Synthetic-only regressions for rejected LLM delivery preservation.

Run with the pre-collection offline guard and --basetemp in Hermes scratch.
The existing contract fixture relocates all imports; no Hermes process runs.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

_spec = importlib.util.spec_from_file_location(
    "_interim_contract_fixtures",
    Path(__file__).resolve().parents[1] / "test_canghai_repair_plan_contracts_20261023.py",
)
assert _spec is not None and _spec.loader is not None
legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(legacy)
code = legacy.code
env = legacy.env
DATE = legacy.DATE


def _reviewed_research(env):
    # Only synthetic positive transport scenarios use the current producer
    # contract. Do not alter the shared legacy/unbound fixture or review flags.
    legacy._research(env)
    summary, _ = env.builder.make_summary(
        DATE, auxiliary_paths=env.builder.approved_d1_auxiliary_paths(DATE))
    legacy._write(env.root / f"data/research/{DATE}/research_summary.json", summary)


@pytest.fixture
def fallback(env):
    calls = []
    module = ModuleType("src.execute.fallback")

    def run(date):
        calls.append(date)
        legacy._deliver(env, legacy._plan(decision_source="python_fallback", mode="fallback"))

    setattr(module, "run_plan_fallback", run)
    env.monkeypatch.setitem(sys.modules, module.__name__, module)
    return calls


def _bad(**changes):
    return legacy._plan(production_ready=False, mode="live", no_trade=False, **changes)


def _snapshot(env):
    return {str(p.relative_to(env.root)): p.read_bytes() for p in env.root.rglob("*") if p.is_file()}


@pytest.mark.parametrize("force", [False, True])
@pytest.mark.parametrize("no_llm", [False, True])
@pytest.mark.parametrize("fault", ["unready_live", "missing_generated", "bad_pool", "wrong_date", "nested_source", "conflicting_fallback", "conflicting_sources"])
def test_rejected_llm_is_preserved_not_certified(env, fallback, capsys, force, no_llm, fault):
    plan = _bad()
    if fault == "missing_generated":
        plan.pop("generated_at")
    elif fault == "bad_pool":
        plan["execution_pool"] = "not a list"
    elif fault == "wrong_date":
        plan["trade_date"] = "20261022"
    elif fault == "nested_source":
        plan.pop("decision_source")
        plan["meta"] = {"decision_source": "llm"}
    elif fault == "conflicting_fallback":
        plan["is_fallback"] = True
    elif fault == "conflicting_sources":
        plan["decision_source"] = "python_fallback"
        plan["meta"] = {"decision_source": "llm"}
    legacy._deliver(env, plan)
    legacy._research(env)
    with pytest.raises((OSError, ValueError, TypeError)) as error:
        env.artifacts.plan_artifact(env.root, DATE)
    calls = []
    env.monkeypatch.setattr(env.ensure, "retry_llm", lambda date: (calls.append(date) or False, "synthetic retry failed"))
    before = _snapshot(env)
    assert env.ensure.ensure_plan(DATE, force=force, no_llm=no_llm) == 1
    assert fallback == []
    assert _snapshot(env) == before  # no JSON/MD mutation, runtime, labels or backup
    assert len(calls) == (0 if no_llm else 1)
    stderr = capsys.readouterr().err
    assert "contract blocked" in stderr
    # Check the exact rejected contract rather than a generic fallback warning.
    assert str(error.value) in stderr


@pytest.mark.parametrize("initial", ["absent", "rejected_llm", "fallback"])
@pytest.mark.parametrize("result", ["rejected_llm", "corrupt", "removed"])
@pytest.mark.parametrize("retry_rc", [0, 17])
def test_retry_current_bytes_win_without_snapshot_restore(env, fallback, capsys, initial, result, retry_rc):
    if initial != "absent":
        legacy._deliver(env, _bad() if initial == "rejected_llm" else legacy._plan(decision_source="python_fallback", mode="fallback"))
    _reviewed_research(env)
    env.monkeypatch.setattr(env.ensure, "_hermes_bin", lambda: "/synthetic/hermes")
    written = []

    def fake_hermes(cmd, **kwargs):
        assert Path(kwargs["cwd"]) == env.root
        legacy._deliver(env, {**_bad(), "generated_at": "2026-10-23T09:01:00+08:00", "analysis": "new original analysis"})
        if result == "corrupt":
            env.canonical.write_bytes(b"new incomplete model JSON")
        elif result == "removed":
            env.canonical.unlink()
        written.append(_snapshot(env))
        return SimpleNamespace(returncode=retry_rc)

    env.monkeypatch.setattr(env.ensure.subprocess, "run", fake_hermes)
    rc = env.ensure.ensure_plan(DATE, force=True)
    # Without identifiable LLM provenance, legacy fallback remains permitted.
    protected = result == "rejected_llm" or initial == "rejected_llm"
    assert rc == (1 if protected else 0)
    assert len(written) == 1
    if protected:
        assert fallback == [] and _snapshot(env) == written[0]
        assert not env.runtime.exists()
        assert "contract blocked" in capsys.readouterr().err
    else:
        assert fallback == [DATE]


@pytest.mark.parametrize("no_llm", [False, True])
def test_real_absence_still_allows_conspicuous_rule_placeholder(env, fallback, no_llm, capsys):
    legacy._research(env)
    env.monkeypatch.setattr(env.ensure, "retry_llm", lambda date: (False, "synthetic no artifact"))
    assert env.ensure.ensure_plan(DATE, no_llm=no_llm) == 0
    assert fallback == [DATE] and not env.runtime.exists()
    assert "非大模型决策" in capsys.readouterr().out


def test_rejected_old_llm_can_be_repaired_by_real_retry(env, fallback):
    legacy._deliver(env, _bad())
    _reviewed_research(env)
    calls = legacy._fake_llm(env)
    assert env.ensure.ensure_plan(DATE, force=True) == 0
    assert len(calls) == 1 and fallback == []
    repaired = env.artifacts.read_object(env.runtime)
    assert repaired == env.artifacts.read_object(env.canonical)
    assert repaired["no_trade"] is True
    assert repaired["risk_limits"]["target_total_position_pct"] == 0.0
    assert repaired["mode"] == "dry_run"
    assert repaired["autonomous_trading_enabled"] is False
    assert repaired["requires_user_confirmation"] is True


def test_missing_research_does_not_fabricate_or_launch(env, fallback):
    legacy._deliver(env, _bad())
    before = _snapshot(env)
    env.monkeypatch.setattr(env.ensure, "retry_llm", lambda date: pytest.fail("missing research must block retry"))
    assert env.ensure.ensure_plan(DATE, force=True) == 1
    assert fallback == [] and _snapshot(env) == before
