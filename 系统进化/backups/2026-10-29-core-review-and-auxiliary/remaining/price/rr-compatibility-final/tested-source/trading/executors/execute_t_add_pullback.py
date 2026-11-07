from __future__ import annotations

from trading.executors._buy_common import run_buy_executor
from trading.executors.base import ExecutionResult
from trading.order.qmt_context import QMTContext
from trading.positions_state import PositionsStateStore


def execute(
    stock_entry: dict,
    rule: dict,
    qmt_ctx: QMTContext,
    positions: PositionsStateStore,
    *,
    simulate: bool = False,
) -> ExecutionResult:
    ts_code = stock_entry["ts_code"]
    if not qmt_ctx.has_position(ts_code):
        return ExecutionResult(
            status="skipped",
            rule_type="t_add_pullback",
            ts_code=ts_code,
            skip_reason="requires_existing_position",
        )
    pos = positions.positions.get(ts_code)
    ratio = stock_entry.get("base_mobile_ratio")
    if ratio is not None and float(ratio) >= 1.0:
        return ExecutionResult(
            status="skipped",
            rule_type="t_add_pullback",
            ts_code=ts_code,
            skip_reason="base_mobile_ratio_blocks_t",
        )
    if pos and pos.t_state.t_add_done:
        return ExecutionResult(
            status="skipped",
            rule_type="t_add_pullback",
            ts_code=ts_code,
            skip_reason="t_add_already_done_today",
        )
    result = run_buy_executor(
        stock_entry,
        rule,
        qmt_ctx,
        positions,
        expected_type="t_add_pullback",
        simulate=simulate,
    )
    if result.status in {"dry_run", "submitted"} and pos is not None:
        pos.t_state.t_add_done = True
        pos.t_state.t_add_qty = result.quantity
        pos.mobile_qty += result.quantity
    return result
