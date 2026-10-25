"""T1 contract closeout: new coverage, never substitutes old case identities.

Only synthetic transports/contexts; run via the audited FINAL scratch runner.
Authorization, trigger, RR, lot sizing and JSONL code remain unmodified.
"""
from __future__ import annotations

from types import SimpleNamespace
import pytest
import test_v1_integration_authorization_20261024 as i1
import test_canghai_rr_scope_20261023 as rr


@pytest.fixture
def boundary_code(tmp_path_factory):
    fixture = i1.code.__wrapped__(tmp_path_factory)
    obj = next(fixture)
    try:
        i1.reset.__wrapped__(obj)
        yield obj
    finally:
        next(fixture, None)


@pytest.fixture
def rr_code(tmp_path_factory, request):
    yield from rr.code.__wrapped__(tmp_path_factory, request)


@pytest.mark.parametrize("mode", ["live", "dry_run"])
@pytest.mark.parametrize("side", ["buy", "sell"])
@pytest.mark.parametrize("book", [10., None, 0, True, float("nan"), float("inf")])
def test_unknown_rule_is_rejected_before_book_even_with_valid_consent(boundary_code, mode, side, book):
    code = boundary_code
    q = i1.direct(code, mode=mode)
    q.holdings = {i1.SYMBOL: dict(total_qty=1000, available_qty=1000, market_value=10000.)}
    setattr(q.quotes[i1.SYMBOL], "ask" if side == "buy" else "bid", book)
    result = q.place_order(ts_code=i1.SYMBOL, side=side, quantity=100, limit_price=10.,
                           rule_type="synthetic_only", reasons=["unknown_rule_must_not_gain_permission"])
    assert result["status"] == "rejected"
    assert result["reason"] == ("buy_rule_not_uniquely_authorized" if side == "buy" else "sell_rule_not_authorized")
    assert code.state.clients == 0 and not i1.orders(code)
    assert code.journal.read_jsonl(q.orders_path) == [result]
    assert not code.journal.read_jsonl(q.decisions_path)


@pytest.mark.parametrize("flags", [{}, {"simulate": True}, {"simulate": True, "force_trigger": True}])
def test_original_100k_five_percent_at_100_is_zero_buy_qty_not_forced_one_lot(rr_code, flags):
    s = rr.stock()
    ctx = rr.FixtureContext([s])  # Keep the ORIGINAL input, not the RR positive fixture's 200k.
    assert ctx.total_asset == ctx.cash == 100000.0 and ctx.holdings == {}
    assert ctx.trade_date == rr.DATE
    assert s["entry_rules"][0]["position_pct"] == .05
    assert s["entry_rules"][0]["max_acceptable_ask"] == ctx.quotes[s["ts_code"]].ask == 100.
    assert rr_code.helper.RR_MIN == 1.8
    assert rr_code.helper.evaluate_stock_buy_eligibility(s, {"ask": 100.}, entry_rule=s["entry_rules"][0])["status"] == "eligible"
    result = rr_code.buy.run_buy_executor(s, s["entry_rules"][0], ctx, SimpleNamespace(positions={}),
                                            expected_type="trend_pullback_buy", **flags)
    assert result.status == "skipped" and result.skip_reason == "zero_buy_qty"
    assert result.quantity == 0
    assert ctx.calls == [] and ctx.events == []  # No order boundary or order event, never a fill.


@pytest.mark.parametrize("mode", ["live", "dry_run"])
@pytest.mark.parametrize("date_field", ["absent", None])
def test_undated_scan_never_inherits_authorized_context_date(boundary_code, mode, date_field):
    code = boundary_code
    q = i1.direct(code, mode=mode)
    payload = dict(opportunities=[dict(ts_code=i1.SYMBOL, action="buy_breakout", sise_pass=True)])
    if date_field != "absent":
        payload["trade_date"] = date_field
    code.session.set_scan_result(payload)  # Deliberately no usable scan date; do NOT repair this fixture.
    result = i1.buy(q)
    assert result["status"] == "rejected" and result["reason"] == "intraday_scan_gate"
    assert code.state.clients == 0 and not i1.orders(code)
    assert code.journal.read_jsonl(q.orders_path) == [result]


def test_loader_missing_scan_date_does_not_default_to_today(boundary_code):
    code = boundary_code
    i1.serialize(code)
    code.session.set_scan_result(dict(opportunities=[dict(ts_code=i1.SYMBOL, action="buy_breakout", sise_pass=True)]))
    code.loader.run_load_plan(i1.DATE, mode="live")
    assert code.state.dispatches == 1
    assert not i1.orders(code)
    assert not code.journal.read_jsonl(code.state.contexts[-1].orders_path)
