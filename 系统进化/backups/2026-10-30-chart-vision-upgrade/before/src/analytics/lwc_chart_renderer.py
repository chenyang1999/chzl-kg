"""Lightweight Charts 无头出图（Playwright + 网页同款指标）。"""
from __future__ import annotations

import json
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from src.api.market_data import fetch_chart_bars
from src.analytics.fast_chart_renderer import CHART_OUT_DIR, DEFAULT_PERIODS

CN_TZ = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[2]
LWC_SCRIPT = ROOT / "web" / "scripts" / "headless" / "lwc_headless_render.mjs"


def _fetch_panel(ts_code: str, item: dict[str, Any], fq: int) -> dict[str, Any]:
    period = str(item.get("period", "1d"))
    days = max(int(item.get("days") or 365), 150)
    label = str(item.get("label") or period)
    data = fetch_chart_bars(ts_code, days=days, period=period, fq=fq)
    return {
        "label": label,
        "period": period,
        "source": data.get("source"),
        "candles": data.get("candles") or [],
        "volumes": data.get("volumes") or [],
        "max_bars": int(item.get("max_bars") or 120),
    }


def render_lwc_multi_period_kline(
    ts_code: str,
    *,
    name: str = "",
    periods: list[dict[str, Any]] | None = None,
    fq: int = 2,
    width: int = 1320,
) -> dict[str, Any]:
    """四周期 LWC 拼图：成交量 + 牛熊线 + 四色四量 + MACD。"""
    if not LWC_SCRIPT.is_file():
        raise FileNotFoundError(f"缺少 LWC 脚本: {LWC_SCRIPT}")

    periods = periods or DEFAULT_PERIODS
    t0 = time.time()
    raw_panels: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(4, len(periods))) as pool:
        futures = {pool.submit(_fetch_panel, ts_code, item, fq): item for item in periods}
        for fut in as_completed(futures):
            raw_panels.append(fut.result())
    fetch_ms = int((time.time() - t0) * 1000)

    raw_panels.sort(
        key=lambda p: next(
            (i for i, d in enumerate(periods) if str(d.get("label", d.get("period"))) == p["label"]),
            99,
        )
    )

    payload = {
        "title": f"{name or ts_code} ({ts_code}) · Lightweight Charts",
        "width": width,
        "panels": raw_panels,
    }

    CHART_OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(CN_TZ).strftime("%Y%m%d_%H%M%S")
    safe = ts_code.replace(".", "_")
    out_path = CHART_OUT_DIR / f"lwc_kline_{safe}_{stamp}.png"

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
        json.dump(payload, tf, ensure_ascii=False)
        payload_path = tf.name

    t1 = time.time()
    try:
        proc = subprocess.run(
            ["node", str(LWC_SCRIPT), "--input", payload_path, "--output", str(out_path)],
            cwd=str(ROOT / "web"),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    finally:
        Path(payload_path).unlink(missing_ok=True)

    render_ms = int((time.time() - t1) * 1000)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "LWC 渲染失败")

    timings: dict[str, Any] = {}
    try:
        timings = json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        timings = {"raw_stdout": proc.stdout[-500:]}

    result: dict[str, Any] = {
        "ts_code": ts_code,
        "name": name,
        "fq": fq,
        "path": str(out_path),
        "bytes": out_path.stat().st_size if out_path.is_file() else 0,
        "fetch_ms": fetch_ms,
        "render_ms": render_ms,
        "total_ms": fetch_ms + render_ms,
        "renderer": "lightweight_charts_playwright",
        "indicators": ["volume", "bull_bear", "sise", "macd"],
        "panels": [
            {"label": p["label"], "period": p["period"], "bars": len(p["candles"]), "source": p.get("source")}
            for p in raw_panels
        ],
        "lwc_timings": timings,
    }
    return result
