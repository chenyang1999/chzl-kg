"""扫描候选池：XTick 分时 + 日线关键位 → 排序后的买点机会。"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from src.settings import DATA_DIR, ROOT
from trading.candidate_pool import Candidate, build_candidate_pool, save_candidate_pool
from trading.daily_levels import candles_from_xtick_rows, compute_daily_levels
from trading.intraday_pattern import analyze_intraday_pattern, fetch_xtick_minute_bars
from trading.schema.watchlist_plan import WatchlistPlan
from trading.sise_filter import evaluate_sise_gate

RUNTIME_DIR = DATA_DIR / "runtime"

WASHOUT_MIN = 0.55
TRAP_BLOCK = 0.55


@dataclass
class EntryOpportunity:
    ts_code: str
    name: str
    pool: str
    entry_style: str
    action: str  # buy_pullback | buy_breakout | watch | skip
    rank_score: float
    last: float
    washout_score: float
    bull_trap_score: float
    slow_bleed_score: float
    in_support: bool
    in_resistance: bool
    trigger_low: float | None
    trigger_breakout: float | None
    suggested_limit: float | None
    sise_vol_red: int = 0
    sise_pass: bool = False
    sise_reason: str = ""
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _fetch_daily_candles(ts_code: str, days: int = 180) -> list[dict[str, Any]]:
    from src.collectors.xtick_collector import XTickCollector

    collector = XTickCollector()
    rows = collector.fetch_kline(ts_code, days=days, period="1d", fq=1)
    return candles_from_xtick_rows(rows)


def _rank_score(
    cand: Candidate,
    pattern: Any,
    daily: Any,
    *,
    cash: float,
    prefer_style: str = "low_absorption",
) -> tuple[float, str, list[str]]:
    reasons: list[str] = []
    last = pattern.last
    style = cand.entry_style

    score = cand.score * 0.25
    in_sup = bool(pattern.meta.get("in_support"))
    in_res = bool(pattern.meta.get("in_resistance"))

    if prefer_style in {"low_absorption", "pullback"} and style in {"low_absorption", "pullback"}:
        score += 0.15

    if in_sup:
        score += 0.2
        reasons.append("in_daily_support_zone")
    if pattern.washout_score >= WASHOUT_MIN and in_sup:
        score += pattern.washout_score * 0.35
        reasons.append(f"washout={pattern.washout_score}")
    if pattern.bull_trap_score >= TRAP_BLOCK:
        score -= 0.25
        reasons.append(f"bull_trap={pattern.bull_trap_score}")
    if pattern.slow_bleed_score >= 0.55:
        score -= 0.2
        reasons.append(f"slow_bleed={pattern.slow_bleed_score}")

    if cand.trigger_low and last <= cand.trigger_low * 1.01:
        score += 0.15
        reasons.append("at_plan_low_trigger")

    action = "watch"
    if style in {"low_absorption", "pullback"}:
        if in_sup and pattern.washout_score >= WASHOUT_MIN and pattern.bull_trap_score < TRAP_BLOCK:
            action = "buy_pullback"
        elif cand.trigger_low and last <= (cand.trigger_confirm or cand.trigger_low):
            action = "buy_pullback"
            reasons.append("price_at_pullback_trigger")
        elif pattern.slow_bleed_score >= 0.55:
            action = "skip"
    elif style == "breakout":
        if cand.trigger_breakout and last >= cand.trigger_breakout and pattern.bull_trap_score < 0.45:
            action = "buy_breakout"
            reasons.append("breakout_confirmed")
        elif in_res and pattern.bull_trap_score >= TRAP_BLOCK:
            action = "skip"
            reasons.append("breakout_looks_like_trap")

    if cash < 5000 and action.startswith("buy"):
        action = "watch"
        reasons.append("insufficient_cash")

    return round(max(0.0, min(100.0, score)), 2), action, reasons


def scan_entry_opportunities(
    plan: WatchlistPlan,
    *,
    trade_date: str,
    cash: float = 0.0,
    held_codes: set[str] | None = None,
    limit: int = 20,
    prefer_style: str = "low_absorption",
) -> dict[str, Any]:
    held = held_codes or set()
    candidates = build_candidate_pool(plan, held_codes=held, trade_date=trade_date, expand_intel=True)
    save_candidate_pool(candidates, trade_date)

    opportunities: list[EntryOpportunity] = []
    errors: list[dict[str, str]] = []

    for cand in candidates[:limit]:
        try:
            daily_candles = _fetch_daily_candles(cand.ts_code)
            daily = compute_daily_levels(cand.ts_code, daily_candles, stock=cand.raw)
            minute_rows = fetch_xtick_minute_bars(cand.ts_code, period="5m")
            pattern = analyze_intraday_pattern(cand.ts_code, minute_rows, daily=daily)
        except Exception as exc:
            errors.append({"ts_code": cand.ts_code, "error": str(exc)})
            continue

        rank, action, reasons = _rank_score(cand, pattern, daily, cash=cash, prefer_style=prefer_style)
        gate = evaluate_sise_gate(cand.ts_code, trade_date=trade_date, held=False)
        if not gate.pass_new_buy:
            action = "skip"
            reasons = reasons + [f"sise:{gate.reason}"]
        suggested = None
        if action == "buy_pullback":
            suggested = cand.trigger_low or pattern.last
        elif action == "buy_breakout":
            suggested = cand.trigger_breakout or pattern.last

        opportunities.append(
            EntryOpportunity(
                ts_code=cand.ts_code,
                name=cand.name,
                pool=cand.pool,
                entry_style=cand.entry_style,
                action=action,
                rank_score=rank,
                last=pattern.last,
                washout_score=pattern.washout_score,
                bull_trap_score=pattern.bull_trap_score,
                slow_bleed_score=pattern.slow_bleed_score,
                sise_vol_red=gate.vol_red,
                sise_pass=gate.pass_new_buy,
                sise_reason=gate.reason,
                in_support=bool(pattern.meta.get("in_support")),
                in_resistance=bool(pattern.meta.get("in_resistance")),
                trigger_low=cand.trigger_low,
                trigger_breakout=cand.trigger_breakout,
                suggested_limit=suggested,
                reasons=reasons,
            )
        )

    opportunities.sort(key=lambda o: (-o.rank_score, o.ts_code))
    buy_ready = [o for o in opportunities if o.action.startswith("buy")]

    payload = {
        "trade_date": trade_date,
        "generated_at": datetime.now().isoformat(),
        "cash": cash,
        "pool_size": len(candidates),
        "scanned": len(opportunities),
        "buy_ready_count": len(buy_ready),
        "prefer_style": prefer_style,
        "opportunities": [o.to_dict() for o in opportunities],
        "top_buy": buy_ready[0].to_dict() if buy_ready else None,
        "errors": errors,
        "candidate_pool_path": str((RUNTIME_DIR / f"candidate_pool_{trade_date}.json").relative_to(ROOT)),
        "disclaimer": "优先低吸；池内票不必然买入；实时数据来自 XTick",
    }

    out_path = RUNTIME_DIR / f"entry_opportunities_{trade_date}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload
