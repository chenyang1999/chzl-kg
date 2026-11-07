#!/usr/bin/env python3
"""One offline formal-plan -> independent paper-ledger cycle; never initializes.

Production plans are exactly data/plans/YYYYMMDD/watchlist_plan.json. Quotes,
calendar and optional primary research snapshots are explicit local JSON inputs.
No settings, environment, broker, network, polling loop or persistent schedule.
Missing market data blocks potential actions; it never manufactures an idle/fill.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from decimal import Decimal, ROUND_FLOOR
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from trading.paper import PaperError, PaperLedger
from trading.paper.ledger import SCRATCH, canonical, cents, day, digest, number, require, stamp
from src.plan.buy_eligibility import evaluate_plan_buy_gate, evaluate_stock_buy_eligibility


def decode(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, 'duplicate_json_key:' + key)
            out[key] = value
        return out
    def nonfinite(value):
        raise PaperError('nonfinite_json_number:' + value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def local_path(value, *, fixture=False):
    p = Path(value).expanduser().resolve()
    require(p.suffix == '.json' and p.name != '.env', 'local_json_required')
    require(p.is_relative_to(SCRATCH.resolve()) or
            (not fixture and p.is_relative_to((ROOT / 'data').resolve())), 'input_path_not_allowed')
    return p


def load(value, *, fixture=False):
    p = local_path(value, fixture=fixture)
    raw = p.read_bytes()
    return decode(raw), hashlib.sha256(raw).hexdigest()


def report_path(value):
    p = Path(value).expanduser().resolve()
    allowed = p.is_relative_to(SCRATCH.resolve()) or (
        p.parent == (ROOT / 'data/execution').resolve()
        and re.fullmatch(r'paper_[A-Za-z0-9_-]+\.json', p.name))
    require(allowed and p.suffix == '.json' and p.parent.is_dir(), 'report_path_not_allowed')
    return p


def write_report(path, result):
    # Strict serialization happens before opening any file; rename is atomic.
    payload = canonical(result) + '\n'
    fd, tmp = tempfile.mkstemp(prefix='.paper_', suffix='.json', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def global_reasons(plan, gate):
    reasons = list(gate['reasons'])
    for section in [plan, plan.get('meta', {}), plan.get('risk_limits', {})]:
        require(isinstance(section, dict), 'invalid_risk_section')
        for flag in ['no_new_buys', 'block_new_buys', 'kill_switch_active']:
            if flag in section and section[flag] is not False:
                reasons.append('global_no_new_buy:' + flag)
    if plan.get('portfolio_rebalance', {}).get('max_new_buys_before_trim_done') == 0:
        reasons.append('rebalance_blocks_new_buy')
    return reasons


def readiness_reasons(plan):
    sections = [plan, plan.get('meta', {})]
    reasons = []
    if plan.get('status') != 'ok':
        reasons.append('plan_not_ready')
    if type(plan.get('no_trade')) is not bool:
        reasons.append('explicit_no_trade_flag_required')
    for key in ['production_ready', 'research_completion_passed']:
        if not any(s.get(key) is True for s in sections) or any(key in s and s[key] is not True for s in sections):
            reasons.append('explicit_plan_readiness_required:' + key)
    for s in sections:
        if s.get('reassessment_required', False) is not False or s.get('is_degraded_plan', False) is not False:
            reasons.append('plan_not_ready')
    return reasons


def kill_snapshot(plan, at):
    risk = plan.get('risk_limits', {})
    require(isinstance(risk, dict), 'invalid_risk_section')
    # RiskLimits already defines this default. Raw JSON may omit Pydantic
    # defaults; omission must not bypass the existing emergency-stop file.
    explicit = 'kill_switch_file' in risk
    token = risk.get('kill_switch_file', 'data/runtime/KILL_SWITCH')
    approved = ROOT / 'data/runtime/KILL_SWITCH'
    # Accept only the exact canonical token, not arbitrary paths/URLs/aliases.
    if token not in ['data/runtime/KILL_SWITCH', str(approved)]:
        return {'configured': True, 'observed_at': at.isoformat(), 'status': 'unknown_path'}, ['unknown_kill_switch_path']
    if approved.is_symlink() or approved.parent.resolve() != approved.parent:
        return {'configured': True, 'observed_at': at.isoformat(), 'status': 'unsafe_path'}, ['unsafe_kill_switch_path']
    exists = approved.exists()  # Only exists; contents are deliberately never read.
    # A canonical active flag is never lowered by an absent file.
    risk['kill_switch_active'] = exists or risk.get('kill_switch_active', False) is not False
    return {'configured': True, 'path': str(approved), 'exists': exists,
            'configuration_source': 'canonical' if explicit else 'schema_default',
            'observed_at': at.isoformat(), 'status': 'owner_exists_snapshot'}, []


def order_rows(ledger, account_id):
    with ledger.transaction() as db:
        return {r['order_id']: {'intent': decode(r['intent_json']), 'status': r['status'],
                'result': decode(r['result_json'])} for r in db.execute(
                'SELECT order_id,intent_json,status,result_json FROM orders WHERE account_id=?', (account_id,))}


def select_exit(plan, snap, symbol):
    stock = PaperLedger._stock(plan, symbol, 'sell')
    if stock is not None and stock.get('exit_rules'):
        return stock, 'current_formal_plan'
    saved = snap.get('managed_exit_plans', {}).get(symbol)
    if isinstance(saved, dict) and isinstance(saved.get('stock'), dict):
        return saved['stock'], 'ledger_managed_exit_plan'
    # Older ledgers may not yet expose managed_exit_plans. Do not patch them,
    # migrate inventory or reinterpret pool absence as a liquidation signal.
    raise PaperError('existing_paper_position_exit_source_missing_or_backend_not_ready')


def buy_quantity(plan, stock, rule, snap, quote_map, at, max_age, price):
    values = {}
    for symbol, pos in snap['positions'].items():
        q = PaperLedger._quote(quote_map.get(symbol), symbol, at, max_age)
        require(q['bid'] is not None, 'held_position_valuation_unavailable')
        values[symbol] = q['bid'] * pos['quantity']
    market = sum(values.values())
    equity = snap['cash_cents'] + market
    fee_model = snap['fee_model']
    fee = 0 if fee_model['model'] == 'zero_fee_assumption' else cents(fee_model['buy'], 'buy_fee')
    total = number(plan.get('risk_limits', {}).get('target_total_position_pct'), 'target_total_position_pct', maximum=1)
    for obj, key in [(plan.get('meta', {}), 'position_cap_pct'),
                     (plan.get('position_cap_derivation', {}), 'final_position_cap_pct')]:
        if key in obj:
            total = min(total, number(obj[key], key, maximum=1))
    single = number(stock.get('max_position_pct'), 'max_position_pct', maximum=1)
    allocation = number(rule.get('position_pct'), 'position_pct', maximum=1)
    budget = min(Decimal(snap['cash_cents'] - fee), single * (equity-fee) - values.get(stock['ts_code'], 0),
                 total * (equity-fee) - market, allocation * (equity-fee))
    qty = max(0, int((budget / price / 100).to_integral_value(rounding=ROUND_FLOOR)) * 100)
    require(qty > 0, 'cash_or_position_budget_below_one_lot')
    return qty


def run_once(args):
    ledger = PaperLedger(args.database, fixture=args.fixture)
    at = ledger.clock(args.now)
    result = {'environment': 'paper', 'event': 'paper_blocked', 'status': 'blocked', 'as_of': at.isoformat(),
              'account_id': args.account_id, 'intents': [], 'orders': [], 'fills': [], 'rejections': [], 'observations': [], 'reasons': []}
    date_token = at.strftime('%Y%m%d')
    expected = ROOT / 'data/plans' / date_token / 'watchlist_plan.json'
    plan_path = local_path(args.plan or expected, fixture=args.fixture)
    require(args.fixture or plan_path == expected, 'only_today_canonical_formal_plan_allowed')
    plan, plan_sha = load(plan_path, fixture=args.fixture)
    require(isinstance(plan, dict) and isinstance(plan.get('meta', {}), dict), 'invalid_plan_meta')
    result['canonical_sha256'] = plan_sha
    result['canonical_path'] = str(plan_path)
    plan = deepcopy(plan)
    meta = plan.setdefault('meta', {})
    require(meta.get('paper_trading_authorized') is True or args.paper_trading_authorized,
            'explicit_paper_authorization_required')
    existing_id = meta.get('paper_authorization_id')
    require(existing_id is None or existing_id == args.authorization_id, 'authorization_mismatch')
    result['authorization'] = {'id': args.authorization_id,
        'source': 'canonical' if existing_id is not None and meta.get('paper_trading_authorized') is True else
                  'explicit_cli' if args.paper_trading_authorized else 'canonical_permission_cli_id'}
    meta['paper_authorization_id'] = args.authorization_id
    meta['paper_trading_authorized'] = True
    # Audit-only fields in this in-memory copy, not modifications to canonical.
    meta['paper_driver_provenance'] = {'canonical_sha256': plan_sha, 'authorization_source': result['authorization']['source']}
    snap = ledger.snapshot(args.account_id, now=args.now)
    result['snapshot_before'] = snap
    require(snap['authorization_id'] == args.authorization_id, 'authorization_mismatch')
    ledger._safety(plan, {'authorization_id': snap['authorization_id']}, args.authorization_id, at)
    kill, kill_errors = kill_snapshot(plan, at)
    result['kill_switch_snapshot'] = kill
    # The shared helper owns global gates, not another symbol's conditions.
    # Keep malformed/unknown scopes fail-closed; preserve the actual plan for
    # the backend's per-stock scope validation and evidence.
    gate_view = dict(plan)
    conditions = plan.get('no_trade_conditions', [])
    if isinstance(conditions, list):
        gate_view['no_trade_conditions'] = [c for c in conditions if not (
            isinstance(c, dict) and c.get('scope') in ['stock', 'symbol']
            and isinstance(c.get('ts_code'), str) and re.fullmatch(r'\d{6}\.(SH|SZ|BJ)', c['ts_code'])
            and type(c.get('active')) is bool)]
    gate = evaluate_plan_buy_gate(gate_view)
    result['global_buy_gate'] = gate
    forbidden = global_reasons(plan, gate)
    unready = readiness_reasons(plan)
    pool = plan.get('execution_pool', [])
    require(isinstance(pool, list) and all(isinstance(s, dict) for s in pool), 'invalid_execution_pool')
    orders = order_rows(ledger, args.account_id)
    pending_sells = {oid: row for oid, row in orders.items()
                     if row['status'] in ['pending', 'partial'] and row['intent'].get('side') == 'sell'}
    result['reasons'] += kill_errors + forbidden + unready
    if not pool:
        result['reasons'].append('execution_pool_empty_no_watch_or_B_plan_promotion')
    if not snap['positions'] and not pending_sells and (forbidden or not pool) and not kill_errors:
        result.update(event='paper_idle', status='idle', snapshot_after=snap)
        result['reasons'].append('empty_paper_account_no_potential_action_market_inputs_not_requested')
        return result
    buy_allowed = not (forbidden or unready or kill_errors)
    if not snap['positions'] and not pending_sells and not buy_allowed:
        result['snapshot_after'] = snap
        return result
    missing = [key for key in ['quotes', 'calendar', 'quote_max_age'] if getattr(args, key) is None]
    if missing:
        result['reasons'] += ['required_input_missing:' + key for key in missing]
        result['snapshot_after'] = snap
        return result
    quotes, qsha = load(args.quotes, fixture=args.fixture)
    calendar, csha = load(args.calendar, fixture=args.fixture)
    result['inputs'] = {'quotes_sha256': qsha, 'calendar_sha256': csha}
    max_age = number(args.quote_max_age, 'quote_max_age', minimum=Decimal('.000001'))
    ledger._calendar(calendar, at)
    require(isinstance(quotes, dict) and isinstance(quotes.get('quotes'), list)
            and all(isinstance(q, dict) for q in quotes['quotes']), 'invalid_quotes_bundle')
    quote_map = {q.get('symbol'): q for q in quotes['quotes']}
    require(len(quote_map) == len(quotes['quotes']), 'duplicate_quote_symbol')
    research = {}
    if buy_allowed and pool:
        try:
            for attr, key in [('research_summary', 'research_summary'), ('r6_research', 'r6_research')]:
                if getattr(args, attr, None):
                    obj, sha = load(getattr(args, attr), fixture=args.fixture)
                    research[key] = obj
                    result['inputs'][key + '_sha256'] = sha
            ledger._research_proof(plan, research.get('research_summary', meta.get('research_summary')),
                research.get('r6_research', meta.get('r6_devil_advocate')), at)
        except (PaperError, OSError, ValueError) as exc:
            buy_allowed = False
            result['reasons'].append(str(exc))

    def reject(symbol, side, reason, index=None):
        normal = reason in ['entry_trigger_not_met', 'exit_trigger_not_met',
                            'rule_time_window_not_met', 't_plus_one_or_no_paper_sellable_lot']
        result['observations' if normal else 'rejections'].append(
            {'symbol': symbol, 'side': side, 'rule_index': index, 'reason': reason})

    def submit(intent):
        result['intents'].append(intent)
        outcome = ledger.execute(account_id=args.account_id, authorization_id=args.authorization_id,
            intent=intent, plan=plan, quotes=quotes, calendar=calendar,
            quote_max_age=args.quote_max_age, now=args.now, **research)
        result['orders'].append(outcome)
        if outcome.get('reason'):
            reject(intent['symbol'], intent['side'], outcome['reason'], intent['rule_index'])
        return outcome

    # Explicit pending sells precede all newly generated intents. A changed plan
    # cannot silently reinterpret a pending rule index or limit.
    reserved = set()
    for oid, row in pending_sells.items():
        intent = row['intent']; symbol = intent['symbol']; reserved.add(symbol)
        try:
            q = ledger._quote(quote_map.get(symbol), symbol, at, max_age)
            stock, _ = select_exit(plan, snap, symbol)
            ledger._rule(stock, intent, q, 'sell', at)
            require(row['result'].get('plan_sha256') == digest(plan), 'pending_paper_sell_plan_changed_requires_reassessment')
            if row['result'].get('quote_key') == q['key']:
                result['orders'].append({'order_id': oid, 'event': 'paper_observation_already_processed', 'fill_quantity': 0})
            else:
                # Fractional exits request the full sellable base because the
                # ledger applies pct once. Replaying after any fractional fill
                # would apply that pct to a smaller base a second time. Until
                # the backend exposes an immutable original sell target, do not
                # silently compound that fraction on a new observation.
                rule = ledger._rule(stock, intent, q, 'sell', at)
                require(not (row['status'] == 'partial' and row['result'].get('filled_quantity', 0) > 0
                             and number(rule.get('quantity_pct'), 'quantity_pct', maximum=1) < 1),
                        'fractional_partial_sell_retry_unsupported_requires_reassessment')
                submit(intent)
        except PaperError as exc:
            reject(symbol, 'sell', str(exc), intent.get('rule_index'))

    # Exits are independent of the execution pool and every buy-only veto.
    actions = [('sell', symbol) for symbol in snap['positions'] if symbol not in reserved]
    if buy_allowed:
        actions += [('buy', s.get('ts_code')) for s in pool if s.get('ts_code') not in reserved]
    sold = set(reserved)
    for side, symbol in actions:
        if side == 'buy' and symbol in sold:
            reject(symbol, side, 'same_cycle_sell_has_priority_no_rebuy'); continue
        try:
            snap = ledger.snapshot(args.account_id, now=args.now)
            if side == 'sell':
                if snap['positions'].get(symbol, {}).get('sellable_quantity', 0) < 100:
                    reject(symbol, side, 't_plus_one_or_no_paper_sellable_lot'); continue
                stock, exit_source = select_exit(plan, snap, symbol)
            else:
                stock = ledger._stock(plan, symbol, side)
            require(isinstance(stock, dict), 'plan_stock_missing')
            assert isinstance(stock, dict)
            q = ledger._quote(quote_map.get(symbol), symbol, at, max_age)
            rules = stock.get('entry_rules' if side == 'buy' else 'exit_rules')
            require(isinstance(rules, list) and bool(rules) and all(isinstance(r, dict) for r in rules), 'plan_rules_missing')
            assert isinstance(rules, list)
            indexes = list(range(len(rules)))
            if side == 'sell':
                require(all(type(r.get('priority', 99)) is int for r in rules), 'invalid_exit_priority')
                indexes.sort(key=lambda i: (rules[i].get('priority', 99), i))
            for idx in indexes:
                try:
                    # Normalize observation time in the key; never receipt time.
                    oid = 'paper-plan-' + digest([plan_sha, args.account_id, symbol, side, idx,
                                                  stamp(q['raw']['observed_at'], 'quote.observed_at').isoformat()])
                    if oid in orders:
                        result['orders'].append({'order_id': oid, 'event': 'paper_observation_already_processed', 'fill_quantity': 0})
                        if side == 'sell': sold.add(symbol)
                        break
                    rule = ledger._rule(stock, {'rule_index': idx}, q, side, at)
                    price = q['ask' if side == 'buy' else 'bid']
                    require(price is not None, 'no_counterparty_depth')
                    if side == 'buy':
                        eligibility = evaluate_stock_buy_eligibility(stock, price / 100, entry_rule=rule)
                        require(eligibility['status'] == 'eligible' and eligibility.get('review_required') is False,
                                'stock_buy_ineligible:' + ','.join(eligibility['reasons']))
                        qty = buy_quantity(plan, stock, rule, snap, quote_map, at, max_age, price)
                    else:
                        # Backend applies quantity_pct exactly once to sellable;
                        # pre-multiplying it here would erroneously square it.
                        qty = snap['positions'][symbol]['sellable_quantity'] // 100 * 100
                    intent = {'order_id': oid, 'symbol': symbol, 'side': side, 'quantity': qty,
                              'limit_price': str(Decimal(price) / 100), 'rule_index': idx}
                    submit(intent)
                    orders[oid] = {'intent': intent}
                    if side == 'sell': sold.add(symbol)
                    break  # At most one selected trigger per symbol and side.
                except PaperError as exc:
                    reject(symbol, side, str(exc), idx)
                    # Unsupported predicates at a higher-priority exit are not
                    # bypassed by executing a lower-priority rule.
                    if 'unsupported' in str(exc):
                        break
        except PaperError as exc:
            reject(symbol, side, str(exc))
    after = ledger.snapshot(args.account_id, now=args.now)
    result['snapshot_after'] = after
    before_ids = {f['fill_id'] for f in result['snapshot_before']['fills']}
    result['fills'] = [f for f in after['fills'] if f['fill_id'] not in before_ids]
    if result['fills']:
        result.update(event='paper_filled', status='filled')
    elif result['rejections'] or result['reasons']:
        result.update(event='paper_blocked', status='blocked')
    elif result['orders']:
        result.update(event='paper_no_new_fill', status='no_fill')
    else:
        result.update(event='paper_no_trigger', status='no_fill')
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--once', action='store_true', required=True)
    p.add_argument('--database', required=True)
    p.add_argument('--account-id', required=True)
    p.add_argument('--authorization-id', required=True)
    p.add_argument('--paper-trading-authorized', action='store_true', help='explicit user paper-only permission for this invocation')
    p.add_argument('--fixture', action='store_true', help='scratch synthetic rehearsal only')
    p.add_argument('--now', help='fixture-only timezone-aware clock')
    p.add_argument('--plan', help='default: today canonical; overrides permitted only in scratch fixtures')
    p.add_argument('--quotes')
    p.add_argument('--calendar')
    p.add_argument('--research-summary')
    p.add_argument('--r6-research')
    p.add_argument('--quote-max-age', help='explicit positive observed quote age in seconds; no numeric default')
    p.add_argument('--report', help='optional scratch JSON or data/execution/paper_<id>.json')
    a = p.parse_args(argv)
    out = None
    result = None
    try:
        if a.report:
            out = report_path(a.report)  # Refuse bad output before any ledger execution.
            protected = [a.database, a.plan, a.quotes, a.calendar, a.research_summary, a.r6_research]
            require(all(v is None or out != Path(v).expanduser().resolve() for v in protected), 'report_cannot_replace_input_or_ledger')
        result = run_once(a)
        if out:
            write_report(out, result)
        print(canonical(result))
        return 2 if result['status'] == 'blocked' else 0
    except (PaperError, OSError, ValueError, TypeError, KeyError, sqlite3.Error) as exc:
        if result is not None:
            # A report-write failure cannot undo or conceal committed fills.
            result['report_error'] = str(exc)
        else:
            result = {'environment': 'paper', 'status': 'blocked', 'event': 'paper_blocked',
                      'reason': str(exc), 'fills': [], 'orders': [], 'intents': []}
        print(canonical(result))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
