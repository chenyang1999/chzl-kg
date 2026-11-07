"""C1 narrow date/bid regression. Run only in an audited scratch snapshot.

Real schema/loader/watcher/wrappers/context/Amygdala/journal; synthetic scan,
settings and last-hop transport from the unchanged I1 fixture. Not live proof.
"""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import importlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_v1_integration_authorization_20261024 import (
    code, reset, direct, buy, sell, plan_dict, serialize, orders, DATE, SYMBOL,
)


def scan_payload(day):
    result = dict(opportunities=[dict(ts_code=SYMBOL, action="buy_breakout", sise_pass=True)])
    if day is not None:
        result["trade_date"] = day
    return result


def receipt(code, q, result):
    rows = code.journal.read_jsonl(q.orders_path)
    raw = ([json.loads(line) for line in q.orders_path.read_text().splitlines() if line.strip()]
           if q.orders_path.exists() else [])
    assert raw == rows
    if isinstance(result, dict) and "at" in result:
        assert rows[-1] == result
    folder = Path(__file__).resolve().parents[2] / "observations"
    folder.mkdir(exist_ok=True)
    case = os.environ["PYTEST_CURRENT_TEST"]
    (folder / (hashlib.sha256(case.encode()).hexdigest() + ".json")).write_text(
        json.dumps(dict(case=case, result=result, journal_readback=raw, transport=orders(code)),
                   ensure_ascii=False, indent=2) + "\n")
    return rows


@pytest.mark.parametrize("scan_date", [DATE, "20990104", None, "", 20990105, False])
@pytest.mark.parametrize("authorized_date", [DATE, None, "", "20990104"])
def test_scan_requires_explicit_nonempty_matching_authorized_date(code, scan_date, authorized_date):
    code.session.set_scan_result(scan_payload(scan_date))
    allowed, reasons = code.session.buy_allowed(
        SYMBOL, entry_style="leader_breakout", trade_date=authorized_date)
    expected = isinstance(authorized_date, str) and bool(authorized_date) and scan_date == authorized_date
    assert allowed is expected
    if not expected:
        assert reasons == ["scan_date_missing_or_mismatch"]
    assert code.state.clients == 0 and not orders(code)


def test_original_call_without_authorized_date_explicitly_refuses(code):
    # The old signature remains callable, but neither dated nor undated scans
    # supply the missing *caller* authorization date on its behalf.
    for day in (DATE, None):
        code.session.set_scan_result(scan_payload(day))
        assert code.session.buy_allowed(SYMBOL, entry_style="leader_breakout") == (
            False, ["scan_date_missing_or_mismatch"])
    assert code.state.clients == 0 and not orders(code)


@pytest.mark.parametrize("mode", ["live", "dry_run"])
@pytest.mark.parametrize("route", ["final", "executor"])
@pytest.mark.parametrize("scan_date", [DATE, "20990104", None])
def test_both_consumers_require_context_date(code, mode, route, scan_date):
    q = direct(code, mode=mode)
    code.session.set_scan_result(scan_payload(scan_date))
    if route == "final":
        result = buy(q)
    else:
        model = code.schema.WatchlistPlan.model_validate(plan_dict())
        entry = model.execution_pool[0].model_dump(mode="json")
        wrapper = importlib.import_module("trading.executors.execute_leader_breakout")
        result = asdict(wrapper.execute(entry, entry["entry_rules"][0], q,
                                       SimpleNamespace(positions={}), simulate=False))
    rows = receipt(code, q, result)
    if scan_date == DATE:
        expected = "submitted" if mode == "live" else "dry_run"
        assert result["status"] == expected and rows[-1]["status"] == expected
        assert len(orders(code)) == int(mode == "live")
        if mode == "live":
            assert orders(code)[0]["quantity"] == 100
            assert rows[-1]["order"]["synthetic_only"] is True
    else:
        assert result["status"] == ("rejected" if route == "final" else "skipped")
        assert result["reason" if route == "final" else "skip_reason"] == "intraday_scan_gate"
        if route == "executor":
            assert "scan_date_missing_or_mismatch" in result["reasons"] and rows == []
        assert code.state.clients == 0 and not orders(code)


@pytest.mark.parametrize("scan_date", [DATE, "20990104", None])
def test_default_loader_dispatch_rejects_old_or_undated_success(code, scan_date):
    serialize(code)
    code.session.set_scan_result(scan_payload(scan_date))
    code.loader.run_load_plan(DATE, mode="live")
    assert code.state.dispatches == 1 and len(code.state.contexts) == 1
    q = code.state.contexts[-1]
    rows = receipt(code, q, {"scan_date": scan_date})
    assert len(orders(code)) == int(scan_date == DATE)
    if scan_date == DATE:
        assert rows[-1]["status"] == "submitted" and rows[-1]["side"] == "buy"
    else:
        assert rows == []


@pytest.mark.parametrize("scan_date", ["20990104", None])
def test_scan_date_gate_does_not_block_legal_bid_sell(code, scan_date):
    q = direct(code)
    q.holdings = {SYMBOL: dict(total_qty=1000, available_qty=1000)}
    q.quotes[SYMBOL].last = q.quotes[SYMBOL].bid = 8.
    code.session.set_scan_result(scan_payload(scan_date))
    result = sell(q, limit_price=8.)
    rows = receipt(code, q, result)
    assert result["status"] == "submitted" and rows[-1]["dry_run"] is False
    assert len(orders(code)) == 1 and orders(code)[0]["limit_price"] == 8.


@pytest.mark.parametrize("limit_price", [.01, 7.99, 8.01])
def test_final_sell_limit_must_equal_existing_valid_bid(code, limit_price):
    q = direct(code)
    q.holdings = {SYMBOL: dict(total_qty=1000, available_qty=1000)}
    q.quotes[SYMBOL].last = q.quotes[SYMBOL].bid = 8.
    result = sell(q, limit_price=limit_price)
    receipt(code, q, result)
    assert result["status"] == "rejected" and result["reason"] == "sell_limit_not_authorized"
    assert code.state.clients == 0 and not orders(code)


def test_watcher_normal_buy_then_scanless_sell_two_rounds_two_dispatches(code):
    serialize(code)
    code.watcher.run_intraday_once(DATE, mode="live", reload=True)
    first = receipt(code, code.state.contexts[-1], {"round": 1})
    assert [(r["side"], r["status"]) for r in first] == [("buy", "submitted")]
    assert orders(code)[0]["quantity"] == 100
    p = plan_dict()
    for key in code.auth.BUY_CAPS:
        p["risk_limits"][key] = 0
    p["execution_pool"][0]["auto_trade_enabled"] = False
    serialize(code, p)
    code.state.holdings = {SYMBOL: dict(ts_code=SYMBOL, total_qty=1000, available_qty=1000,
                                      market_value=8000., cost_price=8.)}
    code.state.last = code.state.bid = 8.
    code.state.scan = False
    code.watcher.run_intraday_once(DATE, mode="live", reload=True)
    rows = receipt(code, code.state.contexts[-1], {"round": 2})
    assert [(r["side"], r["status"]) for r in rows] == [("buy", "submitted"), ("sell", "submitted")]
    assert rows[-1]["quantity"] == 300 and rows[-1]["limit_price"] == 8.
    assert all(r["order"]["synthetic_only"] is True and r["dry_run"] is False for r in rows)
    assert len(code.state.contexts) == code.state.dispatches == 2
    assert [r["side"] for r in orders(code)] == ["buy", "sell"]


def test_watcher_same_day_scans_replace_old_success_two_rounds_two_dispatches(code):
    serialize(code)
    code.session.set_scan_result(scan_payload("20990104"))
    code.loader.run_load_plan(DATE, mode="live", dispatch=False)
    assert code.state.clients == code.state.dispatches == len(code.state.contexts) == 0
    for _ in range(2):
        code.watcher.run_intraday_once(DATE, mode="live", reload=True)
    rows = receipt(code, code.state.contexts[-1], {"rounds": 2})
    assert len(code.state.contexts) == code.state.dispatches == 2
    assert len(orders(code)) == len(rows) == 2
    assert all(r["status"] == "submitted" and r["side"] == "buy" for r in rows)
    assert code.session.buy_allowed(SYMBOL, entry_style="leader_breakout", trade_date=DATE)[0]
