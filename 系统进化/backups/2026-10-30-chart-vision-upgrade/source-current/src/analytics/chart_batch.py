"""Batch chart/vision stages with bounded, independent worker pools."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
from pathlib import Path
import threading
import time

from src.analytics.chart_input import prepare_chart_input
from src.analytics.lwc_chart_renderer import LwcRenderSession, render_identity, render_lwc_multi_period_kline
from src.agents.chart_vision_agent import analysis_identity, analyze_chart_vision


def reusable_analysis(record, prepared, drawing):
    return bool(record and not record.get("error") and record.get("input_digest") == prepared["input_digest"]
                and record.get("render_identity") == drawing and record.get("analysis_identity") == analysis_identity()
                and record.get("summary") and isinstance(record.get("signals"), list))


async def run_chart_batch(universe, concurrency=6, *, render_workers=2, cached=None, force=False,
                          as_of=None, moving_averages=None, macd=False, output_dir=None, periods=None) -> list[dict]:
    if concurrency < 1 or render_workers < 1:
        raise ValueError("worker counts must be positive")
    if not universe:
        return []
    cached = cached or {}
    drawing = render_identity(moving_averages, macd)
    sessions, lock, local = [], threading.Lock(), threading.local()
    loop = asyncio.get_running_loop()
    frozen_as_of = as_of or datetime.now().astimezone().isoformat()

    def prepare(code, name):
        start = time.monotonic()
        try:
            prepared = prepare_chart_input(code, name=name, periods=periods, fq=2, as_of=frozen_as_of)
            old = cached.get(code, {})
            same_analysis = not force and reusable_analysis(old, prepared, drawing)
            path = Path(old.get("chart_path") or "/nonexistent-chart")
            same_image = (not force and old.get("input_digest") == prepared["input_digest"]
                          and old.get("render_identity") == drawing and path.is_file()
                          and old.get("image_sha256") == hashlib.sha256(path.read_bytes()).hexdigest())
            if same_analysis and same_image:
                return {"cached_result": {**old, "reused_analysis": True, "requested_as_of": frozen_as_of}}
            if same_image:
                rendered = {"path": str(path), "render_ms": 0, "fetch_ms": 0, "render_identity": drawing}
            else:
                if not getattr(local, "session", None):
                    local.session = LwcRenderSession()
                    with lock:
                        sessions.append(local.session)
                rendered = render_lwc_multi_period_kline(code, name=name, prepared=prepared, moving_averages=moving_averages,
                                                        macd=macd, session=local.session, output_dir=output_dir)
            rendered["fetch_ms"] = int((time.monotonic() - start) * 1000) - rendered.get("render_ms", 0)
            if same_analysis:
                replacement = Path(rendered["path"])
                return {"cached_result": {**old, "chart_path": str(replacement),
                        "image_sha256": hashlib.sha256(replacement.read_bytes()).hexdigest(),
                        "reused_analysis": True, "requested_as_of": frozen_as_of, "render_ms": rendered["render_ms"]}}
            return {"prepared": prepared, "rendered": rendered, "started": start}
        except Exception as exc:
            return {"error": f"{type(exc).__name__}: {exc}", "error_stage": "input_or_render", "ts_code": code, "name": name}

    def interpret(code, name, item):
        prepared, rendered = item["prepared"], item["rendered"]
        image = Path(rendered["path"]).read_bytes()
        metadata = {"ts_code": code, "name": name, "chart_path": rendered["path"],
                    "input_digest": prepared["input_digest"], "as_of": prepared["as_of"],
                    "render_identity": drawing, "analysis_identity": analysis_identity(),
                    "image_sha256": hashlib.sha256(image).hexdigest(), "fetch_ms": rendered["fetch_ms"],
                    "render_ms": rendered["render_ms"], "lwc_timings": rendered.get("lwc_timings"),
                    "reused_analysis": False}
        t0 = time.monotonic()
        for attempt in range(2):
            try:
                result = analyze_chart_vision(image_bytes=image, mime="image/png", ts_code=code, name=name,
                                              fq=2, period_context=prepared["period_context"])
                return {**result, **metadata, "error": None, "model_attempts": attempt + 1,
                        "vision_s": round(time.monotonic() - t0, 3), "elapsed_s": round(time.monotonic() - item["started"], 3)}
            except Exception as exc:
                if attempt == 0 and getattr(exc, "status_code", None) in (408, 429, 500, 502, 503, 504):
                    time.sleep(0.5)
                    continue
                return {**metadata, "error": f"{type(exc).__name__}: {exc}", "error_stage": "vision",
                        "model_attempts": attempt + 1, "elapsed_s": round(time.monotonic() - item["started"], 3)}
        raise RuntimeError("vision retry loop ended without a result")

    try:
        with ThreadPoolExecutor(max_workers=render_workers) as drawings, ThreadPoolExecutor(max_workers=concurrency) as models:
            async def one(code, name) -> dict:
                item = await loop.run_in_executor(drawings, prepare, code, name)
                if "cached_result" in item:
                    return item["cached_result"]
                if item.get("error"):
                    return item
                return await loop.run_in_executor(models, interpret, code, name, item)
            return await asyncio.gather(*(one(code, name) for code, name in dict(universe).items()))
    finally:
        for session in sessions:
            session.close()
