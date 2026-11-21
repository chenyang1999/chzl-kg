from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from src.settings import ROOT


DEFAULT_CONFIG_PATH = ROOT / "config" / "trading_account.yaml"


@dataclass(frozen=True)
class AccountConfig:
    mode: str
    autonomous_trading_enabled: bool
    requires_user_confirmation: bool
    risk_limits: dict[str, Any]
    default_base_mobile_ratio: float
    daban_max_symbols_per_day: int
    daban_default_sealed_bid_threshold: float


def load_account_config(path: Path | None = None) -> AccountConfig:
    cfg_path = path or DEFAULT_CONFIG_PATH
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    risk = dict(raw.get("risk_limits") or {})
    positions = raw.get("positions") or {}
    daban = raw.get("daban") or {}
    return AccountConfig(
        mode=str(raw.get("mode", "dry_run")),
        autonomous_trading_enabled=bool(raw.get("autonomous_trading_enabled", False)),
        requires_user_confirmation=bool(raw.get("requires_user_confirmation", False)),
        risk_limits=risk,
        default_base_mobile_ratio=float(positions.get("default_base_mobile_ratio", 0.7)),
        daban_max_symbols_per_day=int(daban.get("max_symbols_per_day", 2)),
        daban_default_sealed_bid_threshold=float(daban.get("default_sealed_bid_threshold", 50000)),
    )
