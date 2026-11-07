from __future__ import annotations

from dataclasses import dataclass, field
from math import floor, isfinite
from numbers import Real
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


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    try:
        result = float(value)
        return result if isfinite(result) else None
    except (ValueError, TypeError, OverflowError):
        return None


def _positive(value: Any) -> float | None:
    result = _number(value)
    return result if result is not None and result > 0 else None


def evaluate_buy_trigger(
    *,
    rule: dict[str, Any],
    quote_last: float,
    quote_ask: float,
) -> tuple[bool, list[str]]:
    # Full schema dumps contain inactive null fields. Descriptions/provenance
    # are not predicates; active unknown constraints must never disappear.
    metadata = {"priority", "reason", "derivation_reason", "execution_logic",
                "price_src", "engine_formula"}
    supported = metadata | {"type", "trigger_price", "entry_target_price",
                            "confirm_price", "reclaim_price", "buy_zone", "pullback_zone",
                            "max_acceptable_ask", "position_pct", "max_premium_pct",
                            "review_required"}
    unknown = sorted(k for k, v in rule.items() if k not in supported and v is not None)
    if unknown:
        return False, [f"unsupported buy constraints: {','.join(unknown)}"]
    premium = rule.get("max_premium_pct")
    if premium is not None and (_number(premium) is None or premium != 0):
        return False, ["unsupported buy constraint: max_premium_pct"]
    if rule.get("review_required") not in (None, False):
        return False, ["buy rule requires review"]
    last, ask = _positive(quote_last), _positive(quote_ask)
    if last is None or ask is None:
        return False, ["missing or invalid executable quote"]
    prices: dict[str, float] = {}
    for key in ("trigger_price", "entry_target_price", "confirm_price",
                "reclaim_price", "max_acceptable_ask"):
        if rule.get(key) is not None:
            value = _positive(rule[key])
            if value is None:
                return False, [f"invalid {key}"]
            prices[key] = value
    zones = []
    for key in ("buy_zone", "pullback_zone"):
        zone = rule.get(key)
        if zone is not None:
            if not isinstance(zone, (list, tuple)) or len(zone) != 2:
                return False, [f"invalid {key}"]
            low, high = (_positive(v) for v in zone)
            if low is None or high is None or low > high:
                return False, [f"invalid {key}"]
            zones.append((low, high))
    kind = str(rule.get("type") or "")
    trigger = prices.get("trigger_price")
    if kind in {"leader_breakout", "daban_confirm"}:
        if trigger is None:
            return False, ["missing trigger_price"]
        # Keep the existing 3% fallback cap; never replace an explicit zero or
        # invalid cap with it. A cheap ask alone is not a breakout signal.
        cap = prices.get("max_acceptable_ask", trigger * 1.03)
        if not isfinite(cap):
            return False, ["invalid breakout ask cap"]
        ok = last >= trigger and ask <= cap
    elif kind in {"trend_pullback_buy", "low_absorption_intraday", "t_add_pullback"}:
        bound = prices.get("entry_target_price", trigger)
        if not zones and bound is None:
            return False, ["missing trigger_price or buy_zone"]
        # The price producer uses a zone's lower anchor as trigger_price.
        # Its two-sided zone, when supplied, is the actual pullback predicate.
        ok = True if zones else bound is not None and ask <= bound
    else:
        return False, [f"unsupported buy evaluation for {kind}"]
    ok = ok and all(low <= ask <= high for low, high in zones)
    ok = ok and all(last >= prices[k] for k in ("confirm_price", "reclaim_price") if k in prices)
    if "max_acceptable_ask" in prices:
        ok = ok and ask <= prices["max_acceptable_ask"]
    return ok, [f"{kind} price predicates: last={last}, ask={ask}, met={ok}"]


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
    ts_code: str,
    limit_price: float,
    position_pct: float,
    max_position_pct: float | None = None,
) -> int:
    """Size this symbol at the exact proposed limit; unknown/zero buys nothing."""
    asset = _positive(ctx.total_asset)
    cash = _number(getattr(ctx, "cash", None))
    price, pct = _positive(limit_price), _positive(position_pct)
    if not ts_code or ts_code not in ctx.quotes or asset is None or cash is None:
        return 0
    if cash <= 0 or price is None or pct is None or pct > 1:
        return 0
    notional = min(asset * pct, cash)
    if max_position_pct is not None:
        cap = _number(max_position_pct)
        if cap is None or not 0 <= cap <= 1:
            return 0
        row = getattr(ctx, "holdings", {}).get(ts_code) or {}
        held = _number(row.get("total_qty", 0))
        if held is None or held < 0 or not held.is_integer():
            return 0
        notional = min(notional, asset * cap - held * price)
    if not isfinite(notional) or notional <= 0:
        return 0
    shares = notional / price
    return floor_lot(shares) if isfinite(shares) else 0


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
