"""F1 supplementary boundary evidence; does NOT replace S3's original cases.
Uses I1's reviewed synthetic settings/transport with REAL final policy/journal.
Run only via FINAL/run_parent_verification.py in a fresh scratch snapshot.
"""
from __future__ import annotations
import pytest
from test_v1_integration_authorization_20261024 import (
    code, reset, direct, buy, sell, plan_dict, serialize, orders, DATE, SYMBOL,
)


@pytest.mark.parametrize('side',['buy','sell'])
@pytest.mark.parametrize('invalid',[None,0,True,float('nan'),float('inf')])
def test_authorized_known_rule_still_rejects_invalid_book(code,side,invalid):
    q=direct(code,mode='dry_run')
    q.holdings={SYMBOL:dict(total_qty=1000,available_qty=1000,market_value=10000.)}
    setattr(q.quotes[SYMBOL],'ask' if side=='buy' else 'bid',invalid)
    result=buy(q) if side=='buy' else sell(q)
    assert result['status']=='rejected'
    # Authorization rechecks buy trigger first; no relaxation of either gate.
    assert result['reason']==('buy_trigger_not_met' if side=='buy' else 'missing_or_invalid_executable_quote')
    assert code.state.clients==0 and not orders(code)
    persisted=code.journal.read_jsonl(q.orders_path)
    assert len(persisted)==1 and persisted[0]['status']=='rejected'
    assert persisted[0]['side']==side


def test_authorized_positive_buy_and_independent_legal_exit_persist(code):
    # A real schema -> handoff -> loader -> watcher -> dispatcher -> executor ->
    # final QMTContext -> last-hop SYNTHETIC transport -> actual JSONL read-back.
    serialize(code)
    code.watcher.run_intraday_once(DATE,mode='live',reload=True)
    q=code.state.contexts[-1]
    first=code.journal.read_jsonl(q.orders_path)
    assert len(first)==1 and first[0]['side']=='buy' and first[0]['status']=='submitted'
    assert first[0]['order']['synthetic_only'] is True
    assert orders(code)[0]['quantity']==100
    # Separately supplied fixture holding is NOT inferred to be a broker fill.
    p=plan_dict()
    for key in code.auth.BUY_CAPS:p['risk_limits'][key]=0
    p['execution_pool'][0]['auto_trade_enabled']=False
    serialize(code,p)
    code.state.holdings={SYMBOL:dict(ts_code=SYMBOL,total_qty=1000,available_qty=1000,
                                  market_value=8000.,cost_price=8.)}
    code.state.last=code.state.bid=8.;code.state.scan=False
    code.watcher.run_intraday_once(DATE,mode='live',reload=True)
    last=code.journal.read_jsonl(code.state.contexts[-1].orders_path)
    assert [(r['side'],r['status']) for r in last]==[('buy','submitted'),('sell','submitted')]
    # The existing position-state contract preserves a 70% base and exposes
    # the 30% mobile tranche here; do not mistake this order for a full exit.
    assert last[-1]['quantity']==300 and last[-1]['limit_price']==8.
    assert all(r['order']['synthetic_only'] is True for r in last)
    assert [r['side'] for r in orders(code)]==['buy','sell']
    assert code.state.dispatches==2
