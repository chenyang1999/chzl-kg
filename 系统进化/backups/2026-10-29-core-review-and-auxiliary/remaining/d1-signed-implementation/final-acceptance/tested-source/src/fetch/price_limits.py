"""Dated actual price-limit classification; no board/name percentage guesses.

Existing plan/review limit_pct helpers omit effective dates and disagree on ST
precedence, so they are deliberately not used for live market statistics.
Source contract: Tushare stk_limit (official API document 183). Missing, special
or inconsistent records remain unknown instead of being counted as zero limits.
"""
from __future__ import annotations

import math
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any


def finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return result if math.isfinite(result) else None


def quote_time(value: Any) -> datetime | None:
    """Source time (Shanghai local when timezone absent), never capture time."""
    try:
        text = str(value)
        if "T" not in text and " " not in text:
            return None  # A date alone is not a quote/capture timestamp.
        return datetime.fromisoformat(text)
    except (ValueError, TypeError):
        return None


TZ = timezone(timedelta(hours=8))


def local_time(value: Any) -> datetime | None:
    stamp = quote_time(value)
    try:
        return stamp.replace(tzinfo=stamp.tzinfo or TZ).astimezone(TZ) if stamp else None
    except (OverflowError, ValueError):
        return None


def valid_quote_time(value: Any, trade_date: str, response_at: datetime) -> bool:
    """Regular-session quote, same business day, no later than its response.

    Quote event time is NOT HTTP request time. No quote-age limit is configured;
    don't silently impose either zero seconds or an invented grace interval.
    """
    stamp = local_time(value)
    return bool(stamp and stamp.strftime("%Y%m%d") == trade_date
                and time(9, 30) <= stamp.time() <= time(15)
                and stamp <= response_at)


def quote_age(minimum: Any, maximum: Any, response_at: datetime) -> dict[str, Any]:
    earliest, latest = local_time(minimum), local_time(maximum)
    return {
        "quote_age_min_seconds": (response_at - latest).total_seconds() if latest else None,
        "quote_age_max_seconds": (response_at - earliest).total_seconds() if earliest else None,
        "source_age_limit_seconds": None,
        "freshness_status": "age_limit_not_configured",
        "age_reference_at": response_at.isoformat(),
    }


def load_daily_limits(pro: Any, trade_date: str) -> dict[str, dict[str, Any]]:
    """Request only the given business date, never substitute today's limits."""
    records: list[dict[str, Any]] = []
    offset = 0
    # Official cap is 5800, including B-shares/funds; do not silently truncate.
    while True:
        df = pro.stk_limit(trade_date=trade_date, offset=offset, limit=5800,
                           fields="trade_date,ts_code,pre_close,up_limit,down_limit")
        if df is None or df.empty:
            break
        page = df.to_dict("records")
        if offset and page == records[-len(page):]:
            raise ValueError("stk_limit pagination did not advance")
        records.extend(page)
        if len(page) < 5800:
            break
        offset += len(page)
    out: dict[str, dict[str, Any]] = {}
    conflicts: set[str] = set()
    for row in records:
        code = str(row.get("ts_code") or "")
        if str(row.get("trade_date")) != trade_date or not code:
            continue
        record = {**row, "limit_trade_date": trade_date}
        if code in out and out[code] != record:
            conflicts.add(code)
        out[code] = record
    return {code: row for code, row in out.items() if code not in conflicts}


def classify_price_limit(row: dict[str, Any], trade_date: str | None = None) -> tuple[str, str]:
    """Return limit_up/limit_down/not_limit/unknown plus the evidence reason.

    Effective-date actual bounds take precedence over code prefix or name.
    Explicit suspension/unlimited/special state cannot be a confirmed hit.
    No ST rule, IPO trading-day estimate or inferred price-limit ratio is added.
    """
    if (row.get("no_price_limit") is True or row.get("is_suspended") is True
            or row.get("limit_status") in {"unknown", "unlimited", "special", "suspended"}):
        return "unknown", "special_or_suspended"
    day = str(row.get("limit_trade_date") or row.get("trade_date") or "")
    if not trade_date or day != trade_date:
        return "unknown", "missing_or_mismatched_effective_date"
    close = finite_number(row.get("close"))
    upper = finite_number(row.get("up_limit"))
    lower = finite_number(row.get("down_limit"))
    if close is None or close <= 0 or upper is None or lower is None or not 0 < lower < upper:
        return "unknown", "missing_or_invalid_actual_bounds"
    # Decimal avoids float equality noise; not a widened percentage/tick rule.
    price, hi, lo = map(lambda n: Decimal(str(n)), (close, upper, lower))
    eps = Decimal("0.00000001")
    if price > hi + eps or price < lo - eps:
        return "unknown", "price_outside_actual_bounds"
    if abs(price - hi) <= eps:
        return "limit_up", "dated_actual_price"
    if abs(price - lo) <= eps:
        return "limit_down", "dated_actual_price"
    return "not_limit", "dated_actual_price"
