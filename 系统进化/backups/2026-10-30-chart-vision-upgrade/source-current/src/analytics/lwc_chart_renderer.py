"""Lightweight Charts 无头出图（Playwright + 网页同款指标）。"""
from __future__ import annotations

import json
import selectors
import subprocess
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from src.analytics.chart_input import DEFAULT_PERIODS, prepare_chart_input

CN_TZ = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[2]
LWC_SCRIPT = ROOT / "web" / "scripts" / "headless" / "lwc_headless_render.mjs"
CHART_OUT_DIR = ROOT / "output" / "charts"
RENDER_VERSION = "lwc-clean-v3"


def render_identity(moving_averages=None, macd=False, width=1320) -> dict:
    return {"renderer_version": RENDER_VERSION, "moving_averages": [5, 20] if moving_averages is None else list(moving_averages), "macd": bool(macd), "width": width}


class LwcRenderSession:
    """One render thread owns one Node process/browser, reused across symbols."""

    def __init__(self):
        self.process = subprocess.Popen(
            ["node", str(LWC_SCRIPT), "--worker"], cwd=str(ROOT / "web"),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1,
        )

    def render(self, payload, output_path):
        proc = self.process
        assert proc.stdin is not None and proc.stdout is not None
        if proc.poll() is not None:
            raise RuntimeError("chart browser worker has exited")
        proc.stdin.write(json.dumps({"payload": payload, "output": str(output_path)}, ensure_ascii=False) + "\n")
        proc.stdin.flush()
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout, selectors.EVENT_READ)
            if not selector.select(timeout=120):
                self.close()
                raise TimeoutError("chart browser worker exceeded 120 seconds")
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("chart browser worker closed without a response")
        result = json.loads(line)
        if result.get("error"):
            raise RuntimeError(result["error"])
        return result

    def close(self):
        proc = self.process
        if proc.poll() is None:
            if proc.stdin:
                proc.stdin.close()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        if proc.stdout:
            proc.stdout.close()


def render_lwc_multi_period_kline(
    ts_code: str,
    *,
    name: str = "",
    periods: list[dict[str, Any]] | None = None,
    fq: int = 2,
    width: int = 1320,
    prepared: dict | None = None,
    as_of: str | None = None,
    moving_averages: list[int] | None = None,
    macd: bool = False,
    session: LwcRenderSession | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Clean multi-period chart; share the exact input bars with vision."""
    if not LWC_SCRIPT.is_file():
        raise FileNotFoundError(f"缺少 LWC 脚本: {LWC_SCRIPT}")

    t0 = time.time()
    prepared = prepared or prepare_chart_input(ts_code, name=name, periods=periods, fq=fq, as_of=as_of)
    fetch_ms = int((time.time() - t0) * 1000)
    raw_panels = prepared["panels"]
    identity = render_identity(moving_averages, macd, width)
    payload = {
        "title": f"{name or ts_code} ({ts_code}) · 数据截止 {prepared['as_of']}",
        "width": width,
        "panels": raw_panels,
        "options": identity,
    }
    out_dir = output_dir or CHART_OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(CN_TZ).strftime("%Y%m%d_%H%M%S_%f")
    safe = ts_code.replace(".", "_")
    out_path = out_dir / f"lwc_kline_{safe}_{stamp}.png"
    t1 = time.time()
    own_session = session is None
    session = session or LwcRenderSession()
    try:
        timings = session.render(payload, out_path)
    finally:
        if own_session:
            session.close()
    render_ms = int((time.time() - t1) * 1000)
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
        "indicators": ["volume"] + [f"ma{n}" for n in identity["moving_averages"]] + (["macd"] if macd else []),
        "render_identity": identity,
        "input_digest": prepared["input_digest"],
        "as_of": prepared["as_of"],
        "period_context": prepared["period_context"],
        "panels": [
            {"label": p["label"], "period": p["period"], "bars": len(p["candles"]), "source": p.get("source")}
            for p in raw_panels
        ],
        "lwc_timings": timings,
    }
    return result
