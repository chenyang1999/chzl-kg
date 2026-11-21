from __future__ import annotations

from typing import Any

from trading.schema.watchlist_plan import WatchlistPlan

LEGACY_ENTRY_TYPE_MAP = {
    "deep_pullback_only": "trend_pullback_buy",
    "mainline_reflow_confirm": "trend_pullback_buy",
    "breakout_retest_buy": "leader_breakout",
    "event_driven_open_confirmation": "low_absorption_intraday",
}


def normalize_stock_row(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out.setdefault("theme", "unknown")
    out.setdefault("role", "watch")
    out.setdefault("score", 0)
    out.setdefault("reason", "")
    out.setdefault("entry_rules", [])
    out.setdefault("exit_rules", [])
    rules: list[dict[str, Any]] = []
    for rule in out.get("entry_rules") or []:
        if not isinstance(rule, dict):
            continue
        mapped = dict(rule)
        mapped["type"] = LEGACY_ENTRY_TYPE_MAP.get(str(mapped.get("type") or ""), mapped.get("type"))
        rules.append(mapped)
    out["entry_rules"] = rules
    return out


def normalize_plan_dict(data: dict[str, Any]) -> dict[str, Any]:
    payload = dict(data)
    confirm = payload.get("requires_user_confirmation")
    if isinstance(confirm, list):
        payload["requires_user_confirmation"] = bool(confirm)
        notes = payload.setdefault("notes", [])
        if isinstance(notes, list):
            for item in confirm:
                text = str(item).strip()
                if text and text not in notes:
                    notes.append(text)
    elif confirm is not None and not isinstance(confirm, bool):
        payload["requires_user_confirmation"] = bool(confirm)
    for key in ("execution_pool", "watch_pool"):
        payload[key] = [normalize_stock_row(row) for row in payload.get(key) or [] if isinstance(row, dict)]
    return payload


def normalize_plan(plan: WatchlistPlan) -> WatchlistPlan:
    return WatchlistPlan.model_validate(normalize_plan_dict(plan.model_dump(mode="json")))
