"""Version preflight parity, synthetic inputs and fake transport only.

Run via a pre-collection offline guard, with basetemp beneath Hermes scratch.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

_spec = importlib.util.spec_from_file_location(
    "_input_version_fixtures",
    Path(__file__).resolve().parents[1] / "test_canghai_repair_plan_contracts_20261023.py",
)
assert _spec is not None and _spec.loader is not None
legacy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(legacy)
code = legacy.code
env = legacy.env
DATE = legacy.DATE
RUN = "synthetic-input-version-run"


def prepare(env, *, bound=True, partial=False, auxiliary_binding=True):
    legacy._research(env)
    if partial:
        (env.root / f"data/research/{DATE}/R1_style.json").unlink()
    state = {"trade_date": DATE, "run_id": RUN, "started_ns": 1,
             "stages": {}, "contract_results": {}}
    if bound:
        for unit in env.artifacts.UNIT_FILES:
            if partial and unit == "R1":
                continue
            state["stages"][unit] = {"attempt": 1, "attempt_started_ns": 1}
            path, _, version = env.artifacts.inspect_delivery(env.root, DATE, unit, "json")
            state["contract_results"][unit] = {"json": {
                **version, "passed": True, "run_id": RUN, "attempt": 1}}
        legacy._write(env.root / f"data/health/research_pipeline_{DATE}.json", state)
    # A current producer explicitly binds the reviewed read scope, even when
    # optional snapshots are absent. Run ownership is a separate contract.
    kwargs = {"run_id": RUN if bound else ""}
    if auxiliary_binding:
        kwargs["auxiliary_paths"] = env.builder.approved_d1_auxiliary_paths(DATE)
    summary, _ = env.builder.make_summary(DATE, **kwargs)
    path = env.root / f"data/research/{DATE}/research_summary.json"
    legacy._write(path, summary)
    if bound:
        state["stages"]["summary"] = {"attempt": 1, "attempt_started_ns": 1}
        state["contract_results"]["summary"] = {
            **env.artifacts.file_version(env.root, path),
            "passed": True, "run_id": RUN, "attempt": 1}
        legacy._write(env.root / f"data/health/research_pipeline_{DATE}.json", state)
    env.monkeypatch.delenv("CHZL_RESEARCH_RUN_ID", raising=False)
    return path


def launcher(env, mutate=None, rc=0):
    calls = []
    env.monkeypatch.setattr(env.ensure, "_hermes_bin", lambda: "/offline/hermes")

    def run(cmd, **kwargs):
        calls.append(cmd)
        assert cmd[cmd.index("-p") + 1] == "canghai-plan"
        assert cmd[cmd.index("-s") + 1] == "main_decision_v1"
        assert Path(kwargs["cwd"]) == env.root
        legacy._deliver(env, legacy._plan(generated_at="2026-10-23T09:01:00+08:00"))
        if mutate:
            mutate()
        return SimpleNamespace(returncode=rc)

    env.monkeypatch.setattr(env.ensure.subprocess, "run", run)
    return calls


@pytest.mark.parametrize("bound", [False, True])
def test_legacy_auxiliary_binding_is_not_self_signed(env, bound):
    summary_path = prepare(env, bound=bound, auxiliary_binding=False)
    original = summary_path.read_bytes()
    calls = launcher(env)
    ok, note = env.ensure.retry_llm(DATE)
    assert not ok and "auxiliary binding missing" in note
    assert calls == [] and summary_path.read_bytes() == original
    assert not env.canonical.exists() and not env.runtime.exists()
    assert not (env.root / f"data/logs/research_shell/{DATE}").exists()


def test_standalone_delivery_does_not_invent_reusable_owner(env):
    prepare(env, bound=False)
    calls = launcher(env)
    ok, note = env.ensure.retry_llm(DATE)
    assert ok, note
    assert len(calls) == 1
    logs = env.root / f"data/logs/research_shell/{DATE}"
    inputs = list(logs.glob("D1_retry_*/inputs.json"))
    assert len(inputs) == 1
    assert env.artifacts.read_object(inputs[0])["saved"]["run_id"] is None
    assert list(logs.glob("D1_retry_*/receipt.json")) == []
    plan = env.artifacts.read_object(env.runtime)
    assert plan == env.artifacts.read_object(env.canonical)
    assert plan["no_trade"] is True and plan["execution_pool"] == []
    assert plan["risk_limits"]["target_total_position_pct"] == 0
    assert plan["autonomous_trading_enabled"] is False
    assert plan["requires_user_confirmation"] is True
    # An ownerless standalone delivery still cannot enter trusted inheritance.
    legacy._write(env.root / f"data/health/research_pipeline_{DATE}.json",
                  {"trade_date": DATE, "run_id": ""})
    with pytest.raises(ValueError, match="research owner missing"):
        env.ensure._selective_context(DATE, plan)


def test_owned_delivery_cannot_skip_failed_reuse_receipt(env):
    prepare(env)
    calls = launcher(env)

    def reject_receipt(*args):
        raise ValueError("synthetic checked receipt failure")

    env.monkeypatch.setattr(env.ensure, "_record_d1_delivery", reject_receipt)
    ok, note = env.ensure.retry_llm(DATE)
    assert not ok and "synthetic checked receipt failure" in note
    assert len(calls) == 1
    assert not list((env.root / f"data/logs/research_shell/{DATE}").glob("D1_retry_*/receipt.json"))


def change(env, kind):
    path = env.root / f"data/research/{DATE}/research_summary.json"
    state_path = env.root / f"data/health/research_pipeline_{DATE}.json"
    if kind == "missing_summary":
        path.unlink()
    elif kind == "legacy_summary":
        summary = env.artifacts.read_object(path)
        summary.pop("input_manifest")
        legacy._write(path, summary)
    elif kind in {"primary_same_mtime", "missing_primary"}:
        primary = env.root / f"data/research/{DATE}/R1_style.json"
        before = primary.stat()
        if kind == "missing_primary":
            primary.unlink()
        else:
            raw = primary.read_bytes()
            assert b"fixture" in raw
            primary.write_bytes(raw.replace(b"fixture", b"changed", 1))
            os.utime(primary, ns=(before.st_atime_ns, before.st_mtime_ns))
            assert primary.stat().st_size == before.st_size
            assert primary.stat().st_mtime_ns == before.st_mtime_ns
    elif kind in {"wrong_run", "attempt"}:
        state = env.artifacts.read_object(state_path)
        if kind == "wrong_run":
            state["run_id"] = "newer-synthetic-run"
        else:
            state["stages"]["R1"]["attempt"] = 2
        legacy._write(state_path, state)
    elif kind == "corrupt_state":
        state_path.write_text("bad state")
    elif kind == "empty_state":
        legacy._write(state_path, {})
    elif kind == "env_run":
        env.monkeypatch.setenv("CHZL_RESEARCH_RUN_ID", "wrong-environment-run")
    elif kind == "old_summary":
        summary = env.artifacts.read_object(path)
        summary["confidence"]["R1"] = 0.7
        legacy._write(path, summary)
    else:
        raise AssertionError(kind)


@pytest.mark.parametrize("kind", ["missing_summary", "legacy_summary", "primary_same_mtime",
                                  "missing_primary", "wrong_run", "attempt", "corrupt_state",
                                  "env_run", "old_summary", "empty_state"])
def test_retry_rejects_same_preflight_faults_before_transport(env, kind):
    prepare(env)
    change(env, kind)
    calls = launcher(env)
    ok, note = env.ensure.retry_llm(DATE)
    assert not ok, note
    assert calls == []
    assert not env.runtime.exists()
    assert not (env.root / f"data/logs/research_shell/{DATE}/D1_llm_retry.log").exists()


@pytest.mark.parametrize("bound,partial", [(True, False), (False, False), (True, True)])
def test_valid_versioned_partial_and_zero_budget_delivery(env, bound, partial):
    prepare(env, bound=bound, partial=partial)
    calls = launcher(env)
    ok, note = env.ensure.retry_llm(DATE)
    assert ok, note
    assert len(calls) == 1
    plan = env.artifacts.read_object(env.runtime)
    assert plan == env.artifacts.read_object(env.canonical)
    assert plan["no_trade"] is True and plan["execution_pool"] == []
    assert plan["risk_limits"]["target_total_position_pct"] == 0
    assert plan["mode"] == "dry_run"
    assert plan["autonomous_trading_enabled"] is False
    assert plan["requires_user_confirmation"] is True


@pytest.mark.parametrize("kind", ["primary_same_mtime", "missing_summary", "wrong_run", "attempt", "old_summary"])
def test_input_changes_during_llm_refuse_handoff_without_restoring_analysis(env, kind):
    prepare(env)
    calls = launcher(env, lambda: change(env, kind))
    ok, note = env.ensure.retry_llm(DATE)
    assert not ok, note
    assert len(calls) == 1 and not env.runtime.exists()
    assert env.artifacts.read_object(env.canonical)["generated_at"] == "2026-10-23T09:01:00+08:00"


def test_new_valid_summary_during_llm_cannot_switch_input_batch(env):
    prepare(env, bound=False)

    def refresh():
        change(env, "primary_same_mtime")
        summary, _ = env.builder.make_summary(
            DATE, auxiliary_paths=env.builder.approved_d1_auxiliary_paths(DATE))
        legacy._write(env.root / f"data/research/{DATE}/research_summary.json", summary)

    launcher(env, refresh)
    ok, note = env.ensure.retry_llm(DATE)
    assert not ok, note
    assert not env.runtime.exists() and env.canonical.exists()


def test_standalone_cannot_deliver_after_new_run_appears(env):
    prepare(env, bound=False)
    launcher(env, lambda: legacy._write(
        env.root / f"data/health/research_pipeline_{DATE}.json", {"run_id": RUN}))
    ok, note = env.ensure.retry_llm(DATE)
    assert not ok, note
    assert not env.runtime.exists() and env.canonical.exists()


@pytest.mark.parametrize("force", [False, True])
def test_preflight_failure_preserves_rejected_llm_bytes(env, force):
    prepare(env)
    legacy._deliver(env, legacy._plan(production_ready=False, mode="live", no_trade=False))
    change(env, "primary_same_mtime")
    before = env.canonical.read_bytes()
    calls = launcher(env)
    assert env.ensure.ensure_plan(DATE, force=force) == 1
    assert env.canonical.read_bytes() == before
    assert calls == [] and not env.runtime.exists()


@pytest.mark.parametrize("force", [False, True])
def test_failed_preflight_does_not_add_rule_fallback_completeness_gate(env, force):
    legacy._research(env)
    change(env, "missing_summary")
    calls = launcher(env)
    fallback_calls = []
    import sys
    from types import ModuleType
    fallback = ModuleType("src.execute.fallback")

    def run(date):
        fallback_calls.append(date)
        legacy._deliver(env, legacy._plan(decision_source="python_fallback", mode="fallback"))

    setattr(fallback, "run_plan_fallback", run)
    env.monkeypatch.setitem(sys.modules, fallback.__name__, fallback)
    assert env.ensure.ensure_plan(DATE, force=force) == 0
    assert calls == [] and fallback_calls == [DATE]
    assert not env.runtime.exists()
