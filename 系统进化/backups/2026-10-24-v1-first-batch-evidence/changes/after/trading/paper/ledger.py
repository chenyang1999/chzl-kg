"""Small, fail-closed SQLite paper exchange; all money is integer CNY cents.

Only ordinary SH/SZ main-board common shares (100-share lots, CNY .01 tick)
are supported. Caller supplies local quotes/calendar; a `reliable` marker is
an input assertion, not independent verification of the provider. No live route
exists. Pending orders are explicit re-attempts, never background submissions.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from copy import deepcopy
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from pathlib import Path
from trading.paper.safety import kill_snapshot

CST = timezone(timedelta(hours=8))
SCRATCH = Path('/Users/chenyang/.hermes/cache/scratch')
ROOT = Path(__file__).resolve().parents[2]


class PaperError(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise PaperError(reason)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def text(value, label):
    require(isinstance(value, str) and bool(value.strip()), f'missing_or_invalid:{label}')
    return value


def number(value, label, *, minimum: int | Decimal = 0, maximum=None):
    require(type(value) in (int, float, str, Decimal), f'invalid_number:{label}')
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise PaperError(f'invalid_number:{label}') from exc
    require(result.is_finite() and result >= minimum, f'invalid_number:{label}')
    require(maximum is None or result <= maximum, f'invalid_number:{label}')
    return result


def cents(value, label, *, positive=False) -> int:
    amount = number(value, label)
    require(amount * 100 == (amount * 100).to_integral_value(), f'invalid_tick:{label}')
    require(not positive or amount > 0, f'invalid_price:{label}')
    return int(amount * 100)


def integer(value, label, *, minimum=0) -> int:
    require(type(value) is int and value >= minimum, f'invalid_integer:{label}')
    return value


def stamp(value, label):
    text(value, label)
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise PaperError(f'invalid_timestamp:{label}') from exc
    require(result.tzinfo is not None and result.utcoffset() is not None, f'timezone_required:{label}')
    return result.astimezone(CST)


def day(value):
    text(value, 'trade_date')
    require(bool(re.fullmatch(r'\d{8}|\d{4}-\d{2}-\d{2}', value)), 'invalid_trade_date')
    try:
        return (datetime.strptime(value, '%Y%m%d').date() if len(value) == 8 else date.fromisoformat(value)).isoformat()
    except ValueError as exc:
        raise PaperError('invalid_trade_date') from exc


def symbol_ok(symbol):
    require(isinstance(symbol, str) and bool(re.fullmatch(r'(?:60[0135]\d{3}\.SH|00[0-3]\d{3}\.SZ)', symbol)),
            'unsupported_symbol:only_ordinary_SH_SZ_main_board')


def safe_database_path(path, *, fixture):
    path = Path(path).expanduser().resolve()
    # A relocated checkout is still application-owned, not a fixture directory.
    in_scratch = path.is_relative_to(SCRATCH.resolve()) and not path.is_relative_to(ROOT.resolve())
    in_execution = path.parent == (ROOT / 'data' / 'execution').resolve() and bool(re.fullmatch(r'paper_[A-Za-z0-9_-]+\.sqlite3', path.name))
    require(in_scratch or (not fixture and in_execution), 'paper_database_path_not_allowed')
    require(not fixture or in_scratch, 'fixture_database_must_be_in_scratch')
    return path


SCHEMA = '''
CREATE TABLE IF NOT EXISTS accounts (
 account_id TEXT PRIMARY KEY, cash INTEGER NOT NULL CHECK(cash>=0), initial_cash INTEGER NOT NULL,
 fees INTEGER NOT NULL DEFAULT 0, authorization_id TEXT NOT NULL, seed_source TEXT NOT NULL,
 created_at TEXT NOT NULL, last_at TEXT NOT NULL, time_source TEXT NOT NULL, fee_model TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS lots (
 lot_id INTEGER PRIMARY KEY, account_id TEXT NOT NULL REFERENCES accounts(account_id),
 symbol TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity>=0), price INTEGER NOT NULL,
 buy_date TEXT NOT NULL, sellable_on TEXT NOT NULL, buy_fee INTEGER NOT NULL, order_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS orders (
 account_id TEXT NOT NULL REFERENCES accounts(account_id), order_id TEXT NOT NULL,
 intent_hash TEXT NOT NULL, intent_json TEXT NOT NULL, status TEXT NOT NULL,
 filled_qty INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, last_at TEXT NOT NULL,
 result_json TEXT NOT NULL, PRIMARY KEY(account_id,order_id));
CREATE TABLE IF NOT EXISTS fills (
 fill_id INTEGER PRIMARY KEY, account_id TEXT NOT NULL, order_id TEXT NOT NULL, symbol TEXT NOT NULL,
 side TEXT NOT NULL, quantity INTEGER NOT NULL, price INTEGER NOT NULL, fee INTEGER NOT NULL,
 quote_key TEXT NOT NULL, at TEXT NOT NULL, trade_date TEXT NOT NULL, evidence_json TEXT NOT NULL,
 FOREIGN KEY(account_id,order_id) REFERENCES orders(account_id,order_id));
CREATE TABLE IF NOT EXISTS liquidity (
 quote_key TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, buy_used INTEGER NOT NULL DEFAULT 0,
 sell_used INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS exit_plans (
 account_id TEXT NOT NULL REFERENCES accounts(account_id), symbol TEXT NOT NULL,
 source_json TEXT NOT NULL, PRIMARY KEY(account_id,symbol));
'''


class PaperLedger:
    def __init__(self, path, *, fixture=False):
        self.path = safe_database_path(path, fixture=fixture)
        self.fixture = fixture

    def clock(self, now=None):
        require(now is None or self.fixture, 'historical_clock_forbidden_outside_fixture')
        require(not self.fixture or now is not None, 'fixture_requires_explicit_now')
        return stamp(now, 'now') if now is not None else datetime.now(CST)

    @contextmanager
    def transaction(self, *, create=False):
        require(create or self.path.is_file(), 'paper_uninitialized')
        require(self.path.parent.is_dir(), 'paper_database_parent_missing')
        db = sqlite3.connect(str(self.path) if create else self.path.as_uri() + '?mode=rw',
                             uri=not create, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA synchronous=FULL')
        try:
            if create:
                db.executescript(SCHEMA)
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.execute('COMMIT')
        except BaseException:
            if db.in_transaction:
                db.execute('ROLLBACK')
            raise
        finally:
            db.close()

    def initialize(self, *, account_id, init_cash, authorization_id, seed_source, fee_model, now=None):
        at = self.clock(now).isoformat()
        for key, value in [('account_id', account_id), ('authorization_id', authorization_id), ('seed_source', seed_source)]:
            text(value, key)
        cash = cents(init_cash, 'init_cash', positive=True)
        require(isinstance(fee_model, dict), 'explicit_fee_model_required')
        if fee_model.get('model') == 'zero_fee_assumption':
            require(set(fee_model) == {'model'}, 'invalid_zero_fee_model')
        else:
            require(fee_model.get('model') == 'flat_per_fill' and set(fee_model) == {'model', 'buy', 'sell'}, 'unsupported_fee_model')
            cents(fee_model['buy'], 'buy_fee')
            cents(fee_model['sell'], 'sell_fee')
        with self.transaction(create=True) as db:
            require(db.execute('SELECT 1 FROM accounts WHERE account_id=?', (account_id,)).fetchone() is None, 'account_already_initialized')
            db.execute('INSERT INTO accounts(account_id,cash,initial_cash,authorization_id,seed_source,created_at,last_at,time_source,fee_model) VALUES(?,?,?,?,?,?,?,?,?)',
                       (account_id, cash, cash, authorization_id, seed_source, at, at, 'fixture' if self.fixture else 'system', canonical(fee_model)))
        return self.snapshot(account_id, now=now)

    def _account(self, db, account_id, at, authorization_id=None):
        text(account_id, 'account_id')
        account = db.execute('SELECT * FROM accounts WHERE account_id=?', (account_id,)).fetchone()
        require(account is not None, 'paper_uninitialized')
        require(account['time_source'] == ('fixture' if self.fixture else 'system'), 'ledger_time_source_mismatch')
        require(at >= stamp(account['last_at'], 'ledger.last_at'), 'clock_rollback_forbidden')
        if authorization_id is not None:
            require(account['authorization_id'] == text(authorization_id, 'authorization_id'), 'authorization_mismatch')
        return account

    @staticmethod
    def _calendar(calendar, at):
        require(isinstance(calendar, dict) and calendar.get('reliable') is True, 'reliable_calendar_required')
        text(calendar.get('source'), 'calendar.source')
        require(stamp(calendar.get('published_at'), 'calendar.published_at') <= at, 'future_calendar')
        start, end = day(calendar.get('coverage_start')), day(calendar.get('coverage_end'))
        require(start <= at.date().isoformat() <= end, 'calendar_out_of_coverage')
        days = calendar.get('trading_days')
        require(isinstance(days, list) and bool(days), 'invalid_calendar_days')
        assert isinstance(days, list)
        days = [day(item) for item in days]
        require(days == sorted(set(days)) and all(start <= d <= end for d in days), 'invalid_calendar_days')
        require(at.date().isoformat() in days, 'not_a_trading_day')
        require(time(9, 30) <= at.time() < time(11, 30) or time(13) <= at.time() < time(14, 57),
                'outside_supported_continuous_session')
        return days

    @staticmethod
    def _quote(raw, symbol, at, max_age):
        require(isinstance(raw, dict) and raw.get('symbol') == symbol, 'quote_missing_or_symbol_mismatch')
        symbol_ok(symbol)
        require(raw.get('board') == 'main' and raw.get('security_type') == 'common_stock' and raw.get('is_st') is False,
                'unsupported_security')
        require(raw.get('quantity_unit') == 'shares' and type(raw.get('lot_size')) is int and raw['lot_size'] == 100,
                'unsupported_quantity_unit')
        require(number(raw.get('tick_size'), 'tick_size') == Decimal('.01'), 'unsupported_price_tick')
        text(raw.get('source'), 'quote.source')
        require(day(raw.get('trade_date')) == at.date().isoformat(), 'quote_trade_date_mismatch')
        observed = stamp(raw.get('observed_at'), 'quote.observed_at')
        received = stamp(raw.get('received_at'), 'quote.received_at')
        require(observed <= received <= at, 'future_or_inverted_quote_time')
        require(observed.date() == at.date(), 'quote_observation_date_mismatch')
        require(Decimal(str((at - observed).total_seconds())) <= max_age, 'stale_quote')
        require(time(9, 30) <= observed.time() < time(11, 30) or time(13) <= observed.time() < time(14, 57),
                'quote_outside_supported_session')
        for flag in ['suspended', 'at_upper_limit', 'at_lower_limit']:
            require(type(raw.get(flag)) is bool, f'explicit_quote_flag_required:{flag}')
        require(not raw['suspended'], 'suspended')
        lo, hi = cents(raw.get('lower_limit'), 'lower_limit', positive=True), cents(raw.get('upper_limit'), 'upper_limit', positive=True)
        last = cents(raw.get('last_price'), 'last_price', positive=True)
        require(lo < hi and lo <= last <= hi, 'invalid_price_limits')
        require(raw['at_upper_limit'] == (last == hi) and raw['at_lower_limit'] == (last == lo), 'inconsistent_limit_flags')
        out = {'raw': raw, 'last': last}
        for side in ['bid', 'ask']:
            size = integer(raw.get(side + '_size'), side + '_size')
            price = raw.get(side + '_price')
            require((size == 0 and price is None) or (size > 0 and price is not None), 'inconsistent_quote_depth')
            price = cents(price, side + '_price', positive=True) if price is not None else None
            require(price is None or lo <= price <= hi, 'quote_price_outside_limits')
            out[side], out[side + '_size'] = price, size
        require(out['bid'] is None or out['ask'] is None or out['bid'] < out['ask'], 'crossed_or_locked_quote')
        out['key'] = digest([symbol, raw['source'], observed.isoformat()])
        # received_at is transport metadata, not fresh displayed liquidity.
        out['fingerprint'] = digest({k: v for k, v in raw.items() if k != 'received_at'})
        return out

    @staticmethod
    def _safety(plan, account, authorization_id, at):
        require(isinstance(plan, dict), 'invalid_plan')
        require(plan.get('mode') == 'dry_run' and plan.get('autonomous_trading_enabled') is False, 'live_mode_or_authorization_forbidden')
        for section in [plan, plan.get('meta', {})]:
            require(isinstance(section, dict), 'invalid_plan_meta')
            for flag in ['live_trading_enabled', 'live_orders_authorized', 'real_orders_enabled']:
                require(flag not in section or section[flag] is False, 'live_mode_or_authorization_forbidden')
        meta = plan.get('meta', {})
        require(meta.get('paper_trading_authorized') is True, 'paper_authorization_required')
        require(meta.get('paper_authorization_id') == authorization_id == account['authorization_id'], 'authorization_mismatch')
        require(plan.get('schema_version') in ['1.0', 'watchlist_plan_v1'], 'unsupported_plan_schema')
        require(day(plan.get('trade_date')) == at.date().isoformat(), 'plan_date_mismatch')
        require(stamp(plan.get('generated_at'), 'plan.generated_at') <= at, 'future_plan')

    @staticmethod
    def _stock(plan, symbol, side):
        matches = []
        for pool in ['execution_pool', 'watch_pool']:
            rows = plan.get(pool, [])
            require(isinstance(rows, list) and all(isinstance(s, dict) for s in rows), 'invalid_plan_pool')
            matches += [(s, pool) for s in rows if s.get('ts_code') == symbol]
        if side == 'sell' and not matches:
            return None
        require(len(matches) == 1, 'plan_symbol_missing_or_ambiguous')
        stock, pool = matches[0]
        require(side != 'buy' or pool == 'execution_pool', 'not_execution_pool')
        return stock

    @staticmethod
    def _research_proof(plan, summary, r6, at):
        """Validate supplied offline primary snapshots, never discover real files.

        This is source-bound caller evidence, not independent authentication of
        the research producer. Bare readiness booleans/empty R6 cannot pass.
        """
        require(isinstance(summary, dict), 'required_research_summary_missing')
        require(isinstance(r6, dict), 'required_r6_research_missing')
        plan_time = stamp(plan.get('generated_at'), 'plan.generated_at')
        for label, obj in [('summary', summary), ('r6', r6)]:
            require(day(obj.get('trade_date')) == day(plan.get('trade_date')), 'research_date_mismatch')
            when = stamp(obj.get('generated_at'), label+'.generated_at')
            require(when <= plan_time <= at, 'research_not_consumed_by_plan')
        require(stamp(r6['generated_at'], 'r6.generated_at') <= stamp(summary['generated_at'], 'summary.generated_at'),
                'r6_newer_than_research_summary')
        require(summary.get('orchestrator_status') == 'complete' and summary.get('contract_checks_passed') is True,
                'required_research_not_complete')
        require(summary.get('contract_failures') == {} and summary.get('timeouts') == [], 'required_research_not_complete')
        number(summary.get('fetch_global_severity'), 'fetch_global_severity', maximum=2)
        for unit in ['R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7']:
            for field, expected in [('units', 'complete'), ('contract_results', 'passed')]:
                rows = summary.get(field)
                require(isinstance(rows, dict) and isinstance(rows.get(unit), dict)
                        and rows[unit].get('status') == expected, 'required_research_not_complete:'+unit)
                if field == 'contract_results':
                    require(rows[unit].get('research_status') == 'complete', 'required_research_not_complete:'+unit)
            artifacts = summary.get('artifacts')
            require(isinstance(artifacts, dict), 'research_sources_required')
            text(artifacts.get(unit), 'research_source.'+unit)
        require(r6.get('status') == 'complete' and r6.get('degraded', False) is False, 'r6_not_complete')
        integer(r6.get('candidates_evaluated'), 'r6.candidates_evaluated', minimum=1)
        upstream = r6.get('upstream_usable')
        require(isinstance(upstream, dict) and all(upstream.get(u) is True for u in ['R1','R2','R3','R4','R5','R7']),
                'r6_required_upstream_not_complete')
        require(isinstance(r6.get('hard_rejects'), list) and isinstance(r6.get('counter_arguments'), list), 'invalid_r6')
        return {'summary_sha256': digest(summary), 'r6_sha256': digest(r6),
                'artifacts': deepcopy(summary['artifacts']), 'source': 'supplied_local_research_snapshots'}

    @staticmethod
    def _r6_veto(plan, stock, symbol, summary, raw_r6):
        require(stock.get('r6_hard_reject', False) is False and stock.get('hard_reject', False) is False, 'r6_hard_reject')
        meta_r6 = plan.get('meta', {}).get('r6_devil_advocate', {})
        require(isinstance(meta_r6, dict), 'invalid_r6')
        meta = plan.get('meta', {})
        sources = [plan, meta, meta_r6, meta.get('research_summary') or {}, summary or {}, raw_r6 or {}]
        rejected = plan.get('rejected', [])
        require(isinstance(rejected, list) and all(isinstance(r, dict) for r in rejected), 'invalid_rejected_pool')
        for row in rejected:
            require(row.get('ts_code') != symbol, 'r6_hard_reject' if row.get('source_agent') == 'R6' else 'plan_rejected_stock')
        # D1's real hard_rejects_applied contains reject_id OR a code. Resolve
        # ids using the supplied R6 primary; unresolved vetoes fail closed.
        lookup = {}
        for source in sources:
            require(isinstance(source, dict), 'invalid_r6')
            for key in ['hard_rejects', 'counter_arguments']:
                rows = source.get(key, [])
                require(isinstance(rows, list), 'invalid_r6')
                for row in rows:
                    if isinstance(row, dict) and row.get('reject_id'):
                        text(row['reject_id'], 'r6.reject_id')
                        lookup.setdefault(row['reject_id'], []).append(row)
        def codes(row):
            if isinstance(row, str):
                return set(re.findall(r'\d{6}\.(?:SH|SZ|BJ)', row))
            require(isinstance(row, dict), 'invalid_r6')
            return set().union(*(codes(row.get(k, '')) for k in ['ts_code','target_ts_code','target','name'] if row.get(k) is not None))
        for source in sources:
            for key in ['hard_rejects', 'hard_rejects_applied']:
                rows = source.get(key, [])
                require(isinstance(rows, list), 'invalid_r6')
                for row in rows:
                    found = codes(row)
                    rid = row.get('reject_id') if isinstance(row, dict) else row
                    if not found and isinstance(rid, str):
                        found = set().union(*(codes(item) for item in lookup.get(rid, [])))
                    require(bool(found), 'r6_unresolved_hard_reject')
                    require(symbol not in found, 'r6_hard_reject')
            # A raw primary must not bypass its own hard severity by omitting
            # the derived hard_rejects list entry.
            for row in source.get('counter_arguments', []):
                require(isinstance(row, dict), 'invalid_r6')
                if row.get('severity') == 'hard_reject':
                    found = codes(row)
                    require(bool(found), 'r6_unresolved_hard_reject')
                    require(symbol not in found, 'r6_hard_reject')

    @staticmethod
    def _buy_gate(plan, stock, symbol, *, research_summary, r6_research, at):
        require(plan.get('status') == 'ok', 'plan_not_ready')
        sections = [plan, plan.get('meta', {})]
        for key in ['production_ready', 'research_completion_passed']:
            require(any(section.get(key) is True for section in sections), 'explicit_plan_readiness_required:'+key)
        for section in [plan, plan.get('meta', {})]:
            for key in ['production_ready', 'research_completion_passed']:
                require(section.get(key) is not False and (key not in section or section[key] is True), 'plan_not_ready')
            require(section.get('reassessment_required', False) is False, 'plan_not_ready')
            require(section.get('is_degraded_plan', False) is False, 'plan_not_ready')
        require(type(plan.get('no_trade')) is bool, 'explicit_no_trade_flag_required')
        require(not plan['no_trade'] and plan.get('decision_status') != 'no_trade', 'global_no_new_buy')
        for section in [plan, plan.get('meta', {}), plan.get('risk_limits', {})]:
            require(isinstance(section, dict), 'invalid_risk_section')
            for flag in ['no_new_buys', 'block_new_buys', 'kill_switch_active', 'account_hard_stop_loss_active']:
                require(flag not in section or section[flag] is False, 'global_no_new_buy')
        risk_section = plan.get('risk_limits', {})
        require('kill_switch_file' not in risk_section or risk_section.get('kill_switch_active') is False,
                'file_kill_switch_requires_explicit_owner_snapshot')
        if risk_section.get('account_hard_stop_loss_pct') is not None:
            number(risk_section['account_hard_stop_loss_pct'], 'account_hard_stop_loss_pct', maximum=1)
            require(risk_section.get('account_hard_stop_loss_active') is False, 'account_hard_stop_requires_explicit_owner_snapshot')
        conditions = plan.get('no_trade_conditions', [])
        require(isinstance(conditions, list), 'invalid_global_conditions')
        for condition in conditions:
            require(isinstance(condition, dict) and type(condition.get('active')) is bool, 'invalid_global_condition')
            scope = condition.get('scope', 'global')
            require(scope in ['global', 'stock', 'symbol'], 'unsupported_condition_scope')
            if scope in ['stock', 'symbol']:
                require(isinstance(condition.get('ts_code'), str)
                        and bool(re.fullmatch(r'\d{6}\.(?:SH|SZ|BJ)', condition['ts_code'])), 'invalid_condition_target')
            if condition['active']:
                require(scope != 'global', 'global_no_new_buy')
                require(condition.get('ts_code') != symbol, 'stock_no_new_buy')
        rebalance = plan.get('portfolio_rebalance', {})
        require(isinstance(rebalance, dict), 'invalid_rebalance')
        require(rebalance.get('max_new_buys_before_trim_done') != 0, 'rebalance_blocks_new_buy')
        PaperLedger._r6_veto(plan, stock, symbol, research_summary, r6_research)
        proof = PaperLedger._research_proof(plan, research_summary, r6_research, at)
        eligibility = stock.get('buy_eligibility')
        if eligibility is not None:
            require(isinstance(eligibility, dict), 'stock_buy_ineligible_or_missing')
            # A stale engine-owned RR status can be recomputed; explicit human
            # review and all external vetoes (including nested ones) survive.
            derived_reviews = {'D1_BUY_DEVIATION_REQUIRES_DERIVATION_REASON', 'CONFLICTING_EXIT_PRICE_EVIDENCE',
                               'UNKNOWN_PRICE_PROVENANCE', 'UNKNOWN_EXIT_PRICE_PROVENANCE'}
            old_reviews = eligibility.get('review_reasons', [])
            owned_derived_review = (eligibility.get('source') == 'price_levels_engine'
                                    and eligibility.get('reasons') == ['D1_ENGINE_PRICE_REVIEW_REQUIRED']
                                    and isinstance(old_reviews, list) and all(r in derived_reviews for r in old_reviews)
                                    and eligibility.get('manual_review_required', False) is False)
            require(eligibility.get('review_required', False) is False or owned_derived_review, 'stock_review_required')
            external = eligibility.get('external_qualification') if eligibility.get('source') == 'price_levels_engine' else eligibility
            if external is not None:
                require(isinstance(external, dict) and external.get('status') == 'eligible'
                        and external.get('eligible', True) is True and external.get('review_required', False) is False,
                        'stock_external_buy_ineligible')
        for flag in ['review_required', 'manual_review_required', 'price_review_required']:
            require(stock.get(flag, False) is False, 'stock_review_required')
        stock_conditions = stock.get('no_trade_conditions', [])
        require(isinstance(stock_conditions, list), 'invalid_stock_conditions')
        require(all(isinstance(c, dict) and (c.get('active') is False or
                    (c.get('source') == 'price_levels_engine' and c.get('code') == 'RR_FAIL'))
                    for c in stock_conditions), 'stock_no_new_buy')
        status = stock.get('plan_status') if stock.get('plan_status') is not None else ''
        require(isinstance(status, str), 'invalid_stock_plan_status')
        require(not status.startswith('execution_pool_exit'), 'stock_exit_only')
        require(not status.startswith('watch_') and status != 'agent_candidate_pool'
                and stock.get('role') not in ['watch', 'watch_elastic', 'exit', 'exit_if_no_break'], 'stock_observation_only')
        return plan.get('risk_limits', {}), proof

    @staticmethod
    def _selected_rule(stock, intent, side):
        rules = stock.get('entry_rules' if side == 'buy' else 'exit_rules')
        idx = integer(intent.get('rule_index'), 'rule_index')
        require(isinstance(rules, list) and idx < len(rules) and isinstance(rules[idx], dict), 'plan_rule_missing')
        return rules[idx]

    @staticmethod
    def _rule_shape(rule, side):
        # Only descriptions/provenance are non-predicates. None means inactive
        # on full pydantic dumps. Never ignore active auction/volume/board fields.
        metadata = {'priority', 'reason', 'derivation_reason', 'execution_logic', 'price_src', 'engine_formula'}
        allowed = metadata | {'type', 'trigger_price', 'time_window'}
        allowed |= ({'buy_zone', 'pullback_zone', 'entry_target_price', 'confirm_price', 'reclaim_price',
                     'max_acceptable_ask', 'position_pct', 'max_premium_pct', 'review_required'}
                    if side == 'buy' else {'quantity_pct'})
        require(all(k in allowed or v is None for k, v in rule.items()), 'unsupported_rule_constraints')
        require(rule.get('max_premium_pct') in (None, 0) and not isinstance(rule.get('max_premium_pct'), bool),
                'unsupported_rule_constraints')
        if rule.get('time_window') is not None:
            window = rule['time_window']
            require(isinstance(window, str) and bool(re.fullmatch(r'\d{2}:\d{2}-\d{2}:\d{2}', window)), 'unsupported_time_window')
            start, end = window.split('-')
            try:
                require(time.fromisoformat(start) <= time.fromisoformat(end), 'invalid_time_window')
            except ValueError as exc:
                raise PaperError('invalid_time_window') from exc
        if side == 'buy':
            require(rule.get('type') in ['trend_pullback_buy', 'low_absorption_intraday', 'divergence_pullback',
                                         't_add_pullback', 'leader_breakout'], 'unsupported_entry_rule')
            for key in ['buy_zone', 'pullback_zone']:
                zone = rule.get(key)
                if zone is not None:
                    require(isinstance(zone, (list, tuple)) and len(zone) == 2, 'invalid_numeric_buy_zone')
                    lo, hi = [cents(v, key, positive=True) for v in zone]
                    require(lo <= hi, 'invalid_numeric_buy_zone')
            for key in ['trigger_price', 'entry_target_price', 'confirm_price', 'reclaim_price', 'max_acceptable_ask']:
                if rule.get(key) is not None:
                    cents(rule[key], 'rule.'+key, positive=True)
            require(any(rule.get(k) is not None for k in ['buy_zone','entry_target_price','trigger_price']), 'missing_buy_price_predicate')
            if rule.get('price_src') == 'engine':
                # Producer explicitly nulls this on a one-word/no-valid-entry setup.
                require(rule.get('trigger_price') is not None, 'unsupported_engine_entry_without_trigger')
            if rule.get('type') == 'leader_breakout':
                require(rule.get('trigger_price') is not None and rule.get('max_acceptable_ask') is not None,
                        'breakout_requires_trigger_and_ask_cap')
        else:
            require(rule.get('type') in ['stop_loss_break','intraday_break_exit','take_profit_hit','t_reduce_resistance'],
                    'unsupported_exit_rule')
            cents(rule.get('trigger_price'), 'rule.trigger_price', positive=True)
            require(number(rule.get('quantity_pct'), 'quantity_pct', maximum=1) > 0, 'invalid_exit_quantity')

    @staticmethod
    def _rule(stock, intent, quote, side, at):
        rule = PaperLedger._selected_rule(stock, intent, side)
        PaperLedger._rule_shape(rule, side)
        if rule.get('time_window'):
            start, end = rule['time_window'].split('-')
            require(start <= at.strftime('%H:%M') <= end, 'rule_time_window_not_met')
        kind = rule.get('type')
        if side == 'buy':
            ask = quote['ask']
            triggered = ask is not None
            if kind == 'leader_breakout':
                triggered = triggered and quote['last'] >= cents(rule['trigger_price'], 'trigger_price', positive=True)
            elif rule.get('buy_zone') is None:
                bound = rule.get('entry_target_price')
                if bound is None:
                    bound = rule.get('trigger_price')
                triggered = triggered and ask <= cents(bound, 'buy_price_bound', positive=True)
            # For pullbacks the real price producer uses trigger_price as the
            # zone's LOWER anchor. The explicit two-sided zone is authoritative,
            # not ask<=lower (which would reduce every normal zone to one tick).
            for key in ['buy_zone','pullback_zone']:
                if rule.get(key) is not None:
                    lo, hi = [cents(v, key, positive=True) for v in rule[key]]
                    triggered = triggered and lo <= ask <= hi
            for key in ['confirm_price','reclaim_price']:
                if rule.get(key) is not None:
                    triggered = triggered and quote['last'] >= cents(rule[key], key, positive=True)
            if rule.get('max_acceptable_ask') is not None:
                triggered = triggered and ask <= cents(rule['max_acceptable_ask'], 'max_acceptable_ask', positive=True)
        else:
            trigger = cents(rule['trigger_price'], 'trigger_price', positive=True)
            if kind in ['stop_loss_break', 'intraday_break_exit']:
                triggered = quote['last'] <= trigger
            else:
                triggered = quote['last'] >= trigger or (quote['bid'] is not None and quote['bid'] >= trigger)
        require(triggered, 'entry_trigger_not_met' if side == 'buy' else 'exit_trigger_not_met')
        return rule

    @staticmethod
    def _exit_source(stock, plan, at, order_id):
        rules = stock.get('exit_rules')
        require(isinstance(rules, list) and bool(rules) and all(isinstance(r, dict) for r in rules), 'legal_exit_source_required')
        supported = [r for r in rules if r.get('type') in ['stop_loss_break','intraday_break_exit','take_profit_hit','t_reduce_resistance']]
        require(bool(supported), 'legal_exit_source_required')
        for rule in supported:
            PaperLedger._rule_shape(rule, 'sell')
        return {'stock': deepcopy(stock), 'stock_sha256': digest(stock), 'plan_sha256': digest(plan),
                'generated_at': plan['generated_at'], 'trade_date': plan['trade_date'],
                'order_id': order_id, 'saved_at': at.isoformat(), 'source': 'authorized_paper_plan_snapshot'}

    @staticmethod
    def _save_exit(db, account_id, symbol, source):
        db.execute('INSERT INTO exit_plans(account_id,symbol,source_json) VALUES(?,?,?) '
                   'ON CONFLICT(account_id,symbol) DO UPDATE SET source_json=excluded.source_json',
                   (account_id, symbol, canonical(source)))

    @staticmethod
    def _sell_stock(db, account_id, symbol, stock, plan, at, order_id):
        require(db.execute('SELECT 1 FROM lots WHERE account_id=? AND symbol=? AND quantity>0',
                           (account_id, symbol)).fetchone() is not None, 't_plus_one_or_no_paper_sellable_shares')
        row = db.execute('SELECT source_json FROM exit_plans WHERE account_id=? AND symbol=?', (account_id, symbol)).fetchone()
        saved = json.loads(row[0]) if row else None
        if saved is not None:
            require(isinstance(saved, dict) and isinstance(saved.get('stock'), dict)
                    and saved.get('stock_sha256') == digest(saved['stock'])
                    and saved['stock'].get('ts_code') == symbol
                    and bool(re.fullmatch(r'[0-9a-f]{64}', str(saved.get('plan_sha256')))), 'invalid_saved_exit_source')
        if stock is not None and stock.get('exit_rules'):
            current = PaperLedger._exit_source(stock, plan, at, order_id)
            require(saved is None or stamp(current['generated_at'], 'exit.generated_at') >= stamp(saved['generated_at'], 'saved_exit.generated_at'),
                    'stale_replacement_exit_source')
            # Persist a legal explicit update even when its price has not hit.
            PaperLedger._save_exit(db, account_id, symbol, current)
            return stock, current
        require(saved is not None, 'saved_exit_source_missing')
        assert isinstance(saved, dict)
        return saved['stock'], saved

    @staticmethod
    def _exit_rule_key(rule):
        # Descriptions, priority, pool and plan date do not create a new tranche.
        return digest([rule.get('type'), str(number(rule.get('trigger_price'), 'trigger_price').normalize()),
                       str(number(rule.get('quantity_pct'), 'quantity_pct', maximum=1).normalize()),
                       rule.get('time_window')])

    @staticmethod
    def _position_cycle(fills):
        held, cycle = 0, None
        for fill in fills:
            if fill['side'] == 'buy':
                if held == 0:
                    cycle = fill['fill_id']
                held += fill['quantity']
            else:
                held -= fill['quantity']
            require(held >= 0, 'invalid_paper_fill_history')
        return cycle if held else None

    @classmethod
    def _sell_progress(cls, db, account_id, symbol, rule):
        """Resolve a tranche read-only, including evidence-backed old orders.

        Legacy targets use original sell-day T+1 inventory and immutable fills,
        not today's remainder. Missing evidence never grants another tranche.
        Historical orders/fills are not silently rewritten by this resolver.
        """
        fills = [dict(r) for r in db.execute(
            'SELECT * FROM fills WHERE account_id=? AND symbol=? ORDER BY fill_id', (account_id, symbol))]
        cycle = cls._position_cycle(fills)
        require(cycle is not None, 'fractional_exit_position_history_required')
        key = digest([symbol, cycle, cls._exit_rule_key(rule)])
        for row in db.execute('SELECT * FROM orders WHERE account_id=? ORDER BY created_at,order_id', (account_id,)):
            intent, result = json.loads(row['intent_json']), json.loads(row['result_json'])
            if intent.get('symbol') != symbol or intent.get('side') != 'sell':
                continue
            if row['status'] == 'rejected' and row['filled_qty'] == 0:
                continue  # A refused, unfilled attempt did not consume a tranche.
            own = [f for f in fills if f['order_id'] == row['order_id'] and f['side'] == 'sell']
            stage = result.get('exit_stage_key')
            target = result.get('target_quantity')
            if stage is None:
                original = None
                prefix = []
                original_day = ''
                if own:
                    first = own[0]
                    evidence = json.loads(first['evidence_json'])
                    original = evidence.get('rule')
                    require(isinstance(original, dict), 'legacy_exit_rule_evidence_required')
                    prefix = [f for f in fills if f['fill_id'] < first['fill_id']]
                    original_day = first['trade_date']
                elif row['status'] in ['pending', 'partial', 'superseded']:
                    source = result.get('exit_source', {}).get('stock')
                    if isinstance(source, dict):
                        original = cls._selected_rule(source, intent, 'sell')
                        created = stamp(row['created_at'], 'order.created_at')
                        prefix = [f for f in fills if stamp(f['at'], 'fill.at') <= created]
                        original_day = created.date().isoformat()
                if original is not None and number(original.get('quantity_pct'), 'quantity_pct', maximum=1) < 1:
                    stage = digest([symbol, cls._position_cycle(prefix), cls._exit_rule_key(original)])
                    base = sum(f['quantity'] for f in prefix if f['side'] == 'buy'
                               and f['trade_date'] < original_day) - sum(
                                   f['quantity'] for f in prefix if f['side'] == 'sell')
                    target = min(intent['quantity'], int(Decimal(base) * number(
                        original['quantity_pct'], 'quantity_pct') / 100) * 100)
            if stage != key:
                continue
            integer(target, 'saved_exit_target', minimum=100)
            require(target % 100 == 0 and row['filled_qty'] == sum(f['quantity'] for f in own)
                    and row['filled_qty'] <= target, 'invalid_saved_exit_target')
            return {'order_id': row['order_id'], 'intent': intent, 'result': result,
                    'status': row['status'], 'target_quantity': target, 'exit_stage_key': key,
                    'filled_quantity': row['filled_qty'],
                    'complete': row['filled_qty'] == target or row['status'] == 'superseded'}
        return {'exit_stage_key': key}

    def sell_progress(self, account_id, symbol, rule, *, now=None):
        with self.transaction() as db:
            self._account(db, account_id, self.clock(now))
            return self._sell_progress(db, account_id, symbol, rule)

    @classmethod
    def _supersede_exits(cls, db, account_id, symbol, oid, rule, at):
        priority = rule.get('priority', 99)
        require(type(priority) is int, 'invalid_exit_priority')
        updates = []
        for row in db.execute("SELECT * FROM orders WHERE account_id=? AND status IN ('pending','partial') AND order_id!=?",
                              (account_id, oid)).fetchall():
            intent, result = json.loads(row['intent_json']), json.loads(row['result_json'])
            if intent.get('symbol') != symbol or intent.get('side') != 'sell':
                continue
            prior = result.get('exit_rule')
            if prior is None:
                source = result.get('exit_source')
                source = source.get('stock') if isinstance(source, dict) else None
                if isinstance(source, dict):
                    try:
                        prior = cls._selected_rule(source, intent, 'sell')
                    except PaperError:
                        # Do not invent an old rule or let missing old metadata
                        # veto an independently valid protective exit.
                        continue
            if isinstance(prior, dict) and type(prior.get('priority', 99)) is int and priority < prior.get('priority', 99):
                result.update(status='superseded', superseded_by=oid, superseded_at=at.isoformat())
                updates.append(('superseded', at.isoformat(), canonical(result), account_id, row['order_id']))
        for update in updates:
            db.execute('UPDATE orders SET status=?,last_at=?,result_json=? WHERE account_id=? AND order_id=?', update)

    def execute(self, *, account_id, authorization_id, intent, plan, quotes, calendar, quote_max_age, now=None,
                research_summary=None, r6_research=None):
        at = self.clock(now)
        # Freeze caller-owned values; helper results must not rewrite a formal
        # plan, nor race mutable input objects during this transaction.
        intent, plan, quotes, calendar, research_summary, r6_research = deepcopy(
            (intent, plan, quotes, calendar, research_summary, r6_research))
        text(authorization_id, 'authorization_id')
        require(isinstance(intent, dict), 'invalid_intent')
        require(set(intent) == {'order_id', 'symbol', 'side', 'quantity', 'limit_price', 'rule_index'}, 'invalid_intent_fields')
        oid = text(intent.get('order_id'), 'order_id')
        ihash = digest(intent)
        with self.transaction() as db:
            account = self._account(db, account_id, at, authorization_id)
            old = db.execute('SELECT * FROM orders WHERE account_id=? AND order_id=?', (account_id, oid)).fetchone()
            if old:
                require(old['intent_hash'] == ihash, 'idempotency_key_conflict')
                if old['status'] in ['filled', 'rejected', 'superseded']:
                    result = json.loads(old['result_json'])
                    return dict(result, idempotent_replay=True, event='paper_idempotent_replay',
                                original_event=result['event'], fill_quantity=0)
            else:
                db.execute('INSERT INTO orders(account_id,order_id,intent_hash,intent_json,status,created_at,last_at,result_json) VALUES(?,?,?,?,?,?,?,?)',
                           (account_id, oid, ihash, canonical(intent), 'pending', at.isoformat(), at.isoformat(), '{}'))
            previous_qty = old['filled_qty'] if old else 0
            result = {'account_id': account_id, 'order_id': oid, 'environment': 'paper', 'status': 'pending',
                      'event': 'paper_no_fill', 'filled_quantity': previous_qty, 'fill_quantity': 0,
                      'at': at.isoformat(), 'fee_model': json.loads(account['fee_model']), 'idempotent_replay': False}
            previous_result = {}
            if old:
                previous_result = json.loads(old['result_json'])
                for field in ['target_quantity', 'exit_stage_key', 'exit_rule']:
                    if field in previous_result:
                        result[field] = previous_result[field]
            try:
                risk = {}
                eligibility = {}
                exit_source = {}
                next_days = []
                target = None
                max_age = number(quote_max_age, 'quote_max_age', minimum=Decimal('.000001'))
                symbol, side = intent.get('symbol'), intent.get('side')
                symbol_ok(symbol)
                require(side in ['buy', 'sell'], 'invalid_side')
                requested = integer(intent.get('quantity'), 'quantity', minimum=100)
                require(requested % 100 == 0, 'quantity_must_be_100_share_lots')
                limit = cents(intent.get('limit_price'), 'limit_price', positive=True)
                days = self._calendar(calendar, at)
                self._safety(plan, account, authorization_id, at)
                stock = self._stock(plan, symbol, side)
                require(isinstance(quotes, dict) and isinstance(quotes.get('quotes'), list), 'invalid_quotes_bundle')
                raw_quotes = quotes['quotes']
                require(all(isinstance(q, dict) for q in raw_quotes), 'invalid_quotes_bundle')
                by_symbol = {q.get('symbol'): q for q in raw_quotes}
                require(len(by_symbol) == len(raw_quotes), 'duplicate_quote_symbol')
                q = self._quote(by_symbol.get(symbol), symbol, at, max_age)
                result.update({'quote_key': q['key'], 'plan_sha256': digest(plan), 'calendar_sha256': digest(calendar)})
                liq = db.execute('SELECT * FROM liquidity WHERE quote_key=?', (q['key'],)).fetchone()
                require(liq is None or liq['fingerprint'] == q['fingerprint'], 'conflicting_quote_observation')
                counter = 'ask' if side == 'buy' else 'bid'
                price = q[counter]
                if side == 'buy':
                    assert isinstance(stock, dict)
                    kill, kill_errors = kill_snapshot(plan, at, ROOT)
                    result['kill_switch_snapshot'] = kill
                    require(not kill_errors, ','.join(kill_errors))
                    require(not kill['exists'], 'global_no_new_buy:kill_switch_file_exists')
                    selected = self._selected_rule(stock, intent, 'buy')
                    for field in ['exit_rules', 'no_trade_conditions']:
                        require(isinstance(stock.get(field, []), list)
                                and all(isinstance(row, dict) for row in stock.get(field, [])), 'invalid_stock_'+field)
                    # Lazy import of ONLY the inert shared pure module. Never
                    # import executors.base (it imports QMT) or src.settings.
                    from src.plan.buy_eligibility import evaluate_stock_buy_eligibility, evaluate_plan_buy_gate
                    gate_view = dict(plan)
                    conditions = plan.get('no_trade_conditions', [])
                    if isinstance(conditions, list):
                        # Global helper has a global-only contract. _buy_gate
                        # separately validates every scope, including malformed
                        # rows; another symbol's condition is not a global veto.
                        gate_view['no_trade_conditions'] = [c for c in conditions if not (
                            isinstance(c, dict) and c.get('scope') in ['stock','symbol'] and c.get('ts_code') != symbol)]
                    eligibility = evaluate_stock_buy_eligibility(stock, {'ask': price / 100 if price is not None else None},
                                                                 entry_rule=selected)
                    global_gate = evaluate_plan_buy_gate(gate_view)
                    result.update(buy_eligibility=eligibility, global_buy_gate=global_gate, selected_entry_rule=selected)
                    meta = plan.get('meta', {})
                    summary = research_summary if research_summary is not None else meta.get('research_summary')
                    raw_r6 = r6_research if r6_research is not None else meta.get('r6_devil_advocate')
                    risk, proof = self._buy_gate(plan, stock, symbol, research_summary=summary, r6_research=raw_r6, at=at)
                    result['research_proof'] = proof
                    require(global_gate.get('status') == 'eligible', 'global_no_new_buy:'+','.join(global_gate.get('reasons', [])))
                else:
                    stock, exit_source = self._sell_stock(db, account_id, symbol, stock, plan, at, oid)
                    result['exit_source'] = exit_source
                assert isinstance(stock, dict)
                # No counterparty means pending; do not invent last-price fills.
                if price is None:
                    result['reason'] = 'no_counterparty_depth'
                else:
                    if side == 'buy':
                        require(eligibility.get('status') == 'eligible' and eligibility.get('review_required') is False,
                                'stock_buy_ineligible:'+','.join(eligibility.get('reasons', [])))
                    rule = self._rule(stock, intent, q, side, at)
                    if side == 'sell':
                        if old:
                            prior_rule = previous_result.get('exit_rule')
                            if prior_rule is None and previous_qty:
                                prior_fill = db.execute('SELECT evidence_json FROM fills WHERE account_id=? AND order_id=? ORDER BY fill_id LIMIT 1',
                                                        (account_id, oid)).fetchone()
                                require(prior_fill is not None, 'legacy_exit_rule_evidence_required')
                                prior_rule = json.loads(prior_fill[0]).get('rule')
                            if prior_rule is not None:
                                require(self._exit_rule_key(prior_rule) == self._exit_rule_key(rule),
                                        'pending_paper_sell_rule_changed_requires_reassessment')
                        result['exit_rule'] = deepcopy(rule)
                    require(price <= limit if side == 'buy' else price >= limit, 'limit_price_not_marketable')
                    if side == 'buy':
                        exit_source = self._exit_source(stock, plan, at, oid)
                        previous_exit = db.execute('SELECT source_json FROM exit_plans WHERE account_id=? AND symbol=?',
                                                   (account_id, symbol)).fetchone()
                        if previous_exit:
                            saved_exit = json.loads(previous_exit[0])
                            require(stamp(exit_source['generated_at'], 'exit.generated_at') >=
                                    stamp(saved_exit.get('generated_at'), 'saved_exit.generated_at'), 'stale_replacement_exit_source')
                    used = liq['buy_used' if side == 'buy' else 'sell_used'] if liq else 0
                    depth = max(0, q[counter + '_size'] - used) // 100 * 100
                    qty = min(requested - previous_qty, depth)
                    fee_model = json.loads(account['fee_model'])
                    fee = 0 if fee_model['model'] == 'zero_fee_assumption' else cents(fee_model[side], 'fee')
                    lots = db.execute('SELECT * FROM lots WHERE account_id=? AND quantity>0 ORDER BY buy_date,lot_id', (account_id,)).fetchall()
                    held = {}
                    for lot in lots:
                        held[lot['symbol']] = held.get(lot['symbol'], 0) + lot['quantity']
                    today = at.date().isoformat()
                    if side == 'buy':
                        next_days = [d for d in days if d > today]
                        require(bool(next_days), 'calendar_missing_next_trading_day')
                        prefixes = risk.get('block_prefixes')
                        require(isinstance(prefixes, list) and all(isinstance(p, str) and p for p in prefixes), 'explicit_block_prefixes_required')
                        assert isinstance(prefixes, list)
                        require(not any(symbol.startswith(p) for p in prefixes), 'risk_blocked_prefix')
                        require(stock.get('is_st') is False, 'explicit_non_st_stock_required')
                        max_positions = integer(risk.get('max_positions'), 'max_positions', minimum=1)
                        require(rule.get('type') != 't_add_pullback' or symbol in held, 't_add_requires_paper_holding')
                        require(symbol in held or len(held) < max_positions, 'max_positions')
                        daily = integer(risk.get('max_buy_orders_per_day'), 'max_buy_orders_per_day', minimum=1)
                        sym_daily = integer(risk.get('max_orders_per_symbol_per_day'), 'max_orders_per_symbol_per_day', minimum=1)
                        for count_limit, sym in [(daily, None), (sym_daily, symbol)]:
                            count = db.execute('SELECT COUNT(DISTINCT order_id) FROM fills WHERE account_id=? AND trade_date=? AND side=\'buy\' AND order_id!=? AND (? IS NULL OR symbol=?)',
                                               (account_id, today, oid, sym, sym)).fetchone()[0]
                            require(count < count_limit, 'daily_order_budget')
                        values = {}
                        for held_symbol, held_qty in held.items():
                            hq = self._quote(by_symbol.get(held_symbol), held_symbol, at, max_age)
                            require(hq['bid'] is not None, 'held_position_valuation_unavailable')
                            values[held_symbol] = hq['bid'] * held_qty
                        market = sum(values.values())
                        equity = account['cash'] + market
                        single = number(stock.get('max_position_pct'), 'max_position_pct', maximum=1)
                        total = number(risk.get('target_total_position_pct'), 'target_total_position_pct', maximum=1)
                        for container, field in [(plan.get('meta', {}), 'position_cap_pct'),
                                                 (plan.get('position_cap_derivation', {}), 'final_position_cap_pct')]:
                            require(isinstance(container, dict), 'invalid_position_cap')
                            if field in container:
                                total = min(total, number(container[field], field, maximum=1))
                        allocation = number(rule.get('position_pct'), 'position_pct', maximum=1)
                        budgets = [Decimal(account['cash'] - fee), single * (equity-fee) - values.get(symbol, 0),
                                   total * (equity-fee) - market, allocation * (equity-fee) - previous_qty * price]
                        affordable = max(0, int((min(budgets) / price / 100).to_integral_value(rounding=ROUND_FLOOR)) * 100)
                        qty = min(qty, affordable)
                        require(qty > 0 or depth == 0, 'cash_or_position_budget')
                    else:
                        sellable = sum(l['quantity'] for l in lots if l['symbol'] == symbol and l['sellable_on'] <= today)
                        require(sellable > 0, 't_plus_one_or_no_paper_sellable_shares')
                        pct = number(rule.get('quantity_pct'), 'quantity_pct', maximum=1)
                        if pct < 1:
                            progress = self._sell_progress(db, account_id, symbol, rule)
                            require(progress.get('order_id', oid) == oid, 'fractional_exit_stage_already_started')
                            if old and (previous_qty or previous_result.get('exit_stage_key')):
                                require(progress.get('order_id') == oid, 'fractional_exit_position_cycle_changed')
                            target = integer(progress.get('target_quantity', min(requested, int(
                                (Decimal(sellable) * pct / 100).to_integral_value(rounding=ROUND_FLOOR)) * 100)),
                                'exit_target', minimum=100)
                            result.update(target_quantity=target, exit_stage_key=progress['exit_stage_key'])
                            sell_cap = min(sellable, target - previous_qty)
                        else:
                            # Full-exit requests retain their explicit quantity
                            # and T+1 partial contract, unlike ratio bases.
                            target = requested
                            sell_cap = sellable
                        qty = min(qty, sell_cap)
                        require(qty > 0 or depth == 0, 'sell_quantity_budget')
                        require(account['cash'] + qty * price >= fee, 'sell_fee_exceeds_cash_and_proceeds')
                    if qty == 0:
                        result['reason'] = 'displayed_depth_exhausted_or_below_lot'
                    else:
                        # All mutations below commit or roll back together, including liquidity.
                        if side == 'sell':
                            self._supersede_exits(db, account_id, symbol, oid, rule, at)
                        db.execute('INSERT OR IGNORE INTO liquidity(quote_key,fingerprint) VALUES(?,?)', (q['key'], q['fingerprint']))
                        col = 'buy_used' if side == 'buy' else 'sell_used'
                        db.execute(f'UPDATE liquidity SET {col}={col}+? WHERE quote_key=?', (qty, q['key']))
                        if side == 'buy':
                            db.execute('UPDATE accounts SET cash=cash-?,fees=fees+? WHERE account_id=?', (qty*price+fee, fee, account_id))
                            db.execute('INSERT INTO lots(account_id,symbol,quantity,price,buy_date,sellable_on,buy_fee,order_id) VALUES(?,?,?,?,?,?,?,?)',
                                       (account_id, symbol, qty, price, today, next_days[0], fee, oid))
                            self._save_exit(db, account_id, symbol, exit_source)
                        else:
                            remain = qty
                            for lot in lots:
                                if lot['symbol'] != symbol or lot['sellable_on'] > today:
                                    continue
                                take = min(remain, lot['quantity'])
                                db.execute('UPDATE lots SET quantity=quantity-? WHERE lot_id=?', (take, lot['lot_id']))
                                remain -= take
                                if not remain:
                                    break
                            db.execute('UPDATE accounts SET cash=cash+?,fees=fees+? WHERE account_id=?', (qty*price-fee, fee, account_id))
                        evidence = {'quote': q['raw'], 'rule': rule, 'plan_sha256': digest(plan), 'calendar_sha256': digest(calendar),
                                    'buy_eligibility': result.get('buy_eligibility'), 'global_buy_gate': result.get('global_buy_gate'),
                                    'research_proof': result.get('research_proof'), 'stock_snapshot': stock,
                                    'exit_source': exit_source,
                                    'plan_stop_loss': stock.get('stop_loss'), 'plan_take_profit': stock.get('take_profit'),
                                    'time_source': account['time_source'], 'fee_model': fee_model,
                                    'accounting': 'gross_zero_fee_assumption' if fee_model['model'] == 'zero_fee_assumption' else 'explicit_flat_fee_simulation'}
                        db.execute('INSERT INTO fills(account_id,order_id,symbol,side,quantity,price,fee,quote_key,at,trade_date,evidence_json) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                                   (account_id, oid, symbol, side, qty, price, fee, q['key'], at.isoformat(), today, canonical(evidence)))
                        result.update({'event': 'paper_filled', 'fill_quantity': qty, 'filled_quantity': previous_qty+qty,
                                       'price_cents': price, 'fee_cents': fee,
                                       'status': 'filled' if previous_qty+qty == (target if side == 'sell' else requested) else 'partial'})
            except PaperError as exc:
                result.update({'status': 'partial' if previous_qty else 'rejected', 'reason': str(exc)})
            if result['status'] == 'pending' and previous_qty:
                result['status'] = 'partial'
            db.execute('UPDATE orders SET status=?,filled_qty=?,last_at=?,result_json=? WHERE account_id=? AND order_id=?',
                       (result['status'], result['filled_quantity'], at.isoformat(), canonical(result), account_id, oid))
            db.execute('UPDATE accounts SET last_at=? WHERE account_id=?', (at.isoformat(), account_id))
            return result

    def snapshot(self, account_id, *, now=None):
        at = self.clock(now)
        with self.transaction() as db:
            a = self._account(db, account_id, at)
            lots = [dict(r) for r in db.execute('SELECT * FROM lots WHERE account_id=? ORDER BY lot_id', (account_id,))]
            positions = {}
            for lot in lots:
                if not lot['quantity']:
                    continue
                p = positions.setdefault(lot['symbol'], {'quantity': 0, 'sellable_quantity': 0, 'cost_cents': 0})
                p['quantity'] += lot['quantity']
                p['sellable_quantity'] += lot['quantity'] if lot['sellable_on'] <= at.date().isoformat() else 0
                p['cost_cents'] += lot['quantity'] * lot['price']
            fills = [dict(r) for r in db.execute('SELECT fill_id,order_id,symbol,side,quantity,price,fee,quote_key,at,trade_date FROM fills WHERE account_id=? ORDER BY fill_id', (account_id,))]
            orders = [json.loads(r[0]) for r in db.execute('SELECT result_json FROM orders WHERE account_id=? ORDER BY created_at,order_id', (account_id,))]
            exits = {r['symbol']: json.loads(r['source_json']) for r in db.execute(
                'SELECT symbol,source_json FROM exit_plans WHERE account_id=?', (account_id,))}
            return {'environment': 'paper', 'account_id': account_id, 'cash_cents': a['cash'], 'initial_cash_cents': a['initial_cash'],
                    'fees_cents': a['fees'], 'fee_model': json.loads(a['fee_model']), 'seed_source': a['seed_source'],
                    'authorization_id': a['authorization_id'], 'time_source': a['time_source'], 'positions': positions,
                    'lots': lots, 'fills': fills, 'orders': orders, 'managed_exit_plans': exits, 'as_of': at.isoformat()}
