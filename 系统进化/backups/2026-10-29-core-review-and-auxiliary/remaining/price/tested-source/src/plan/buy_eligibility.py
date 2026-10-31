"""Pure buy-only RR qualification; eligibility is NOT trading authorization.

No settings, files, quotes retrieval, account, or broker dependencies. Consumers
must additionally enforce pool promotion, global gates, budgets and permission.
Never apply these functions to liquidation/sell decisions.
"""
from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from math import isfinite
from numbers import Real
import re
from typing import Any

ENGINE_SOURCE = "price_levels_engine"
RR_MIN = 1.8  # Same default as price_levels.derive; not the 1/2/3 sizing tiers.


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, Real):
        return None
    try:
        value = float(value)
        return value if isfinite(value) else None
    except (OverflowError, ValueError, TypeError):
        return None


def _positive(value: Any) -> float | None:
    value = _number(value)
    return value if value is not None and value > 0 else None


def is_engine_rr_condition(condition: Any) -> bool:
    """Only this exact provenance+code is owned by the price engine."""
    return (isinstance(condition, Mapping)
            and condition.get("source") == ENGINE_SOURCE
            and condition.get("code") == "RR_FAIL")


def _rule_buy(rule: Mapping) -> float | None:
    zone = rule.get("buy_zone")
    if zone is not None:
        if not isinstance(zone, (list, tuple)) or len(zone) != 2:
            return None
        low, high = (_positive(v) for v in zone)
        return high if low is not None and high is not None and low <= high else None
    for key in ("entry_target_price", "trigger_price"):
        if rule.get(key) is not None:
            return _positive(rule[key])
    return None


def _exit_price(stock: Mapping, key: str, rule_type: str) -> Any:
    # An explicit invalid value must not silently fall back to another source.
    if key in stock:
        return stock[key]
    prices = [r.get("trigger_price") for r in stock.get("exit_rules", [])
              if isinstance(r, Mapping) and r.get("type") == rule_type]
    return prices[0] if len(prices) == 1 else None


def evaluate_stock_buy_eligibility(
    stock: Mapping,
    quote_or_buy_price: Any = None,
    *,
    entry_rule: Mapping | None = None,
) -> dict[str, Any]:
    """Evaluate exact stock/rule and proposed buy price, fail closed on unknown.

    quote_or_buy_price: positive finite number, mapping with ask, or object.ask.
    A provided quote NEVER falls back to last. With no quote use the planned
    buy-zone upper edge. Pin entry_rule when more than one entry exists.
    Engine and original D1 prices remain separate; lawful D1 adjustments use
    their own stop/take and the actual proposed buy price, never cached engine RR.
    Differences are audit evidence, not a zero-deviation permission threshold.
    Review is required for unknown provenance, conflicting original evidence,
    explicit owner review, or >10% buy deviation without derivation_reason.
    """
    out: dict[str, Any] = dict(source=ENGINE_SOURCE, scope="stock_buy_only", ts_code=stock.get("ts_code"),
               status="unknown", reasons=[], rr_min=RR_MIN, risk_reward_ratio=None,
               buy_price=None, stop_loss=None, take_profit=None,
               price_source=None, review_required=False, review_reasons=[])

    def require_review(reason: str) -> None:
        out["review_required"] = True
        if reason not in out["review_reasons"]:
            out["review_reasons"].append(reason)

    def finish(status: str, reason: str) -> dict[str, Any]:
        out["status"] = status
        out["reasons"].append(reason)
        return out

    previous = stock.get("buy_eligibility")
    engine_cache = isinstance(previous, Mapping) and previous.get("source") == ENGINE_SOURCE
    if isinstance(previous, Mapping) and previous.get("source") == ENGINE_SOURCE:
        previous = previous.get("external_qualification")
    if stock.get("review_required") is True:
        require_review("EXPLICIT_STOCK_REVIEW_REQUIRED")
    if isinstance(previous, Mapping):
        out["external_qualification"] = dict(previous)
        if previous.get("source") != ENGINE_SOURCE and previous.get("review_required") is True:
            require_review("EXTERNAL_QUALIFICATION_REVIEW_REQUIRED")
    if isinstance(previous, Mapping) and previous.get("source") != ENGINE_SOURCE:
        if previous.get("status") != "eligible":
            return finish("blocked" if previous.get("status") == "blocked" else "unknown",
                          "EXTERNAL_BUY_ELIGIBILITY")
    for c in stock.get("no_trade_conditions") or []:
        if not is_engine_rr_condition(c) and isinstance(c, Mapping) and c.get("active") is not False:
            return finish("blocked", "STOCK_NO_TRADE_CONDITION")
    levels = stock.get("engine_levels")
    if engine_cache and levels is None:
        return finish("unknown", "ENGINE_EVIDENCE_MISSING")
    if levels is not None and (not isinstance(levels, Mapping) or levels.get("ok") is not True):
        return finish("unknown", "ENGINE_LEVELS_UNVERIFIED")
    if entry_rule is None:
        rules = [r for r in stock.get("entry_rules", []) if isinstance(r, Mapping)]
        if len(rules) > 1:
            return finish("unknown", "ENTRY_RULE_REQUIRES_SELECTION")
        entry_rule = rules[0] if rules else stock
    planned_buy = _rule_buy(entry_rule)
    if planned_buy is None:
        return finish("unknown", "MISSING_OR_INVALID_PLANNED_BUY_PRICE")
    if entry_rule.get("review_required") is True:
        require_review("EXPLICIT_ENTRY_REVIEW_REQUIRED")
    price_src = entry_rule.get("price_src", stock.get("price_src"))
    # Missing price_src on original plan fields is the legacy D1 contract;
    # an explicit unfamiliar/backfill source is not verified D1 evidence.
    if price_src not in (None, "D1", "d1", "engine"):
        require_review("UNKNOWN_PRICE_PROVENANCE")
    engine_price = price_src == "engine"
    out["price_source"] = ("engine" if engine_price else
                           "D1" if price_src in (None, "D1", "d1") else "unknown")
    if engine_price:
        if not isinstance(levels, Mapping) or planned_buy != _rule_buy(levels):
            return finish("unknown", "ENGINE_PRICE_PROVENANCE_MISMATCH")
        stop, take = levels.get("stop_loss"), levels.get("take_profit")
        # Generated entry prices do not replace original, sourced exit risk.
        has_exit = any(isinstance(r, Mapping) and r.get("type") in
                       ("stop_loss_break", "take_profit_hit") for r in stock.get("exit_rules", []))
        if "stop_loss" in stock or "take_profit" in stock or has_exit:
            stop = _exit_price(stock, "stop_loss", "stop_loss_break")
            take = _exit_price(stock, "take_profit", "take_profit_hit")
            out["risk_price_source"] = "D1_exits"
    else:
        stop = _exit_price(stock, "stop_loss", "stop_loss_break")
        take = _exit_price(stock, "take_profit", "take_profit_hit")
    # Conflicting evidence means disagreement within the actual D1 exit
    # contract, not simply a lawful difference from the engine baseline.
    for rule_type, selected in (("stop_loss_break", stop), ("take_profit_hit", take)):
        for rule in stock.get("exit_rules", []):
            if not isinstance(rule, Mapping) or rule.get("type") != rule_type:
                continue
            if rule.get("review_required") is True:
                require_review("EXPLICIT_EXIT_REVIEW_REQUIRED")
            if rule.get("price_src") not in (None, "D1", "d1", "engine"):
                require_review("UNKNOWN_EXIT_PRICE_PROVENANCE")
            if rule.get("trigger_price") != selected:
                require_review("CONFLICTING_EXIT_PRICE_EVIDENCE")
    if isinstance(levels, Mapping):
        engine_buy = _rule_buy(levels)
        comparison: dict[str, Any] = {
            "selected": {"buy_zone": entry_rule.get("buy_zone"), "buy_price": planned_buy,
                         "stop_loss": stop, "take_profit": take},
            "engine": {"buy_zone": levels.get("buy_zone"), "buy_price": engine_buy,
                       "stop_loss": levels.get("stop_loss"), "take_profit": levels.get("take_profit")},
        }
        comparison["differs"] = (
            planned_buy != engine_buy or stop != levels.get("stop_loss")
            or take != levels.get("take_profit")
            or (entry_rule.get("buy_zone") is not None
                and entry_rule.get("buy_zone") != levels.get("buy_zone")))
        if engine_buy is not None:
            comparison["buy_high_deviation_pct"] = round((planned_buy / engine_buy - 1) * 100, 1)
            # Existing >10% buy-high comparison, not an invented zero/tolerance
            # gate. Decimal keeps exactly 10% on the permitted boundary.
            d1_value, engine_value = Decimal(str(planned_buy)), Decimal(str(engine_buy))
            exceeds = d1_value < engine_value * Decimal("0.90") or d1_value > engine_value * Decimal("1.10")
            reason = entry_rule.get("derivation_reason") or stock.get("derivation_reason")
            if not engine_price and exceeds and not (isinstance(reason, str) and reason.strip()):
                require_review("D1_BUY_DEVIATION_REQUIRES_DERIVATION_REASON")
        out["price_comparison"] = comparison
    if quote_or_buy_price is None:
        buy = planned_buy
    elif isinstance(quote_or_buy_price, Mapping):
        buy = _positive(quote_or_buy_price.get("ask"))
    elif isinstance(quote_or_buy_price, Real):
        buy = _positive(quote_or_buy_price)
    else:
        buy = _positive(getattr(quote_or_buy_price, "ask", None))
    stop, take = _positive(stop), _positive(take)
    out.update(buy_price=buy, stop_loss=stop, take_profit=take)
    if buy is None or stop is None or take is None:
        return finish("unknown", "MISSING_OR_INVALID_RR_PRICES")
    if stop >= buy or take <= buy:
        return finish("blocked", "INVALID_RISK_REWARD_PRICE_ORDER")
    # Preserve the deterministic engine's rounding and formula boundaries.
    risk = round(buy - stop, 2)
    if risk <= 0:
        return finish("unknown", "INVALID_ROUNDED_RISK")
    rr = round((take - buy) / risk, 2)
    if not isfinite(rr):
        return finish("unknown", "NONFINITE_RISK_REWARD")
    out["risk_reward_ratio"] = rr
    if rr < RR_MIN:
        return finish("blocked", "RR_FAIL")
    if out["review_required"]:
        return finish("unknown", "D1_ENGINE_PRICE_REVIEW_REQUIRED")
    return finish("eligible", "RR_PASS_NOT_TRADE_AUTHORIZATION")


def evaluate_plan_buy_gate(plan: Mapping, *, ts_code: str | None = None) -> dict[str, Any]:
    """Independent global buy gate; preserve real blockers and explicit zero caps.

    Raw legacy engine RR_FAIL is NOT ignored here: only enrichment, which has
    actually recomputed every stock, may migrate that owned condition.
    """
    reasons: list[str] = []
    if plan.get("no_trade") is not None and plan.get("no_trade") is not False:
        reasons.append("NO_TRADE")
    if plan.get("decision_status") == "no_trade":
        reasons.append("DECISION_NO_TRADE")
    conditions = plan.get("no_trade_conditions", [])
    if not isinstance(conditions, list):
        reasons.append("INVALID_NO_TRADE_CONDITIONS")
    else:
        for condition in conditions:
            if not isinstance(condition, Mapping):
                reasons.append("ACTIVE_NO_TRADE_CONDITION")
                continue
            scope = condition.get("scope", "global")
            if scope in ("stock", "symbol"):
                target = condition.get("ts_code")
                if not isinstance(target, str) or not re.fullmatch(r"\d{6}\.(?:SH|SZ|BJ)", target):
                    reasons.append("INVALID_STOCK_NO_TRADE_CONDITION")
                elif condition.get("active") is not False and target == ts_code:
                    reasons.append("ACTIVE_STOCK_NO_TRADE_CONDITION")
            elif scope != "global":
                reasons.append("INVALID_NO_TRADE_SCOPE")
            elif condition.get("active") is not False:
                reasons.append("ACTIVE_NO_TRADE_CONDITION")
    for container, key in ((plan.get("risk_limits", {}), "target_total_position_pct"),
                           (plan.get("meta", {}), "position_cap_pct"),
                           (plan.get("position_cap_derivation", {}), "final_position_cap_pct")):
        if isinstance(container, Mapping) and key in container:
            value = _number(container[key])
            if value is None or value <= 0:
                reasons.append("ZERO_OR_INVALID_POSITION_BUDGET")
    return {"status": "blocked" if reasons else "eligible", "scope": "global_buy_only",
            "reasons": reasons}
