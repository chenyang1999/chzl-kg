"""Shared, time-bounded chart data; no credentials or market I/O at import."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any

CN_TZ = timezone(timedelta(hours=8))
DEFAULT_PERIODS = [
    {"period": "1d", "days": 365, "label": "日K", "max_bars": 120},
    {"period": "1w", "days": 520, "label": "周K", "max_bars": 80},
    {"period": "60m", "days": 60, "label": "60分", "max_bars": 120},
    {"period": "15m", "days": 30, "label": "15分", "max_bars": 120},
]


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def cutoff_time(value: str | None = None) -> datetime:
    if not value:
        return datetime.now(CN_TZ)
    if len(value) == 8 and value.isdigit():
        return datetime.strptime(value, "%Y%m%d").replace(hour=23, minute=59, second=59, tzinfo=CN_TZ)
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CN_TZ)
    return dt.astimezone(CN_TZ)


def bar_time(value: Any) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000 if value > 1e12 else value, CN_TZ)
    dt = datetime.fromisoformat(str(value))
    return dt.replace(tzinfo=CN_TZ) if dt.tzinfo is None else dt.astimezone(CN_TZ)


def context_from_panels(panels: list[dict]) -> list[dict]:
    out = []
    for panel in panels:
        bars = panel.get("candles") or []
        item = {"period": panel["period"], "label": panel["label"], "source": panel.get("source"), "count": len(bars)}
        if not bars:
            out.append({**item, "empty": True})
            continue
        closes = [float(b["close"]) for b in bars]
        last, previous = bars[-1], bars[-2] if len(bars) > 1 else bars[-1]
        item.update(close=closes[-1], last_date=last["time"], pct_chg=(closes[-1] / float(previous["close"]) - 1) * 100 if previous["close"] else None)
        for n in (5, 20, 60):
            item[f"ma{n}"] = sum(closes[-n:]) / n if len(closes) >= n else None
        item["high20"] = max(float(b["high"]) for b in bars[-20:])
        item["low20"] = min(float(b["low"]) for b in bars[-20:])
        volumes = {str(v["time"]): float(v["value"]) for v in panel.get("volumes", [])}
        item["volume_last"] = volumes.get(str(last["time"]))
        recent_volumes = [volumes.get(str(b["time"])) for b in bars[-5:]]
        valid_volumes = [v for v in recent_volumes if v is not None]
        item["volume_ma5"] = sum(valid_volumes) / 5 if len(valid_volumes) == 5 else None
        item["volume_ratio5"] = item["volume_last"] / item["volume_ma5"] if item["volume_last"] is not None and item["volume_ma5"] else None
        item["volume_unit"] = "source_native"
        item["trend"] = "多头排列" if item["ma20"] and item["ma60"] and closes[-1] > item["ma20"] > item["ma60"] else "空头排列" if item["ma20"] and item["ma60"] and closes[-1] < item["ma20"] < item["ma60"] else "震荡"
        item["price_anchors"] = [{"time": b["time"], "high": b["high"], "low": b["low"], "close": b["close"]} for b in bars[-20:]]
        out.append(item)
    return out


def prepare_chart_input(ts_code: str, *, name: str = "", periods: list[dict] | None = None, fq: int = 2, as_of: str | None = None, fetcher=None) -> dict:
    """Fetch each period once; the renderer and vision consume these exact bars."""
    if fetcher is None:
        from src.api.market_data import fetch_chart_bars
        fetcher = fetch_chart_bars
    periods = periods or DEFAULT_PERIODS
    cutoff = cutoff_time(as_of)
    # Existing collectors interpret end_date at midnight. Fetch through the next
    # midnight, then discard bars outside the requested instant locally.
    end_date = (cutoff + timedelta(days=1)).strftime("%Y-%m-%d")

    def fetch(item):
        raw = fetcher(ts_code, days=int(item.get("days") or 365), period=item["period"], fq=fq, end_date=end_date)
        bars = [dict(b) for b in raw.get("candles", []) if bar_time(b["time"]) <= cutoff]
        bars.sort(key=lambda b: bar_time(b["time"]))
        # Historical daily/weekly aggregates cannot prove an intraday past view.
        if cutoff.date() < datetime.now(CN_TZ).date() and cutoff.hour < 15:
            bars = [b for b in bars if not isinstance(b["time"], str) or bar_time(b["time"]).date() < cutoff.date()]
        times = {str(b["time"]) for b in bars}
        volumes = [dict(v) for v in raw.get("volumes", []) if str(v["time"]) in times]
        return {"label": item.get("label", item["period"]), "period": item["period"], "source": raw.get("source"), "candles": bars, "volumes": volumes, "max_bars": int(item.get("max_bars") or 120)}

    with ThreadPoolExecutor(max_workers=min(4, len(periods))) as pool:
        panels = list(pool.map(fetch, periods))
    if not any(p["candles"] for p in panels):
        raise ValueError(f"no chart bars available for {ts_code} at requested cutoff")
    identity = {"ts_code": ts_code, "name": name, "fq": fq, "periods": periods, "panels": panels, "period_context": context_from_panels(panels)}
    return {**identity, "as_of": cutoff.isoformat(), "input_digest": digest(identity)}
