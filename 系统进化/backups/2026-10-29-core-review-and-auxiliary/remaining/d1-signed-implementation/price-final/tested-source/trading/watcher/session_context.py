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
    # A scan is a replacement snapshot, not an incremental success cache.
    # Invalidate first so malformed/empty/failed retries cannot keep old buys.
    clear_session()
    if not isinstance(payload, dict):
        return
    _SESSION["scan_meta"] = {
        "trade_date": payload.get("trade_date"),
        "buy_ready_count": payload.get("buy_ready_count"),
        "top_buy": payload.get("top_buy"),
    }
    failed = {str(row.get("ts_code") or "") for row in payload.get("errors") or []
              if isinstance(row, dict)}
    rows = payload.get("opportunities")
    if not isinstance(rows, list):
        return
    for row in rows:
        if not isinstance(row, dict):
            continue
        code = row.get("ts_code")
        if isinstance(code, str) and code and code not in failed:
            if code in _SESSION["opportunities"]:
                # Conflicting/duplicate evidence is not a confirmed signal.
                failed.add(code)
                _SESSION["opportunities"].pop(code, None)
            else:
                _SESSION["opportunities"][code] = dict(row)


def set_pattern(ts_code: str, pattern: dict[str, Any]) -> None:
    _SESSION["patterns"][ts_code] = pattern


def get_opportunity(ts_code: str) -> dict[str, Any] | None:
    return _SESSION["opportunities"].get(ts_code)


def get_pattern(ts_code: str) -> dict[str, Any] | None:
    return _SESSION["patterns"].get(ts_code)


def buy_allowed(ts_code: str, *, entry_style: str = "pullback",
                trade_date: str | None = None) -> tuple[bool, list[str]]:
    # The caller must supply its authorized plan/context date. Never infer
    # today's date or reuse a successful scan from another session/day.
    if (not isinstance(trade_date, str) or not trade_date
            or _SESSION["scan_meta"].get("trade_date") != trade_date):
        return False, ["scan_date_missing_or_mismatch"]
    opp = get_opportunity(ts_code)
    if opp is None:
        return False, ["missing_scan_evidence"]
    action = str(opp.get("action") or "watch")
    reasons = opp.get("reasons") or []
    if not isinstance(reasons, list):
        return False, ["invalid_scan_reasons"]
    if opp.get("sise_pass") is not True:
        return False, ["sise_gate_failed", opp.get("sise_reason") or "四色四量未达标"]
    if entry_style in {"low_absorption", "pullback", "low_absorption_intraday",
                       "t_add_pullback", "trend_pullback_buy"}:
        required = "buy_pullback"
    elif entry_style in {"breakout", "leader_breakout", "daban_confirm"}:
        required = "buy_breakout"
    else:
        return False, [f"unsupported_scan_entry_style={entry_style}"]
    if action != required:
        return False, [f"scan_action={action}; required={required}", *reasons]
    return True, [f"scan_action={action}", *reasons]
