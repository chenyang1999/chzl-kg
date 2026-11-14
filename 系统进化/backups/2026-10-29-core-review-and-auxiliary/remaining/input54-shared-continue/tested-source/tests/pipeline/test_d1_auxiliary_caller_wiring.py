"""Synthetic D1 caller regression; no model, business data or publication.

Exercise the real safety-net retry function and real bound input consumers.
Only the external model transport and downstream plan acceptance/publication
are substituted: this is not a complete plan-schema or production-model test.
The shell check below is syntax/source-order coverage, not a business replay.
"""
from __future__ import annotations

from copy import deepcopy
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
from types import SimpleNamespace

import pytest

from test_bound_auxiliary_inputs import DATE, RUN, REPO, make, native, save


def commit_summary(n, summary):
    path = n.root / f"data/research/{DATE}/research_summary.json"
    save(path, summary)
    fp = n.a.file_version(n.root, path)
    n.state["stages"]["summary"] = {"attempt": 1, "attempt_started_ns": fp["mtime_ns"] - 1}
    n.state["contract_results"]["summary"] = {**fp, "passed": True, "run_id": RUN, "attempt": 1}
    save(n.state_path, n.state)
    return path


@pytest.mark.parametrize("case", ["valid", "missing", "old-summary", "drift-before", "drift-during", "rebind-during"])
def test_real_safety_net_rechecks_approved_auxiliary_before_acceptance(native, monkeypatch, case):
    n = native
    if case == "missing":
        (n.root / n.scope["attention"][0]).unlink()
    summary = make(n, approved=case != "old-summary")
    commit_summary(n, summary)
    if case == "drift-before":
        save(n.root / n.scope["attention"][0], {"trade_date": DATE, "zero": 1})

    plan_dir = n.root / "scripts/plan"
    plan_dir.mkdir()
    (plan_dir / "__init__.py").write_text("")
    # Optional frozen source is used only for the baseline red comparison.
    source = Path(os.environ.get("INPUT01_TEST_CALLER_SOURCE", str(REPO / "scripts/plan/ensure_watchlist_plan.py")))
    shutil.copyfile(source, plan_dir / "ensure_watchlist_plan.py")
    caller = importlib.import_module("scripts.plan.ensure_watchlist_plan")
    monkeypatch.setenv("CHZL_RESEARCH_RUN_ID", RUN)
    monkeypatch.setattr(caller, "_hermes_bin", lambda: "/synthetic/hermes")
    verified, transports, publications, returned_aux = [], [], [], []
    real_verify = n.b.verify_saved_inputs

    def verify(*args, **kwargs):
        verified.append(deepcopy(kwargs.get("auxiliary_paths")))
        return real_verify(*args, **kwargs)

    def fake_model(argv, **kwargs):
        assert "canghai-plan" in argv and "main_decision_v1" in argv
        transports.append(argv)
        # The synthetic transport exercises the documented pull interface. It
        # does not certify that an actual model read or understood these bytes.
        returned_aux.append(n.b.consume_bound_auxiliary_inputs(summary, root=n.root, approved_paths=n.scope))
        save(n.root / f"data/plans/{DATE}/watchlist_plan.json", {
            "trade_date": DATE, "decision_source": "llm", "no_trade": True,
            "generated_at": "2099-01-06T08:00:00+08:00",
            "mode": "dry_run", "autonomous_trading_enabled": False,
            "execution_pool": [], "risk_limits": {"new_buy_budget": 0},
        })
        if case == "drift-during":
            save(n.root / n.scope["attention"][0], {"trade_date": DATE, "zero": 1})
        if case == "rebind-during":
            replacement = make(n)
            replacement["synthetic_rebind"] = True
            commit_summary(n, replacement)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(n.b, "verify_saved_inputs", verify)
    monkeypatch.setattr(caller.subprocess, "run", fake_model)
    monkeypatch.setattr(caller, "plan_artifact", lambda *args, **kwargs: {"passed": True})
    monkeypatch.setattr(caller, "publish_runtime_plan", lambda *args, **kwargs: publications.append(args))
    accepted, detail = caller.retry_llm(DATE)
    # Missing optional file is a bound gap. Missing protocol binding is not a
    # file gap: the caller must not self-bind old research or launch a model.
    preflight_blocked = case in {"drift-before", "old-summary"}
    expected = case in {"valid", "missing"}
    assert accepted is expected, detail
    assert len(transports) == (0 if preflight_blocked else 1)
    assert len(publications) == (1 if expected else 0)
    assert verified == [n.scope] * (1 if preflight_blocked else 2)
    if expected:
        plan = json.loads((n.root / f"data/plans/{DATE}/watchlist_plan.json").read_text())
        assert plan["no_trade"] is True and plan["risk_limits"]["new_buy_budget"] == 0
        assert plan["execution_pool"] == [] and plan["autonomous_trading_enabled"] is False
        aux = returned_aux[0]
        if case == "valid":
            assert aux["attention"]["payload"]["zero"] == 0
            assert aux["emotion_cycle"]["payload"]["metrics_date"] == "20990105"
        else:
            assert aux["attention"]["status"] == "unavailable" and "payload" not in aux["attention"]


def test_actual_cli_preflight_emits_same_summary_fingerprint(native, monkeypatch, capsys):
    n = native
    commit_summary(n, make(n))
    monkeypatch.setattr(sys, "argv", ["build_research_summary.py", "--date", DATE, "--run-id", RUN, "--verify-inputs"])
    outputs = []
    for _ in range(2):
        assert n.b.main() == 0
        output = capsys.readouterr().out
        line = next(line for line in output.splitlines() if line.startswith("research_summary_input_version="))
        version = json.loads(line.split("=", 1)[1])
        assert version == n.a.file_version(n.root, n.root / f"data/research/{DATE}/research_summary.json")
        outputs.append(output)
    assert outputs[0] == outputs[1]


def test_prior_session_attention_window_is_preserved_not_rejected_or_relabelled(native):
    n = native
    # Match the existing producer's distinct target day and observation day.
    payload = {**n.payloads["attention"], "requested_trade_date": DATE,
               "resolved_trade_date": "20990105", "status": "degraded",
               "degraded": ["today contains the latest completed session, not today's open"]}
    save(n.root / n.scope["attention"][0], payload)
    result = n.b.consume_bound_auxiliary_inputs(make(n), root=n.root, approved_paths=n.scope)
    assert result["attention"]["status"] == "available"  # readable, not trade-approved
    assert result["attention"]["payload"] == payload
    assert result["attention"]["payload"]["status"] == "degraded"
    assert result["attention"]["payload"]["resolved_trade_date"] == "20990105"


def test_shell_rechecks_same_input_version_before_attempt_acceptance():
    source = (REPO / "scripts/research/run_research_shell.sh").read_text()
    function = source.split("run_agent() {", 1)[1].split("# 07:15", 1)[0]
    first = function.index("input_version=$(")
    model = function.index('"$ROOT/scripts/research/native_usage.py" run')
    second = function.index("current_input_version=$(")
    compare = function.index('"$current_input_version" != "$input_version"')
    acceptance = function.index("state attempt-result")
    assert first < model < second < compare < acceptance
    assert function.count("--verify-inputs") == 2
    # Both actual launcher prompts must permit the same two bound consumers.
    match = re.search(r'^D1_PROMPT="([^\n]*)"$', source, re.M)
    assert match is not None
    normal = match.group(1)
    safety = (REPO / "scripts/plan/ensure_watchlist_plan.py").read_text()
    for text in [normal, safety]:
        for required in ("attention_signals.json", "emotion_cycle.json", "consume_bound_auxiliary_inputs",
                         "approved_d1_auxiliary_paths", "bound_auxiliary_inputs", "不补抓", "不把未读当无风险"):
            assert required in text
