#!/usr/bin/env python3
"""R5 候选票池推导(唯一真源) · 2026-09-30 新增。

## 为什么存在

此前 `scripts/fetch/run_chart_vision_snapshot.py` 的票池是**硬编码常量**
`DEFAULT_UNIVERSE`(兆易创新/瑞芯微/乐鑫科技…一组算力/存储旧常客),从不随当日
R2 更新。2026-09-30 实测:快照 12 票与 R5 实际候选**仅 1 票重合**(301308.SZ),
等于每天白烧 24 次 vision LLM 调用(06:50 + 15:50 两档 × 12 票),产出零价值。

本模块把"R5 今天要深挖哪几只票"的推导收敛到一处,供:
- `scripts/fetch/run_chart_vision_snapshot.py` — 生成预渲染快照
- R5 skill(`analyze_stock_profile_v1`) — 读快照时校验覆盖度

## 口径(与 R5 完全一致)

R5 的候选来源是 `src/research/r5_stock_profiles.py::_collect_leaders()`:
跨 `main_lines[].leaders[]` 去重,按 R5 的 `MAX_LEADERS=15` 截断。

本模块**复用**同一函数,避免两处口径漂移。差异只有一处:
main_lines 候选为空时,额外从 `secondary_lines[].leaders_hint` 解析兜底
(该字段是自然语言,如 "002912中新赛克(2连板…)/603636南威软件…")。
R2 的 `main_lines[].leaders` 在 `leaders_degraded=true` 时会为空,
此时 R5 会抛异常降级 skeleton —— 这里给快照生成一个兜底池,不让它空转。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# secondary_lines[].leaders_hint 的自然语言解析:
#   形如 "002912中新赛克(2连板·float 47.2亿caution·AI安全)/603636南威软件(...)"
_HINT_RE = re.compile(r"(\d{6})[\s·:：]*([\u4e00-\u9fa5A-Za-z0-9]{2,10})")


def _infer_exchange(code6: str) -> str:
    """6 位代码 → 交易所后缀。与 tushare 命名一致。"""
    if code6.startswith(("60", "68", "90")):
        return "SH"
    if code6.startswith(("00", "30", "20")):
        return "SZ"
    if code6.startswith(("43", "83", "87", "92")):
        return "BJ"
    return "SH"


def parse_leaders_hint(hint: str) -> list[tuple[str, str]]:
    """把 R2 secondary_lines[].leaders_hint 的自然语言解析成 [(ts_code, name)]。"""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for code6, name in _HINT_RE.findall(hint or ""):
        ts_code = f"{code6}.{_infer_exchange(code6)}"
        if ts_code in seen:
            continue
        seen.add(ts_code)
        out.append((ts_code, name))
    return out


def _hint_pool(r2: dict) -> list[tuple[str, str]]:
    """从 secondary_lines[].leaders_hint 解析龙头（自然语言兜底）。"""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for sec in r2.get("secondary_lines") or []:
        for ts_code, name in parse_leaders_hint(sec.get("leaders_hint", "")):
            if ts_code not in seen:
                seen.add(ts_code)
                out.append((ts_code, name))
    return out


def derive(r2: dict) -> tuple[list[tuple[str, str]], dict]:
    """从**已加载的 R2 payload** 推导票池。返回 ([(ts_code,name)], meta)。

    R5 与快照生成器都调这里，口径不可能分叉。
    顺序：main_lines[].leaders（R2 自己的排序，通常比 R5 的 15 只更多/更全）
        → secondary_lines[].leaders_hint（main_lines 无 leaders 时兜底）。
    """
    sys.path.insert(0, str(ROOT))
    from src.research.r5_stock_profiles import _collect_leaders

    out, seen = [], set()
    for L in _collect_leaders(r2) or []:
        code = L.get("ts_code")
        if code and code not in seen:
            seen.add(code)
            out.append((code, L.get("name", "")))
    if out:
        return out, {"source": "R2.main_lines[].leaders", "count": len(out)}

    out = _hint_pool(r2)
    return out, {
        "source": "R2.secondary_lines[].leaders_hint (fallback)",
        "count": len(out),
        "note": "main_lines 无 leaders(可能 leaders_degraded)",
    }


def derive_from_file(trade_date: str) -> tuple[list[tuple[str, str]], dict]:
    """读当日 R2 文件后推导票池。读不到返回 ([], meta with reason)。"""
    path = ROOT / "data" / "research" / trade_date / "R2_main_sectors.json"
    meta: dict = {"r2_path": str(path.relative_to(ROOT)), "source": None, "count": 0}
    if not path.exists():
        meta["reason"] = "R2_main_sectors.json 不存在"
        return [], meta
    try:
        r2 = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        meta["reason"] = f"R2 读取失败 {type(exc).__name__}"
        return [], meta
    if r2.get("status") != "complete":
        meta["reason"] = f"R2 status={r2.get('status')}"
        return [], meta
    pool, m = derive(r2)
    meta.update(m)
    return pool, meta



def load_snapshot(date: str) -> tuple[dict[str, dict], dict]:
    """读快照,返回 ({ts_code: 票画像}, meta)。优先当日归档,回退 latest 指针。"""
    for rel in (f"data/raw/{date}/chart_vision_snapshot.json", "data/cache/chart_vision_latest.json"):
        p = ROOT / rel
        if not p.exists():
            continue
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        results = payload.get("results") or {}
        ok = {k: v for k, v in results.items() if not v.get("error")}
        return ok, {
            "path": rel,
            "generated_at": payload.get("generated_at"),
            "snapshot_date": payload.get("date"),
            "ok": len(ok),
            "n": len(results),
        }
    return {}, {"path": None, "reason": "快照不存在"}


def coverage(date: str, needed: list[tuple[str, str]]) -> dict:
    """快照对 needed 票池的覆盖度。判断"要不要再花一次 vision 调用"用。

    关键:必须同时校验 `snapshot_date == date` —— 否则会把**前一日**的快照
    当成当日覆盖(data/cache/chart_vision_latest.json 是跨日指针)。
    """
    snap, meta = load_snapshot(date)
    same_day = meta.get("snapshot_date") == date
    need = [c for c, _ in needed]
    hit = [c for c in need if c in snap] if same_day else []
    return {
        "covered": hit,
        "missing": [c for c in need if c not in hit],
        "coverage": round(len(hit) / len(need), 3) if need else 0.0,
        "snapshot_date": meta.get("snapshot_date"),
        "same_day": same_day,
        "snapshot_path": meta.get("path"),
        "snapshot_generated_at": meta.get("generated_at"),
    }



if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else None
    if not date:
        from datetime import datetime

        date = datetime.now().strftime("%Y%m%d")
    pool, meta = derive_from_file(date)
    print(json.dumps({"trade_date": date, "pool": pool, "meta": meta}, ensure_ascii=False, indent=2))
