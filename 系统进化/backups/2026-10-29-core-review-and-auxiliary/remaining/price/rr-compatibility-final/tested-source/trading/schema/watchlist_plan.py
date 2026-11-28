from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


EntryRuleType = Literal[
    "trend_pullback_buy",
    "leader_breakout",
    "daban_confirm",
    "low_absorption_intraday",
    "t_add_pullback",
]

ExitRuleType = Literal[
    "exit_at_open",
    "exit_if_no_new_high",
    "t_reduce_resistance",
    "stop_loss_break",
    "take_profit_hit",
    "sector_switch_exit",
    "intraday_break_exit",
    "volume_price_divergence",
]

PlanStatus = Literal[
    "execution_pool_hold",
    "execution_pool_hold_add_on_pullback",
    "execution_pool_hold_partial_take",
    "execution_pool_exit_at_open",
    "execution_pool_exit_if_no_new_high",
    "watch_pool_wait_for_entry",
    "watch_pool_only",
    "agent_candidate_pool",
]

StockRole = Literal[
    "leader",
    "core_midcap",
    "core_largecap",
    "elastic_core",
    "watch_elastic",
    "watch",
    "exit",
    "exit_if_no_break",
]


class EntryRule(BaseModel):
    type: str
    trigger_price: Optional[float] = None
    max_premium_pct: float = 0.0
    position_pct: float = 0.0
    entry_target_price: Optional[float] = None
    confirm_price: Optional[float] = None
    max_acceptable_ask: Optional[float] = None
    execution_logic: Optional[str] = None
    derivation_reason: Optional[str] = None
    buy_zone: Optional[list[float]] = None
    pullback_zone: Optional[list[float]] = None
    reclaim_price: Optional[float] = None
    time_window: Optional[str] = None
    sealed_bid_threshold: Optional[float] = None
    max_break_count_today: Optional[int] = None
    only_first_seal: Optional[bool] = None
    t_round_limit: Optional[int] = None

    model_config = {"extra": "allow"}


class ExitRule(BaseModel):
    type: str
    trigger_price: Optional[float] = None
    quantity_pct: float = 1.0
    trigger_condition: Optional[str] = None
    priority: int = 99
    time_window: Optional[str] = None
    reason: Optional[str] = None
    t_round_limit: Optional[int] = None

    model_config = {"extra": "allow"}


class StockEntry(BaseModel):
    ts_code: str
    name: str
    theme: str = "unknown"
    role: str = "watch"
    score: int = Field(ge=0, le=100)
    plan_status: Optional[str] = None
    auto_trade_enabled: bool = False
    requires_user_confirmation: bool = False
    max_position_pct: float = Field(default=0.1, ge=0, le=1)
    is_st: bool = False
    reason: str = ""
    stop_loss: float = 0.0
    take_profit: Optional[float] = None
    trigger_price: dict[str, Any] = Field(default_factory=dict)
    entry_rules: list[EntryRule] = Field(default_factory=list)
    exit_rules: list[ExitRule] = Field(default_factory=list)
    sise_red_count: int = 0
    sise_note: str = ""
    base_mobile_ratio: Optional[float] = Field(default=None, ge=0.5, le=1.0)
    alpha_logic: list[str] = Field(default_factory=list)

    model_config = {"extra": "allow"}


class RiskLimits(BaseModel):
    target_total_position_pct: float = 0.75
    max_positions: int = 5
    max_buy_orders_per_day: int = 4
    max_orders_per_symbol_per_day: int = 2
    block_prefixes: list[str] = Field(default_factory=list)
    block_st: bool = True
    kill_switch_file: str = "data/runtime/KILL_SWITCH"
    account_hard_stop_loss_pct: Optional[float] = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="before")
    @classmethod
    def validate_execution_risk(cls, value: Any) -> dict[str, Any]:
        # Check raw input before Pydantic can coerce strings/bools into budgets.
        # The pure execution helper owns the contract; preserve explicit keys
        # so schema defaults do not become model_fields_set spending consent.
        from trading.execution_authorization import validate_risk_limits

        return validate_risk_limits(value)


class WatchlistPlan(BaseModel):
    schema_version: str = "1.0"
    trade_date: str
    mode: Literal["live", "dry_run"] = "dry_run"
    agent_name: str = (
        "盘前预案 Agent / Stock Selection & Setup Agent / Alpha-Setup Agent"
    )
    generated_at: str = ""
    generated_by: Optional[str] = None
    status: Optional[Literal["ok", "stub", "degraded"]] = "ok"
    status_note: Optional[str] = None
    trading_style: str = "mainline_right_side_with_trend_pullback"
    autonomous_trading_enabled: bool = False
    requires_user_confirmation: bool = False
    data_sources: dict[str, Any] = Field(default_factory=dict)
    market_context: dict[str, Any] = Field(default_factory=dict)
    risk_limits: RiskLimits = Field(default_factory=RiskLimits)
    portfolio_rebalance: dict[str, Any] = Field(default_factory=dict)
    sector_core_watchlist: list[dict[str, Any]] = Field(default_factory=list)
    execution_pool: list[StockEntry] = Field(default_factory=list)
    watch_pool: list[StockEntry] = Field(default_factory=list)
    rejected: list[dict[str, Any]] = Field(default_factory=list)
    research_anchor_only: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"extra": "allow"}

    @field_validator("trade_date")
    @classmethod
    def validate_trade_date(cls, value: str) -> str:
        compact = value.replace("-", "")
        if len(compact) != 8 or not compact.isdigit():
            raise ValueError(f"trade_date must be YYYYMMDD, got {value!r}")
        return compact

    def model_dump_plan(self) -> dict[str, Any]:
        return self.model_dump(mode="json", exclude_none=False)
