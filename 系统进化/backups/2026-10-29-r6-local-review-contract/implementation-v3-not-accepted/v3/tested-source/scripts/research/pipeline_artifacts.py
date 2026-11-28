"""Shared offline artifact inspection and trusted delivery/version receipts.

No research generation, trading decisions, network/DB/model calls.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import tempfile

UNIT_FILES = {
    "R1": "R1_style.json", "R2": "R2_main_sectors.json", "R3": "R3_sentiment.json",
    "R4": "R4_news.json", "R5": "R5_stock_profiles.json", "R6": "R6_devil_advocate.json",
    "R7": "R7_capital_flow.json",
}
MD_DIRS = dict(zip((*UNIT_FILES, "D1"),
                   ("风格研判", "主线研判", "群聊情绪", "消息面", "个股画像", "反证", "资金面", "盘前预案")))
PRIMARY_FIELDS = {
    "R1": ("style", "sentiment_score"), "R2": ("main_lines",),
    "R3": ("resonance_top_themes", "sentiment_score"), "R4": ("top_events",),
    "R5": ("profiles",), "R6": ("counter_arguments", "hard_rejects"),
    "R7": ("main_force", "northbound"),
}
USABLE_STATUSES = {"complete", "completed", "ok", "partial", "degraded"}


def read_object(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON object required: {path.name}")
    return data


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(value, out, ensure_ascii=False, indent=2, allow_nan=False)
            out.write("\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def validate_date(date: str) -> str:
    if not isinstance(date, str) or not re.fullmatch(r"[0-9]{8}", date):
        raise ValueError("trade_date must be an exact YYYYMMDD")
    datetime.strptime(date, "%Y%m%d")
    return date


def safe_artifact_path(root: Path, path: Path) -> Path:
    """Reject traversal and symlink indirection before reading artifact bytes."""
    root = root.absolute()
    path = path.absolute()
    if ".." in path.parts or not path.is_relative_to(root):
        raise ValueError("artifact path escapes approved root")
    current = root
    for part in path.relative_to(root).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("artifact symlink is not an approved primary path")
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("artifact resolves outside approved root")
    return path


def file_version(root: Path, path: Path) -> dict:
    """Hash the opened version, rejecting replacement during the read."""
    path = safe_artifact_path(root, path)
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        raw = stream.read()
        after = os.fstat(stream.fileno())
    current = path.stat()
    attrs = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    if any(getattr(before, k) != getattr(after, k) or getattr(after, k) != getattr(current, k) for k in attrs):
        raise ValueError("artifact changed during inspection")
    return {"path": str(path.relative_to(root.absolute())), "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw), "mtime_ns": after.st_mtime_ns}


def _fresh(path: Path, since_ns: int | None) -> None:
    if since_ns is not None and path.stat().st_mtime_ns < since_ns:
        raise ValueError(f"stale artifact from before this attempt: {path.name}")


def _date(data: dict, date: str) -> None:
    if str(data.get("trade_date", "")).replace("-", "") != date:
        raise ValueError(f"trade_date mismatch: {data.get('trade_date')!r}, expected {date}")


def _has_primary(unit: str, data: dict) -> bool:
    return any(k in data and isinstance(data[k], (list, dict, str, int, float)) for k in PRIMARY_FIELDS[unit])


def legal_r5_skip(root: Path, date: str, data: dict) -> bool:
    reason = data.get("reason") or data.get("skip_reason")
    if data.get("profiles") != [] or not isinstance(reason, str) or not reason.strip():
        return False
    try:
        r2_path = safe_artifact_path(root, root / "data/research" / validate_date(date) / UNIT_FILES["R2"])
        r2 = read_object(r2_path)
        _date(r2, date)
        if r2.get("status") not in USABLE_STATUSES or not isinstance(r2.get("main_lines"), list):
            return False
        secondary = r2.get("secondary_lines", [])
        if secondary is None:
            secondary = []
        if not isinstance(secondary, list):
            return False
        lines = r2["main_lines"] + secondary
        if any(not isinstance(line, dict) or not isinstance(line.get("leaders", []), list) for line in lines):
            return False
        return not any(line.get("leaders") for line in lines)
    except (OSError, ValueError, TypeError):
        return False


def validate_candidate_shape(unit: str, data: dict) -> None:
    """Only containers read by candidate consumers; no counts/trading thresholds."""
    def entries(value, field):
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise ValueError(f"{unit}: invalid candidate shape: {field} must be a list of objects")
        return value

    def codes(items, field):
        for item in items:
            if item.get("ts_code") is not None and not isinstance(item["ts_code"], str):
                raise ValueError(f"{unit}: invalid candidate shape: {field}.ts_code must be a string or null")

    if unit == "R2":
        for field in ("main_lines", "secondary_lines"):
            for line in entries(data.get(field, []), field):
                codes(entries(line.get("leaders", []), field + ".leaders"), field + ".leaders")
    elif unit == "R5":
        codes(entries(data.get("profiles", []), "profiles"), "profiles")


def research_artifact(root: Path, date: str, unit: str, *, since_ns: int | None = None) -> tuple[Path, dict]:
    """Resolve ONLY same-day R7 aliases; no glob over evidence/validation files.

    A primary canonical file wins. A pointer/absent canonical may resolve to the
    exact dated R7 filename. R7 alone also permits a one-hop canonical symlink
    whose literal target is that same-directory dated basename. The generic
    safe_artifact_path remains closed to all symlinks; receipts bind the regular
    primary target, with its own content/date/mtime (never the link's existence).
    """
    validate_date(date)
    if unit not in UNIT_FILES:
        raise ValueError("unknown research unit")
    canonical = root / "data/research" / date / UNIT_FILES[unit]
    if unit == "R7" and canonical.is_symlink():
        safe_artifact_path(root, canonical.parent)
        if os.readlink(canonical) != f"R7_capital_flow_{date}.json":
            raise ValueError("R7 symlink must target the exact same-directory same-day dated primary artifact")
        path = safe_artifact_path(root, canonical.with_name(f"R7_capital_flow_{date}.json"))
        if not stat.S_ISREG(path.stat().st_mode):
            raise ValueError("R7 symlink target must be a regular primary file")
        data = read_object(path)
    else:
        canonical = safe_artifact_path(root, canonical)
        path = canonical
        data = read_object(path) if path.is_file() else {}
    if unit == "R7" and not _has_primary(unit, data):
        dated = safe_artifact_path(root, canonical.with_name(f"R7_capital_flow_{date}.json"))
        allowed = {dated.name, str(dated.relative_to(root.absolute()))}
        keys = ("canonical_path", "artifact_path", "target", "alias_of", "path", "pointer", "ref")
        # Check EVERY declared pointer, not just the first plausible alias.
        for key in keys:
            if key in data and (not isinstance(data[key], str) or data[key] not in allowed):
                raise ValueError("R7 alias must target the exact same-day dated primary artifact")
        if data:
            _date(data, date)
        path = dated
        data = read_object(path)
    _fresh(path, since_ns)
    _date(data, date)
    validate_candidate_shape(unit, data)
    status = str(data.get("status") or ("degraded" if data.get("degraded") else "complete"))
    if status == "skipped":
        if unit != "R5" or not legal_r5_skip(root, date, data):
            raise ValueError(f"{unit}: unexplained/unsupported skip")
    elif status not in USABLE_STATUSES:
        raise ValueError(f"{unit}: unusable status={status}")
    if not _has_primary(unit, data):
        raise ValueError(f"{unit}: primary research fields missing (pointer/skeleton is not research)")
    return path, data


def plan_reassessment_reasons(data: dict) -> list[str]:
    """Explicit incompleteness survives safe publication; absence is legacy.

    Delivery, research readiness and execution consent are separate contracts.
    Do not infer completion from LLM provenance or a safe no-trade decision.
    """
    reasons = []
    for label, section in (("plan", data), ("meta", data.get("meta") or {})):
        if not isinstance(section, dict):
            continue
        for key in ("production_ready", "research_completion_passed"):
            if key in section and section[key] is not True:
                reasons.append(f"{label}.{key} is not true")
        if section.get("reassessment_required") is True:
            reasons.append(f"{label}.reassessment_required")
    return reasons


def plan_artifact(root: Path, date: str, *, since_ns: int | None = None) -> tuple[Path, dict]:
    path = safe_artifact_path(root, root / "data/plans" / validate_date(date) / "watchlist_plan.json")
    data = read_object(path)
    _fresh(path, since_ns)
    _date(data, date)
    meta = data.get("meta") or {}
    source = data.get("decision_source") or meta.get("decision_source")
    if (data.get("is_fallback") or meta.get("python_fallback") or
            "rule" in str(data.get("agent_name", "")).lower() or
            data.get("mode") in {"fallback", "python_fallback"}):
        raise ValueError("D1 is a fallback/rule artifact, not LLM delivery")
    if source != "llm":
        raise ValueError("D1 must explicitly declare decision_source=llm")
    if not data.get("generated_at") or not isinstance(data.get("execution_pool"), list):
        raise ValueError("D1 missing generated_at/execution_pool")
    from trading.load_plan import validate_plan_for_date
    validate_plan_for_date(data, date)
    # An empty execution pool is a valid no-trade decision, not a model failure.
    return path, data


def md_artifact(root: Path, date: str, unit: str, *, since_ns: int | None = None) -> Path:
    validate_date(date)
    if unit not in MD_DIRS:
        raise ValueError("unknown human report unit")
    path = safe_artifact_path(root, root / "chzl_kg/投研交易" / MD_DIRS[unit] / f"{date}.md")
    _fresh(path, since_ns)
    if len(path.read_text(encoding="utf-8").splitlines()) < 5:
        raise ValueError(f"{unit}: missing/substantially empty human report")
    return path


def inspect_delivery(root: Path, date: str, unit: str, kind: str, *, since_ns: int | None = None) -> tuple[Path, dict, dict]:
    """Validate content between two matching byte-version inspections."""
    def inspect():
        if kind == "md":
            return md_artifact(root, date, unit, since_ns=since_ns), {}
        if kind != "json":
            raise ValueError("delivery kind must be json or md")
        return (plan_artifact(root, date, since_ns=since_ns) if unit == "D1" else
                research_artifact(root, date, unit, since_ns=since_ns))
    path, _ = inspect()
    before = file_version(root, path)
    checked_path, payload = inspect()
    after = file_version(root, checked_path)
    if before != after:
        raise ValueError("artifact version changed during validation")
    return checked_path, payload, after


def attempt_identity(state: dict, unit: str) -> tuple[str, int, int]:
    stages = state.get("stages")
    entry = stages.get(unit, {}) if isinstance(stages, dict) else {}
    if not isinstance(entry, dict):
        raise ValueError(f"{unit}: invalid stage evidence")
    run_id, attempt, started = state.get("run_id"), entry.get("attempt"), entry.get("attempt_started_ns")
    if (not isinstance(run_id, str) or not run_id or type(attempt) is not int or attempt < 1
            or type(started) is not int or started < 1):
        raise ValueError(f"{unit}: current run/attempt identity missing")
    return run_id, attempt, started


def verify_binding(root: Path, path: Path, record: dict, run_id: str, attempt: int) -> dict:
    """Missing legacy hashes are unbound, NEVER a self-reported hash pass."""
    if (not isinstance(record, dict) or record.get("passed") is not True or not run_id or record.get("run_id") != run_id
            or type(record.get("attempt")) is not int or record["attempt"] != attempt
            or not isinstance(record.get("sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", record["sha256"])
            or type(record.get("bytes")) is not int or type(record.get("mtime_ns")) is not int):
        raise ValueError("delivery not bound to this checked run/attempt version")
    current = file_version(root, path)
    if any(record.get(key) != value for key, value in current.items()):
        raise ValueError("delivery file version differs from checked binding")
    return current


def verify_payload_identity(payload: dict, run_id: str, attempt: int) -> None:
    if "run_id" in payload and payload["run_id"] != run_id:
        raise ValueError("artifact declares a different run_id")
    if "attempt" in payload and (type(payload["attempt"]) is not int or payload["attempt"] != attempt):
        raise ValueError("artifact declares a different attempt")


def verified_delivery(root: Path, date: str, unit: str, kind: str, state: dict) -> tuple[Path, dict]:
    """Read-only current-attempt verification shared by health and summary."""
    if state.get("trade_date") != date:
        raise ValueError("delivery state trade_date mismatch")
    run_id, attempt, started = attempt_identity(state, unit)
    path, payload, version = inspect_delivery(root, date, unit, kind, since_ns=started)
    results = state.get("contract_results")
    unit_results = results.get(unit, {}) if isinstance(results, dict) else {}
    if not isinstance(unit_results, dict):
        raise ValueError(f"{unit}: invalid contract evidence")
    record = unit_results.get(kind, {})
    verify_binding(root, path, record, run_id, attempt)
    if any(record.get(key) != value for key, value in version.items()):
        raise ValueError("delivery changed after content validation")
    verify_payload_identity(payload, run_id, attempt)
    if unit == "R5" and kind == "json" and payload.get("status") == "skipped":
        verified_delivery(root, date, "R2", "json", state)
    return path, payload


def publish_runtime_plan(root: Path, date: str, *, since_ns: int | None = None) -> Path:
    """Trusted implementation handoff: canonical -> runtime ONLY, atomically.

    The LLM profile need not (and must not) gain runtime write permission.
    No loaded/execution artifacts or trading gates are changed here.
    """
    _, data = plan_artifact(root, date, since_ns=since_ns)
    md_artifact(root, date, "D1", since_ns=since_ns)
    # Reuse execution's schema/authorization staging boundary rather than
    # introducing a second copy path that could bypass its no-promotion checks.
    from trading import load_plan
    if Path(load_plan.DATA_DIR).resolve() != (root / "data").resolve():
        raise ValueError("execution staging root mismatch; refusing cross-root handoff")
    runtime = load_plan.stage_plan(date)
    if read_object(runtime) != data:
        raise OSError("runtime handoff read-back mismatch")
    return runtime


# Trusted receipts live beside the existing pipeline health state; immutable
# source copies stay beside their original report. No new service/history DB.
HISTORY_LEDGER_VERSION = "research_history_receipts_v1"


def _history_ledger(root: Path, date: str) -> tuple[Path, dict]:
    from scripts.research.history_evidence import _bounded_snapshot, _load_json, digest
    path = safe_artifact_path(root, root / f"data/health/research_history_{validate_date(date)}.json")
    if not path.exists():
        return path, {"schema_version": HISTORY_LEDGER_VERSION, "trade_date": date, "deliveries": []}
    _, blob = _bounded_snapshot(root, path, 262144)
    value = _load_json(blob)
    if (not isinstance(value, dict) or value.get("schema_version") != HISTORY_LEDGER_VERSION or
            value.get("trade_date") != date or not isinstance(value.get("deliveries"), list) or
            len(value["deliveries"]) > 64):
        raise ValueError("invalid trusted history receipt ledger")
    for receipt in value["deliveries"]:
        if (not isinstance(receipt, dict) or receipt.get("receipt_sha256") !=
                digest({k: v for k, v in receipt.items() if k != "receipt_sha256"})):
            raise ValueError("history receipt digest mismatch")
    return path, value


def _persist_history_receipt(root: Path, date: str, unit: str, blob: bytes, receipt: dict) -> dict:
    """Called only under the shared health-directory lock; no timestamp input."""
    from datetime import timezone
    from scripts.research.history_evidence import _bounded_snapshot, digest
    ledger_path, ledger = _history_ledger(root, date)
    identity = {k: receipt[k] for k in ("unit", "source_version", "source_run_id", "attempt")}
    for old in ledger["deliveries"]:
        if all(old.get(k) == v for k, v in identity.items()):
            fp, _ = _bounded_snapshot(root, root / old["snapshot"]["path"], 524288)
            if fp != old["snapshot"]:
                raise ValueError("registered immutable history version changed")
            return old
    if len(ledger["deliveries"]) >= 64:
        raise ValueError("daily history receipt limit exceeded; never silently drop counterevidence")
    sha = hashlib.sha256(blob).hexdigest()
    folder = "reports" if unit == "E1" else "research"
    stem = "E1_data" if unit == "E1" else Path(UNIT_FILES[unit]).stem
    path = safe_artifact_path(root, root / f"data/{folder}/{date}/{stem}.history.{sha}.json")
    if not path.exists():
        # Exclusive creation never overwrites a prior version, even after reruns.
        with path.open("xb") as stream:
            stream.write(blob)
            stream.flush()
            os.fsync(stream.fileno())
    fp, saved = _bounded_snapshot(root, path, 524288)
    if saved != blob:
        raise ValueError("immutable history snapshot read-back mismatch")
    receipt = {**receipt, "snapshot": fp,
               "first_available_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
               "availability_basis": "trusted_receiver_actual_reception_not_original_publication",
               "source_family": "canghai_research_and_review"}
    receipt["receipt_sha256"] = digest(receipt)
    ledger["deliveries"].append(receipt)
    if len(json.dumps(ledger, ensure_ascii=False).encode()) > 262144:
        raise ValueError("history receipt ledger byte limit exceeded")
    atomic_json(ledger_path, ledger)
    if read_object(ledger_path) != ledger:
        raise OSError("history receipt read-back mismatch")
    return receipt


def receive_history_delivery(root: Path, date: str, run_id: str, unit: str,
                             *, receiving_date: str | None = None) -> dict:
    """Receive NEW checked R2/R6 deliveries, or existing E1 market fields NOW.

    Never retrofit historical first availability. E1 reception is a new receipt
    at the next research boundary, NOT proof of its original publication/run.
    Only market postmortem/corrections are transported, not account/performance.
    """
    from scripts.research.history_evidence import _bounded_snapshot, _load_json, instant
    from scripts.research.pipeline_state import locked_state
    validate_date(date)
    target_date = validate_date(receiving_date or date)
    if unit not in {"R2", "R6", "E1"}:
        raise ValueError("only R2/R6/E1 history delivery supported")
    with locked_state(root, target_date) as state:
        if (state.get("trade_date") != target_date or state.get("run_id") != run_id or
                state.get("status") not in {"started", "running"}):
            raise ValueError("history reception requires the active current research run")
        if unit == "E1":
            source_path = root / f"data/reports/{date}/E1_data.json"
            fp, raw = _bounded_snapshot(root, source_path, 524288)
            payload = _load_json(raw)
            if (not isinstance(payload, dict) or payload.get("schema_version") != "e1_daily_review_v1" or
                    payload.get("trade_date") != date or payload.get("status") not in USABLE_STATUSES):
                raise ValueError("E1 market feedback requires usable explicit date/status/schema")
            from datetime import timezone
            if instant(payload.get("generated_at")) > datetime.now(timezone.utc):
                raise ValueError("E1 generated_at is in the future")
            fields = {k: payload[k] for k in ("sector_postmortem", "logic_corrections") if payload.get(k)}
            if not fields or any(not isinstance(v, (list, dict)) for v in fields.values()):
                raise ValueError("E1 market postmortem/corrections unavailable")
            # Preserve complete selected objects, including qualifications/unknown.
            projected = {"schema_version": "e1_market_feedback_projection_v1", "trade_date": date,
                         "generated_at": payload["generated_at"], **fields}
            raw = (json.dumps(projected, ensure_ascii=False, allow_nan=False) + "\n").encode()
            source_run, attempt = None, None  # Existing E1 has no trusted run receipt.
        else:
            if date != target_date:
                raise ValueError("new R2/R6 reception must belong to the active day")
            if state.get("stages", {}).get(unit, {}).get("status") != "completed":
                raise ValueError("history reception requires completed current delivery")
            from scripts.research.history_evidence import checked_report_snapshot
            fp, payload, _ = checked_report_snapshot(root, date, run_id, unit, state, 524288)
            after_fp, raw = _bounded_snapshot(root, root / fp["path"], 524288)
            if after_fp != fp or _load_json(raw) != payload:
                raise ValueError("source changed during history reception")
            source_run, attempt, _ = attempt_identity(state, unit)
        receipt = _persist_history_receipt(root, date, unit, raw, {
            "unit": unit, "source_version": fp, "source_run_id": source_run,
            "attempt": attempt, "receiving_run_id": run_id, "receiving_trade_date": target_date})
        if unit in {"R2", "R6"}:
            state["contract_results"][unit]["json"]["first_available_at"] = receipt["first_available_at"]
        if unit == "R2":
            from scripts.research.history_evidence import delivery_adjudications
            state["history_adjudications"] = delivery_adjudications(root, date, run_id, payload, fp)
    # Read the exact target after the locked writer publishes its state.
    saved_state = read_object(root / f"data/health/research_pipeline_{target_date}.json")
    if unit in {"R2", "R6"} and saved_state.get("run_id") == run_id:
        if saved_state["contract_results"][unit]["json"].get("first_available_at") != receipt["first_available_at"]:
            raise OSError("history first reception state read-back mismatch")
    return receipt


R6_REQUIRED_MODES = (1, 2, 6, 7)


def json_pointer(payload, pointer: str):
    """RFC 6901 existence, not truthiness or a financial interpretation."""
    if not isinstance(pointer, str) or (pointer and not pointer.startswith('/')):
        raise ValueError('invalid evidence json_pointer')
    value = payload
    for token in pointer.split('/')[1:] if pointer else []:
        if re.search(r'~(?![01])', token):
            raise ValueError('invalid RFC6901 escape')
        token = token.replace('~1', '/').replace('~0', '~')
        if isinstance(value, dict) and token in value:
            value = value[token]
        elif isinstance(value, list) and re.fullmatch(r'0|[1-9][0-9]*', token) and int(token) < len(value):
            value = value[int(token)]
        else:
            raise ValueError('evidence json_pointer does not exist')
    return value


def r6_checks(payload: dict) -> dict:
    patterns = payload.get('patterns_status', {})
    if not isinstance(patterns, dict):
        raise ValueError('patterns_status must be an object')
    checks = {}
    modes = set()
    for pattern in patterns.values():
        if not isinstance(pattern, dict):
            raise ValueError('pattern must be an object')
        if 'candidate_checks' not in pattern:
            continue  # Legacy prose is preserved, not certified coverage.
        mode = pattern.get('mode_id')
        if type(mode) is not int or mode not in range(1, 11) or mode in modes:
            raise ValueError('unknown/duplicate mode identity')
        modes.add(mode)
        entries = pattern.get('candidate_checks')
        if not isinstance(entries, list):
            raise ValueError('candidate_checks must be an array')
        for check in entries:
            if not isinstance(check, dict) or not isinstance(check.get('ts_code'), str):
                raise ValueError('invalid candidate check')
            key = (mode, check['ts_code'])
            if key in checks:
                raise ValueError('duplicate candidate check')
            checks[key] = check
    return checks


def r6_coverage(payload: dict, codes: list[str], sources: dict) -> dict:
    """Pure coverage/reference validation. R6 owns semantics and time windows.

    `sources` must come from the trusted bound reader, never the model proposal.
    Old global booleans are deliberately ignored. False and zero are evidence.
    """
    checks = r6_checks(payload)
    completed, evaluated = [], set()
    for (mode, code), check in checks.items():
        if code not in codes:
            raise ValueError('candidate check outside original research objects')
        completion = check.get('completion')
        refs, missing = check.get('evidence_refs'), check.get('missing_evidence')
        if (completion not in {'completed', 'incomplete'} or not isinstance(refs, list)
                or not isinstance(missing, list) or any(not isinstance(x, str) or not x.strip() for x in missing)):
            raise ValueError('invalid completion/evidence/missing_evidence')
        for ref in refs:
            if not isinstance(ref, dict) or set(ref) != {'source', 'json_pointer'} or ref['source'] not in sources:
                raise ValueError('evidence source outside bound scope')
            value = json_pointer(sources[ref['source']], ref['json_pointer'])
            if completion == 'completed' and value is None:
                raise ValueError('null evidence cannot certify completion')

        if completion == 'completed':
            if not refs or missing:
                raise ValueError('completed check lacks required evidence references')
            evaluated.add(code)
        elif not missing:
            raise ValueError('incomplete check must retain missing evidence')
    for code in codes:
        if all(checks.get((m, code), {}).get('completion') == 'completed' for m in R6_REQUIRED_MODES):
            completed.append(code)
    return {'completed': completed, 'incomplete': [c for c in codes if c not in completed],
            'evaluated': sorted(evaluated), 'formal_review_completed': bool(codes) and len(completed) == len(codes)}


def merge_r6_revision(original: dict, proposal: dict, targets: dict, codes: list[str], sources: dict) -> tuple[dict, dict]:
    """Only nominated incomplete cells change; all original findings survive."""
    from copy import deepcopy
    if not isinstance(proposal, dict) or set(proposal) != {'candidate_checks', 'counter_arguments', 'hard_rejects', 'markdown'}:
        raise ValueError('local proposal has unexpected fields')
    if not isinstance(proposal['markdown'], str) or not proposal['markdown'].strip():
        raise ValueError('local Markdown delivery missing')
    old = r6_checks(original)
    expected = {(m, c) for c, modes in targets.items() for m in modes}
    updates = {}
    if not isinstance(proposal['candidate_checks'], list):
        raise ValueError('local candidate_checks must be array')
    for entry in proposal['candidate_checks']:
        if not isinstance(entry, dict) or set(entry) != {'mode_id','ts_code','completion','evidence_refs','missing_evidence'} or type(entry.get('mode_id')) is not int:
            raise ValueError('local candidate check fields/mode_id invalid')
        key = (entry['mode_id'], entry.get('ts_code'))
        if key not in expected or key in updates:
            raise ValueError('local update outside approved targets or duplicate')
        if old.get(key, {}).get('completion') == 'completed':
            raise ValueError('cannot replace completed check')
        replacement = {k: deepcopy(v) for k, v in entry.items() if k != 'mode_id'}
        if key in old:
            preserved = deepcopy(old[key])
            old_refs = preserved.get('evidence_refs', [])
            if not isinstance(old_refs,list) or not isinstance(replacement['evidence_refs'],list):
                raise ValueError('candidate evidence_refs must be an array')
            combined = deepcopy(old_refs)
            combined.extend(ref for ref in replacement['evidence_refs'] if ref not in combined)
            preserved.update(replacement)
            preserved['evidence_refs'] = combined
            replacement = preserved
        updates[key] = replacement
    if set(updates) != expected:
        raise ValueError('local proposal missing nominated checks')
    result = deepcopy(original)
    patterns = result.setdefault('patterns_status', {})
    for (mode, code), check in updates.items():
        keys = [k for k,v in patterns.items() if v.get('mode_id') == mode]
        if keys:
            pattern = patterns[keys[0]]
            pattern.setdefault('candidate_checks', [])
        else:
            name = f'local_mode_{mode}'
            if name in patterns:
                raise ValueError('reserved local mode name collision')
            pattern = patterns[name] = {'mode_id': mode, 'candidate_checks': []}
        entries = pattern['candidate_checks']
        index = next((i for i,c in enumerate(entries) if c.get('ts_code') == code), None)
        if index is None:
            entries.append(check)
        else:
            entries[index] = check
    for field in ('counter_arguments', 'hard_rejects'):
        items = proposal[field]
        if not isinstance(items, list) or any(not isinstance(x, dict) for x in items):
            raise ValueError('local findings must be arrays of objects')
        for item in items:
            if item.get('ts_code') not in targets or type(item.get('mode_id')) is not int or item['mode_id'] not in targets[item['ts_code']]:
                raise ValueError('new finding outside nominated scope')
            if field == 'counter_arguments' and item.get('severity') not in {'soft_suggest','strong_suggest','hard_reject'}:
                raise ValueError('invalid counter-argument severity')
            if (field == 'hard_rejects' or item.get('severity') == 'hard_reject') and item['mode_id'] not in {6,7}:
                raise ValueError('only existing mode 6/7 may produce hard rejects')
        result.setdefault(field, []).extend(deepcopy(items))
    coverage = r6_coverage(result, codes, sources)
    result['formal_review_completed'] = coverage['formal_review_completed']
    # Completion is not approval; never manufacture a positive review verdict.
    if not coverage['formal_review_completed']:
        result['status'] = 'partial'
        result['review_passed'] = False
    else:
        result['status'] = 'complete'
    if result.get('hard_rejects') or any(x.get('severity') == 'hard_reject' for x in result.get('counter_arguments',[])):
        result['review_passed'] = False
    # A legacy count is not retroactively a machine-certified per-stock count.
    # Only replace the whole-batch count when full structured coverage proves it.
    if coverage['formal_review_completed']:
        result['candidates_evaluated'] = len(codes)
    return result, coverage


def confidence(data: dict) -> float | None:
    """Unknown/unrated is null, not a measured zero (bool is not a score)."""
    value = data.get("confidence")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if 0 <= value <= 1 and math.isfinite(value) else None
