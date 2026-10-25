from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from src.settings import DATA_DIR, ROOT
from src.trading_agent.models import is_blocked_prefix, normalize_name_is_st
from trading.account_config import AccountConfig, DEFAULT_CONFIG_PATH, load_account_config as _load_account_config
from trading.execution_authorization import bind_execution_authorization, buy_budget_reasons, merge_risk_limits, resolve_execution_mode, validate_risk_limits
from trading.executors.registry import all_entry_types, all_exit_types
from trading.order.qmt_context import QMTContext
from trading.positions_state import PositionsStateStore
from trading.schema.normalize import normalize_plan_dict
from trading.schema.watchlist_plan import StockEntry, WatchlistPlan
from trading.watcher.dispatch import dispatch_plan, simulate_all_rule_types

RUNTIME_DIR = DATA_DIR / "runtime"


def load_account_config() -> AccountConfig:
    """Check raw consent before the legacy config reader can coerce strings."""
    import yaml

    raw = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("mode") not in ("live", "dry_run"):
        raise ValueError("account mode must be explicit live or dry_run")
    for key in ("autonomous_trading_enabled", "requires_user_confirmation"):
        if type(raw.get(key)) is not bool:
            raise ValueError(f"account {key} must be an explicit boolean")
    risk = validate_risk_limits(raw.get("risk_limits", {}))
    from dataclasses import replace
    return replace(_load_account_config(DEFAULT_CONFIG_PATH), mode=raw["mode"],
                   autonomous_trading_enabled=raw["autonomous_trading_enabled"],
                   requires_user_confirmation=raw["requires_user_confirmation"], risk_limits=risk)


def _plan_payload(plan: WatchlistPlan) -> dict[str, Any]:
    payload = plan.model_dump(mode="json")
    # Do not turn schema's descriptive positive defaults into budget authority.
    payload["risk_limits"] = plan.risk_limits.model_dump(mode="json", exclude_unset=True)
    for pool in ("execution_pool", "watch_pool"):
        for stock, row in zip(getattr(plan, pool), payload[pool]):
            if "max_position_pct" not in stock.model_fields_set:
                row["max_position_pct"] = 0
    return payload


def _validated_trade_date(trade_date: object) -> str:
    if not isinstance(trade_date, str) or not re.fullmatch(r"\d{8}|\d{4}-\d{2}-\d{2}", trade_date):
        raise ValueError("trade_date must be YYYYMMDD or YYYY-MM-DD")
    compact = trade_date.replace("-", "")
    datetime.strptime(compact, "%Y%m%d")
    return compact


def plan_path(trade_date: str) -> Path:
    trade_date = _validated_trade_date(trade_date)
    canonical = DATA_DIR / "plans" / trade_date / "watchlist_plan.json"
    if canonical.exists():
        return canonical
    return RUNTIME_DIR / f"watchlist_plan_{trade_date}.json"


def load_raw_plan(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"watchlist plan not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def parse_plan(data: dict[str, Any]) -> WatchlistPlan:
    hermes_status = data.get("status")
    if hermes_status == "stub":
        raise ValueError(f"refusing stub plan for trade_date={data.get('trade_date')}")
    return WatchlistPlan.model_validate(normalize_plan_dict(data))


def validate_plan_for_date(data: dict[str, Any], trade_date: str) -> WatchlistPlan:
    """Validate the execution handoff before touching runtime or QMT.

    Normalization is deliberately not allowed to discard malformed pool rows or
    coerce safety flags at this boundary. Unknown schema versions fail closed.
    """
    trade_date = _validated_trade_date(trade_date)
    if not isinstance(data, dict):
        raise ValueError("watchlist plan must be an object")
    if data.get("schema_version") not in ("1.0", "watchlist_plan_v1"):
        raise ValueError("unsupported watchlist plan schema_version")
    if _validated_trade_date(data.get("trade_date")) != trade_date:
        raise ValueError(f"watchlist plan trade_date mismatch: expected {trade_date}")
    if data.get("mode") not in ("live", "dry_run"):
        raise ValueError("watchlist plan mode must be live or dry_run")
    for flag in ("autonomous_trading_enabled", "requires_user_confirmation"):
        if type(data.get(flag)) is not bool:
            raise ValueError(f"watchlist plan {flag} must be an explicit boolean")
    if "no_trade" in data and type(data["no_trade"]) is not bool:
        raise ValueError("watchlist plan no_trade must be a boolean")
    if (data.get("no_trade") or data.get("decision_status") == "no_trade") and data["mode"] == "live":
        raise ValueError("no_trade plan cannot use live mode")
    from scripts.research.pipeline_artifacts import plan_reassessment_reasons
    if plan_reassessment_reasons(data) and (
        data["mode"] != "dry_run"
        or data["autonomous_trading_enabled"]
        or not data["requires_user_confirmation"]
    ):
        raise ValueError("unready plan must remain dry_run with explicit user confirmation and no autonomy")
    for pool in ("execution_pool", "watch_pool"):
        rows = data.get(pool)
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError(f"watchlist plan {pool} must be a list of objects")
        for row in rows:
            for flag in ("auto_trade_enabled", "requires_user_confirmation"):
                if flag in row and type(row[flag]) is not bool:
                    raise ValueError(f"{pool}.{flag} must be a boolean")
            for rules in ("entry_rules", "exit_rules"):
                if rules in row and (not isinstance(row[rules], list) or any(
                    not isinstance(rule, dict) for rule in row[rules]
                )):
                    raise ValueError(f"{pool}.{rules} must be a list of objects")
    validate_risk_limits(data.get("risk_limits", {}))
    plan = parse_plan(data)
    entry_types, exit_types = all_entry_types(), all_exit_types()
    for stock in plan.execution_pool + plan.watch_pool:
        if any(rule.type not in entry_types for rule in stock.entry_rules):
            raise ValueError("unsupported entry_rules[].type")
        if any(rule.type not in exit_types for rule in stock.exit_rules):
            raise ValueError("unsupported exit_rules[].type")
    return plan


def _atomic_write(path: Path, content: bytes) -> None:
    """Same-directory replace: failure leaves the last good file intact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as fh:
            temporary = Path(fh.name)
            fh.write(content)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def stage_plan(trade_date: str) -> Path:
    """Canonical is authoritative; never use existence/mtime as freshness.

    Bad canonical input raises rather than executing an obsolete good copy.
    Replacing a restricted same-day copy is not permission to promote to live;
    that transition requires explicit review outside this automatic handoff.
    """
    trade_date = _validated_trade_date(trade_date)
    src = plan_path(trade_date)
    runtime = RUNTIME_DIR / f"watchlist_plan_{trade_date}.json"
    content = src.read_bytes()
    candidate = validate_plan_for_date(json.loads(content), trade_date)
    if src == runtime:
        return runtime
    if runtime.exists():
        previous_content = runtime.read_bytes()
        if previous_content == content:
            return runtime
        try:
            previous = validate_plan_for_date(json.loads(previous_content), trade_date)
        except (ValueError, TypeError):
            previous = None  # Invalid cache is not an execution authority.
        if previous is not None and candidate.mode == "live" and (
            previous.mode != "live"
            or getattr(previous, "no_trade", False)
            or getattr(previous, "decision_status", None) == "no_trade"
            or (candidate.autonomous_trading_enabled and not previous.autonomous_trading_enabled)
            or (previous.requires_user_confirmation and not candidate.requires_user_confirmation)
        ):
            raise ValueError("staging cannot expand live authorization; explicit review required")
    _atomic_write(runtime, content)
    return runtime


def apply_account_overrides(plan: WatchlistPlan, account: AccountConfig) -> WatchlistPlan:
    # Validate injected AccountConfig objects too, without coercing permissions.
    resolve_execution_mode(
        plan_mode=plan.mode, plan_autonomous=plan.autonomous_trading_enabled,
        plan_confirmation=plan.requires_user_confirmation, account_mode=account.mode,
        account_autonomous=account.autonomous_trading_enabled,
        account_confirmation=account.requires_user_confirmation, requested_mode="dry_run",
    )
    payload = _plan_payload(plan)
    # Account settings can restrict a plan, never grant missing plan consent.
    no_trade = bool(payload.get("no_trade")) or payload.get("decision_status") == "no_trade"
    payload["mode"] = "live" if plan.mode == account.mode == "live" and not no_trade else "dry_run"
    payload["autonomous_trading_enabled"] = plan.autonomous_trading_enabled and account.autonomous_trading_enabled and not no_trade
    payload["requires_user_confirmation"] = plan.requires_user_confirmation or account.requires_user_confirmation or no_trade
    # Existing schema safety defaults apply even when omitted; unlike budget
    # defaults they are protections, not grants of spending authority.
    for key in ("block_prefixes", "block_st", "kill_switch_file", "account_hard_stop_loss_pct"):
        payload["risk_limits"].setdefault(key, getattr(plan.risk_limits, key))
    payload["risk_limits"] = merge_risk_limits(payload["risk_limits"], account.risk_limits)
    reasons = buy_budget_reasons(payload["risk_limits"])
    payload["execution_authorization"] = {"buy_budget_blockers": reasons}
    for row in payload["execution_pool"]:
        row["auto_trade_enabled"] = bool(
            row["auto_trade_enabled"] and not row["requires_user_confirmation"]
            and payload["autonomous_trading_enabled"]
            and not payload["requires_user_confirmation"] and not reasons
        )
    return WatchlistPlan.model_validate(payload)


def _compliance_reason(stock: StockEntry, risk: dict[str, Any]) -> str | None:
    prefixes = tuple(risk.get("block_prefixes") or ())
    if prefixes and is_blocked_prefix(stock.ts_code, prefixes):
        return f"blocked prefix: {stock.ts_code}"
    if risk.get("block_st") and (stock.is_st or normalize_name_is_st(stock.name)):
        return "blocked ST/risk-warning stock"
    return None


def apply_compliance(plan: WatchlistPlan) -> WatchlistPlan:
    risk = plan.risk_limits.model_dump()
    execution: list[StockEntry] = []
    watch: list[StockEntry] = []
    rejected = list(plan.rejected)

    for stock in plan.execution_pool:
        reason = _compliance_reason(stock, risk)
        if reason:
            rejected.append({**stock.model_dump(mode="json"), "reason": reason, "from_pool": "execution_pool"})
            if stock.exit_rules or stock.plan_status == "execution_pool_exit_at_open":
                # A buy prohibition cannot remove an explicitly planned exit.
                execution.append(stock.model_copy(update={"auto_trade_enabled": False, "entry_rules": []}))
        else:
            execution.append(stock)
    for stock in plan.watch_pool:
        reason = _compliance_reason(stock, risk)
        if reason:
            rejected.append({**stock.model_dump(mode="json"), "reason": reason, "from_pool": "watch_pool"})
            if stock.exit_rules or stock.plan_status == "execution_pool_exit_at_open":
                watch.append(stock.model_copy(update={"auto_trade_enabled": False, "entry_rules": []}))
        else:
            watch.append(stock)

    payload = _plan_payload(plan)
    payload["execution_pool"] = [s.model_dump(mode="json") for s in execution]
    payload["watch_pool"] = [s.model_dump(mode="json") for s in watch]
    payload["rejected"] = rejected
    return WatchlistPlan.model_validate(payload)


def apply_qmt_overrides(
    plan: WatchlistPlan,
    holdings: dict[str, dict[str, Any]],
    *,
    account: AccountConfig,
) -> WatchlistPlan:
    payload = _plan_payload(plan)
    exec_rows: list[dict[str, Any]] = []
    for raw in payload.get("execution_pool") or []:
        row = dict(raw)
        code = row["ts_code"]
        held = code in holdings and int(holdings[code].get("total_qty") or 0) > 0
        row["auto_trade_enabled"] = bool(
            row["auto_trade_enabled"] and not row["requires_user_confirmation"]
            and plan.autonomous_trading_enabled and not plan.requires_user_confirmation
            and not buy_budget_reasons(payload["risk_limits"])
        )
        if held and not row.get("plan_status"):
            row["plan_status"] = "execution_pool_hold"
        exec_rows.append(row)
    # The legacy dispatcher exits only execution_pool. Expose held watch rows
    # with explicit exit rules as exit-only copies, never as buy promotions.
    execution_codes = {row["ts_code"] for row in exec_rows}
    for raw in payload.get("watch_pool") or []:
        code = raw["ts_code"]
        if (code not in execution_codes and int(holdings.get(code, {}).get("total_qty") or 0) > 0
                and (raw.get("exit_rules") or raw.get("plan_status") == "execution_pool_exit_at_open")):
            exec_rows.append({**raw, "auto_trade_enabled": False, "entry_rules": []})
            execution_codes.add(code)
    payload["execution_pool"] = exec_rows

    qmt_audit = {
        "tool": "trading.load_plan",
        "asof": datetime.now().isoformat(),
        "holdings_count": len(holdings),
        "status": "complete",
    }
    payload.setdefault("data_sources", {})["qmt"] = qmt_audit
    return WatchlistPlan.model_validate(payload)


def tighten_stop_loss(plan: WatchlistPlan) -> WatchlistPlan:
    hard_pct = plan.risk_limits.account_hard_stop_loss_pct
    if not hard_pct:
        return plan
    payload = _plan_payload(plan)
    for row in payload.get("execution_pool") or []:
        cost_hint = float(row.get("stop_loss") or 0)
        if cost_hint <= 0:
            continue
        account_floor = cost_hint * (1 - float(hard_pct))
        row["stop_loss"] = max(cost_hint, account_floor)
    return WatchlistPlan.model_validate(payload)


def write_plan(plan: WatchlistPlan, path: Path) -> None:
    _atomic_write(path, json.dumps(_plan_payload(plan), ensure_ascii=False, indent=2).encode("utf-8"))


def write_pipeline_state(
    trade_date: str,
    *,
    mode: str,
    dispatch_report: dict[str, Any],
    plan_path_value: str,
) -> Path:
    out = RUNTIME_DIR / f"pipeline_state_{trade_date}.json"
    payload = {
        "schema_version": "1.0",
        "trade_date": trade_date,
        "generated_at": datetime.now().isoformat(),
        "generated_by": "trading.load_plan@v1",
        "status": "ok",
        "steps": {
            "load_plan": {
                "status": "ok",
                "plan_path": plan_path_value,
                "mode": mode,
            },
            "dispatch": dispatch_report,
        },
        "registered_entry_types": all_entry_types(),
        "registered_exit_types": all_exit_types(),
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def run_load_plan(
    trade_date: str,
    *,
    mode: str | None = None,
    simulate: bool = False,
    account_config: AccountConfig | None = None,
    dispatch: bool = True,
) -> dict[str, Any]:
    """Prepare a validated loaded copy, optionally execute one legacy pass.

    Compatibility default dispatch=True preserves CLI/existing callers.
    dispatch=False performs only plan/account I/O: no QMT construction,
    holdings, position writes/resets or executor calls. Watcher/daemon use this
    explicit preparation path and own their single dispatch.
    """
    if type(dispatch) is not bool or type(simulate) is not bool:
        raise ValueError("dispatch and simulate must be booleans")
    if not dispatch and simulate:
        raise ValueError("simulate-all-rules requires dispatch=True")
    trade_date = _validated_trade_date(trade_date)
    src = stage_plan(trade_date)
    plan = validate_plan_for_date(load_raw_plan(src), trade_date)
    account = account_config or load_account_config()
    plan = apply_account_overrides(plan, account)
    effective_mode = resolve_execution_mode(
        plan_mode=plan.mode, plan_autonomous=plan.autonomous_trading_enabled,
        plan_confirmation=plan.requires_user_confirmation, account_mode=account.mode,
        account_autonomous=account.autonomous_trading_enabled,
        account_confirmation=account.requires_user_confirmation,
        requested_mode=mode, simulate=simulate,
    )
    payload = _plan_payload(plan)
    payload["mode"] = effective_mode
    plan = WatchlistPlan.model_validate(payload)
    dry_run = effective_mode == "dry_run"

    plan = apply_compliance(plan)
    plan = tighten_stop_loss(plan)

    loaded_path = RUNTIME_DIR / f"watchlist_plan_{trade_date}.loaded.json"
    if not dispatch:
        write_plan(plan, loaded_path)
        return {"ok": True, "trade_date": trade_date, "mode": effective_mode,
                "plan_path": str(loaded_path), "dispatched": False}

    qmt_ctx = QMTContext(
        trade_date=trade_date,
        dry_run=dry_run,
        kill_switch_file=plan.risk_limits.kill_switch_file,
        authorization=bind_execution_authorization(plan, account, effective_mode=effective_mode),
    )
    qmt_ctx.refresh_holdings(allow_file_fallback=True)
    plan = apply_qmt_overrides(plan, qmt_ctx.holdings, account=account)
    qmt_ctx.authorization = bind_execution_authorization(plan, account, effective_mode=effective_mode)

    positions = PositionsStateStore.for_mode(trade_date=trade_date, dry_run=dry_run)
    positions.load()
    # Reloading within one date must not erase completed T actions.
    for position in positions.positions.values():
        if position.t_state.date != trade_date:
            from trading.positions_state import TState
            position.t_state = TState(date=trade_date)
    positions.ensure_from_holdings(
        qmt_ctx.holdings,
        base_mobile_ratio=account.default_base_mobile_ratio,
    )
    for stock in plan.execution_pool:
        ratio = stock.base_mobile_ratio or account.default_base_mobile_ratio
        if stock.ts_code in positions.positions:
            positions.positions[stock.ts_code].base_mobile_ratio = ratio
    positions.save()

    write_plan(plan, loaded_path)

    if dry_run and simulate:
        dispatch_report = simulate_all_rule_types(plan, qmt_ctx, positions)
    else:
        dispatch_report = dispatch_plan(plan, qmt_ctx, positions, simulate=dry_run)

    positions.save()
    state_path = write_pipeline_state(
        trade_date,
        mode=effective_mode,
        dispatch_report={
            "entry_count": len(dispatch_report.entry_results),
            "exit_count": len(dispatch_report.exit_results),
            "watch_started": dispatch_report.watch_started,
            "skipped": dispatch_report.skipped,
            "entry_results": dispatch_report.entry_results,
            "exit_results": dispatch_report.exit_results,
        },
        plan_path_value=str(loaded_path.relative_to(ROOT)),
    )

    return {
        "ok": True,
        "trade_date": trade_date,
        "mode": effective_mode,
        "plan_path": str(loaded_path),
        "dispatched": True,
        "pipeline_state_path": str(state_path),
        "orders_path": str(qmt_ctx.orders_path),
        "events_path": str(qmt_ctx.events_path),
        "dispatch": dispatch_report,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Load Hermes watchlist_plan and dispatch executors")
    parser.add_argument("--date", dest="trade_date", default=datetime.now().strftime("%Y%m%d"))
    parser.add_argument("--mode", choices=["live", "dry_run"], default=None)
    parser.add_argument(
        "--simulate-all-rules",
        action="store_true",
        help="dry-run only: force one pass per entry/exit executor type",
    )
    args = parser.parse_args(argv)
    trade_date = args.trade_date.replace("-", "")
    result = run_load_plan(
        trade_date,
        mode=args.mode,
        simulate=args.simulate_all_rules,
    )
    print(json.dumps({k: v for k, v in result.items() if k != "dispatch"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
