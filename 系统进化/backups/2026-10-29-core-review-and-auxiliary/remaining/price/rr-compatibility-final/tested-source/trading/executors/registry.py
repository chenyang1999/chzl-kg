from __future__ import annotations

from typing import Any, Callable

from trading.executors.base import ExecutionResult
from trading.executors import (
    execute_daban_confirm,
    execute_exit_at_open,
    execute_exit_if_no_new_high,
    execute_intraday_break_exit,
    execute_leader_breakout,
    execute_low_absorption_intraday,
    execute_sector_switch_exit,
    execute_stop_loss_break,
    execute_t_add_pullback,
    execute_take_profit_hit,
    execute_trend_pullback_buy,
    execute_t_reduce_resistance,
    execute_volume_price_divergence,
)
from trading.order.qmt_context import QMTContext
from trading.positions_state import PositionsStateStore

EntryExecutor = Callable[..., ExecutionResult]
ExitExecutor = Callable[..., ExecutionResult]

ENTRY_EXECUTORS: dict[str, EntryExecutor] = {
    "trend_pullback_buy": execute_trend_pullback_buy.execute,
    "leader_breakout": execute_leader_breakout.execute,
    "daban_confirm": execute_daban_confirm.execute,
    "low_absorption_intraday": execute_low_absorption_intraday.execute,
    "t_add_pullback": execute_t_add_pullback.execute,
}

EXIT_EXECUTORS: dict[str, ExitExecutor] = {
    "exit_at_open": execute_exit_at_open.execute,
    "exit_if_no_new_high": execute_exit_if_no_new_high.execute,
    "t_reduce_resistance": execute_t_reduce_resistance.execute,
    "stop_loss_break": execute_stop_loss_break.execute,
    "take_profit_hit": execute_take_profit_hit.execute,
    "sector_switch_exit": execute_sector_switch_exit.execute,
    "intraday_break_exit": execute_intraday_break_exit.execute,
    "volume_price_divergence": execute_volume_price_divergence.execute,
}


def get_entry_executor(rule_type: str) -> EntryExecutor:
    try:
        return ENTRY_EXECUTORS[rule_type]
    except KeyError as exc:
        raise KeyError(f"unknown entry_rules[].type: {rule_type}") from exc


def get_exit_executor(rule_type: str) -> ExitExecutor:
    try:
        return EXIT_EXECUTORS[rule_type]
    except KeyError as exc:
        raise KeyError(f"unknown exit_rules[].type: {rule_type}") from exc


def all_entry_types() -> list[str]:
    return list(ENTRY_EXECUTORS)


def all_exit_types() -> list[str]:
    return list(EXIT_EXECUTORS)
