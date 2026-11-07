#!/usr/bin/env python3
"""Atomic business state at the EXISTING research_pipeline_YYYYMMDD.json path.

status is business state, never the scheduler/nohup result. All updates lock the
existing health directory inode (no new durable lock path). An older run cannot
finish over a newer run. Readers always see one complete JSON document.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.research.pipeline_artifacts import (
    MD_DIRS, UNIT_FILES, atomic_json, attempt_identity, file_version, inspect_delivery,
    md_artifact, plan_artifact, publish_runtime_plan, read_object, research_artifact,
    safe_artifact_path, validate_date, verified_delivery, verify_binding, verify_payload_identity,
)

ROOT = Path(__file__).resolve().parents[2]
SHANGHAI = timezone(timedelta(hours=8), name="Asia/Shanghai")


def policy_metadata(state: dict, date: str) -> None:
    """User goals, not admission/kill/trading gates; use the existing day state.

    The native machine report is ingested by the launcher-bound usage adapter.
    Lifecycle-only attempts remain unknown. No model prose creates token charges.
    Previously persisted observations stay intact across same-day run changes.
    A business-day grouping is NOT a renewed 50M allowance.
    """
    generated = now()
    instant = datetime.fromisoformat(generated).astimezone(SHANGHAI)
    target = datetime.strptime(validate_date(date), "%Y%m%d").replace(
        hour=8, minute=30, tzinfo=SHANGHAI)
    # Delivery timing does not establish source provenance or replay mode.
    mode = ("past_business_date" if instant.date() > target.date() else
            "future_business_date" if instant.date() < target.date() else
            "after_delivery_target" if instant >= target else "pre_delivery")
    state["resource_policy"] = {
        "hard_token_limit": None, "token_effort_target": 50_000_000,
        "enforcement": "observe_only", "allowance_renewal": "none",
        "effort_target_scope": "continuous_task_including_reruns_and_retries",
        "aggregation_scope": "business_trade_date_all_runs_models_retries_safety_nets",
    }
    state["run_context"] = {"generated_at": generated, "mode": mode,
                            "pipeline_started_at": state["started_at"],
                            "timing_basis": "actual_pipeline_observation_not_source_observation"}
    state["delivery_target"] = {
        "timezone": "Asia/Shanghai", "local_time": "08:30:00",
        "target_at": target.isoformat(), "applies_to": "normal_trading_day_premarket",
        "calendar_status": "not_checked_here", "deadline_action": "observe_only",
        "result": "pending_overdue" if instant >= target else "pending",
    }
    observation = state.setdefault("resource_observation", {
        "trade_date": date, "known_total_tokens": None, "native_reported_total_tokens": None,
        "usage_status": "usage_unknown", "coverage": "insufficient",
        "target_comparison": "unknown", "attempts": {},
        "metering": "native_usage_file_available_no_registered_report_yet",
        "observed_scope": "research_shell_attempt_lifecycle_only",
        "coverage_gaps": ["provider_usage", "model_internal_retries", "tool_models",
                          "independent_safety_net", "prior_unobserved_runs"],
    })
    if (not isinstance(observation, dict) or observation.get("trade_date") != date
            or not isinstance(observation.get("attempts"), dict)):
        raise ValueError("invalid day resource observation; refusing silent reset")


def attempt_key(run_id: str, unit: str, attempt: int) -> str:
    return json.dumps([run_id, unit, attempt], ensure_ascii=False, separators=(",", ":"))


def attempt_result(root: Path, date: str, run_id: str, unit: str, attempt: int, rc: int) -> None:
    """Record a process result, NEVER a usage settlement or delivery success."""
    def apply(state):
        if type(attempt) is not int or attempt < 1 or type(rc) is not int:
            raise ValueError("invalid attempt/process result")
        if attempt_identity(state, unit)[:2] != (run_id, attempt):
            raise ValueError("refusing result from superseded attempt")
        record = state["resource_observation"]["attempts"][attempt_key(run_id, unit, attempt)]
        if record["process_exit_code"] is not None:
            if record["process_exit_code"] != rc:
                raise ValueError("conflicting attempt process result")
            return
        record.update(process_exit_code=rc, outcome="process_returned", observed_at=now())
    update(root, date, run_id, apply)


def now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="microseconds")


def state_path(root: Path, date: str) -> Path:
    return safe_artifact_path(root, root / "data/health" / f"research_pipeline_{validate_date(date)}.json")


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return pid > 1
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


@contextmanager
def locked_state(root: Path, date: str):
    path = state_path(root, date)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            state = read_object(path)
        except FileNotFoundError:
            state = {}
        yield state
        atomic_json(path, state)
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def start(root: Path, date: str, run_id: str, pid: int, status: str) -> None:
    if not isinstance(run_id, str) or not run_id or status not in {"started", "running"}:
        raise ValueError("pipeline start requires run_id and started/running status")
    with locked_state(root, date) as state:
        same = state.get("run_id") == run_id
        if not same and state.get("status") in {"started", "running"}:
            if alive(int(state.get("pid") or 0)):
                raise ValueError(f"pipeline already active: run_id={state.get('run_id')}, pid={state.get('pid')}")
        if same and state.get("status") in {"completed", "failed"}:
            raise ValueError("terminal run cannot be restarted; allocate a new run_id")
        if not same:
            # Keep day observations, not old run/attempt/SHA delivery authority.
            observation_present = "resource_observation" in state
            observation = state.get("resource_observation")
            if observation_present and (state.get("trade_date") != date or not isinstance(observation, dict)):
                raise ValueError("invalid day resource observation; refusing silent reset")
            state.clear()
            state.update({"schema_version": "research_pipeline_v2", "pipeline": "research_shell",
                          "trade_date": date, "run_id": run_id, "started_at": now(),
                          "started_ns": time.time_ns(), "finished_at": None,
                          "missing_json": [], "missing_md": [], "missing_count": 0,
                          "total_expected": 15, "stages": {}, "contract_results": {}, "error": None})
            if observation is not None:
                state["resource_observation"] = observation
        policy_metadata(state, date)
        state.update(status=status, pid=pid, updated_at=now())


def update(root: Path, date: str, run_id: str, fn) -> None:
    with locked_state(root, date) as state:
        if state.get("run_id") != run_id:
            raise ValueError("refusing update from superseded run")
        if state.get("status") in {"completed", "failed"}:
            raise ValueError("refusing update to terminal business state")
        fn(state)
        state["updated_at"] = now()


def stage(root: Path, date: str, run_id: str, name: str, status: str, error: str = "", attempt: int = 0) -> None:
    def apply(state):
        if status not in {"running", "completed", "failed", "skipped"} or type(attempt) is not int or attempt < 0:
            raise ValueError("invalid stage status/attempt")
        previous = state["stages"].get(name, {})
        if attempt and previous.get("attempt", 0) > attempt:
            raise ValueError("refusing stale stage attempt")
        entry = {**previous, "status": status, "error": error or None}
        entry.setdefault("started_at", now())
        if attempt:
            entry["attempt"] = attempt
        if status == "running" and name in {*UNIT_FILES, "D1", "summary"}:
            # Each new attempt invalidates old evidence, including same-day files.
            state["contract_results"].pop(name, None)
            entry["attempt"] = attempt or previous.get("attempt", 0) + 1
            entry["attempt_started_ns"] = time.time_ns()
            entry["run_id"] = run_id
            entry.pop("finished_at", None)
            if name != "summary":
                observations = state.get("resource_observation", {}).get("attempts")
                if observations is not None:
                    observations.setdefault(attempt_key(run_id, name, entry["attempt"]), {
                        "run_id": run_id, "stage": name, "attempt": entry["attempt"],
                        "started_at": now(), "usage": None, "usage_status": "usage_unknown",
                        "process_exit_code": None, "outcome": "running",
                    })
        if status in {"completed", "failed", "skipped"}:
            entry["finished_at"] = now()
        state["stages"][name] = entry
        if name == "summary" and status == "completed":
            path = root / "data/research" / date / "research_summary.json"
            # This completion event binds the exact summary checked at handoff.
            before = file_version(root, path)
            summary_contract(root, date, run_id, state["started_ns"], state=state)
            if file_version(root, path) != before:
                raise ValueError("summary changed during completion check")
            state["contract_results"]["summary"] = {
                "passed": True, **before, "run_id": run_id, "attempt": entry.get("attempt", 1),
                "inputs": {unit: dict(state["contract_results"][unit]["json"]) for unit in UNIT_FILES}}
    update(root, date, run_id, apply)


def attempt_start(root: Path, date: str, run_id: str, unit: str) -> int:
    state = read_object(state_path(root, date))
    if state.get("run_id") != run_id:
        raise ValueError("attempt belongs to superseded run")
    return attempt_identity(state, unit)[2]


def check(root: Path, date: str, run_id: str, unit: str, since: Path | None = None) -> bool:
    snapshot = read_object(state_path(root, date))
    identity = attempt_identity(snapshot, unit)
    if identity[0] != run_id:
        raise ValueError("check belongs to superseded run")
    if snapshot["stages"][unit].get("status") != "running":
        raise ValueError("check requires a running current attempt")
    since_ns = max(identity[2], since.stat().st_mtime_ns) if since else identity[2]
    results = {}
    for kind in ("json", "md"):
        try:
            # Keep the actual helper boundary observable to fault-injection.
            if kind == "md":
                md_artifact(root, date, unit, since_ns=since_ns)
            path, payload, version = inspect_delivery(root, date, unit, kind, since_ns=since_ns)
            verify_payload_identity(payload, run_id, identity[1])
            if unit == "R5" and kind == "json" and payload.get("status") == "skipped":
                verified_delivery(root, date, "R2", "json", snapshot)
            results[kind] = {"passed": True, **version, "run_id": run_id, "attempt": identity[1]}
        except (OSError, ValueError, TypeError) as exc:
            results[kind] = {"passed": False, "error": str(exc), "run_id": run_id, "attempt": identity[1]}
            if kind == "md" and unit in UNIT_FILES:
                try:
                    _, payload = research_artifact(root, date, unit, since_ns=since_ns)
                    if payload.get("md_delivery"):
                        results[kind]["delivery_blocker"] = payload["md_delivery"]
                except (OSError, ValueError, TypeError):
                    pass
    def apply(state):
        if attempt_identity(state, unit) != identity or state["stages"][unit].get("status") != "running":
            raise ValueError("refusing check from superseded attempt")
        # Compare again while holding the business-state lock. Do not bless a
        # replacement that arrived after validation or during another unit check.
        for kind, record in results.items():
            if record["passed"]:
                try:
                    verified_path = root / record["path"]
                    verify_binding(root, verified_path, record, run_id, identity[1])
                except (OSError, ValueError, TypeError) as exc:
                    results[kind] = {**record, "passed": False, "error": str(exc)}
        state["contract_results"][unit] = results
    update(root, date, run_id, apply)
    return all(r["passed"] for r in results.values())


def finish(root: Path, date: str, run_id: str, rc: int, error: str = "", *, skipped: bool = False) -> bool:
    completed = False
    def apply(state):
        nonlocal completed
        if not skipped:
            since_ns = state["started_ns"]
            missing_json, missing_md = [], []
            for unit in MD_DIRS:
                for kind in ("json", "md"):
                    try:
                        verified_delivery(root, date, unit, kind, state)
                    except (OSError, ValueError, TypeError) as exc:
                        previous = state["contract_results"].setdefault(unit, {}).get(kind, {})
                        state["contract_results"][unit][kind] = {**previous, "passed": False, "error": str(exc)}
                        if kind == "json" and unit in UNIT_FILES:
                            missing_json.append(Path(UNIT_FILES[unit]).stem)
                        elif kind == "md":
                            missing_md.append(f"{unit}:{MD_DIRS[unit]}")
            # Keep legacy total_expected=15 (7 research JSON + 8 MD). D1 JSON,
            # summary and runtime handoff are additional named contract results.
            state.update(missing_json=missing_json, missing_md=missing_md,
                         missing_count=len(missing_json) + len(missing_md))
            def checked_summary():
                summary_contract(root, date, run_id, since_ns, state=state)
                path = root / "data/research" / date / "research_summary.json"
                entry = state.get("stages", {}).get("summary", {})
                receipt = state["contract_results"].get("summary", {})
                verify_binding(root, path, receipt, run_id, entry.get("attempt", 1))
                for unit in UNIT_FILES:
                    primary, _ = verified_delivery(root, date, unit, "json", state)
                    verify_binding(root, primary, receipt.get("inputs", {}).get(unit, {}),
                                   run_id, attempt_identity(state, unit)[1])
            for name, fn in {
                "D1_json": lambda: verified_delivery(root, date, "D1", "json", state),
                "summary": checked_summary,
                "runtime_handoff": lambda: runtime_contract(root, date),
            }.items():
                previous = state["contract_results"].get(name, {})
                try:
                    fn()
                    state["contract_results"][name] = {**previous, "passed": True}
                except (OSError, ValueError, TypeError) as exc:
                    state["contract_results"][name] = {**previous, "passed": False, "error": str(exc)}
            # Revisit the byte receipts immediately before terminal publication;
            # later contract inspection must not leave an earlier pass stale.
            for unit in MD_DIRS:
                for kind in ("json", "md"):
                    record = state["contract_results"][unit][kind]
                    if record.get("passed") is not True:
                        continue
                    try:
                        verified_delivery(root, date, unit, kind, state)
                    except (OSError, ValueError, TypeError) as exc:
                        record.update(passed=False, error=str(exc))
                        if kind == "json" and unit in UNIT_FILES:
                            missing_json.append(Path(UNIT_FILES[unit]).stem)
                        elif kind == "md":
                            missing_md.append(f"{unit}:{MD_DIRS[unit]}")
                        if kind == "json" and unit == "D1":
                            state["contract_results"]["D1_json"] = {"passed": False, "error": str(exc)}
            if state["contract_results"]["summary"].get("passed"):
                try:
                    checked_summary()
                except (OSError, ValueError, TypeError) as exc:
                    state["contract_results"]["summary"].update(passed=False, error=str(exc))
            state["missing_count"] = len(missing_json) + len(missing_md)
        failures = [k for k, v in state["stages"].items() if v["status"] in {"failed", "running"}]
        bad_contracts = [k for k in ("D1_json", "summary", "runtime_handoff")
                         if state["contract_results"].get(k, {}).get("passed") is False]
        failed = bool(rc or failures or bad_contracts or state["missing_count"])
        state.update(status="failed" if failed else "completed", finished_at=now(),
                     process_exit_code=rc, exit_code=(rc or 1) if failed else 0,
                     error=(error or f"failed stages={failures}; contracts={bad_contracts}; missing={state['missing_count']}") if failed else None)
        completed = not failed
        if skipped:
            state["skipped"] = True
        # Timing/usage observations cannot grant delivery or trading permission.
        if "delivery_target" in state:
            target = state["delivery_target"]
            on_target = datetime.fromisoformat(state["finished_at"]) <= datetime.fromisoformat(target["target_at"])
            target["result"] = ("not_applicable" if skipped and completed else
                                "failed" if not completed else
                                "delivered_on_target" if on_target else "delivered_late")
        for record in state.get("resource_observation", {}).get("attempts", {}).values():
            if record.get("run_id") == run_id and record.get("outcome") == "running":
                record.update(outcome="interrupted_or_unobserved", observed_at=state["finished_at"])
    update(root, date, run_id, apply)
    return completed


def summary_contract(root: Path, date: str, run_id: str, since_ns: int, *, state: dict | None = None) -> None:
    path = safe_artifact_path(root, root / "data/research" / validate_date(date) / "research_summary.json")
    data = read_object(path)
    if path.stat().st_mtime_ns < since_ns or data.get("run_id") != run_id:
        raise ValueError("stale/mismatched research_summary run")
    if str(data.get("trade_date", "")).replace("-", "") != date:
        raise ValueError("summary trade_date mismatch")
    if data.get("orchestrator_status") not in {"complete", "partial"}:
        raise ValueError("summary has no usable primary research")
    if not isinstance(data.get("contract_checks_passed"), bool):
        raise ValueError("summary contract check result missing")
    # Partial/degraded research remains consumable; missing current units and
    # checker crashes are delivery failures, not permission to erase candidates.
    pointers = data.get("artifacts", {})
    if not isinstance(pointers, dict):
        raise ValueError("summary artifact pointers must be an object")
    missing = set(UNIT_FILES) - set(pointers)
    if missing or "_error" in data.get("contract_failures", {}):
        raise ValueError(f"summary missing usable units={sorted(missing)} or checker failed")
    state = state if state is not None else read_object(state_path(root, date))
    if state.get("run_id") != run_id:
        raise ValueError("summary belongs to superseded run")
    manifest = data.get("input_manifest")
    if manifest is not None:
        if not isinstance(manifest, dict):
            raise ValueError("summary input_manifest must be an object")
        unsigned = {k: v for k, v in manifest.items() if k != "sha256"}
        digest = hashlib.sha256(json.dumps(unsigned, sort_keys=True, ensure_ascii=False,
                                          separators=(",", ":"), allow_nan=False).encode()).hexdigest()
        if (manifest.get("sha256") != digest or manifest.get("run_id") != run_id
                or manifest.get("trade_date") != date or manifest.get("authorized_main_inputs") != pointers):
            raise ValueError("summary input_manifest digest/identity/pointers mismatch")
    for unit in UNIT_FILES:
        checked_path, _ = verified_delivery(root, date, unit, "json", state)
        if pointers[unit] != str(checked_path.relative_to(root)):
            raise ValueError(f"summary {unit} does not reference the checked current primary")
        if manifest is not None:
            units = manifest.get("units")
            evidence = units.get(unit, {}) if isinstance(units, dict) else {}
            evidence = evidence.get("json", {}) if isinstance(evidence, dict) else {}
            if not isinstance(evidence, dict):
                raise ValueError(f"summary {unit} input evidence must be an object")
            receipt = state["contract_results"][unit]["json"]
            if any(evidence.get(k) != receipt.get(k) for k in ("path", "sha256", "bytes", "mtime_ns")):
                raise ValueError(f"summary {unit} input version differs from checked delivery")


def runtime_contract(root: Path, date: str) -> None:
    _, canonical = plan_artifact(root, date)
    runtime_path = safe_artifact_path(root, root / "data/runtime" / f"watchlist_plan_{validate_date(date)}.json")
    runtime = read_object(runtime_path)
    if runtime != canonical:
        raise ValueError("runtime does not match authoritative canonical D1 plan")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("command", choices=("start", "stage", "check", "finish", "handoff", "reap", "policy", "attempt-result"))
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--date", required=True)
    ap.add_argument("--run-id", default=os.environ.get("CHZL_RESEARCH_RUN_ID", ""))
    ap.add_argument("--pid", type=int, default=os.getppid())
    ap.add_argument("--status", default="running")
    ap.add_argument("--stage", default="startup")
    ap.add_argument("--error", default="")
    ap.add_argument("--attempt", type=int, default=0)
    ap.add_argument("--rc", type=int, default=0)
    ap.add_argument("--since", type=Path)
    ap.add_argument("--skipped", action="store_true")
    args = ap.parse_args()
    try:
        if args.command == "start":
            start(args.root, args.date, args.run_id, args.pid, args.status)
        elif args.command == "policy":
            snapshot = read_object(state_path(args.root, args.date))
            if snapshot.get("run_id") != args.run_id or snapshot.get("status") not in {"started", "running"}:
                raise ValueError("policy read belongs to superseded/terminal run")
            context = {key: snapshot[key] for key in (
                "resource_policy", "delivery_target", "run_context")}
            context["resource_observation"] = {
                key: snapshot["resource_observation"].get(key)
                for key in ("usage_status", "coverage", "metering", "target_comparison",
                            "known_total_tokens", "native_reported_total_tokens", "coverage_gaps")}
            print(json.dumps(context, ensure_ascii=False, separators=(",", ":")))
        elif args.command == "attempt-result":
            attempt_result(args.root, args.date, args.run_id, args.stage, args.attempt, args.rc)
        elif args.command == "stage":
            stage(args.root, args.date, args.run_id, args.stage, args.status, args.error, args.attempt)
        elif args.command == "check":
            return 0 if check(args.root, args.date, args.run_id, args.stage, args.since) else 1
        elif args.command == "finish":
            return 0 if finish(args.root, args.date, args.run_id, args.rc, args.error, skipped=args.skipped) else 1
        elif args.command == "handoff":
            snapshot = read_object(state_path(args.root, args.date))
            if snapshot.get("run_id") != args.run_id or snapshot.get("status") not in {"started", "running"}:
                raise ValueError("handoff belongs to superseded/terminal run")
            for kind in ("json", "md"):
                verified_delivery(args.root, args.date, "D1", kind, snapshot)
            since_ns = attempt_identity(snapshot, "D1")[2]
            if args.since:
                since_ns = max(since_ns, args.since.stat().st_mtime_ns)
            publish_runtime_plan(args.root, args.date, since_ns=since_ns)
            for kind in ("json", "md"):
                verified_delivery(args.root, args.date, "D1", kind, snapshot)
        elif args.command == "reap":
            state = read_object(state_path(args.root, args.date))
            if state.get("status") in {"started", "running"} and not alive(int(state.get("pid") or 0)):
                finish(args.root, args.date, state["run_id"], 1, "pipeline process disappeared before terminal delivery")
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f"pipeline_state: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
