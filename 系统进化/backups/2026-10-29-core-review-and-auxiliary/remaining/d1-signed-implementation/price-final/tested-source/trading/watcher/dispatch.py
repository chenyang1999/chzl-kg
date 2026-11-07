from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.plan.buy_eligibility import evaluate_plan_buy_gate
from trading.executors.registry import get_entry_executor, get_exit_executor
from trading.order.qmt_context import QMTContext
from trading.positions_state import PositionsStateStore
from trading.schema.watchlist_plan import StockEntry, WatchlistPlan


@dataclass
class MonitorTask:
    pool: str
    stock: dict[str, Any]
    rule: dict[str, Any]
    rule_kind: str  # entry | exit
    priority: int = 99


@dataclass
class DispatchReport:
    entry_results: list[dict[str, Any]] = field(default_factory=list)
    exit_results: list[dict[str, Any]] = field(default_factory=list)
    watch_started: list[str] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)


def build_monitor_tasks(plan: WatchlistPlan) -> list[MonitorTask]:
    tasks: list[MonitorTask] = []
    for stock in plan.execution_pool:
        entry = stock.model_dump(mode="json")
        for rule in entry.get("exit_rules") or []:
            tasks.append(
                MonitorTask(
                    pool="execution_pool",
                    stock=entry,
                    rule=rule,
                    rule_kind="exit",
                    priority=int(rule.get("priority") or 99),
                )
            )
        for rule in entry.get("entry_rules") or []:
            tasks.append(
                MonitorTask(
                    pool="execution_pool",
                    stock=entry,
                    rule=rule,
                    rule_kind="entry",
                    priority=50,
                )
            )
    for stock in plan.watch_pool:
        entry = stock.model_dump(mode="json")
        tasks.append(
            MonitorTask(
                pool="watch_pool",
                stock=entry,
                rule={},
                rule_kind="watch",
                priority=100,
            )
        )
    return sorted(tasks, key=lambda t: t.priority)


def dispatch_plan(
    plan: WatchlistPlan,
    qmt_ctx: QMTContext,
    positions: PositionsStateStore,
    *,
    simulate: bool = False,
) -> DispatchReport:
    report = DispatchReport()
    # Global restrictions are independent of per-stock RR and only gate buys.
    global_buy_gate = evaluate_plan_buy_gate(plan.model_dump(mode="json"))
    symbols = [s.ts_code for s in plan.execution_pool] + [s.ts_code for s in plan.watch_pool]
    qmt_ctx.refresh_quotes(symbols)

    for stock in plan.execution_pool:
        entry = stock.model_dump(mode="json")
        if stock.plan_status == "execution_pool_exit_at_open":
            rule = {"type": "exit_at_open", "quantity_pct": 1.0, "priority": 0}
            executor = get_exit_executor("exit_at_open")
            result = executor(entry, rule, qmt_ctx, positions, simulate=simulate)
            report.exit_results.append(result.__dict__)

        exit_rules = sorted(entry.get("exit_rules") or [], key=lambda r: int(r.get("priority") or 99))
        for rule in exit_rules:
            if rule.get("type") == "exit_at_open" and stock.plan_status == "execution_pool_exit_at_open":
                continue
            executor = get_exit_executor(str(rule["type"]))
            result = executor(entry, rule, qmt_ctx, positions, simulate=simulate)
            report.exit_results.append(result.__dict__)

        if global_buy_gate["status"] != "eligible":
            report.skipped.append({"ts_code": stock.ts_code, "reason": "global_buy_gate",
                                   "reasons": global_buy_gate["reasons"]})
            continue
        stock_buy_gate = evaluate_plan_buy_gate(plan.model_dump(mode="json"), ts_code=stock.ts_code)
        if stock_buy_gate["status"] != "eligible":
            report.skipped.append({"ts_code": stock.ts_code, "reason": "stock_buy_gate",
                                   "reasons": stock_buy_gate["reasons"]})
            continue
        if not stock.auto_trade_enabled:
            report.skipped.append({"ts_code": stock.ts_code, "reason": "auto_trade_disabled"})
            continue

        for rule in entry.get("entry_rules") or []:
            # T3 · optional judgment node (pilot): CHZL_JUDGMENT_NODE=buy_confirm
            # → scripts/judgment_nodes/buy_confirm.py · confirm/reject/defer_60s · 3s · timeout→reject
            # See scripts/judgment_nodes/README.md
            if os.environ.get("CHZL_JUDGMENT_NODE") == "buy_confirm" and not simulate:
                quote = qmt_ctx.quotes.get(stock.ts_code)
                verdict = _run_buy_confirm_judgment(entry, rule, quote)
                if verdict in {"reject", "defer_60s"}:
                    report.skipped.append(
                        {
                            "ts_code": stock.ts_code,
                            "reason": f"judgment_node:{verdict}",
                            "rule_type": rule.get("type"),
                        }
                    )
                    continue
            executor = get_entry_executor(str(rule["type"]))
            result = executor(entry, rule, qmt_ctx, positions, simulate=simulate)
            report.entry_results.append(result.__dict__)

    for stock in plan.watch_pool:
        qmt_ctx.log_event(
            {
                "at": datetime.now().isoformat(),
                "event": "watch_started",
                "ts_code": stock.ts_code,
                "pool": "watch_pool",
            }
        )
        report.watch_started.append(stock.ts_code)

    return report


def _run_buy_confirm_judgment(
    stock_entry: dict[str, Any],
    rule: dict[str, Any],
    quote: Any,
) -> str:
    from scripts.judgment_nodes.buy_confirm import run_buy_confirm

    context = {
        "ts_code": stock_entry.get("ts_code"),
        "trigger_price": rule.get("trigger_price"),
        "ask": getattr(quote, "ask", None) if quote else None,
        "last": getattr(quote, "last", None) if quote else None,
        "sector": stock_entry.get("sector"),
    }
    payload = run_buy_confirm(context)
    return str(payload.get("result") or "reject")


def simulate_all_rule_types(plan: WatchlistPlan, qmt_ctx: QMTContext, positions: PositionsStateStore) -> DispatchReport:
    """Dry-run helper: force one pass per registered executor type using fixture prices."""
    from trading.executors.registry import all_entry_types, all_exit_types

    report = DispatchReport()
    if not plan.execution_pool:
        return report

    template = plan.execution_pool[0].model_dump(mode="json")
    ts_code = template["ts_code"]
    from src.trading_agent.models import Quote

    qmt_ctx.quotes[ts_code] = Quote(ts_code=ts_code, last=50.0, ask=50.0, bid=49.8)
    if not qmt_ctx.has_position(ts_code):
        qmt_ctx.holdings[ts_code] = {"ts_code": ts_code, "total_qty": 1000, "available_qty": 1000, "cost_price": 48.0}
        qmt_ctx.total_asset = max(qmt_ctx.total_asset, 500000.0)
    positions.ensure_from_holdings(qmt_ctx.holdings, base_mobile_ratio=0.7)

    for rule_type in all_exit_types():
        rule = {
            "type": rule_type,
            "trigger_price": 55.0 if rule_type != "exit_at_open" else None,
            "quantity_pct": 0.3,
            "priority": 1,
        }
        result = get_exit_executor(rule_type)(template, rule, qmt_ctx, positions, simulate=True)
        report.exit_results.append(result.__dict__)

    for rule_type in all_entry_types():
        rule = {
            "type": rule_type,
            "trigger_price": 52.0,
            "position_pct": 0.05,
            "max_acceptable_ask": 53.0,
        }
        result = get_entry_executor(rule_type)(template, rule, qmt_ctx, positions, simulate=True)
        report.entry_results.append(result.__dict__)

    return report
