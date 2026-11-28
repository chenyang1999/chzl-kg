#!/usr/bin/env python3
"""canghai-fetch · Chart Vision 批量快照(并发绕过 MCP 串行瓶颈)。

背景(2026-07-08):
- 单次 chart_vision_analyze 45-90s(出图 8-20s + 4 周期 fetch 4-12s + vision LLM 20-45s)
- MCP tool 是同步 def · sub-agent 通过 stdio JSON-RPC 只能串行调 → 12 只票 × 45s = 540s
  → sub-agent 600s 硬超时(R5 v2 就是这样挂的)
- 因此绕过 MCP,直接调 analyze_chart_vision 函数 + asyncio.gather 并发 6-8 路
- 预计 12 只票 60-90s 落盘

调用方式:
    .venv/bin/python scripts/fetch/run_chart_vision_snapshot.py --universe <path>
    .venv/bin/python scripts/fetch/run_chart_vision_snapshot.py                # 当日 R2 候选；无候选不调用

产出:
    data/raw/YYYYMMDD/chart_vision_snapshot.json         (当日归档)
    data/cache/chart_vision_latest.json                   (最新指针,R agent 消费入口)

失败策略:单只失败不阻塞整体 · 结果 dict 里带 error 字段。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import time
import tempfile
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

CONCURRENCY = 6  # LLM 并发上限(apiyi 侧不打限流)


def _pool_from_r2(date: str) -> list[tuple[str, str]]:
    """已声明研究候选与同日计划池的看图并集；不造票，不改变交易资格。"""
    try:
        from src.research.candidate_pool import chart_universe

        pool, meta = chart_universe(date)
        if pool:
            print(
                f"[pool] 已声明图表对象 {len(pool)} 票 · source={meta.get('source')}",
                flush=True,
            )
            return pool
        print(f"[pool] R2 无候选({meta.get('reason') or meta.get('note')}) → 跳过", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 — 可选图像预渲染不阻塞研究
        print(f"[pool] R2 推导失败 {type(exc).__name__}: {exc} → 跳过", file=sys.stderr)
    return []



def _load_universe(path: Path | None) -> list[tuple[str, str]]:
    if not path:
        return []
    if not path.exists():
        raise FileNotFoundError(f"universe file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return list(dict((item["ts_code"], item.get("name", "")) for item in data).items())
    if isinstance(data, list):
        if not all(isinstance(item, str) and item for item in data):
            raise ValueError("universe entries must be nonempty ts_code strings")
        return list(dict.fromkeys((item, "") for item in data))
    raise ValueError(f"universe format not recognized: {type(data)}")


def _analyze_one(ts_code: str, name: str) -> dict:
    """在线程池里跑一只票(analyze_chart_vision + 出图都是 sync)。"""
    t0 = time.time()
    try:
        from src.analytics.lwc_chart_renderer import render_lwc_multi_period_kline
        from src.agents.chart_vision_agent import analyze_chart_vision

        render_info = render_lwc_multi_period_kline(ts_code, name=name, fq=2)
        path = Path(render_info["path"])
        image_bytes = path.read_bytes()
        analysis = analyze_chart_vision(
            image_bytes=image_bytes,
            mime="image/png",
            ts_code=ts_code,
            name=name,
            fq=2,
            period_context=render_info["period_context"],
        )
        analysis["chart_path"] = str(path)
        analysis["fetch_ms"] = render_info.get("fetch_ms")
        analysis["render_ms"] = render_info.get("render_ms")
        analysis["elapsed_s"] = round(time.time() - t0, 2)
        analysis["error"] = None
        return analysis
    except Exception as exc:
        return {
            "ts_code": ts_code,
            "name": name,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc().splitlines()[-5:],
            "elapsed_s": round(time.time() - t0, 2),
        }


async def _run_all(universe: list[tuple[str, str]], concurrency: int, **options) -> list[dict]:
    from src.analytics.chart_batch import run_chart_batch
    return await run_chart_batch(universe, concurrency, **options)


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, suffix=".tmp", delete=False, encoding="utf-8") as stream:
        temp = Path(stream.name)
        json.dump(payload, stream, ensure_ascii=False, indent=2)
    try:
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", type=Path, default=None, help="JSON file: [{ts_code,name},...] or [ts_code,...]")
    parser.add_argument("--date", type=str, default=None, help="YYYYMMDD (default=today)")
    parser.add_argument("--concurrency", type=int, default=CONCURRENCY)
    parser.add_argument("--render-workers", type=int, default=2)
    parser.add_argument("--codes", nargs="+", help="Explicit ts_code list for review or ad-hoc research; no fixed stock-count cap")
    parser.add_argument("--as-of", help="Input cutoff as ISO timestamp; historical dates never fetch past their date")
    parser.add_argument("--no-ma", action="store_true", help="Candles and volume only, without moving-average overlays")
    parser.add_argument("--macd", action="store_true", help="Include optional MACD pane")
    parser.add_argument("--output-dir", type=Path, help="Isolated output directory; does not update production snapshots")
    parser.add_argument(
        "--force",
        action="store_true",
        help="重算选中票池；默认仅补当日有效快照未覆盖的票",
    )
    args = parser.parse_args()

    date = args.date or datetime.now().strftime("%Y%m%d")
    try:
        datetime.strptime(date, "%Y%m%d")
        if args.codes and args.universe:
            raise ValueError("choose --codes or --universe, not both")
        universe = list(dict.fromkeys((c, "") for c in args.codes)) if args.codes else _load_universe(args.universe) if args.universe else _pool_from_r2(date)
        if any(not isinstance(c, str) or not re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", c) for c, _ in universe):
            raise ValueError("stock identifiers must be literal six-digit codes with .SH/.SZ/.BJ suffixes")
        if args.concurrency < 1 or args.render_workers < 1:
            raise ValueError("worker counts must be positive")
        from src.analytics.chart_input import cutoff_time
        as_of = args.as_of or (date if date < datetime.now().strftime("%Y%m%d") else None)
        cutoff = cutoff_time(as_of)
        if cutoff.strftime("%Y%m%d") > date or cutoff > datetime.now(cutoff.tzinfo):
            raise ValueError("input cutoff is in the future or after the report date")
        as_of = cutoff.isoformat()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"[fatal] 无效票池: {exc}", file=sys.stderr)
        return 2
    if not universe:
        print(f"[chart_vision ⏭️] {date} 零候选 · 零模型调用", flush=True)
        return 0

    from src.research.candidate_pool import load_snapshot

    cached, _ = load_snapshot(date)
    if args.output_dir:
        output_cache = args.output_dir / "chart_vision_snapshot.json"
        prior = json.loads(output_cache.read_text()) if output_cache.is_file() else {}
        cached = prior.get("results", {}) if prior.get("date") == date else {}
    selected_count = len(universe)
    print(f"[pool] selected={selected_count} · checking shared-input/model/render identities before reuse", flush=True)

    # 空池不加载凭据；非空池用同一份真实输入核验缓存，再决定是否画图/调模型。
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env")
    except ImportError:
        pass
    if not (os.environ.get("VISION_API_KEY") or os.environ.get("OPENAI_API_KEY")):
        print("[fatal] VISION_API_KEY / OPENAI_API_KEY 未设置", file=sys.stderr)
        return 2

    print(f"[chart_vision] date={date} · N={len(universe)} · concurrency={args.concurrency}", flush=True)

    t0 = time.time()

    results = asyncio.run(_run_all(universe, args.concurrency, render_workers=args.render_workers,
                                  cached=cached, force=args.force, as_of=as_of,
                                  moving_averages=[] if args.no_ma else None, macd=args.macd,
                                  output_dir=args.output_dir / "charts" if args.output_dir else None))
    total_s = round(time.time() - t0, 2)

    ok = sum(1 for r in results if not r.get("error"))
    fail = len(results) - ok

    # ── 与既有快照合并（2026-09-30）──────────────────────────────────────
    # 动机：`--universe` 补渲（R5 misses 队列）此前会**整份覆盖**当日快照，
    #   把之前算好的票全丢掉（实测把 13 票快照打成 1 票）。改为按 ts_code 合并：
    #   本次结果覆盖同码旧值，其余票保留。只对**当日**快照合并，避免跨日串味。
    results_map = {r["ts_code"]: r for r in results}
    for code, rec in cached.items():
        results_map.setdefault(code, rec)
    raw_dir = args.output_dir or ROOT / "data" / "raw" / date
    raw_path = raw_dir / "chart_vision_snapshot.json"
    merged_from: str | None = None
    if raw_path.exists():
        try:
            prior = json.loads(raw_path.read_text(encoding="utf-8"))
            if isinstance(prior, dict) and prior.get("date") == date and isinstance(prior.get("results"), dict):
                for code, rec in prior["results"].items():
                    if not isinstance(rec, dict):
                        continue
                    results_map.setdefault(code, rec)  # 本次没重算的票保留旧结果
                merged_from = prior.get("generated_at")
        except (json.JSONDecodeError, OSError):
            pass

    all_ok = sum(1 for r in results_map.values() if not r.get("error"))
    all_fail = len(results_map) - all_ok
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "date": date,
        "concurrency": args.concurrency,
        "render_workers": args.render_workers,
        "schema_version": "chart_vision_v2",
        "total_elapsed_s": total_s,
        "ok": all_ok,
        "fail": all_fail,
        "n": len(results_map),
        "results": results_map,
        "run": {"selected": selected_count, "requested": len(results), "recomputed": sum(1 for r in results if not r.get("error") and not r.get("reused_analysis")), "reused": sum(1 for r in results if r.get("reused_analysis")), "failed": fail, "merged_from": merged_from},
    }

    raw_dir.mkdir(parents=True, exist_ok=True)
    _atomic_json(raw_path, payload)

    if not args.output_dir:
        cache_dir = ROOT / "data" / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        latest_path = cache_dir / "chart_vision_latest.json"
        _atomic_json(latest_path, payload)

    print(
        f"[chart_vision ✅] {ok}/{len(results)} · {total_s}s · {raw_path}",
        flush=True,
    )
    if fail:
        print(f"[chart_vision ⚠️] {fail} failures:", flush=True)
        for r in results:
            if r.get("error"):
                print(f"  - {r['ts_code']} {r.get('name','')}: {r['error']}", flush=True)
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
