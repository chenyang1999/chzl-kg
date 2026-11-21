#!/usr/bin/env python3
"""scripts/plan/run_retreat_reversal.py · 退潮次日翻多检测 CLI。

产出:
  data/research/<date>/retreat_reversal.json
  chzl_kg/投研交易/翻多检测/<date>.md (人读)

非退潮次日 → state=not_applicable, 仅写 JSON 不渲染 md (供 cron 每日自门控)。

用法: python3 scripts/plan/run_retreat_reversal.py [--date YYYYMMDD] [--force-md]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.research.retreat_reversal import detect  # noqa: E402

TZ = timezone(timedelta(hours=8))


def render_md(v: dict) -> str:
    state_label = {
        "reversal_confirmed": "🟢 翻多确认",
        "downtrend_confirmed": "🔴 续跌确认",
        "pending": "🟡 待确认",
        "not_applicable": "⚪ 不适用",
    }[v["state"]]
    b = v.get("breadth") or {}
    from src.fetch.price_limits import finite_number
    def number(value, spec=""):
        n = finite_number(value)
        return format(n, spec) if n is not None else "未知"
    lines = [
        "---",
        f"date: {v['trade_date'][:4]}-{v['trade_date'][4:6]}-{v['trade_date'][6:]}",
        f"checked_at: {v['checked_at']}",
        "agent: retreat-reversal-detector",
        "---",
        "",
        f"# 退潮次日翻多检测 · {v['trade_date']}",
        "",
        f"**状态**: {state_label}",
        f"**T-1({v['prev_date']})基线**: {v['is_retreat_baseline'].get('reason')}",
        "",
    ]
    observed = finite_number(b.get("valid_n"))
    breadth = b.get("breadth") if observed is not None and observed > 0 else None
    lines += [
        "## 盘中指标（数据质量与授权分开）", "",
        f"- 样本广度: **{number(breadth)}** (请求{number(b.get('requested_n'), '.0f')}/有效{number(b.get('valid_n'), '.0f')}/缺失{number(b.get('missing_n'), '.0f')})",
        f"- 涨跌停已确认计数: 涨停{number(b.get('limit_up'), '.0f') if observed and observed > 0 else '未知'} / 跌停{number(b.get('limit_down'), '.0f') if observed and observed > 0 else '未知'}；边界已知样本{number(b.get('limit_known_n'), '.0f')} / 未知样本{number(b.get('limit_unknown_n'), '.0f')}（未知不等于0，非全市场保证）",
        f"- 昨涨停票今日红盘率: **{number(v.get('yesterday_lu_green_ratio'))}** (有效样本 {number(v.get('yesterday_lu_n'), '.0f')})",
        f"- 上证观测涨跌幅: {number(v.get('index_pct'))}%",
        f"- 市场参考档位: **{number(v.get('suggested_cap'), '.0%')}**；不授予交易权限，不改变D1预算",
        "- D1预算/no_trade/个股资格原样有效；预算缺失不代表可交易。",
        "", "### D1预算上下文（原值）", "", "```json",
        json.dumps(v.get("plan_budget_context") or {}, ensure_ascii=False, sort_keys=True),
        "```", "", "### 时点质量", "",
        "报价所属时点与采集时刻分别检验；报价年龄上限未配置，未声称已验证新鲜。",
        "```json", json.dumps(v.get("source_time_quality") or {}, ensure_ascii=False, sort_keys=True), "```",
        "", "## 动作", "",
    ]
    lines += [f"- {a}" for a in v.get("actions") or []]
    if v.get("data_quality_issues"):
        lines += ["", "### 数据不足", *[f"- {a}" for a in v["data_quality_issues"]]]
    if v.get("promote_candidates"):
        lines += ["", "### 池内已红盘参考候选（非交易授权）", "",
                  "| 代码 | 名称 | 涨幅 | 来源池 |", "|------|------|------|--------|"]
        for c in v["promote_candidates"]:
            lines.append(f"| `{c.get('ts_code','')}` | {c.get('name','')} | {number(c.get('pct'), '+.2f')}% | {c.get('pool','plan')} |")
    lines += ["", "> 旧声明：31个退潮日样本、核心二证90%及失败二证100%。原始统计证据本次未复核；保留历史声明边界，不构成当前保证，不改变原信号阈值。", ""]
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(TZ).strftime("%Y%m%d"))
    ap.add_argument("--force-md", action="store_true")
    args = ap.parse_args()

    plan_path = ROOT / "data" / "plans" / args.date / "watchlist_plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.is_file() else None

    v = detect(args.date, plan=plan).to_dict()

    out_json = ROOT / "data" / "research" / args.date / "retreat_reversal.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(v, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

    md_path = None
    if v["state"] != "not_applicable" or args.force_md:
        md_path = ROOT / "chzl_kg" / "投研交易" / "翻多检测" / f"{args.date}.md"
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_md(v), encoding="utf-8")

    print(json.dumps({
        "state": v["state"],
        "suggested_cap": v["suggested_cap"],
        "cap_semantics": v["cap_semantics"],
        "trading_authorized": v["trading_authorized"],
        "json": str(out_json.relative_to(ROOT)),
        "md": str(md_path.relative_to(ROOT)) if md_path else None,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
