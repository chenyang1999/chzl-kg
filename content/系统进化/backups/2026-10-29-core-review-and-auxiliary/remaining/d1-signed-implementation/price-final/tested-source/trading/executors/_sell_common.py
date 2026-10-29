from __future__ import annotations

from datetime import datetime

from trading.executors.base import (
    ExecutionResult,
    compute_sell_qty,
    evaluate_sell_trigger,
    rule_dict,
    stock_entry_dict,
)
from trading.order.qmt_context import QMTContext
from trading.positions_state import PositionsStateStore


def run_sell_executor(
    stock_entry: dict,
    rule: dict,
    qmt_ctx: QMTContext,
    positions: PositionsStateStore,
    *,
    expected_type: str,
    simulate: bool = False,
    force_trigger: bool = False,
) -> ExecutionResult:
    entry = stock_entry_dict(stock_entry)
    rule = rule_dict(rule)
    ts_code = entry["ts_code"]
    rule_type = str(rule.get("type") or "")
    if rule_type != expected_type:
        raise ValueError(f"executor/type mismatch: {expected_type} != {rule_type}")

    # Binding belongs to the trusted composition root, never this caller.
    # Reject even a first call with an unrelated/empty store before quote I/O.
    try:
        pos = qmt_ctx.sell_position_state(ts_code, store=positions)
        if positions is None:
            raise ValueError("sell_positions_store_mismatch")
    except ValueError as exc:
        return ExecutionResult(status="rejected", rule_type=rule_type,
                               ts_code=ts_code, skip_reason=str(exc))

    if not qmt_ctx.has_position(ts_code) and not simulate:
        return ExecutionResult(
            status="skipped",
            rule_type=rule_type,
            ts_code=ts_code,
            skip_reason="no_position",
        )

    quote = qmt_ctx.quotes.get(ts_code)
    if quote is None:
        qmt_ctx.refresh_quotes([ts_code])
        quote = qmt_ctx.quotes.get(ts_code)

    ok, reasons = evaluate_sell_trigger(
        rule=rule,
        quote_last=float(quote.last if quote else entry.get("stop_loss") or 0),
        quote_bid=float(quote.bid if quote else 0),
    )
    opp = None
    try:
        from trading.watcher.session_context import get_opportunity

        opp = get_opportunity(ts_code)
    except Exception:
        opp = None
    if ok and rule_type == "t_reduce_resistance" and opp:
        trap = float(opp.get("bull_trap_score") or 0)
        if trap >= 0.55:
            reasons = reasons + [f"bull_trap_score={trap}_favor_reduce"]
    if ok and rule_type == "volume_price_divergence" and opp:
        trap = float(opp.get("bull_trap_score") or 0)
        ok = trap >= 0.55
        reasons = [f"volume_price_divergence trap={trap}"]
    if ok and rule_type == "intraday_break_exit" and opp:
        bleed = float(opp.get("slow_bleed_score") or 0)
        fast = "fast_drop" in (opp.get("reasons") or [])
        if bleed < 0.45 and not fast:
            ok = False
            reasons = reasons + ["intraday_drop_not_confirmed_slow_bleed"]
    if force_trigger and simulate:
        ok = True
        reasons = [f"simulate {rule_type}"]

    if rule_type == "t_reduce_resistance" and pos:
        trigger = float(rule.get("trigger_price") or 0)
        if quote and quote.last > trigger * 1.02 and not simulate:
            qmt_ctx.log_event(
                {
                    "at": datetime.now().isoformat(),
                    "event": "t_reduce_skipped",
                    "ts_code": ts_code,
                    "reason": "防卖飞:放量突破",
                    "current_price": quote.last,
                    "trigger_price": trigger,
                }
            )
            return ExecutionResult(
                status="skipped",
                rule_type=rule_type,
                ts_code=ts_code,
                skip_reason="anti_chase_breakout",
                reasons=reasons,
            )
        if pos.t_state.t_reduce_done:
            return ExecutionResult(
                status="skipped",
                rule_type=rule_type,
                ts_code=ts_code,
                skip_reason="t_reduce_already_done_today",
            )

    if not ok and not simulate:
        return ExecutionResult(
            status="skipped",
            rule_type=rule_type,
            ts_code=ts_code,
            skip_reason="trigger_not_met",
            reasons=reasons,
        )

    available = qmt_ctx.available_qty(ts_code) or 1000 if simulate else qmt_ctx.available_qty(ts_code)
    qty = compute_sell_qty(
        pos,
        quantity_pct=float(rule.get("quantity_pct") or 1.0),
        available_qty=available,
    )
    if qty <= 0:
        return ExecutionResult(
            status="skipped",
            rule_type=rule_type,
            ts_code=ts_code,
            skip_reason="zero_sell_qty",
        )

    limit_price = float(quote.bid if quote and quote.bid else rule.get("trigger_price") or 0)
    order = qmt_ctx.place_order(
        ts_code=ts_code,
        side="sell",
        quantity=qty,
        limit_price=limit_price,
        rule_type=rule_type,
        reasons=reasons,
        sell_rule=rule,
        sell_position=pos,
    )
    if rule_type == "t_reduce_resistance" and pos and order.get("status") in {"dry_run", "submitted"}:
        pos.t_state.t_reduce_done = True
        pos.t_state.t_reduce_qty = qty
        pos.mobile_qty = max(0, pos.mobile_qty - qty)

    qmt_ctx.log_event(
        {
            "at": datetime.now().isoformat(),
            "ts_code": ts_code,
            "exit_type": rule_type,
            "simulate": simulate,
        }
    )
    return ExecutionResult(
        status=str(order.get("status") or "unknown"),
        rule_type=rule_type,
        ts_code=ts_code,
        side="sell",
        quantity=qty,
        limit_price=limit_price,
        reasons=reasons,
        skip_reason=order.get("reason"),
        meta={key: order[key] for key in ("sell_intent_id", "sell_attempt_id") if key in order},
    )
