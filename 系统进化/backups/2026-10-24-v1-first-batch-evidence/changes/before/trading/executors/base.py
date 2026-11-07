from __future__ import annotations

from dataclasses import dataclass, field
from math import floor
from typing import Any

from trading.order.qmt_context import QMTContext
from trading.positions_state import PositionState, PositionsStateStore

LOT_SIZE = 100


@dataclass
class ExecutionResult:
    status: str
    rule_type: str
    ts_code: str
    side: str | None = None
    quantity: int = 0
    limit_price: float | None = None
    reasons: list[str] = field(default_factory=list)
    skip_reason: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


def floor_lot(qty: float) -> int:
    return int(floor(qty / LOT_SIZE) * LOT_SIZE)


def stock_entry_dict(stock: Any) -> dict[str, Any]:
    if hasattr(stock, "model_dump"):
        return stock.model_dump(mode="json")
    return dict(stock)


def rule_dict(rule: Any) -> dict[str, Any]:
    if hasattr(rule, "model_dump"):
        return rule.model_dump(mode="json")
    return dict(rule)


def evaluate_buy_trigger(
    *,
    rule: dict[str, Any],
    quote_last: float,
    quote_ask: float,
) -> tuple[bool, list[str]]:
    rule_type = str(rule.get("type") or "")
    trigger = rule.get("trigger_price")
    max_ask = rule.get("max_acceptable_ask")
    reasons: list[str] = []
    if trigger is None:
        return False, ["missing trigger_price"]
    trigger_f = float(trigger)
    if rule_type in {"trend_pullback_buy", "low_absorption_intraday", "t_add_pullback"}:
        ok = quote_last <= trigger_f or quote_ask <= trigger_f
        reasons = [f"pullback trigger {trigger_f}, last={quote_last}, ask={quote_ask}"]
        return ok, reasons
    if rule_type in {"leader_breakout", "daban_confirm"}:
        ok = quote_ask <= float(max_ask or trigger_f * 1.03)
        reasons = [f"breakout ask guard {max_ask or trigger_f}, ask={quote_ask}"]
        return ok, reasons
    return False, [f"unsupported buy evaluation for {rule_type}"]


def evaluate_sell_trigger(
    *,
    rule: dict[str, Any],
    quote_last: float,
    quote_bid: float,
) -> tuple[bool, list[str]]:
    rule_type = str(rule.get("type") or "")
    trigger = rule.get("trigger_price")
    if rule_type == "exit_at_open":
        return True, ["exit_at_open pre-open queue"]
    if rule_type == "exit_if_no_new_high":
        return True, ["exit_if_no_new_high session check delegated to watcher"]
    if trigger is None and rule_type not in {"sector_switch_exit", "volume_price_divergence"}:
        return False, ["missing trigger_price"]
    trigger_f = float(trigger or 0)
    if rule_type in {"stop_loss_break", "intraday_break_exit"}:
        ok = quote_last <= trigger_f
        return ok, [f"break sell trigger {trigger_f}, last={quote_last}"]
    if rule_type in {"take_profit_hit", "t_reduce_resistance"}:
        ok = quote_last >= trigger_f or quote_bid >= trigger_f
        return ok, [f"resistance/profit trigger {trigger_f}, last={quote_last}"]
    if rule_type in {"sector_switch_exit", "volume_price_divergence"}:
        return True, [rule.get("trigger_condition") or rule_type]
    return False, [f"unsupported sell evaluation for {rule_type}"]


def compute_buy_qty(
    ctx: QMTContext,
    *,
    position_pct: float,
) -> int:
    if ctx.total_asset <= 0:
        return LOT_SIZE
    notional = ctx.total_asset * max(position_pct, 0)
    quote_budget = max(ctx.quotes.values(), key=lambda q: q.last, default=None)
    price = quote_budget.last if quote_budget else 0
    if price <= 0:
        return LOT_SIZE
    return max(LOT_SIZE, floor_lot(notional / price))


def compute_sell_qty(
    pos: PositionState | None,
    *,
    quantity_pct: float,
    available_qty: int,
) -> int:
    if available_qty <= 0:
        return 0
    if pos is not None and pos.mobile_qty > 0:
        mobile_avail = pos.available_mobile_qty()
        target = floor_lot(mobile_avail * quantity_pct)
        return min(target, mobile_avail, available_qty)
    return floor_lot(available_qty * quantity_pct) or available_qty
