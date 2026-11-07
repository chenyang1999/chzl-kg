"""单次 intraday 会话缓存：xtick 扫描结果供 executor 读取。"""
from __future__ import annotations

from typing import Any

_SESSION: dict[str, Any] = {
    "patterns": {},
    "daily_levels": {},
    "opportunities": {},
    "scan_meta": {},
}


def clear_session() -> None:
    _SESSION["patterns"] = {}
    _SESSION["daily_levels"] = {}
    _SESSION["opportunities"] = {}
    _SESSION["scan_meta"] = {}


def set_scan_result(payload: dict[str, Any]) -> None:
    _SESSION["scan_meta"] = {
        "trade_date": payload.get("trade_date"),
        "buy_ready_count": payload.get("buy_ready_count"),
        "top_buy": payload.get("top_buy"),
    }
    for row in payload.get("opportunities") or []:
        code = str(row.get("ts_code") or "")
        if code:
            _SESSION["opportunities"][code] = row


def set_pattern(ts_code: str, pattern: dict[str, Any]) -> None:
    _SESSION["patterns"][ts_code] = pattern


def get_opportunity(ts_code: str) -> dict[str, Any] | None:
    return _SESSION["opportunities"].get(ts_code)


def get_pattern(ts_code: str) -> dict[str, Any] | None:
    return _SESSION["patterns"].get(ts_code)


def buy_allowed(ts_code: str, *, entry_style: str = "pullback") -> tuple[bool, list[str]]:
    opp = get_opportunity(ts_code)
    if opp is None:
        return True, ["no_scan_data_pass_through"]
    action = str(opp.get("action") or "watch")
    if action == "skip":
        return False, [f"scan_action=skip", *(opp.get("reasons") or [])]
    sise_ok = bool(opp.get("sise_pass"))
    if not sise_ok:
        return False, ["sise_gate_failed", opp.get("sise_reason") or "四色四量未达标"]
    if entry_style in {"low_absorption", "pullback", "t_add_pullback", "trend_pullback_buy"}:
        if action == "buy_pullback":
            return True, [f"scan_action={action}", *(opp.get("reasons") or [])]
        if action == "watch":
            return False, ["scan_waiting_for_pullback_setup", *(opp.get("reasons") or [])]
    if entry_style in {"leader_breakout", "daban_confirm"}:
        if action == "buy_breakout":
            return True, [f"scan_action={action}", *(opp.get("reasons") or [])]
        return False, ["scan_no_breakout_setup"]
    return action.startswith("buy"), [f"scan_action={action}"]
