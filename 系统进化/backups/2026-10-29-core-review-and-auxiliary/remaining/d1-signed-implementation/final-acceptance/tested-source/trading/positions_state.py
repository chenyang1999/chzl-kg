from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from src.settings import DATA_DIR, ROOT


RUNTIME_DIR = DATA_DIR / "runtime"


@dataclass
class TState:
    date: str
    t_add_done: bool = False
    t_reduce_done: bool = False
    t_add_qty: int = 0
    t_reduce_qty: int = 0


@dataclass
class PositionState:
    ts_code: str
    total_qty: int = 0
    base_qty: int = 0
    mobile_qty: int = 0
    avg_cost: float = 0.0
    base_mobile_ratio: float = 0.7
    t_state: TState = field(default_factory=lambda: TState(date=""))

    def available_mobile_qty(self) -> int:
        return max(0, self.mobile_qty - self.t_state.t_add_qty)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts_code": self.ts_code,
            "total_qty": self.total_qty,
            "base_qty": self.base_qty,
            "mobile_qty": self.mobile_qty,
            "avg_cost": self.avg_cost,
            "base_mobile_ratio": self.base_mobile_ratio,
            "t_state": {
                "date": self.t_state.date,
                "t_add_done": self.t_state.t_add_done,
                "t_reduce_done": self.t_state.t_reduce_done,
                "t_add_qty": self.t_state.t_add_qty,
                "t_reduce_qty": self.t_state.t_reduce_qty,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PositionState:
        t_raw = data.get("t_state") or {}
        return cls(
            ts_code=str(data["ts_code"]),
            total_qty=int(data.get("total_qty") or 0),
            base_qty=int(data.get("base_qty") or 0),
            mobile_qty=int(data.get("mobile_qty") or 0),
            avg_cost=float(data.get("avg_cost") or 0),
            base_mobile_ratio=float(data.get("base_mobile_ratio") or 0.7),
            t_state=TState(
                date=str(t_raw.get("date") or ""),
                t_add_done=bool(t_raw.get("t_add_done")),
                t_reduce_done=bool(t_raw.get("t_reduce_done")),
                t_add_qty=int(t_raw.get("t_add_qty") or 0),
                t_reduce_qty=int(t_raw.get("t_reduce_qty") or 0),
            ),
        )


class PositionsStateStore:
    def __init__(self, path: Path, *, trade_date: str) -> None:
        self.path = path
        self.trade_date = trade_date
        self.positions: dict[str, PositionState] = {}

    @classmethod
    def for_mode(cls, *, trade_date: str, dry_run: bool) -> PositionsStateStore:
        name = "dry_run_positions_state.json" if dry_run else "positions_state.json"
        return cls(RUNTIME_DIR / name, trade_date=trade_date)

    def load(self) -> None:
        if not self.path.exists():
            self.positions = {}
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        rows = data.get("positions") or []
        self.positions = {str(row["ts_code"]): PositionState.from_dict(row) for row in rows}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "trade_date": self.trade_date,
            "positions": [row.to_dict() for row in self.positions.values()],
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def ensure_from_holdings(
        self,
        holdings: dict[str, dict[str, Any]],
        *,
        base_mobile_ratio: float,
    ) -> None:
        for ts_code, row in holdings.items():
            total = int(row.get("total_qty") or row.get("qty") or 0)
            ratio = float(row.get("base_mobile_ratio") or base_mobile_ratio)
            if ts_code in self.positions:
                pos = self.positions[ts_code]
                pos.total_qty = total
            else:
                base = int(total * ratio)
                mobile = max(0, total - base)
                pos = PositionState(
                    ts_code=ts_code,
                    total_qty=total,
                    base_qty=base,
                    mobile_qty=mobile,
                    avg_cost=float(row.get("cost_price") or row.get("avg_cost") or 0),
                    base_mobile_ratio=ratio,
                    t_state=TState(date=self.trade_date),
                )
                self.positions[ts_code] = pos

    def reset_daily_t_state(self) -> None:
        for pos in self.positions.values():
            pos.t_state = TState(date=self.trade_date)


def kill_switch_active(kill_switch_file: str) -> bool:
    path = Path(kill_switch_file)
    if not path.is_absolute():
        path = ROOT / path
    return path.exists()
