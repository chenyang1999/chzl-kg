from __future__ import annotations

from datetime import datetime
from math import isfinite

from src.plan.buy_eligibility import evaluate_stock_buy_eligibility

from trading.executors.base import (
    ExecutionResult,
    compute_buy_qty,
    evaluate_buy_trigger,
    rule_dict,
    stock_entry_dict,
)
from trading.order.qmt_context import QMTContext
from trading.positions_state import PositionsStateStore


def run_buy_executor(
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

    # Watch/B-plan research is never promoted by merely calling an executor.
    if (entry.get("auto_trade_enabled") is not True
            or not str(entry.get("plan_status") or "").startswith("execution_pool_")):
        return ExecutionResult(status="skipped", rule_type=rule_type, ts_code=ts_code,
                               skip_reason="stock_buy_not_authorized")
    for budget in (rule.get("position_pct"), entry.get("max_position_pct", 0)):
        if (isinstance(budget, bool) or not isinstance(budget, (int, float))
                or not isfinite(budget) or budget <= 0):
            return ExecutionResult(status="skipped", rule_type=rule_type, ts_code=ts_code,
                                   skip_reason="zero_or_invalid_stock_buy_budget")

    quote = qmt_ctx.quotes.get(ts_code)
    if quote is None:
        qmt_ctx.refresh_quotes([ts_code])
        quote = qmt_ctx.quotes.get(ts_code)
    if quote is None:
        return ExecutionResult(
            status="skipped",
            rule_type=rule_type,
            ts_code=ts_code,
            skip_reason="missing_quote",
        )

    # Check the exact proposed limit, not the cached engine buy-zone RR. No
    # simulate/force-trigger branch may bypass this buy-only gate.
    # Keep the existing proposed-limit contract: an explicit max ask is the
    # submitted limit, otherwise use the book ask. Trigger evaluation below
    # still requires a valid actual ask and never substitutes last for it.
    limit_price = rule.get("max_acceptable_ask")
    if limit_price is None:
        limit_price = quote.ask
    eligibility = evaluate_stock_buy_eligibility(
        entry, {"ask": limit_price}, entry_rule=rule)
    if eligibility["status"] != "eligible":
        return ExecutionResult(status="skipped", rule_type=rule_type, ts_code=ts_code,
                               skip_reason="stock_buy_eligibility",
                               reasons=eligibility["reasons"], meta={"buy_eligibility": eligibility})

    ok, reasons = evaluate_buy_trigger(
        rule=rule,
        quote_last=quote.last,
        quote_ask=quote.ask,
    )
    try:
        from trading.watcher.session_context import buy_allowed

        scan_ok, scan_reasons = buy_allowed(
            ts_code, entry_style=rule_type, trade_date=qmt_ctx.trade_date)
    except Exception:
        scan_ok, scan_reasons = False, ["scan_evidence_unavailable"]
    if not scan_ok:
        return ExecutionResult(
            status="skipped",
            rule_type=rule_type,
            ts_code=ts_code,
            skip_reason="intraday_scan_gate",
            reasons=reasons + scan_reasons,
        )
    reasons = reasons + scan_reasons
    # simulate/force_trigger select a test mode, not permission to place buys
    # without evidence. Synthetic callers must provide valid quotes and scans.
    if not ok:
        return ExecutionResult(
            status="skipped",
            rule_type=rule_type,
            ts_code=ts_code,
            skip_reason="trigger_not_met",
            reasons=reasons,
        )

    qty = compute_buy_qty(qmt_ctx, ts_code=ts_code, limit_price=limit_price,
                          position_pct=rule["position_pct"],
                          max_position_pct=entry["max_position_pct"])
    if qty <= 0:
        return ExecutionResult(status="skipped", rule_type=rule_type, ts_code=ts_code,
                               skip_reason="zero_buy_qty", reasons=reasons)
    limit_price = float(limit_price)
    order = qmt_ctx.place_order(
        ts_code=ts_code,
        side="buy",
        quantity=qty,
        limit_price=limit_price,
        rule_type=rule_type,
        reasons=reasons,
        position_pct=float(rule.get("position_pct") or 0),
    )
    qmt_ctx.log_event(
        {
            "at": datetime.now().isoformat(),
            "ts_code": ts_code,
            "entry_type": rule_type,
            "quote": {"last": quote.last, "ask": quote.ask, "bid": quote.bid},
            "simulate": simulate,
        }
    )
    return ExecutionResult(
        status=str(order.get("status") or "unknown"),
        rule_type=rule_type,
        ts_code=ts_code,
        side="buy",
        quantity=qty,
        limit_price=limit_price,
        reasons=reasons,
    )
