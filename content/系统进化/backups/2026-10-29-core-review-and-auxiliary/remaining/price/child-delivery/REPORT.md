# PRICE-02/03 limited internal repair, not full acceptance

## Applied scope
Only src/plan/price_levels.py changed in production; new independent tests/pipeline/test_price_contract_alignment.py. No other production/test file, skill, plan, budget, permission, data, kb, credential, DB, network, model or git operation was used. Original bytes are in before/, final bytes in after/, exact patch in only.diff. Basetemp parent existed before pytest. Reviewed original chart runner was reused via runpy; an additional pre-collection import/SQLite guard was installed before pytest. All native audit outputs show zero violations; every per-run source digest is stable. No assertions were removed, xfailed or filtered.

## Internal outcomes
- Missing/unknown/omitted derive channel fails before technical lookup, with no buy zone, trigger or RR. Existing explicit recognized channels remain accepted.
- Existing below-market >10% unreachable classification now returns unusable original-channel evidence, original buy zone retained, trigger/RR absent; automatic MA10 replacement was removed. No alternate zone/stop or new price was invented.
- PRICE-01 raw/rounded stop geometry rejection is retained byte-for-byte; all 13 geometry cases passed.
- Planned scenario still uses the existing buy-zone upper edge for base stop, two-decimal risk and RR, and two-decimal output. Trigger is an entry condition, NOT an alternative proposed buy price. Existing stop percentages, RR 1.8, buy-zone formulas and sizing tiers are unchanged. No tick tolerance was introduced.
- Consumer evaluate_stock_buy_eligibility already recomputes each actual proposed price. _buy_common uses explicit max_acceptable_ask as limit, else ask; a passing planned-zone RR does not mean its higher maximum-ask limit qualifies. Tests exercise planned and actual-limit scenarios separately and existing rounding boundaries.

## Exact unimplemented caller changes (scripts/plan/apply_price_levels.py)
1. pick_channel lines 29-46 must return None for empty/no recognized ORIGINAL channel rather than trend_pullback_buy; it must not load technical data or select divergence from ref/MA10>8%. Explicit original recognized single channel must be returned unchanged. Existing generated engine entries are not original channel authorization.
2. apply_to_plan.run lines 81-89 must pass that optional channel without a fallback; derive now fails closed on None. Rejected evidence replaces stale qualification; do not synthesize entry_rules, rewrite existing entry/exit rules or change pool/budget/permission. No call-stack introspection should be added inside derive to detect fabricated caller authorization.
3. Conflicting multiple original channel rules cannot be represented by one stock-wide engine_levels. Safe immediate behavior is unknown/no generated new price; a per-rule scenario/evidence design needs explicit owner contract. Do not choose first rule or switch strategy to keep a candidate.
These changes are necessary to close PRICE-02 end-to-end and were NOT applied because only price_levels.py is writable in this task. New tests retain three real caller failures (watch empty, B empty, explicit trend overwritten).

## Remaining policy and compatibility boundaries
- PRICE-03 has no justified numeric algorithm change from this inspection: planned vs actual are already distinct consistent scenarios. Making max_acceptable_ask or trigger the shared planned stop/take basis, or moving the existing max limit to preserve RR, changes risk policy; it was not implemented. Owner must decide if unified reporting should show both scenario-qualified RRs. Eligibility remains NOT authorization.
- Actual exchange minimum tick by instrument is not defined by these modules. Current 2-decimal representation is preserved; no exchange-valid tick or new epsilon/tolerance is certified.
- The existing >10% unreachable heuristic is not an exchange-specific full-day reachability proof; upper-limit reachability or instrument-calendar/tick rules need an existing approved contract. Explicit trend with missing MA50 still has the existing ref fallback; removal/redefinition is a separate precise policy question, not evidence of a measured MA50.
- One unchanged old RR test invokes derive without explicit channel; it now fails because implicit authorization is intentionally removed. Recommended test migration is to add channel=trend_pullback_buy to its two explicit-formula calls, retaining assertions; historical test was not edited.
- Four other old RR failures reproduce on original before/ source: FixtureContext missing sell_position_state (one); omitted trading.execution_authorization from isolated copy closure (three). Do not relax authorization or change sell production to make these pass. Parent may repair only the synthetic copy closure/type fixtures under separate file authorization.
- All tests are synthetic/offline; natural production adoption, current-day plans and trading permission are untested/unchanged. These items are not fully closed.

## Skill suggestion only
Document explicit channel selection, no empty-entry MA50 fabrication or unreachable MA10 substitution, separate planned-high and actual-proposed-limit RR, and unchanged quote precision/no invented tolerance. No skill was edited.

## Native results and exact versions
See results.json and commands.txt; all three native pytest returns were 1, wrapper audit violations and source drift were zero. All full queues ran without -k or maxfail. Native XML and logs are baseline.xml/.log, joint.xml/.log, baseline_rr.xml/.log. Counts below are programmatically parsed; overlapping queues must not be added.

```json
{
  "baseline": {
    "count": 19,
    "by_file": {
      "tests.pipeline.test_price_contract_alignment": {
        "failed": 12,
        "passed": 7
      }
    },
    "failures": [
      "tests.pipeline.test_price_contract_alignment::test_missing_or_unsupported_channel_never_loads_tech_or_invents_ma50[None]",
      "tests.pipeline.test_price_contract_alignment::test_missing_or_unsupported_channel_never_loads_tech_or_invents_ma50[]",
      "tests.pipeline.test_price_contract_alignment::test_missing_or_unsupported_channel_never_loads_tech_or_invents_ma50[unknown]",
      "tests.pipeline.test_price_contract_alignment::test_missing_or_unsupported_channel_never_loads_tech_or_invents_ma50[MA50]",
      "tests.pipeline.test_price_contract_alignment::test_missing_or_unsupported_channel_never_loads_tech_or_invents_ma50[low_absorption_intraday]",
      "tests.pipeline.test_price_contract_alignment::test_omitted_channel_is_not_implicit_authorization",
      "tests.pipeline.test_price_contract_alignment::test_unreachable_explicit_trend_keeps_original_zone_never_switches_ma10[False]",
      "tests.pipeline.test_price_contract_alignment::test_unreachable_explicit_trend_keeps_original_zone_never_switches_ma10[True]",
      "tests.pipeline.test_price_contract_alignment::test_existing_ten_percent_unreachable_boundary_without_new_tolerance[89.99-False]",
      "tests.pipeline.test_price_contract_alignment::test_caller_empty_entry_without_channel_must_not_manufacture_ma50[watch_pool]",
      "tests.pipeline.test_price_contract_alignment::test_caller_empty_entry_without_channel_must_not_manufacture_ma50[b_plan]",
      "tests.pipeline.test_price_contract_alignment::test_caller_cannot_replace_explicit_legal_trend_with_divergence"
    ],
    "exit": 1
  },
  "joint": {
    "count": 141,
    "by_file": {
      "tests.pipeline.test_price_contract_alignment": {
        "passed": 16,
        "failed": 3
      },
      "tests.pipeline.test_price_geometry_validity": {
        "passed": 13
      },
      "tests.test_canghai_rr_scope_20261023": {
        "passed": 104,
        "failed": 5
      }
    },
    "failures": [
      "tests.pipeline.test_price_contract_alignment::test_caller_empty_entry_without_channel_must_not_manufacture_ma50[watch_pool]",
      "tests.pipeline.test_price_contract_alignment::test_caller_empty_entry_without_channel_must_not_manufacture_ma50[b_plan]",
      "tests.pipeline.test_price_contract_alignment::test_caller_cannot_replace_explicit_legal_trend_with_divergence",
      "tests.test_canghai_rr_scope_20261023::test_actual_common_buy_blocks_only_bad_stock_and_sell_still_runs",
      "tests.test_canghai_rr_scope_20261023::test_dispatch_global_gate_does_not_stop_legal_sell_or_research",
      "tests.test_canghai_rr_scope_20261023::test_actual_dispatch_mixed_rr_has_no_global_contagion",
      "tests.test_canghai_rr_scope_20261023::test_real_engine_formula_2r_and_1_8_threshold",
      "tests.test_canghai_rr_scope_20261023::test_scoped_dispatch_keeps_good_buy_bad_sell_and_watch"
    ],
    "exit": 1
  },
  "baseline_rr": {
    "count": 109,
    "by_file": {
      ".hermes.cache.scratch.premarket-all-price-20261029.before.tests.test_canghai_rr_scope_20261023": {
        "passed": 105,
        "failed": 4
      }
    },
    "failures": [
      ".hermes.cache.scratch.premarket-all-price-20261029.before.tests.test_canghai_rr_scope_20261023::test_actual_common_buy_blocks_only_bad_stock_and_sell_still_runs",
      ".hermes.cache.scratch.premarket-all-price-20261029.before.tests.test_canghai_rr_scope_20261023::test_dispatch_global_gate_does_not_stop_legal_sell_or_research",
      ".hermes.cache.scratch.premarket-all-price-20261029.before.tests.test_canghai_rr_scope_20261023::test_actual_dispatch_mixed_rr_has_no_global_contagion",
      ".hermes.cache.scratch.premarket-all-price-20261029.before.tests.test_canghai_rr_scope_20261023::test_scoped_dispatch_keeps_good_buy_bad_sell_and_watch"
    ],
    "exit": 1
  }
}
```

Production source SHA256 before: eaac8de71f2f817638ef1a79bdf9a4de34a7008a59d315e4d135d2a56cf784fa
Production source SHA256 after: c547df87ecbf58f9e5f8ef9562e8d416c559d1681125f99d8cc11a8a97115380

All source digests: before_manifest.json, after_manifest.json, and per-run receipt.json. Restore only price_levels.py from before/src/plan/price_levels.py after checking the current source still matches the after digest; do not overwrite concurrent changes.
