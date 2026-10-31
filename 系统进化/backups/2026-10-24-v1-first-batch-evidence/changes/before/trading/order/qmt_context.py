from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from src.execute.amygdala import Amygdala
from src.settings import DATA_DIR, ROOT
from src.trading_agent.journal import append_jsonl
from src.trading_agent.models import Quote, kill_switch_active as legacy_kill_switch
from src.trading_agent.qmt_client import QMTMCPClient


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
        if self.dry_run:
            for code in symbols:
                row = self.holdings.get(code) or {}
                last = float(row.get("last_price") or row.get("last") or 0)
                if last <= 0:
                    continue
                self.quotes[code] = Quote(
                    ts_code=code,
                    last=last,
                    ask=last,
                    bid=last,
                )
            return
        try:
            client = self._ensure_client()
            self.quotes.update(client.get_quotes(symbols))
        except Exception:
            for code in symbols:
                row = self.holdings.get(code) or {}
                last = float(row.get("last_price") or row.get("last") or 0)
                if last <= 0:
                    continue
                self.quotes[code] = Quote(
                    ts_code=code,
                    last=last,
                    ask=last,
                    bid=last,
                )

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
        if avail is not None:
            return int(avail)
        return int(row.get("total_qty") or 0)
