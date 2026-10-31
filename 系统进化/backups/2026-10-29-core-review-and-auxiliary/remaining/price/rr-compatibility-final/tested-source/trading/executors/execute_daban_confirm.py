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
    if not simulate and qmt_ctx.has_position(stock_entry["ts_code"]):
        return ExecutionResult(
            status="skipped",
            rule_type="daban_confirm",
            ts_code=stock_entry["ts_code"],
            skip_reason="already_holding",
        )
    return run_buy_executor(
        stock_entry,
        rule,
        qmt_ctx,
        positions,
        expected_type="daban_confirm",
        simulate=simulate,
        force_trigger=True,
    )
