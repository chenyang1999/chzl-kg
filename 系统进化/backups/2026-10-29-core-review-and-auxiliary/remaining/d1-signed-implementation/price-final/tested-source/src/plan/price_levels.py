#!/usr/bin/env python3
"""src/plan/price_levels.py · 买卖价位确定性推导引擎。

**这套公式不是模型拍的**，是从 `src/plan/d1_algorithm.py::_stock_entry_base` 抽出的
规则算法（原用于 execution_pool），现在统一给 execution / watch / B计划 使用。

推导口径（全部可复算）：

1) 止损 stop_loss
   - 基础: ref * (1 - drop)          drop = 5%(10cm票) / 8%(20cm票,1.2x放宽)
   - 结构: 熊线 * 0.99（跌破牛熊分界）
   - 趋势: MA10 * 0.99（短线均线破位）
   - 取三者中 **最高** = 最保守（先跌破哪个就用哪个）

2) 低吸买区 trend_pullback_buy
   - 下沿 = min(MA50 即决策线, 牛线) * 0.99   （回踩到决策线/牛线附近）
   - 上沿 = MA50 * 1.01
   - 最高可接受 = 上沿 * 1.02
   - 若现价距买区上沿 > 10% → 标记 unreachable，注明"需回撤 X% 才触发"，不假装能买到

3) 半路/打板买区 leader_breakout
   - pivot = max(昨收, 20日最高 hi20)
   - 触发价 = pivot（突破即买，不是等涨过 3%）
   - 买区 = [pivot*0.995, pivot*(1+slack)]，slack=3%(点火行情)/1.5%(普通)
   - 溢价上限 7%，一字板无买点（等开板分歧）

4) 止盈 take_profit
   - RR 目标 2:1 → take = buy + 2*(buy - stop)
   - 若 20 日高点在 2R 之下且高于 buy → 取 hi20 作为第一压力位止盈
   - 连板妖股不设长目标（走量价/板块退出）

5) RR = (take - buy) / (buy - stop)，< 1.8 直接标 RR_FAIL（不参与）
"""
from __future__ import annotations

import sqlite3
from math import isfinite
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DB = ROOT / "kb/research.db"


def load_tech(ts_code: str, trade_date: str) -> dict[str, Any]:
    """从 kb/research.db 取技术位（trade_date 前最近一个交易日）。"""
    con = sqlite3.connect(str(DB))
    row = con.execute(
        "SELECT trade_date, close, ma5, ma10, ma20, ma30, ma50, ma60, ma120, "
        "niu_xian, xiong_xian, boll_mid, boll_upper FROM stock_tech_daily "
        "WHERE ts_code=? AND trade_date<? ORDER BY trade_date DESC LIMIT 1",
        (ts_code, trade_date)).fetchone()
    cols = ["trade_date", "close", "ma5", "ma10", "ma20", "ma30", "ma50", "ma60",
            "ma120", "niu_xian", "xiong_xian", "boll_mid", "boll_upper"]
    tech = dict(zip(cols, row)) if row else {}
    # 20日高低点
    h = con.execute(
        "SELECT MAX(high), MIN(low) FROM market_daily_bars WHERE ts_code=? "
        "AND trade_date<? AND trade_date>=?", (ts_code, trade_date, _shift(trade_date, -30))).fetchone()
    if h:
        tech["hi20"], tech["lo20"] = h[0], h[1]
    con.close()
    for k in list(tech):
        if k != "trade_date" and tech[k] is not None:
            tech[k] = float(tech[k])
    return tech


def _shift(date: str, days: int) -> str:
    from datetime import datetime, timedelta
    return (datetime.strptime(date, "%Y%m%d") + timedelta(days=days)).strftime("%Y%m%d")


def limit_pct(ts_code: str, name: str = "") -> int:
    """涨停幅度: 20cm(创业板/科创板) / 30cm(北交所) / 10cm(主板) / 5cm(ST主板)."""
    if ts_code.startswith(("300", "301", "688", "689")):
        return 20
    if ts_code.endswith(".BJ"):
        return 30
    if "ST" in (name or "").upper():
        return 5
    return 10


def derive(
    ts_code: str,
    trade_date: str,
    *,
    name: str = "",
    ref_close: float | None = None,
    channel: str | None = None,
    ignition: bool = False,
    one_word: bool = False,
    rr_min: float = 1.8,
) -> dict[str, Any]:
    """按显式通道推导情景；买区上沿是计划拟买基准，不是实际委托价。

    触发价只表示入场条件。消费者对实际拟委托价须另行重算 RR，
    不得把此处基于买区上沿的 RR 借给 max_acceptable_ask 或盘口 ask。
    无明确通道不能推断 MA50；不可达的原情景不能换用其他均线凑价。
    """
    if channel not in ("trend_pullback_buy", "leader_breakout", "divergence_pullback"):
        return {"ts_code": ts_code, "ok": False,
                "reason": "missing_or_unsupported_channel: 需明确已有通道，未生成价位",
                "channel": channel, "trigger_price": None, "risk_reward_ratio": None}
    tech = load_tech(ts_code, trade_date)
    ref = float(ref_close or tech.get("close") or 0)
    if ref <= 0:
        return {"ts_code": ts_code, "ok": False, "reason": "无价格数据"}

    lim = limit_pct(ts_code, name)
    drop = 0.08 if lim >= 20 else 0.05

    ma10, ma50 = tech.get("ma10"), tech.get("ma50")
    niu, xiong = tech.get("niu_xian"), tech.get("xiong_xian")
    hi20 = tech.get("hi20")

    # ── 1) 先定买区（止损必须以买入价为基准，不能用昨收） ──
    buy_zone: list[float] | None = None
    trigger = None
    max_ask = None
    unreachable = None
    if channel == "leader_breakout":
        pivot = max(ref, float(hi20 or ref))
        slack = 0.03 if ignition else 0.015
        buy_zone = [round(pivot * 0.995, 2), round(pivot * (1 + slack), 2)]
        trigger = round(pivot, 2)
        max_ask = round(pivot * 1.07, 2)
        formula = (f"pivot=max(昨收{ref:.2f}, 20日高{float(hi20 or ref):.2f})={pivot:.2f}; "
                   f"买区=[pivot×0.995, pivot×(1+{slack:.1%})]; 溢价上限7%")
        if one_word:
            formula += "；⚠️一字板无有效买点，等开板分歧"
            trigger = None
    elif channel == "divergence_pullback":
        # 强势票(身位龙/中军)分歧回踩口径: 以昨收为基准回撤 3%~8% 承接
        # 适用于现价远离均线的连板/首板强势票——均线回踩对它们永远不可达
        buy_zone = [round(ref * 0.92, 2), round(ref * 0.97, 2)]
        trigger = buy_zone[1]
        max_ask = round(ref * 0.995, 2)
        formula = (f"强势票分歧口径: 以昨收{ref:.2f}为基准, 买区=[昨收×0.92={buy_zone[0]:.2f}, "
                   f"昨收×0.97={buy_zone[1]:.2f}] (回撤 3%~8%); 最高接受=昨收×0.995={max_ask:.2f}")
        if one_word:
            formula += "；⚠️一字板需等开板换手后再按此区间承接"
            trigger = None
    else:
        if (isinstance(ma50, bool) or not isinstance(ma50, (int, float))
                or not isfinite(ma50) or ma50 <= 0):
            return {"ts_code": ts_code, "ok": False,
                    "reason": "missing_technical_ma50: 原通道所需MA50缺失或无效，未用昨收代替",
                    "ref_close": round(ref, 2), "limit_pct": lim, "channel": channel,
                    "missing_inputs": ["ma50"],
                    "trigger_price": None, "risk_reward_ratio": None}
        base = ma50
        lower_line = min(base, float(niu or base))
        buy_zone = [round(lower_line * 0.99, 2), round(base * 1.01, 2)]
        # 买区过宽(MA50与牛线相距太远)→ 收窄到基准线 ±1.5%
        if buy_zone[0] > 0 and (buy_zone[1] / buy_zone[0] - 1) > 0.07:
            buy_zone = [round(base * 0.985, 2), round(base * 1.015, 2)]
            formula_note = f"（原始[MA50/牛线]区间过宽已收窄至基准线±1.5%）"
        else:
            formula_note = ""
        trigger = buy_zone[0]
        max_ask = round(buy_zone[1] * 1.02, 2)
        formula = (f"决策线MA50={base:.2f}, 牛线={float(niu or base):.2f}; "
                   f"买区=[min(MA50,牛线)×0.99={buy_zone[0]:.2f}, MA50×1.01={buy_zone[1]:.2f}]; "
                   f"最高接受={max_ask:.2f}{formula_note}")
        if one_word:
            formula += "；⚠️一字板无有效买点，等开板分歧"
            trigger = None
        gap = (buy_zone[1] / ref - 1) * 100
        if gap < -10:
            unreachable = round(gap, 1)

        if unreachable is not None:
            # Keep the authorized scenario and its original zone as evidence.
            # The existing >10% diagnostic is not a license to switch to MA10.
            # Its legacy reason code is not an exchange price-band certificate.
            return {"ts_code": ts_code, "ok": False,
                    "reason": "unreachable_buy_zone: 原10%距离诊断触发；当日边界未核，不能据此确认不可达；保留原通道，未生成执行价位",
                    "ref_close": round(ref, 2), "limit_pct": lim, "channel": channel,
                    "buy_zone": buy_zone, "unreachable_pct": unreachable,
                    "reference_gap_pct": unreachable, "reachability_status": "unverified",
                    "trigger_price": None, "risk_reward_ratio": None}

    # ── 2) 止损: 以买入价(买区上沿)为基准, 三者取最高但必须低于买价 ──
    buy_ref = buy_zone[1] if buy_zone else ref
    low_edge = buy_zone[0] if buy_zone else ref
    cands: list[tuple[str, float]] = [
        (f"买价×(1-{drop:.0%})", buy_ref * (1 - drop))]
    for lbl, v in (("熊线×0.99", (xiong * 0.99) if xiong else None),
                   ("MA10×0.99", (ma10 * 0.99) if ma10 else None)):
        if v is not None and v < low_edge * 0.998:  # 结构位必须在买区下沿之下才有意义
            cands.append((lbl, v))
    stop_label, stop_loss = max(cands, key=lambda x: x[1])
    raw_stop_loss = stop_loss
    stop_loss = round(stop_loss, 2)
    if raw_stop_loss >= low_edge or stop_loss >= low_edge:
        # Reusing cands[0] cannot fix a base stop already inside the buy zone.
        # Refuse this scenario instead of inventing a wider stop or new zone.
        return {
            "ts_code": ts_code,
            "ok": False,
            "reason": "invalid_stop_geometry: 止损未低于买区下沿（含报价舍入），未生成可执行价位",
            "ref_close": round(ref, 2),
            "limit_pct": lim,
            "channel": channel,
            "buy_zone": buy_zone,
            "trigger_price": None,
            "stop_loss": stop_loss,
            "risk_reward_ratio": None,
        }

    # ── 3) 止盈 & RR ──
    risk = round(buy_ref - stop_loss, 2)
    take_2r = round(buy_ref + 2 * risk, 2)
    take = take_2r
    take_formula = f"2R目标 = 买{buy_ref:.2f} + 2×(买入价-止损{risk:.2f}) = {take_2r:.2f}"
    if hi20 and buy_ref * 1.05 < float(hi20) < take_2r:
        take = round(float(hi20), 2)
        take_formula = (f"20日高点{float(hi20):.2f} 低于2R目标{take_2r:.2f} 且高于买价5%以上 "
                        f"→ 取前高作第一压力位")
    rr = round((take - buy_ref) / risk, 2) if risk > 0 else None

    # 买区相对现价的位置（决定是"回踩买"还是"站回才买"）
    if buy_zone:
        if buy_zone[1] < ref * 0.995:
            relation = "below_price"      # 回踩买入
            relation_txt = f"回踩 {abs((buy_zone[1]/ref-1)*100):.1f}% 到买区才触发"
        elif buy_zone[0] > ref * 1.005:
            relation = "above_price"      # 需向上突破/站回
            relation_txt = f"需上破 {(buy_zone[0]/ref-1)*100:+.1f}% 站上买区才成立（不是现在能买）"
        else:
            relation = "at_price"
            relation_txt = "买区覆盖现价，按盘中承接执行"
    else:
        relation, relation_txt = None, "无有效买点"

    return {
        "ts_code": ts_code,
        "ok": True,
        "ref_close": round(ref, 2),
        "limit_pct": lim,
        "channel": channel,
        "buy_zone": buy_zone,
        "trigger_price": trigger,
        "max_acceptable_ask": max_ask,
        "stop_loss": stop_loss,
        "take_profit": take,
        "risk_reward_ratio": rr,
        "rr_grade": ("pass" if rr and rr >= rr_min else "RR_FAIL"),
        "unreachable_pct": unreachable,
        "buy_zone_relation": relation,
        "buy_zone_relation_txt": relation_txt,
        "tech": {k: (round(v, 2) if isinstance(v, float) else v)
                 for k, v in tech.items() if k in ("ma5", "ma10", "ma20", "ma50", "niu_xian", "xiong_xian", "hi20", "lo20")},
        "formula": {
            "stop": f"止损={stop_label} → {stop_loss:.2f}（三者取最高: "
                    + ", ".join(f"{lbl}={v:.2f}" for lbl, v in cands) + "）",
            "buy": formula,
            "take": take_formula,
            "rr": f"RR=({take:.2f}-{buy_ref:.2f})/({buy_ref:.2f}-{stop_loss:.2f})={rr}",
        },
    }
