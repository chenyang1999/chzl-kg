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
    if not isinstance(r2, dict):
        meta["reason"] = "R2 payload 必须是对象"
        return [], meta
    if r2.get("status") not in {"complete", "partial"}:
        meta["reason"] = f"R2 status={r2.get('status')}"
        return [], meta
    pool, m = derive(r2)
    meta.update(m)
    return pool, meta



def chart_universe(date: str) -> tuple[list[tuple[str, str]], dict]:
    """Uncapped chart coverage, independent of R5's research-profile quota.

    Existing research and same-date published plan objects are chart requests,
    not permission to trade. Explicit CLI lists remain a separate entry point.
    """
    selected, sources, issues = {}, {}, []

    def add(items, source):
        for item in items or []:
            if not isinstance(item, dict):
                continue
            code = item.get("ts_code")
            if not isinstance(code, str) or not re.fullmatch(r"\d{6}\.(SH|SZ|BJ)", code):
                continue
            selected.setdefault(code, item.get("name", ""))
            sources.setdefault(code, []).append(source)

    plan_path = ROOT / f"data/plans/{date}/watchlist_plan.json"
    if not plan_path.is_file():
        earlier = sorted(p for p in (ROOT / "data/plans").glob("*/watchlist_plan.json")
                         if re.fullmatch(r"\d{8}", p.parent.name) and p.parent.name < date)
        if earlier:
            plan_path = earlier[-1]
    plan_date = plan_path.parent.name
    for relative, kind in ((f"data/research/{date}/R2_main_sectors.json", "research"),
                           (str(plan_path.relative_to(ROOT)), "plan")):
        path = ROOT / relative
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            issues.append(f"{relative}: {type(exc).__name__}")
            continue
        expected_date = date if kind == "research" else plan_date
        if not isinstance(payload, dict) or payload.get("trade_date") != expected_date:
            issues.append(f"{relative}: missing/mismatched trade_date")
            continue
        if kind == "research":
            if payload.get("status") not in {"complete", "partial"}:
                issues.append(f"{relative}: status={payload.get('status')}")
                continue
            for key in ("main_lines", "secondary_lines"):
                for sector in payload.get(key) or []:
                    if not isinstance(sector, dict):
                        continue
                    add(sector.get("leaders"), f"R2.{key}")
                    add([{"ts_code": c, "name": n} for c, n in parse_leaders_hint(sector.get("leaders_hint", ""))], f"R2.{key}.hint")
        else:
            for key in ("execution_pool", "watch_pool", "b_plan"):
                items = payload.get(key) or []
                if isinstance(items, dict):
                    items = items.get("stocks", [])
                add(items, f"plan.{key}")
    return list(selected.items()), {"source": "chart_research_and_plan_union", "count": len(selected), "provenance": sources, "issues": issues,
                                   "plan_path": str(plan_path.relative_to(ROOT)), "plan_date": plan_date, "prior_plan_used_for_membership_only": plan_date < date}


def load_snapshot(date: str) -> tuple[dict[str, dict], dict]:
    """合并有效同日记录；归档优先，latest 只补缺，不复用跨日或坏记录。"""
    ok: dict[str, dict] = {}
    meta: dict = {"path": None, "reason": "无有效同日快照"}
    for rel in (f"data/raw/{date}/chart_vision_snapshot.json", "data/cache/chart_vision_latest.json"):
        p = ROOT / rel
        if not p.exists():
            continue
        try:
            payload = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(payload, dict) or payload.get("date") != date:
            continue
        results = payload.get("results")
        if not isinstance(results, dict):
            continue
        if meta["path"] is None:
            meta = {"path": rel, "generated_at": payload.get("generated_at"), "snapshot_date": date}
        for code, rec in results.items():
            if isinstance(rec, dict) and rec and not rec.get("error") and rec.get("ts_code", code) == code:
                ok.setdefault(code, rec)
    meta["ok"] = len(ok)
    return ok, meta


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
