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
    .venv/bin/python scripts/fetch/run_chart_vision_snapshot.py                # 用默认票池

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
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# 加载 .env
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

# 兜底票池(仅在 R2 不可用时):历史算力/存储常客
# ⚠️ 2026-09-30 起票池改为从当日 R2 龙头动态推导(见 candidate_pool.py)。
#    此前这里是唯一来源,导致快照算的全是固定旧票池 —— 实测与 R5 实际候选
#    仅 1/12 重合,每天白烧 24 次 vision 调用。DEFAULT_UNIVERSE 降级为兜底。
DEFAULT_UNIVERSE = [
    # R2 主线 12 只
    ("000977.SZ", "浪潮信息"),
    ("000938.SZ", "紫光股份"),
    ("300017.SZ", "网宿科技"),
    ("002396.SZ", "星网锐捷"),
    ("001339.SZ", "智微智能"),
    ("301308.SZ", "江波龙"),
    ("300223.SZ", "北京君正"),
    ("688766.SH", "普冉股份"),
    ("603986.SH", "兆易创新"),
    ("603893.SH", "瑞芯微"),
    ("688018.SH", "乐鑫科技"),
    ("688521.SH", "芯原股份"),
]

CONCURRENCY = 6  # LLM 并发上限(apiyi 侧不打限流)


def _pool_from_r2(date: str) -> list[tuple[str, str]]:
    """从当日 R2 龙头推导票池;失败则回退 DEFAULT_UNIVERSE。"""
    try:
        from src.research.candidate_pool import derive_from_file

        pool, meta = derive_from_file(date)
        if pool:
            print(
                f"[pool] 从 R2 推导 {len(pool)} 票 · source={meta.get('source')}",
                flush=True,
            )
            return pool
        print(f"[pool] R2 无候选({meta.get('reason') or meta.get('note')}) → 回退默认票池", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 — 兜底必须宽
        print(f"[pool] R2 推导失败 {type(exc).__name__}: {exc} → 回退默认票池", file=sys.stderr)
    return DEFAULT_UNIVERSE



def _load_universe(path: Path | None) -> list[tuple[str, str]]:
    if not path:
        return DEFAULT_UNIVERSE
    if not path.exists():
        print(f"[warn] universe file not found: {path} → 用默认票池", file=sys.stderr)
        return DEFAULT_UNIVERSE
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list) and data and isinstance(data[0], dict):
        return [(item["ts_code"], item.get("name", "")) for item in data]
    if isinstance(data, list):
        return [(item, "") for item in data]
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


async def _run_all(universe: list[tuple[str, str]], concurrency: int) -> list[dict]:
    loop = asyncio.get_event_loop()
    sem = asyncio.Semaphore(concurrency)
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        async def _bounded(ts_code: str, name: str):
            async with sem:
                print(f"[start] {ts_code} {name}", flush=True)
                result = await loop.run_in_executor(pool, _analyze_one, ts_code, name)
                status = "ok" if not result.get("error") else "FAIL"
                print(
                    f"[done]  {ts_code} {name} · {status} · {result.get('elapsed_s')}s",
                    flush=True,
                )
                return result

        return await asyncio.gather(*[_bounded(c, n) for c, n in universe])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--universe", type=Path, default=None, help="JSON file: [{ts_code,name},...] or [ts_code,...]")
    parser.add_argument("--date", type=str, default=None, help="YYYYMMDD (default=today)")
    parser.add_argument("--concurrency", type=int, default=CONCURRENCY)
    parser.add_argument(
        "--force",
        action="store_true",
        help="已有快照也重算(默认:当日快照已存在且覆盖充分则静默跳过,省 vision 调用)",
    )
    args = parser.parse_args()

    if not os.environ.get("OPENAI_API_KEY"):
        print("[fatal] OPENAI_API_KEY 未设置 · 检查 .env", file=sys.stderr)
        return 2

    date = args.date or datetime.now().strftime("%Y%m%d")
    # 票池:显式 --universe > 当日 R2 龙头 > DEFAULT_UNIVERSE
    universe = _load_universe(args.universe) if args.universe else _pool_from_r2(date)

    # ── 省 vision 调用:当日快照已存在且覆盖本票池 ≥50% 就跳过 ──────────────
    # 2026-09-30 新增。动机:15:50 档此前无条件重算,而盘前 R5 早已在 08:1x 完成,
    # 盘后那次无人消费;且 R5 直调 MCP 不读快照 = 纯烧。现在盘后再触发会静默跳过。
    if not args.force:
        from src.research.candidate_pool import coverage

        cov = coverage(date, universe)
        if cov["same_day"] and cov["coverage"] >= 0.5:
            print(
                f"[chart_vision ⏭️] {date} 快照已覆盖 {len(cov['covered'])}/{len(universe)} "
                f"({cov['coverage']:.0%}) · generated_at={cov['snapshot_generated_at']} · 跳过(加 --force 可强制重算)",
                flush=True,
            )
            return 0

    print(f"[chart_vision] date={date} · N={len(universe)} · concurrency={args.concurrency}", flush=True)

    t0 = time.time()
    results = asyncio.run(_run_all(universe, args.concurrency))
    total_s = round(time.time() - t0, 2)

    ok = sum(1 for r in results if not r.get("error"))
    fail = len(results) - ok

    # ── 与既有快照合并（2026-09-30）──────────────────────────────────────
    # 动机：`--universe` 补渲（R5 misses 队列）此前会**整份覆盖**当日快照，
    #   把之前算好的票全丢掉（实测把 13 票快照打成 1 票）。改为按 ts_code 合并：
    #   本次结果覆盖同码旧值，其余票保留。只对**当日**快照合并，避免跨日串味。
    results_map = {r["ts_code"]: r for r in results}
    raw_dir = ROOT / "data" / "raw" / date
    raw_path = raw_dir / "chart_vision_snapshot.json"
    merged_from: str | None = None
    if raw_path.exists():
        try:
            prior = json.loads(raw_path.read_text(encoding="utf-8"))
            if prior.get("date") == date:
                for code, rec in (prior.get("results") or {}).items():
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
        "total_elapsed_s": total_s,
        "ok": all_ok,
        "fail": all_fail,
        "n": len(results_map),
        "results": results_map,
        "run": {"requested": len(results), "recomputed": ok, "failed": fail, "merged_from": merged_from},
    }

    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    cache_dir = ROOT / "data" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    latest_path = cache_dir / "chart_vision_latest.json"
    latest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"[chart_vision ✅] {ok}/{len(results)} · {total_s}s · {raw_path.relative_to(ROOT)}",
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
