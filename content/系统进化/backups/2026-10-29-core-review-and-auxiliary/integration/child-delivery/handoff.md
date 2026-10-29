# INPUT-01 handoff (synthetic verification only)

## Outcome
Only scripts/research/build_research_summary.py and new tests/pipeline/test_bound_auxiliary_inputs.py were changed by this task. The normal summary CLI now passes approved_d1_auxiliary_paths(date) from reviewed code into make_summary; --verify-inputs passes the same scope into verify_saved_inputs. No CLI/config opt-in or new data directory was added.

input_manifest.bound_auxiliary_inputs binds the two exact same-day existing paths to their SHA/bytes/mtime and the current main manifest versions including run/attempt receipts. Auxiliary payloads are returned separately by consume_bound_auxiliary_inputs(..., approved_paths=approved_d1_auxiliary_paths(date)), never added to artifacts.R1-R7. No caller scope means no auxiliary reads. Candidate adapters remain pending/approved_adapter_only and cannot authorize this consumer. Missing/invalid-at-bind snapshots have unavailable records with no fabricated payload and remain gaps even if files later arrive; available-version drift is rejected. Original vetoes, partial objects, zero/None, no_trade and zero cap remain unchanged.

## Verification
Collection-before-import guard blocks production data/.env/account/DB access, external network/process execution, and writes outside scratch. Guard self-tests exercised allowed scratch read/write and synthetic denied boundaries before collection. No test-run violations and no tested-source drift.
- New independent suite: 28 passed.
- Original signed-input 16 cases: passed unchanged.
- Full concurrently updated queue: 44 passed, 1 failed (twice). Existing test_signed_input_review_contract.py changed externally from its saved baseline and gained test_confirmed_required_review_scope_and_auxiliary_downgrade_are_explicit; its R6 docs assertion required 资金与消息交叉, absent from docs/agents/R6-反证Agent.md. That file/test was not modified here.
- Explicit final selection: 44 passed, 1 deselected; exclusion is exactly tests/pipeline/test_signed_input_review_contract.py::test_confirmed_required_review_scope_and_auxiliary_downgrade_are_explicit. This is not a claim that the full 45-case queue passed.
- Saved receipts: test_receipt-first-failure.json, test_receipt-full-current-failure.json, test_receipt.json. Baseline bytes and SHA are retained next to them; round-only.diff is this task's two-file diff, not a git diff.
- Unrelated make_summary orchestration imports were substituted in synthetic fixtures; snapshots, primary collection, delivery receipts, make_summary, consumers and verify_saved_inputs were real. No production replay or LLM-read/adoption claim.

## Parent-only caller changes still required (not applied)
1. scripts/research/run_research_shell.sh: existing summary/--verify-inputs CLI calls now bind/check auxiliary inputs without call-flag changes. Replace only the prompt's blanket attention/emotion prohibition with explicit permission to use the bound two-snapshot consumer and retain the prohibition for corrections/calendar/observation/accounts. D1 must obtain the actual auxiliary payloads from consume_bound_auxiliary_inputs(saved, root=ROOT, approved_paths=approved_d1_auxiliary_paths(date)); file flags cannot grant authority. Add the same --verify-inputs call AFTER D1 returns and BEFORE accepting/publishing its delivery, using the original owner run_id. Prompt must retain unknown/unavailable and must not claim required gates completed from mere binding.
2. scripts/plan/ensure_watchlist_plan.py: at D1 initial/final preflight (current lines 284 and 341) import approved_d1_auxiliary_paths alongside verify_saved_inputs and add auxiliary_paths=approved_d1_auxiliary_paths(date) to both calls. Apply the same scope to the bound-plan/event snapshot verification around line 486 if that path promises full D1 input replay. Do not change the pure-R1-R7 consumer around line 630. Align _LLM_PROMPT with shell prompt and call the bound consumer for actual model-readable auxiliary data. Compare the same saved summary fingerprint at completion; do not rebuild/rebind missing inputs during D1.
3. Both callers: legacy summaries lacking bound_auxiliary_inputs are not silently upgraded from approved_adapter_only; report a binding gap and return to the existing research owner. Do not let D1 manufacture a new manifest/approval.

## Parent-only skill wording suggestion (not applied)
In main_decision_v1 本轮版本与辅助读取边界, state that user approval now covers only data/research/{date}/attention_signals.json and emotion_cycle.json as existing snapshots. Require the reviewed-code exact scope plus current input_manifest.bound_auxiliary_inputs and the actual separate consumer; verify the same summary/main/auxiliary versions before and after the run. Unavailable is a gap, not zero/false/no-risk, and permits no fetch or substitute dates. Other candidates, error books, calendar and account access remain unapproved. Read permission never changes writes, trade permission, R6 vetoes, no_trade, zero budget or required-gate readiness. Keep event-reassessment boundaries separate. Do not modify R6 skill/schema under this task.

## Final source SHA and baseline drift
```json
{
  "sha256": {
    "scripts/research/build_research_summary.py": "32336a82851263497d0630e0f83ab5ae0004cd3518d4e316bb87067f5cce9fcc",
    "tests/pipeline/test_bound_auxiliary_inputs.py": "166ffe44ccc8cda58e65b3a1254bdb0fbcd207dd98d28645ea749ad7058ab25c"
  },
  "shared_baseline_drift": {
    "scripts/research/build_research_summary.py": true,
    "tests/pipeline/test_signed_input_review_contract.py": true,
    "scripts/research/run_research_shell.sh": false,
    "scripts/plan/ensure_watchlist_plan.py": false
  },
  "test_exit": 0,
  "violations": []
}
```
