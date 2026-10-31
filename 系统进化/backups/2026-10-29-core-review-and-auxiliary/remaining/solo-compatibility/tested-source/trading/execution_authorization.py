"""Pure, restrictive execution-boundary helpers; no settings/broker/file I/O.

Only existing RiskLimits fields have merge semantics. Unknown predicates must
be implemented/reviewed rather than silently dropped or guessed by name.
Eligibility/buy budgets never authorize a sell or grant live consent.
"""
from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any
from dataclasses import dataclass
import json

POSITION_CAP = "target_total_position_pct"
COUNT_CAPS = ("max_positions", "max_buy_orders_per_day", "max_orders_per_symbol_per_day")
BUY_CAPS = (POSITION_CAP, *COUNT_CAPS)
KNOWN_RISK_FIELDS = {*BUY_CAPS, "block_prefixes", "block_st", "kill_switch_file",
                     "account_hard_stop_loss_pct"}


def validate_risk_limits(risk: Any) -> dict[str, Any]:
    if not isinstance(risk, Mapping):
        raise ValueError("risk_limits must be an object")
    if set(risk) - KNOWN_RISK_FIELDS:
        raise ValueError("unsupported risk_limits fields: " + ", ".join(sorted(set(risk) - KNOWN_RISK_FIELDS)))
    out = dict(risk)
    for key, value in out.items():
        if key in (POSITION_CAP, "account_hard_stop_loss_pct"):
            if key == "account_hard_stop_loss_pct" and value is None:
                continue  # Schema-defined optional protection, not a buy budget.
            if (type(value) not in (int, float) or not isfinite(value)
                    or not 0 <= value <= 1):
                raise ValueError(f"risk_limits.{key} must be a finite fraction in [0, 1]")
        elif key in COUNT_CAPS:
            if type(value) is not int or value < 0:
                raise ValueError(f"risk_limits.{key} must be a nonnegative integer")
        elif key == "block_st":
            if type(value) is not bool:
                raise ValueError("risk_limits.block_st must be a boolean")
        elif key == "block_prefixes":
            if (not isinstance(value, list) or any(not isinstance(p, str) or not p
                    or not p.isascii() or not p.isdigit() or len(p) > 6 for p in value)):
                raise ValueError("risk_limits.block_prefixes must be a list of numeric prefixes")
        elif key == "kill_switch_file":
            if not isinstance(value, str) or not value.strip():
                raise ValueError("risk_limits.kill_switch_file must be a nonempty path")
    return out


def merge_risk_limits(plan: Mapping, account: Mapping) -> dict[str, Any]:
    """Intersect explicit caps; never populate a missing plan budget from account.

    Schema defaults for non-budget safety fields remain the caller's concern.
    Account-only protections are allowed; different kill-switch paths cannot be
    represented by the single-path schema, so require explicit reconciliation.
    """
    left, right = validate_risk_limits(plan), validate_risk_limits(account)
    out = dict(left)
    for key, value in right.items():
        if key in BUY_CAPS:
            if key in left:
                out[key] = min(left[key], value)
        elif key == "block_prefixes":
            out[key] = list(dict.fromkeys([*left.get(key, []), *value]))
        elif key == "block_st":
            out[key] = left.get(key, True) or value
        elif key == "account_hard_stop_loss_pct":
            # Existing loader treats 0/None as disabled, unlike buy caps where
            # zero is a hard ban. Disabled protection cannot erase an active one.
            values = [v for v in (left.get(key), value) if v not in (None, 0)]
            out[key] = min(values) if values else (0 if left.get(key) == 0 or value == 0 else None)
        elif key == "kill_switch_file":
            if key in left and left[key] != value:
                raise ValueError("conflicting risk_limits.kill_switch_file; cannot discard either protection")
            out[key] = value
    return out


def buy_budget_reasons(risk: Mapping) -> list[str]:
    risk = validate_risk_limits(risk)
    return [f"{key}:{'missing' if key not in risk else 'zero'}" for key in BUY_CAPS
            if key not in risk or risk[key] == 0]


def resolve_execution_mode(*, plan_mode: Any, plan_autonomous: Any,
                           plan_confirmation: Any, account_mode: Any,
                           account_autonomous: Any, account_confirmation: Any,
                           requested_mode: Any = None, simulate: bool = False) -> str:
    """CLI/live is a request, not consent; explicit dry_run only restricts."""
    if plan_mode not in ("live", "dry_run") or account_mode not in ("live", "dry_run"):
        raise ValueError("execution mode must be live or dry_run")
    if requested_mode not in (None, "live", "dry_run") or type(simulate) is not bool:
        raise ValueError("invalid execution mode/simulate request")
    for value in (plan_autonomous, plan_confirmation, account_autonomous, account_confirmation):
        if type(value) is not bool:
            raise ValueError("execution authorization flags must be explicit booleans")
    effective = "dry_run" if simulate or requested_mode == "dry_run" else (
        "live" if plan_mode == account_mode == "live" else "dry_run")
    if requested_mode == "live" and not simulate and effective != "live":
        raise ValueError("live mode cannot override a dry_run/no_trade plan or account")
    if effective == "live" and (not plan_autonomous or plan_confirmation
                               or not account_autonomous or account_confirmation):
        raise ValueError("live dispatch requires both plan and account authorization")
    return effective


@dataclass(frozen=True)
class ExecutionAuthorization:
    """Detached snapshots; rechecked at place_order, not serialized authority."""
    plan_json: str
    account_json: str
    effective_mode: str

    def validated_plan(self, *, trade_date: str, dry_run: bool) -> dict[str, Any]:
        from trading.schema.watchlist_plan import WatchlistPlan

        if type(dry_run) is not bool or self.effective_mode != ("dry_run" if dry_run else "live"):
            raise ValueError("authorization_mode_mismatch")
        plan, account = json.loads(self.plan_json), json.loads(self.account_json)
        checked = WatchlistPlan.model_validate(plan)
        if checked.trade_date != trade_date:
            raise ValueError("authorization_date_mismatch")
        from scripts.research.pipeline_artifacts import plan_reassessment_reasons
        if self.effective_mode == "live" and (
                plan.get("no_trade") or plan.get("decision_status") == "no_trade"
                or plan_reassessment_reasons(plan)):
            raise ValueError("authorization_plan_not_live_ready")
        for row in plan.get("execution_pool", []) + plan.get("watch_pool", []):
            for key in ("auto_trade_enabled", "requires_user_confirmation"):
                if type(row.get(key)) is not bool:
                    raise ValueError("authorization_stock_flags_invalid")
        actual = resolve_execution_mode(
            plan_mode=plan.get("mode"), plan_autonomous=plan.get("autonomous_trading_enabled"),
            plan_confirmation=plan.get("requires_user_confirmation"), account_mode=account.get("mode"),
            account_autonomous=account.get("autonomous_trading_enabled"),
            account_confirmation=account.get("requires_user_confirmation"),
            requested_mode=self.effective_mode,
        )
        if actual != self.effective_mode:
            raise ValueError("authorization_mode_mismatch")
        # Retain explicit-budget provenance instead of schema positive defaults.
        plan["risk_limits"] = merge_risk_limits(plan.get("risk_limits", {}), account.get("risk_limits", {}))
        plan["autonomous_trading_enabled"] = plan["autonomous_trading_enabled"] and account["autonomous_trading_enabled"]
        plan["requires_user_confirmation"] = plan["requires_user_confirmation"] or account["requires_user_confirmation"]
        return plan


def bind_execution_authorization(plan: Any, account: Any, *, effective_mode: str) -> ExecutionAuthorization:
    """Freeze consumer-validated schema/account state; add no permissions."""
    payload = plan.model_dump(mode="json")
    payload["risk_limits"] = plan.risk_limits.model_dump(mode="json", exclude_unset=True)
    for pool in ("execution_pool", "watch_pool"):
        for stock, row in zip(getattr(plan, pool), payload[pool]):
            if "max_position_pct" not in stock.model_fields_set:
                row["max_position_pct"] = 0  # Missing is not schema-default spending consent.
    account_payload = {key: getattr(account, key) for key in (
        "mode", "autonomous_trading_enabled", "requires_user_confirmation", "risk_limits")}
    result = ExecutionAuthorization(
        json.dumps(payload, allow_nan=False), json.dumps(account_payload, allow_nan=False), effective_mode)
    result.validated_plan(trade_date=plan.trade_date, dry_run=effective_mode == "dry_run")
    return result
