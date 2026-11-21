from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from enum import Enum
from math import floor
from pathlib import Path
from typing import Any, Literal


ALLOWED_ROLES = {"leader", "core_midcap", "elastic_core"}
BLOCKED_ROLES = {"follow", "junk"}
ALLOWED_ENTRY_TYPES = {
    "leader_breakout",
    "mainline_reflow_confirm",
    "trend_pullback_buy",
    "breakout_retest_buy",
    "event_driven_open_confirmation",  # Bug #4: Event-driven catalysts — don't exclude by money flow
}
BLOCKED_PREFIXES_DEFAULT = ("300", "688", "920")
LOT_SIZE = 100


class DecisionAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    REJECT = "reject"
    HOLD = "hold"


@dataclass(frozen=True)
class AlphaCandidate:
    ts_code: str
    name: str
    theme: str
    role: str
    score: float
    alpha_logic: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    is_st: bool = False

    @property
    def prefix(self) -> str:
        return self.ts_code.split(".")[0][:3]


@dataclass(frozen=True)
class EntryRule:
    type: str
    position_pct: float
    max_premium_pct: float
    trigger_price: float | None = None
    pullback_zone: tuple[float, float] | None = None
    reclaim_price: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EntryRule":
        zone = data.get("pullback_zone")
        return cls(
            type=str(data["type"]),
            position_pct=float(data.get("position_pct", 0.0)),
            max_premium_pct=float(data.get("max_premium_pct", 0.0)),
            trigger_price=_maybe_float(data.get("trigger_price")),
            pullback_zone=(float(zone[0]), float(zone[1])) if zone else None,
            reclaim_price=_maybe_float(data.get("reclaim_price")),
        )

    @property
    def reference_price(self) -> float | None:
        if self.type in ("trend_pullback_buy", "event_driven_open_confirmation"):
            if self.reclaim_price is not None:
                return self.reclaim_price
            if self.pullback_zone is not None:
                return self.pullback_zone[1]
        return self.trigger_price


@dataclass(frozen=True)
class PlanSymbol:
    ts_code: str
    name: str
    theme: str
    role: str
    score: float
    alpha_logic: list[str]
    auto_trade_enabled: bool
    max_position_pct: float
    entry_rules: list[EntryRule]
    stop_loss: float
    take_profit: float | None = None
    is_st: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlanSymbol":
        return cls(
            ts_code=str(data["ts_code"]),
            name=str(data.get("name", "")),
            theme=str(data.get("theme", "")),
            role=str(data.get("role", "")),
            score=float(data.get("score", 0)),
            alpha_logic=[str(x) for x in data.get("alpha_logic", [])],
            auto_trade_enabled=bool(data.get("auto_trade_enabled", False)),
            max_position_pct=float(data.get("max_position_pct", 0.0)),
            entry_rules=[EntryRule.from_dict(x) for x in data.get("entry_rules", [])],
            stop_loss=float(data.get("stop_loss", 0.0)),
            take_profit=_maybe_float(data.get("take_profit")),
            is_st=bool(data.get("is_st", False)),
        )


@dataclass(frozen=True)
class RiskLimits:
    target_total_position_pct: float = 0.4
    max_positions: int = 4
    max_buy_orders_per_day: int = 4
    max_orders_per_symbol_per_day: int = 2
    block_prefixes: tuple[str, ...] = BLOCKED_PREFIXES_DEFAULT
    block_st: bool = True
    kill_switch_file: str = "data/runtime/KILL_SWITCH"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "RiskLimits":
        data = data or {}
        return cls(
            target_total_position_pct=float(data.get("target_total_position_pct", 0.4)),
            max_positions=int(data.get("max_positions", 4)),
            max_buy_orders_per_day=int(data.get("max_buy_orders_per_day", 4)),
            max_orders_per_symbol_per_day=int(data.get("max_orders_per_symbol_per_day", 2)),
            block_prefixes=tuple(data.get("block_prefixes", BLOCKED_PREFIXES_DEFAULT)),
            block_st=bool(data.get("block_st", True)),
            kill_switch_file=str(data.get("kill_switch_file", "data/runtime/KILL_SWITCH")),
        )


@dataclass(frozen=True)
class SectorEffect:
    theme: str
    status: Literal["strong", "neutral", "weak", "unknown"] = "unknown"
    strength_score: float = 0.0
    breadth_count: int = 0
    leader_count: int = 0
    core_symbols: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SectorEffect":
        return cls(
            theme=str(data.get("theme", "")),
            status=str(data.get("status", "unknown")),  # type: ignore[arg-type]
            strength_score=float(data.get("strength_score", 0.0)),
            breadth_count=int(data.get("breadth_count", 0)),
            leader_count=int(data.get("leader_count", 0)),
            core_symbols=tuple(str(x) for x in data.get("core_symbols", [])),
            reasons=tuple(str(x) for x in data.get("reasons", [])),
        )

    @property
    def allows_new_buy(self) -> bool:
        if self.status == "weak":
            return False
        if self.status == "strong":
            return self.strength_score >= 55 and (self.breadth_count >= 2 or self.leader_count >= 1)
        if self.status == "neutral":
            return self.strength_score >= 45 and self.leader_count >= 1
        return True


@dataclass(frozen=True)
class WatchlistPlan:
    trade_date: str
    mode: Literal["dry_run", "live"]
    trading_style: str
    risk_limits: RiskLimits
    execution_pool: list[PlanSymbol]
    watch_pool: list[dict[str, Any]] = field(default_factory=list)
    rejected: list[dict[str, Any]] = field(default_factory=list)
    sector_effects: dict[str, SectorEffect] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WatchlistPlan":
        mode = str(data.get("mode", "dry_run"))
        if mode not in {"dry_run", "live"}:
            raise ValueError(f"invalid mode: {mode}")
        raw_sector_effects = data.get("sector_effects") or {}
        if isinstance(raw_sector_effects, list):
            sector_effects = {
                str(item.get("theme", "")): SectorEffect.from_dict(item)
                for item in raw_sector_effects
                if item.get("theme")
            }
        else:
            sector_effects = {
                str(theme): SectorEffect.from_dict({"theme": theme, **effect})
                for theme, effect in dict(raw_sector_effects).items()
            }
        return cls(
            trade_date=str(data["trade_date"]),
            mode=mode,  # type: ignore[arg-type]
            trading_style=str(data.get("trading_style", "mainline_right_side_with_trend_pullback")),
            risk_limits=RiskLimits.from_dict(data.get("risk_limits")),
            execution_pool=[PlanSymbol.from_dict(x) for x in data.get("execution_pool", [])],
            watch_pool=list(data.get("watch_pool", [])),
            rejected=list(data.get("rejected", [])),
            sector_effects=sector_effects,
        )

    def symbol(self, ts_code: str) -> PlanSymbol | None:
        for item in self.execution_pool:
            if item.ts_code == ts_code:
                return item
        return None


@dataclass(frozen=True)
class Quote:
    ts_code: str
    last: float
    ask: float
    bid: float
    high_limit: float | None = None
    low_limit: float | None = None


@dataclass(frozen=True)
class IntradaySignalSnapshot:
    """Auxiliary intraday signal snapshot from xTick/WeFlow/research sources.

    Execution prices must still come from QMT Quote, not from this snapshot.
    """

    ts_code: str
    source: str
    last: float | None = None
    bid: float | None = None
    ask: float | None = None
    market_emotion_score: float | None = None
    limit_up_count: int | None = None
    limit_down_count: int | None = None
    max_limit_up_days: int | None = None
    news_titles: tuple[str, ...] = ()


@dataclass(frozen=True)
class PositionSnapshot:
    ts_code: str
    total_qty: int
    available_qty: int
    today_buy_qty: int = 0


@dataclass(frozen=True)
class TPlan:
    ts_code: str
    base_qty: int
    mobile_qty: int
    trend_mode: Literal["uptrend", "box", "downtrend"]
    support_price: float
    resistance_price: float
    max_t_rounds_per_day: int = 1
    t_buy_cutoff: time = time(14, 30)
    kill_switch_file: str | None = None


@dataclass(frozen=True)
class AccountSnapshot:
    total_asset: float
    cash: float
    positions: dict[str, float] = field(default_factory=dict)  # market value by ts_code
    open_buy_orders: dict[str, int] = field(default_factory=dict)
    buy_count_by_symbol: dict[str, int] = field(default_factory=dict)
    total_buy_orders_today: int = 0

    @property
    def position_count(self) -> int:
        return len([v for v in self.positions.values() if v > 0])

    @property
    def total_position_value(self) -> float:
        return sum(v for v in self.positions.values() if v > 0)


@dataclass(frozen=True)
class TradeEvent:
    ts_code: str
    entry_type: str
    at: datetime


@dataclass(frozen=True)
class TradeDecision:
    action: DecisionAction
    ts_code: str
    side: Literal["buy", "sell"] | None = None
    quantity: int = 0
    limit_price: float | None = None
    dry_run: bool = True
    reasons: tuple[str, ...] = ()
    rule_type: str | None = None
    position_pct: float = 0.0

    @classmethod
    def reject(cls, ts_code: str, reason: str) -> "TradeDecision":
        return cls(action=DecisionAction.REJECT, ts_code=ts_code, reasons=(reason,))


def _maybe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def is_blocked_prefix(ts_code: str, prefixes: tuple[str, ...] = BLOCKED_PREFIXES_DEFAULT) -> bool:
    code = ts_code.split(".")[0]
    return any(code.startswith(prefix) for prefix in prefixes)


def normalize_name_is_st(name: str) -> bool:
    """Detect A-share ST / *ST / delisting markers without substring false positives (e.g. 'test')."""
    compact = name.strip()
    if not compact:
        return False
    if "退" in compact or "风险警示" in compact:
        return True
    upper = compact.upper().replace(" ", "")
    if upper.startswith(("*ST", "S*ST")):
        return True
    if "*ST" in upper:
        return True
    if upper.startswith("ST") and len(upper) > 2:
        rest = upper[2:]
        if rest[0].isdigit():
            return True
        if any("\u4e00" <= ch <= "\u9fff" for ch in rest[:1]):
            return True
    return False


def floor_lot(quantity: float) -> int:
    return int(floor(quantity / LOT_SIZE) * LOT_SIZE)


def is_after_new_entry_cutoff(now: datetime, cutoff: time = time(14, 30)) -> bool:
    return now.time() >= cutoff


def kill_switch_active(path: str | Path, root: Path | None = None) -> bool:
    p = Path(path)
    if not p.is_absolute() and root is not None:
        p = root / p
    return p.exists()
