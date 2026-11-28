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
    return run_buy_executor(
        stock_entry,
        rule,
        qmt_ctx,
        positions,
        expected_type="leader_breakout",
        simulate=simulate,
    )
