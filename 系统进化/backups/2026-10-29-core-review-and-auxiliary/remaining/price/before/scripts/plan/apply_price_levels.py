#!/usr/bin/env python3
"""apply_price_levels.py · 用确定性引擎给预案全部标的算买/卖价位。

价位来源: src/plan/price_levels.py（规则算法，不是模型拍脑袋）
- execution_pool: 保留 D1 原值, 同时算引擎值, 偏离>10% 标 deviate 供复核
- watch_pool / B计划候选: 直接用引擎值写入 entry_rules (price_src=engine)

产出:
  chzl_kg/投研交易/盘前预案/YYYYMMDD_价位推导.md   每票公式明细
  更新 data/plans/YYYYMMDD/watchlist_plan.json
"""
from __future__ import annotations

import argparse
import json
import sys
from math import isfinite
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.plan.price_levels import derive  # noqa: E402
from src.plan.buy_eligibility import (  # noqa: E402
    ENGINE_SOURCE, evaluate_stock_buy_eligibility, is_engine_rr_condition,
)


def pick_channel(stock: dict, td: str) -> str:
    """选择价位口径: 强势票(远离均线)用分歧回踩, 其余用均线回踩/突破。"""
    explicit = None
    for r in (stock.get("entry_rules") or []):
        if r.get("type") in ("trend_pullback_buy", "leader_breakout",
                             "divergence_pullback") and r.get("price_src") != "engine":
            explicit = r["type"]
            break
    ref = stock.get("reference_close") or 0
    # 现价相对 MA10 溢价 > 8% → 强势票, 用分歧回踩口径
    from src.plan.price_levels import load_tech
    t = load_tech(stock["ts_code"], td)
    ma10 = t.get("ma10")
    if explicit == "leader_breakout":
        return "leader_breakout"
    if ma10 and ref and ref / ma10 - 1 > 0.08:
        return "divergence_pullback"
    return explicit or "trend_pullback_buy"


def fmt(v, nd=2):
    return f"{v:.{nd}f}" if isinstance(v, (int, float)) else "—"


def has_original_entry(stock: dict) -> bool:
    """A D1 trigger-only rule is original pricing too, not an engine blank."""
    rules = list(stock.get("entry_rules") or []) + [stock]
    return any(e.get("price_src") not in ("tech_backfill", "engine")
               and any(e.get(k) is not None and not isinstance(e.get(k), dict)
                       for k in ("buy_zone", "entry_target_price", "trigger_price"))
               for e in rules)


def d1_buy_high(stock: dict):
    for rule in stock.get("entry_rules") or []:
        zone = rule.get("buy_zone")
        if isinstance(zone, (list, tuple)) and len(zone) == 2:
            high = zone[1]
            if (not isinstance(high, bool) and isinstance(high, (int, float))
                    and isfinite(high) and high > 0):
                return high
    return None


def apply_to_plan(plan: dict, td: str, *, write_prices: bool = True) -> list[dict]:
    """Enrich in memory; filesystem writes belong exclusively to main().

    Replace this engine's evidence even on failed refreshes. Keep research,
    original D1 levels, authorization, zero budgets and all sell rules intact.
    """
    rows: list[dict] = []

    def run(stock: dict, group: str) -> dict:
        try:
            ch = pick_channel(stock, td)
            r = derive(stock["ts_code"], td, name=stock.get("name", ""),
                       ref_close=stock.get("reference_close"), channel=ch)
        except Exception as exc:
            # A failed refresh must replace stale successful qualifications.
            r = {"ts_code": stock["ts_code"], "ok": False,
                 "reason": f"price_levels_failed:{type(exc).__name__}"}
        r["group"] = group
        r["name"] = stock.get("name")
        rows.append(r)
        stock["engine_levels"] = {k: r.get(k) for k in
                                  ("ok", "reason", "buy_zone", "trigger_price", "stop_loss",
                                   "take_profit", "risk_reward_ratio", "rr_grade",
                                   "buy_zone_relation_txt")}
        stock["engine_levels"].update(source=ENGINE_SOURCE, price_src="engine")
        if isinstance(stock.get("no_trade_conditions"), list):
            stock["no_trade_conditions"] = [c for c in stock["no_trade_conditions"]
                                             if not is_engine_rr_condition(c)]
        return r

    for s in plan.get("execution_pool", []):
        r = run(s, "执行池")
        # 与 D1 原值比对
        d1_buy = d1_buy_high(s)
        if d1_buy and r.get("buy_zone"):
            dev = (d1_buy / r["buy_zone"][1] - 1) * 100
            s["engine_levels"]["deviate_pct"] = round(dev, 1)
            if abs(dev) > 10:
                s["engine_levels"]["note"] = f"⚠️ D1原买价较引擎值偏离{dev:+.1f}%,需说明依据"

    if write_prices:
        for w in plan.get("watch_pool", []):
            has_d1_price = has_original_entry(w)
            r = run(w, "观察池")
            if not r.get("ok") or not r.get("buy_zone"):
                continue

            if has_d1_price:
                # D1 原值保留，只记录引擎值供对比
                d1 = d1_buy_high(w)
                if d1 is not None:
                    w["engine_levels"]["d1_buy_high"] = d1
                    w["engine_levels"]["deviate_pct"] = round(
                        (d1 / r["buy_zone"][1] - 1) * 100, 1)
                continue
            w["reference_close"] = w.get("reference_close") or r["ref_close"]
            w["entry_rules"] = [{
                "type": r["channel"],
                "trigger_price": r["trigger_price"],
                "buy_zone": r["buy_zone"],
                "position_pct": 0.0,
                "max_acceptable_ask": r["max_acceptable_ask"],
                "execution_logic": f"规则引擎: {r['buy_zone_relation_txt']}；RR={r['risk_reward_ratio']} ({r['rr_grade']})",
                "price_src": "engine",
                "engine_formula": r["formula"],
            }]
        # B plans are research, not promotion/authorization. Compute evidence
        # even for candidates without a matching watch row; keep original D1.
        for d in plan.get("seesaw_plan", {}).get("seesaw_directions", []):
            for c in d.get("candidates", []):
                r = run(c, "B计划")
                has_d1_price = has_original_entry(c)
                if r.get("ok") and r.get("buy_zone") and not has_d1_price:
                    c.update({"buy_zone": r.get("buy_zone"),
                              "trigger_price": r.get("trigger_price"),
                              "stop_loss": r.get("stop_loss"),
                              "take_profit": r.get("take_profit"),
                              "risk_reward_ratio": r.get("risk_reward_ratio"),
                              "price_src": "engine"})

    stocks = list(plan.get("execution_pool", []))
    if write_prices:
        stocks += list(plan.get("watch_pool", []))
        stocks += [c for d in plan.get("seesaw_plan", {}).get("seesaw_directions", [])
                   for c in d.get("candidates", [])]
    for stock in stocks:
        old = stock.get("buy_eligibility")
        result = evaluate_stock_buy_eligibility(stock)
        if isinstance(old, dict) and old.get("source") != ENGINE_SOURCE:
            result["external_qualification"] = old
        stock["buy_eligibility"] = result

    # Only this producer's exact legacy code+source is migratable. Preserve the
    # old objects for audit. Never infer that no_trade/zero budgets were ours.
    conditions = plan.get("no_trade_conditions")
    if isinstance(conditions, list):
        owned = [c for c in conditions if is_engine_rr_condition(c)]
        if owned:
            history = plan.setdefault("price_levels_rr_migration", [])
            for c in owned:
                if c not in history:
                    history.append(c)
            plan["no_trade_conditions"] = [c for c in conditions if not is_engine_rr_condition(c)]
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True)
    ap.add_argument("--write-json", action="store_true", help="把引擎价位写回 watch_pool entry_rules")
    args = ap.parse_args()
    td = args.date
    path = ROOT / f"data/plans/{td}/watchlist_plan.json"
    plan = json.loads(path.read_text(encoding="utf-8"))
    rows = apply_to_plan(plan, td, write_prices=args.write_json)
    rr_fail = [r for r in rows if r.get("ok") and r["rr_grade"] == "RR_FAIL"]

    # ── 渲染推导明细 ──
    L = [f"# {td} 价位推导明细（规则引擎，非模型拍价）", ""]
    L.append("> 引擎: `src/plan/price_levels.py` ｜ 止损=以买入价为基准三者取高；买区=决策线/牛线回踩或 pivot 突破；止盈=2R 或前高压制。")
    L.append("")
    L.append("| 分组 | 票 | 现价 | 买区 | 触发 | 止损 | 止盈 | RR | 判定 | 买区关系 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        if not r.get("ok"):
            L.append(f"| {r['group']} | {r.get('name')} {r['ts_code']} | — | — | — | — | — | — | 无数据 | — |")
            continue
        bz = r["buy_zone"]
        bz_txt = f"{fmt(bz[0])}~{fmt(bz[1])}" if bz else "无（一字/不可买）"
        L.append(
            f"| {r['group']} | {r['name']} {r['ts_code']} | {fmt(r['ref_close'])} | {bz_txt} | "
            f"{fmt(r.get('trigger_price'))} | {fmt(r['stop_loss'])} | {fmt(r['take_profit'])} | "
            f"{fmt(r['risk_reward_ratio'])} | {r['rr_grade']} | {r['buy_zone_relation_txt']} |")
    L.append("")
    L.append("## 逐票公式")
    L.append("")
    if rr_fail:
        L.append(f"> 🚫 **RR_FAIL（不参与开仓）**: "
                 + "、".join(f"{r['name']} RR={r['risk_reward_ratio']}" for r in rr_fail)
                 + " —— 仅该票 buy_eligibility 禁新买；不污染全局，研究与合法卖出保留")
        L.append("")
    L.append("> buy_eligibility 是 RR 资格而非交易授权；unknown/blocked 不得新买。"
             " D1/引擎差异留审计；合法微调按 D1 三价与实际拟委托价重算。"
             " 买区偏离>10%须 derivation_reason；来源不明/证据冲突/显式复核不得新买。"
             " 不得借用引擎 RR 代表实际委托价 RR。")
    b_candidates = [c for d in plan.get("seesaw_plan", {}).get("seesaw_directions", [])
                    for c in d.get("candidates", [])]
    for group in (plan.get("execution_pool", []), plan.get("watch_pool", []), b_candidates):
        for stock in group:
            eligibility = stock.get("buy_eligibility", {})
            L.append(f"- {stock.get('ts_code')}: {eligibility.get('status', 'unknown')} "
                     f"来源={eligibility.get('price_source')} 复核={eligibility.get('review_required')} "
                     f"原因={','.join(eligibility.get('reasons', []))}")
    for r in rows:
        if not r.get("ok"):
            continue
        L.append(f"### {r['name']} {r['ts_code']}（{r['group']}｜{r['channel']}）")
        L.append("")
        f = r["formula"]
        L.append(f"- **止损** {f['stop']}")
        L.append(f"- **买区** {f['buy']}")
        L.append(f"- **止盈** {f['take']}")
        L.append(f"- **RR** {f['rr']} → `{r['rr_grade']}`")
        t = r.get("tech") or {}
        L.append(f"- **技术位** MA10={fmt(t.get('ma10'))} ｜ MA50={fmt(t.get('ma50'))} ｜ 牛线={fmt(t.get('niu_xian'))} "
                 f"｜ 熊线={fmt(t.get('xiong_xian'))} ｜ 20日高={fmt(t.get('hi20'))} ｜ 20日低={fmt(t.get('lo20'))}")
        L.append("")

    out = ROOT / f"chzl_kg/投研交易/盘前预案/{td}_价位推导.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L), encoding="utf-8")
    if args.write_json:
        path.write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"rows={len(rows)} -> {out}")


if __name__ == "__main__":
    main()
