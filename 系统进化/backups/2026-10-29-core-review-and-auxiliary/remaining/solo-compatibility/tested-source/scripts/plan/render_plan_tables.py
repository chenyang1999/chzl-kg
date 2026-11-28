#!/usr/bin/env python3
"""watchlist_plan.json → existing 点位表 path; shared deterministic views.

Rendering never fetches prices or changes trading permissions. Explicit --in and
--out allow fully isolated offline use; defaults retain the existing CLI paths.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.plan.quick_reference import (
    render_constraints, render_sector_overview, render_pool_reference,
    render_seesaw_reference, table, text, price, decision_origin,
)


def prior_close(code: str, before_date: str) -> float | None:
    """Legacy explicit lookup; no renderer calls this function."""
    import sqlite3
    db = ROOT / "kb/research.db"
    if not db.exists():
        return None
    with sqlite3.connect(db.as_uri() + "?mode=ro", uri=True) as con:
        row = con.execute(
            "SELECT close FROM market_daily_bars WHERE ts_code=? AND trade_date<? "
            "ORDER BY trade_date DESC LIMIT 1", (code, before_date)).fetchone()
    return row[0] if row else None


def fmt(value, pct=False):
    """Compatibility helper; missing prices stay visibly missing."""
    return text(value) if pct else price(value)


def band_text(ae: dict | None) -> str:
    ae = ae or {}
    lines = [f"昨收 {price(ae.get('base_close'))}；预期开盘带 {text(ae.get('expected_open_band'))}"]
    for key, band in (ae.get("bands") or {}).items():
        lines.append(f"{text(key)}：{text(band.get('open_pct'))}；{text(band.get('action'))}；{text(band.get('action_type'))}")
    return "<br>".join(lines)


def exec_block(s: dict) -> list[str]:
    return render_pool_reference({"execution_pool": [s]}, [s], "执行池")


def watch_block(w: dict, trade_date: str, extra_note: str = "") -> list[str]:
    # Compatibility only: do not read production DB or mutate the caller's item.
    return ([text(extra_note), ""] if extra_note else []) + render_pool_reference(
        {"trade_date": trade_date, "watch_pool": [w]}, [w], "观察池")


def render_plan_tables_md(plan: dict) -> str:
    decision_source, is_fallback = decision_origin(plan)
    lines = [f"# {text(plan.get('trade_date'))} 盘前预案 · 点位表版", "",
             f"> 计划生成时点：{text(plan.get('generated_at'))}；决策来源：{text(decision_source)}", ""]
    if is_fallback:
        lines += ["> 🚨 Python FALLBACK · 非大模型决策，不可据此下单。", ""]
    lines += render_sector_overview(plan)
    lines += render_constraints(plan)
    for key, label in (("execution_pool", "执行池"), ("watch_pool", "观察池")):
        pool = plan.get(key) or []
        lines += [f"## {label}（{len(pool)} 只）", ""]
        lines += render_pool_reference(plan, pool, label)
        auction = [[text(s.get("name")) + " " + text(s.get("ts_code")), band_text(s.get("auction_expectation"))]
                   for s in pool if s.get("auction_expectation")]
        if auction:
            lines += [f"### {label}竞价预期（原计划）", ""]
            lines += table(["股票", "区间／判定／动作"], auction)
    lines += render_seesaw_reference(plan)
    lines += ["## 禁入／否决名单", ""]
    for s in plan.get("rejected") or []:
        lines.append(f"- {text(s.get('name'))} {text(s.get('ts_code'))}：{text(s.get('reason'))}")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now().strftime("%Y%m%d"))
    ap.add_argument("--in", dest="inp", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    plan_path = Path(args.inp) if args.inp else ROOT / f"data/plans/{args.date}/watchlist_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    td = plan["trade_date"]
    out = Path(args.out) if args.out else ROOT / f"chzl_kg/投研交易/盘前预案/{td}_点位表.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_plan_tables_md(plan), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
