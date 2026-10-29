from trading.executors._sell_common import run_sell_executor


def execute(stock_entry, rule, qmt_ctx, positions, *, simulate=False):
    return run_sell_executor(
        stock_entry, rule, qmt_ctx, positions,
        expected_type="sector_switch_exit", simulate=simulate, force_trigger=simulate,
    )
