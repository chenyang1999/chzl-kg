from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from math import isfinite
from pathlib import Path
from typing import Any
import json

from src.execute.amygdala import Amygdala
from src.settings import DATA_DIR, ROOT
from src.trading_agent.journal import append_jsonl
from src.trading_agent.models import Quote, kill_switch_active as legacy_kill_switch
from src.trading_agent.qmt_client import QMTMCPClient
from trading.execution_authorization import ExecutionAuthorization, buy_budget_reasons


@dataclass
class QMTContext:
    trade_date: str
    dry_run: bool
    kill_switch_file: str
    holdings: dict[str, dict[str, Any]] = field(default_factory=dict)
    quotes: dict[str, Quote] = field(default_factory=dict)
    total_asset: float = 0.0
    cash: float = 0.0
    _client: QMTMCPClient | None = None
    runtime_dir: Path = field(default_factory=lambda: DATA_DIR / "runtime")
    authorization: ExecutionAuthorization | None = None

    @property
    def orders_path(self) -> Path:
        name = (
            f"dry_run_orders_{self.trade_date}.jsonl"
            if self.dry_run
            else f"orders_{self.trade_date}.jsonl"
        )
        return self.runtime_dir / name

    @property
    def events_path(self) -> Path:
        name = (
            f"dry_run_events_{self.trade_date}.jsonl"
            if self.dry_run
            else f"events_{self.trade_date}.jsonl"
        )
        return self.runtime_dir / name

    @property
    def decisions_path(self) -> Path:
        name = (
            f"dry_run_decisions_{self.trade_date}.jsonl"
            if self.dry_run
            else f"decisions_{self.trade_date}.jsonl"
        )
        return self.runtime_dir / name

    def kill_switch_active(self) -> bool:
        return legacy_kill_switch(self.kill_switch_file, ROOT)

    def refresh_holdings(self, *, allow_file_fallback: bool = True) -> None:
        file_path = self.runtime_dir / f"holdings_{self.trade_date}.json"
        if allow_file_fallback and file_path.exists():
            import json

            data = json.loads(file_path.read_text(encoding="utf-8"))
            self._apply_holdings_payload(data)
            return
        try:
            client = self._ensure_client()
            data = client.get_holdings(include_trades=False)
            self._apply_holdings_payload(data)
        except Exception:
            if allow_file_fallback and file_path.exists():
                import json

                data = json.loads(file_path.read_text(encoding="utf-8"))
                self._apply_holdings_payload(data)

    def _apply_holdings_payload(self, data: dict[str, Any]) -> None:
        summary = data.get("summary") or {}
        self.total_asset = float(summary.get("total_asset") or 0)
        self.cash = float(summary.get("cash") or 0)
        self.holdings = {}
        for row in data.get("positions") or []:
            code = str(row.get("ts_code") or "")
            if code:
                self.holdings[code] = row

    def refresh_quotes(self, symbols: list[str]) -> None:
        if not symbols:
            return
        # Dry-run may consume explicitly supplied books, but must not invent
        # them from holdings or connect to a broker merely to record intents.
        if self.dry_run:
            return
        # A failed live refresh invalidates requested quotes; cached holding
        # last is neither a bid nor an ask.
        for code in symbols:
            self.quotes.pop(code, None)
        try:
            client = self._ensure_client()
            quotes = client.get_quotes(symbols)
            self.quotes.update({code: quotes[code] for code in symbols if code in quotes})
        except Exception:
            return

    def _ensure_client(self) -> QMTMCPClient:
        if self._client is None:
            self._client = QMTMCPClient()
        return self._client

    def place_order(
        self,
        *,
        ts_code: str,
        side: str,
        quantity: int,
        limit_price: float,
        rule_type: str,
        reasons: list[str],
        position_pct: float = 0.0,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now().isoformat()
        record: dict[str, Any] = {
            "at": now,
            "ts_code": ts_code,
            "side": side,
            "quantity": quantity,
            "limit_price": limit_price,
            "rule_type": rule_type,
            "reasons": reasons,
            "position_pct": position_pct,
            "dry_run": self.dry_run,
            "meta": meta or {},
        }
        if self.kill_switch_active():
            record["status"] = "rejected"
            record["reason"] = "kill_switch_active"
            append_jsonl(self.orders_path, record)
            return record
        authorization_reason = self._authorization_reason(
            ts_code=ts_code, side=side, quantity=quantity,
            limit_price=limit_price, rule_type=rule_type)
        if authorization_reason:
            record.update(status="rejected", reason=authorization_reason)
            append_jsonl(self.orders_path, record)
            return record
        # A holding last/plan trigger is not an executable book, even if a
        # caller supplies it as limit_price. Authorization above is independent
        # of this side-specific executable-book check.
        quote = self.quotes.get(ts_code)
        book_price = getattr(quote, "ask" if side.lower() in {"buy", "b"} else "bid", None)
        if (isinstance(book_price, bool) or not isinstance(book_price, (int, float))
                or not isfinite(book_price) or book_price <= 0):
            record["status"] = "rejected"
            record["reason"] = "missing_or_invalid_executable_quote"
            append_jsonl(self.orders_path, record)
            return record

        # Existing sell wrappers submit the executable bid. Bind the final
        # forwarded limit too; a positive bid alone does not authorize any price.
        if side == "sell" and limit_price != book_price:
            record.update(status="rejected", reason="sell_limit_not_authorized")
            append_jsonl(self.orders_path, record)
            return record

        amy = Amygdala()
        if side.lower() in {"buy", "b"}:
            meta = meta or {}
            verdict = amy.check_buy_order(
                ts_code=ts_code,
                name=str(meta.get("name") or ""),
                quantity=quantity,
                limit_price=limit_price,
                total_asset=self.total_asset,
                holdings=self.holdings,
                sector=meta.get("sector"),
            )
            if not verdict.allowed:
                record["status"] = "rejected"
                record["reason"] = verdict.reason
                record["amygdala_code"] = verdict.code
                append_jsonl(self.orders_path, record)
                return record
        elif side.lower() in {"sell", "s"}:
            verdict = amy.check_sell_order(
                ts_code=ts_code,
                quantity=quantity,
                available_qty=self.available_qty(ts_code),
            )
            if not verdict.allowed:
                record["status"] = "rejected"
                record["reason"] = verdict.reason
                record["amygdala_code"] = verdict.code
                append_jsonl(self.orders_path, record)
                return record

        if self.dry_run:
            record["status"] = "dry_run"
            record["order_id"] = None
            append_jsonl(self.orders_path, record)
            append_jsonl(
                self.decisions_path,
                {
                    "at": now,
                    "action": side,
                    "ts_code": ts_code,
                    "side": side,
                    "quantity": quantity,
                    "limit_price": limit_price,
                    "dry_run": True,
                    "rule_type": rule_type,
                    "reasons": reasons,
                },
            )
            return record

        client = self._ensure_client()
        order = client.place_limit_order(
            symbol=ts_code,
            side=side,
            quantity=quantity,
            limit_price=limit_price,
            remark=f"trading {rule_type}",
        )
        record["status"] = "submitted"
        record["order"] = order
        append_jsonl(self.orders_path, record)
        return record

    def _authorization_reason(self, *, ts_code: str, side: str, quantity: int,
                              limit_price: float, rule_type: str) -> str | None:
        """Final boundary, independent of dispatcher/force/simulate.

        Read-only contexts (after_close) need no order authorization; do not
        put this gate in _ensure_client/refresh_holdings.
        """
        if (side not in {"buy", "sell"} or type(quantity) is not int or quantity <= 0
                or type(limit_price) not in (int, float) or not isfinite(limit_price) or limit_price <= 0):
            return "invalid_order"
        if type(self.authorization) is not ExecutionAuthorization:
            return "execution_authorization_missing_or_invalid"
        try:
            plan = self.authorization.validated_plan(trade_date=self.trade_date, dry_run=self.dry_run)
            risk = plan["risk_limits"]
            if risk.get("kill_switch_file") != self.kill_switch_file:
                return "authorization_kill_switch_mismatch"
            pool = plan["execution_pool"] if side == "buy" else plan["execution_pool"] + plan["watch_pool"]
            stocks = [s for s in pool if s["ts_code"] == ts_code]
            # Held watch exit projection intentionally occurs in both pools.
            if side == "sell":
                stocks = stocks[:1]
            if len(stocks) != 1:
                return "stock_order_not_authorized"
            stock = stocks[0]
            if side == "sell":
                explicit = any(r["type"] == rule_type for r in stock["exit_rules"])
                if not explicit and not (rule_type == "exit_at_open" and stock.get("plan_status") == "execution_pool_exit_at_open"):
                    return "sell_rule_not_authorized"
                if quantity > self.available_qty(ts_code):
                    return "exceeds_available_qty"
                return None  # No buy budget, buy scan, or buy-auto requirement.
            if (plan.get("autonomous_trading_enabled") is not True
                    or plan.get("requires_user_confirmation") is not False):
                return "plan_account_buy_not_authorized"
            if (stock.get("auto_trade_enabled") is not True
                    or stock.get("requires_user_confirmation") is not False
                    or not str(stock.get("plan_status") or "").startswith("execution_pool_")):
                return "stock_buy_not_authorized"
            blockers = buy_budget_reasons(risk)
            if blockers:
                return "buy_budget_blocked:" + ",".join(blockers)
            from src.plan.buy_eligibility import evaluate_plan_buy_gate, evaluate_stock_buy_eligibility
            from src.trading_agent.models import is_blocked_prefix, normalize_name_is_st
            from trading.executors.base import evaluate_buy_trigger
            from trading.watcher.session_context import buy_allowed

            if evaluate_plan_buy_gate(plan, ts_code=ts_code)["status"] != "eligible":
                return "global_or_stock_buy_gate"
            if (is_blocked_prefix(ts_code, tuple(risk.get("block_prefixes", [])))
                    or risk.get("block_st", True) and (stock.get("is_st") or normalize_name_is_st(stock["name"]))):
                return "stock_buy_compliance"
            rules = [r for r in stock["entry_rules"] if r["type"] == rule_type]
            if len(rules) != 1:
                return "buy_rule_not_uniquely_authorized"
            rule = rules[0]
            quote = self.quotes.get(ts_code)
            if quote is None:
                return "missing_or_invalid_executable_quote"
            if not evaluate_buy_trigger(rule=rule, quote_last=quote.last,
                                        quote_ask=quote.ask)[0]:
                return "buy_trigger_not_met"
            expected_price = rule.get("max_acceptable_ask")
            if expected_price is None:
                expected_price = getattr(quote, "ask", None)
            if limit_price != expected_price:
                return "buy_limit_not_authorized"
            if evaluate_stock_buy_eligibility(stock, {"ask": limit_price}, entry_rule=rule)["status"] != "eligible":
                return "stock_buy_eligibility"
            if not buy_allowed(ts_code, entry_style=rule_type,
                               trade_date=self.trade_date)[0]:
                return "intraday_scan_gate"
            return self._buy_capacity_reason(stock, rule, risk, quantity, limit_price)
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RuntimeError):
            return "execution_authorization_invalid"

    def _buy_capacity_reason(self, stock: dict, rule: dict, risk: dict,
                             quantity: int, price: float) -> str | None:
        """Existing caps and mode-specific journal, never a new allowance.

        Reserve all accepted buy notional conservatively; do not release on an
        unverified fill/cancel. Reconciliation/cross-process atomicity remains
        a live-rollout blocker, not something this local journal can certify.
        """
        def number(value: Any) -> Decimal:
            if type(value) not in (int, float) or not isfinite(value) or value < 0:
                raise ValueError("unknown capacity")
            return Decimal(str(value))

        try:
            asset, cash = number(self.total_asset), number(self.cash)
            pct, cap = number(rule.get("position_pct")), number(stock.get("max_position_pct"))
            if asset <= 0 or pct <= 0 or cap <= 0 or pct > 1 or cap > 1 or quantity % 100:
                return "zero_or_invalid_stock_buy_budget"
            rows = [json.loads(line) for line in self.orders_path.read_text(encoding="utf-8").splitlines() if line.strip()] if self.orders_path.exists() else []
            status = "dry_run" if self.dry_run else "submitted"
            buys = [r for r in rows if r.get("status") == status and r.get("side") == "buy"]
            if len(buys) >= risk["max_buy_orders_per_day"]:
                return "daily_buy_order_cap_reached"
            if sum(r["ts_code"] == stock["ts_code"] for r in buys) >= risk["max_orders_per_symbol_per_day"]:
                return "symbol_buy_order_cap_reached"
            held_values = {}
            for code, row in self.holdings.items():
                qty = number(row.get("total_qty"))
                if qty != qty.to_integral_value():
                    raise ValueError("invalid holding qty")
                if qty > 0:
                    held_values[code] = number(row.get("market_value"))
                    if held_values[code] <= 0:
                        raise ValueError("unknown holding value")
            reserved = {}
            for row in buys:
                value = number(row["quantity"]) * number(row["limit_price"])
                reserved[row["ts_code"]] = reserved.get(row["ts_code"], Decimal(0)) + value
            codes = set(held_values) | set(reserved)
            if stock["ts_code"] not in codes and len(codes) >= risk["max_positions"]:
                return "max_positions_reached"
            value = Decimal(quantity) * number(price)
            pending = sum(reserved.values(), Decimal(0))
            if value > cash - pending:
                return "cash_budget_exceeded"
            if value > asset * pct:
                return "rule_buy_budget_exceeded"
            if value + held_values.get(stock["ts_code"], Decimal(0)) + reserved.get(stock["ts_code"], Decimal(0)) > asset * cap:
                return "stock_position_cap_exceeded"
            if value + sum(held_values.values(), Decimal(0)) + pending > asset * number(risk["target_total_position_pct"]):
                return "total_position_cap_exceeded"
        except (OSError, ValueError, TypeError, KeyError, InvalidOperation, OverflowError, AttributeError):
            return "buy_capacity_evidence_invalid"
        return None

    def log_event(self, payload: dict[str, Any]) -> None:
        append_jsonl(self.events_path, payload)

    def has_position(self, ts_code: str) -> bool:
        row = self.holdings.get(ts_code) or {}
        return int(row.get("total_qty") or 0) > 0

    def position_qty(self, ts_code: str) -> int:
        row = self.holdings.get(ts_code) or {}
        return int(row.get("total_qty") or 0)

    def available_qty(self, ts_code: str) -> int:
        row = self.holdings.get(ts_code) or {}
        avail = row.get("available_qty")
        if isinstance(avail, bool) or not isinstance(avail, (int, float, str, Decimal)):
            return 0
        try:
            value = Decimal(str(avail))
            if not value.is_finite() or value < 0 or value != value.to_integral_value():
                return 0
            return int(value)
        except (InvalidOperation, ValueError, TypeError, OverflowError):
            return 0
