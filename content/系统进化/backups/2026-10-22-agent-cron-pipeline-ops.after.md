---
name: agent-cron-pipeline-ops
description: Debug agent cron pipelines that daily produce data files.
version: 1.0.0
author: hermes
license: MIT
metadata:
  hermes:
    tags: [cron, pipelines, agents, devops, scheduled-jobs]
    related_skills: [data-freshness-audit]
---

# Agent-Cron Pipeline Ops

## When to Use

- User complains scheduled tasks "make the directory messy", "use stale/old data", or "keep failing silently".
- Auditing or reworking `hermes cron` jobs that run agent skills / scripts producing daily files (research pipelines, fetchers, watchers, review agents).
- Wiring a corrections/feedback store so daily decisions actually consume past lessons.

Class-level playbook for the recurring failure modes of **agent-powered scheduled pipelines** — crons that kick off LLM agents or scripts which read data, produce artifacts, and write files day after day. These systems rot in predictable ways; most "my cron is making a mess / using stale data" complaints are one of the patterns below.

## Step 0 — Map the pipeline before touching anything

- Separate model invocation, tool execution, business completion, delivery, and consumer reload before naming the cause. A generated news report proves that invocation ran; it does not prove the decision stage ran under the correct identity or delivered its files. Inspect the failing stage's own log before recommending a model switch.
- Trace each launcher to its actual `-p` profile and compare every requested output with that profile's write whitelist. A preloaded skill does not grant write authority. Route each stage to its owner, preserve that identity on retries, and test the real argv with a fake Hermes executable; do not broaden permissions to conceal a routing bug.
- For background wrappers, distinguish “worker launched” from “business completed.” A `nohup ... &` followed by exit 0 cannot certify later stages. Compare the scheduler's finish time with the worker log and existing business-health artifact; report both layers separately.
- Establish a baseline before editing: inspect staged/unstaged/untracked state, run relevant isolated tests, and record pre-existing failures. Do not infer an interrupted edit from dirty files or sparse Git history; state when authorship and timing are unproven.
- Keep model migration independent from pipeline repair. When the user elects to retain the model, preserve the provider/model settings and diagnose routing, contracts, delivery and consumers without changing trading rules.
- List all active crons (`hermes cron list`) — the user's `cron list` often shows MORE jobs than the obvious ones; enumerate all of them (active + paused).
- For each job note: schedule, script, workdir, last-run status, and **what files it writes and where**. Read the wrapper script under `~/.hermes/scripts/` (Hermes cron scripts live there, NOT in the repo's `cron/`).
- Check `git status` to see what's polluted — but remember machine output may be gitignored already (file-system mess ≠ git mess).

## Pattern 1 — Agent crons dump temp scripts where nothing forbids it

An agent-type cron (runs a skill, `execute_code` often unavailable) frequently writes a throwaway `.py`/`.sh` to **repo root or `data/raw/`** because the skill says nothing about output paths. This has bitten TWICE (small-cap miner → repo root; event-tracker → `data/raw/YYYYMMDD/`).
- Fix: the skill that the cron loads MUST carry a **"Cron 模式" section** with explicit output-path discipline: temp scripts go to a gitignored `scripts/<area>/_tmp/`, run-and-delete after use; only real data files land in `data/raw/`; the final report goes to its one canonical path.
- Add the `_tmp/` dir to `.gitignore`.
- Clean the already-dumped files (verify the real output artifact exists first — e.g. the md report — before deleting the temp script).

## Pattern 2 — Consumer runs before its producer → stale data

Classic: research pipeline at 07:00, data fetch at 07:15 → the news unit consumed Friday's data with "回推" and missed Monday's morning news entirely (worst on Mondays).
- Fix BOTH sides: move the producer earlier AND make the consumer wrapper **wait for the producer's manifest** before launching (`for i in $(seq 1 N); do [ -f manifest ] && break; sleep 10; done`).
- Diagnose by comparing file mtimes of the consumer artifact vs its upstream input — a unit generated before its input file's mtime is an ordering bug, not a data outage.

## Pattern 3 — Log accumulation with no rotation

Every run writes a timestamped log (`data/logs/<job>/<ts>.log`) and never cleans up → hundreds of files. Even a 100% failing job still writes an error log each run.
- Fix: add rotation INSIDE the wrapper right after `mkdir -p`: `find "$LOG_DIR" -type f -name '*.log' -mtime +N -delete` (N = 7–30 depending on value). Also sweep old per-day dirs with `-maxdepth 1 -type d -name '20*' -mtime +30 -exec rm -rf {} +`.
- A zombie job that targets a removed backend (dead ngrok/MCP) runs 100% error forever: **pause the cron** (reversible) rather than delete, and note the backend is dead.

## Pattern 4 — Write-only feedback loops (corrections never fed back)

A system can "reflect" beautifully (E1 writes error_case_*.md with verification) while daily decision agents in fresh context never read them — the same mistake recurs despite being documented. Proof: W30 already had "R6 blanket bear case" and "R2 mainline miss" cases, and W36 repeated them.
- Fix the READ side, not just the write side:
  - Make the reader interface match the current format (`get_all_corrections` only globbed legacy `CORR_*.json` while the corpus was `error_case_*.md` → 39 cases unread).
  - Inject recent corrections into the daily decision skill as a **Step 0.4**: read last-3-weeks `error_case_*.md`, for each hit state whether today's plan avoids that mistake, and record `corrections_applied` in the plan's meta so you can verify the loop later.

## Pattern 5 — macOS cron-script pitfalls

- **No GNU `timeout`** on macOS (it's `gtimeout` from coreutils). A script using `timeout 300 ...` fails with "command not found" on a Mac. Use pure bash: run the command in background, poll for the output file up to N×sleep, then `kill $PID` if not done.
- No `seq`-safe timeouts with `#!/bin/bash` — fine, but always `bash -n` the wrapper after editing.
- `timeout`-style language and `-exec rm -rf {} +` triggers smart-approval on recursive deletes — expected, not an error.
- **A wrapper script must call the project interpreter explicitly (`.venv/bin/python`), never bare `python3`.** The system `python3` lacks the project's deps, and when the failing call is a **gate** written as `VAR=$(python3 -c ... 2>/dev/null || echo 0)`, the interpreter error is swallowed into the fallback — a trading-day check returned `0`, so the job printed *"非交易日, 跳过"* and exited 0. `hermes cron list` shows it healthy while it never does any work, and the wrong branch is indistinguishable from a real holiday. Rule: **gates must fail loud** — no `2>/dev/null || echo <benign value>` around a check, and any shell-out needing a library uses the venv interpreter path. To verify a gate, run the wrapper once on a **known trading day** and confirm it proceeds past the gate, not merely that it exits 0.

## Pattern 6 — Serial LLM steps blow a hard real-world deadline

A research pipeline whose DAG is serial (R5 → R6 → D1) can run the final decision step 10+ minutes past a hard wall-clock deadline (e.g. D1 预案 must land before 09:28 竞价校准). Symptom: the downstream P1/P2 job runs on time but reports `timeout_no_amendment` because its required input (the plan) didn't exist yet. Diagnose by reading the pipeline log's per-step `launching R*` timestamps — the bottleneck is the slowest serial step (an N-stock profile step can take 40 min), not the final step itself.
- Fix the scheduling, not the deadline: give the downstream a **safety-net fallback cron** that runs ~15 min before the deadline — a script (`ensure_*.py`) that is idempotent: if the real artifact already exists it exits silently (empty stdout = `--no-agent` cron doesn't disturb), else it generates a rules-based fallback. Then the deadline-facing job (P1) always has input.
- Also trim per-step budget: LLM-agent steps with `--max-turns 80` each do dozens of turns; dropping to ~60 materially shortens the long tail. Keep quality checks (schema-valid JSON, md contract) as the success gate, not turn count.
- A fallback script that exists on disk but has **no cron entry referencing it** is dead config — check `hermes cron list` for the job before trusting that a safety net is deployed.
- **"Idempotent" over file-existence alone silently pins the first (worst) run.** The safety net skipped whenever `plan.json` existed, but the 08:30 fallback had been built BEFORE its upstream inputs landed (R5 08:33, R6 08:52) → empty result frozen for the whole day, and the 09:20 re-run never rebuilt it. Make idempotence check **input freshness**: compare the fallback artifact's `generated_at` against mtimes of its key upstream artifacts; rebuild when upstream is newer. Always exempt the real (LLM/main-path) artifact from being overwritten — identify it by a marker (`meta.python_fallback` / `agent_name`), not by mtime alone.

## Pattern 7 — Provider quota exhaustion ≠ rate limit; retry won't fix it

LLM API errors come in two flavors and need different handling: **rate limit** ("Requests are too frequent", resets in seconds) is fixed by retry with backoff; **quota exhaustion** ("You have exceeded the 5-hour/weekly usage quota. It will reset at <time>") resets only on a clock boundary — retrying is pointless and burns time. A 5-hour quota can be exhausted mid-pipeline: R1-R5 eat the window, R6/D1 die at 08:00+, and (worse) this repeats day after day at roughly the same wall-clock position because the window rolls.
- Retry logic must distinguish them: check the log for `usage quota`/`exceeded` (quota → wait for reset, don't hammer) vs `rate.limit`/`too frequent` (backoff and retry). A grep for bare `exceeded` is a false-positive trap — model output routinely contains "exceeded max turns"; match the specific quota phrase.
- Mitigate structural quota pressure: pin the provider+model explicitly on every agent cron (a model-switch can silently drift jobs), cut per-step turns, and keep a second provider as a nightly-refresh home for the heaviest jobs.
- **Unpinned jobs drift to a dead endpoint and 404 every day, silently.** Concrete signature: `request.url = https://api.minimaxi.com/anthropic/chat/completions` while `request.body.model = ark-code-latest` — the model id belongs to one provider, the URL to another. `hermes cron list` reports it plainly (**`error: HTTP 404 ... (N failures in a row)`**) but nothing else surfaces it, so a decision job can be dead for five weeks while nobody notices; the daily artifacts still appear because a fallback wrote them. Audit: dump every job's `provider`/`model` and treat `None` on an agent-type job as a finding, then check the last N `request_dump_cron_<id>_*` for `error.status_code`. Fix with `hermes cron edit <id> --provider <p> --model <m> --pin`.

## Pattern 8 — Gates that `continue` hide their own failures

A filter that drops a candidate with a bare `continue` leaves no trace: the item is absent from the output, absent from every secondary list, and the artifact still looks schema-valid (empty pool = "no opportunities today"). The pipeline reports success while producing nothing.
- **Every drop must be recorded with a reason** and surfaced in the artifact (`data_sources.grade_gate_drops: [{ts_code, role, stage, reason}]`). Then "why is exec empty?" is a lookup, not an investigation.
- **Demote, don't delete**: a candidate rejected by one gate should land in the next-tier list (watch pool) with `reason_code=gate_dropped`, so the invariant holds — *every input is in exactly one visible bucket (execute / watch / rejected), never in none*.
- **Cross-check input vs output counts**: if R2 nominates 6 leaders and the plan shows 2, the other 4 must be explained. A count mismatch between a producer's nominations and the final pool is the fastest detector of this class. Verify per-item, not in aggregate.

## Pattern 9 — A missing field read as "worst possible" inverts a filter

Grading/threshold filters often map unknown values to a low rank. When the upstream **never emits the field at all**, the entire comparison degrades silently: a `risk>=B` clause becomes permanently false, or permanently true (the gate stops filtering). Both are bugs, and neither raises an error.
- Detect: grep the producer's output for the field across many days **before** trusting any filter that reads it (`0/330 profiles across 30 days` → the field has never existed).
- Detect: read the docstring/contract for a documented degrade default ("missing → default B") and verify the code implements it; a documented default that the code ignores is a high-signal find.
- Fix at the source (make the producer emit it) *and* at the consumer (apply the contracted default via one helper, e.g. `_effective_grades()`), then re-check that the gate still discriminates — a default that makes the filter always-true is not a fix.
- Quantify the blast radius before/after across historical artifacts (`old_pass → new_pass` per day) so the change is auditable and you can spot over-correction.

## Pattern 10 — Single-path logic that self-defeats in strong conditions

A pipeline that admits candidates through exactly **one** entry condition will be empty precisely when the market is most tradeable. Example: entry required "pullback to the 50-day line", but in a hot momentum regime leaders sit 20–30% *above* that line, so the condition can never be satisfied — the stronger the session, the more certain the empty output.
- Symptom: the pool is empty/undersized on strong days and full on quiet days (inverted from intuition). Check by grouping historical outputs by regime, not by date.
- Fix: make the entry channel **conditional on a regime/mode input** (e.g. style classification), with an explicit conservative fallback to the original single channel when that input is missing. Never widen the gate unconditionally.
- When the operator's own playbook has N channels (aggressive / pullback / follow), the code must implement N paths — if runtime code already looks up a channel by type but the producer never emits it, the missing half is the producer, not the executor.
- Some candidates are legitimately un-enterable *today* (limit-up locked, no intraday liquidity). Keep them visible with an explicit no-chase flag rather than dropping them — the flag tells the human "this is why I can't act", an omission tells them nothing.
- **A human-readable artifact must render the actionable numbers, not counts.** A renderer printing `entry_rules: 2 条` while holding full price zones in JSON makes a working plan look empty; the user sees "no plan" and blames the agent. Assert the rendered output contains the concrete values (prices/zones/logic) whenever the JSON has them.

## Pattern 11 — A fallback that impersonates the primary path is worse than no artifact

A "safety net" is not a background detail: once the primary path breaks, **the fallback IS the primary path**, every day. If it does not announce itself, the operator reads a degraded artifact as a real decision.

Concrete failure: a D1 decision cron 404'd every trading day for ~5 weeks; the 08:30 safety net then wrote a **pure-Python rules plan** labeled `mode="live"` with `agent_name="D1-main-decision (main_decision_v1, rule v1)"` and `execution_pool=0`. The human-readable plan carried `mode: live` in its frontmatter and the literal string `"D1 规则版 v1: ... mode=live."` in its body — indistinguishable from a normal day. The user's conclusion was "D1 just gave me no picks today"; they never suspected the LLM had never run. When they finally read it they challenged the architecture itself ("my hard requirement is that the LLM makes the decision, how can a pure price-volume Python program decide?")

Rules:
- **Every degradation level gets a truth field** on the artifact — `decision_source: llm | rule_v1_standalone | python_fallback`, plus `is_fallback` — and the human artifact renders it in a loud banner naming *what failed and where to look*, not just "error".
- **Enforce it in code**, not by convention: an `assert not (fallback and mode == "live")` turns a labeling slip into a crash. Note which paths are which — a builder function used only by the rules path must never emit `decision_source="llm"`.
- **Refuse to emit a degraded artifact when its required inputs are missing.** "No plan yet" beats "a plausible-looking empty plan": the empty rule plan flowed all day into auction calibration as if valid. Gate the fallback on upstream readiness and let the next tick retry.
- **A fallback must retry the primary path first**, not only substitute for it. Order: real artifact present → exit silently; else re-run the LLM with a realistic timeout; only then fall back, loudly.
- **Deduplicate the nets and lock them.** Several jobs pointing at the same `ensure_*` script can start concurrent duplicate decisions, burning quota and overwriting each other's output; take a pid lock (with a stale-lock timeout) around the expensive path.
- **The fallback's own timeout must match the task's real duration.** A retry budget of 600s against a step that measurably needs 26–39 min makes the retry path decorative.

## Pattern 12 — "Why does this take two hours?" — measure before optimizing

The instinct — and usually the operator's first hypothesis — is "the data fetching is slow". Measure before agreeing or rebuilding anything.

Method: parse the agent log for per-call `API call #N ... latency=Xs in=T out=U` and `tool <name> completed (Xs)`, then sum by category.

Worked example (152-min serial pre-market pipeline):

| Category | Time | Share |
|---|---|---|
| LLM calls (245 of them) | **133 min** | **91%** |
| ALL tool execution (343) | 13 min | 9% |
| — of which MCP data fetches (76) | 9 min | 6% |

Data fetching was 6% of wall clock. The real cost was **per-call context**: every session opened at 28–48k input tokens before doing any work — 29 tool schemas at 54k chars (the `tool_search` meta-tool alone was 15k chars / 3.7k tokens and went unused all day; unused tools totalled ~39k chars ≈ 9.8k tokens re-sent on *every* call), a 26k-char system prompt, and the skill body injected **twice** (system prompt *and* the user message, ~11k tokens of pure duplication). Latency scaled with input size: `<50k → 11s`, `50–100k → 18s`, `100–150k → 37s`, `>150k → 54s`.

- Fixes here are **config, not architecture**: disable unused toolsets, stop injecting a skill body twice, and parallelize serial vision/render calls (one loop of 12 serial `chart_vision_analyze` calls cost 500s = 64% of all tool time).
- Also inspect call *counts*: hundreds of `execute_code`/`terminal` calls (112 + 45 today) mean agents are hand-probing data with ad-hoc scripts instead of one repository data tool.
- Only after this analysis should you touch schedules — and re-derive them from the **measured** critical path, not the documented intent.

## Pattern 13 — A producer whose artifact nobody reads (orphan analysis)

A scheduled job can be 100% healthy and still be pure waste: it runs, spends real money, writes a file — and no consumer anywhere reads it. `hermes cron list` shows green, so nothing flags it, and the operator only notices as a vague "why is this burning so much?"

- **Detect by consumer reference count.** For every scheduled producer, grep its output filename/path across `skills/`, `src/`, and the other scripts. References only in its own writer (and in a health check) = orphan. The real consumer's skill is the decisive place to look: if the skill that *should* read it has zero mentions, the artifact is dead no matter how fresh it is.
- **Second detector: hardcoded input lists.** A snapshot/analysis script whose universe is a literal list of tickers instead of today's nominated candidates silently degrades into "compute on irrelevant names". Measure the intersection between the artifact's coverage and the pipeline's actual candidates — near-zero overlap confirms it, and it stays invisible while the file's schema looks perfect.
- **Cost the waste in units the operator feels.** "2 runs/day × 12 tickers × 40s ≈ 24 vision calls/day on names nothing reads" lands; "there is an orphan file" does not. Also check the ordering: an artifact written *after* its theoretical consumer already ran can never be read that day even if the consumer did reference it.
- **Fix by choosing a state, don't leave it running-and-ignored.** Either delete the job, or make its output a **reader-side cache**: the consumer checks it first and only falls back to live calls on a miss — and in that case the producer must be **input-driven** (read today's candidates), never a hardcoded pool.
- **Check both directions before deleting.** That nothing reads its artifact, AND that no other job duplicates the same work under a different name (same script, same toolset, different cron id → one job).

## Pattern 14 — Nobody is alerted to a repeated failure

The worst outage in this class is not a crash, it is a **streak**: a job failing every single day for weeks, visible only in `hermes cron list`. The daily artifacts still appear because a fallback wrote them, so the operator's inputs look normal right up until they question a decision built from fabricated data.

- Any job whose `failure_streak` reaches a small threshold (≈3) must **page the operator through a channel they already read** (the morning briefing / push), not merely record an error field in a file nobody opens.
- Implement it on the health-check job that already runs — iterate `hermes cron list` and surface every job with a streak. Do not stand up a second monitoring stack for this.
- "Artifact exists" is insufficient evidence of health: also verify the artifact's own `decision_source` / mode marker. A fallback path produces a file on exactly the days the primary failed, which is why existence checks alone stay green through a weeks-long outage.
- Audit `provider`/`model` on every agent job in the same pass — an unpinned job is the most common seed of a silent streak (see Pattern 7).

## Verification checklist

- Isolate production output paths in every regression test, including HTTP/API tests; synthetic fixtures must never be written into historical runtime or report directories.
- Preserve YAML frontmatter at the beginning of a backfilled human report, and record original research time, rendered-draft time (when different), and actual delivery time separately; delivery repair must not masquerade as fresh research.
- Validate canonical plan content before atomically refreshing runtime copies; malformed input blocks that pass, and account settings must not expand the plan's trading authorization.

- Exercise launchers in a temporary sandbox with a fake Hermes command: success, nonzero exit, rate-limit response, exit 0 without fresh output, and pre-existing stale output. Assert actual profiles, retry identity, canonical output paths and business terminal state; syntax checks alone do not establish recovery.
- Verify the downstream reader, not just the writer: a new canonical plan can remain unused when an existing runtime or loaded copy suppresses staging/reload. Test source selection and safety flags in isolation; never run the live executor merely to validate file handoff.
- Separate acceptance claims: a schema-valid LLM no-trade report restores decision delivery, not missing upstream research or a usable trading plan. Do not present an infrastructure-induced empty pool as proof that the market has no opportunities. Mark intraday recovery with its real generation and source-data times instead of backdating it to premarket.
- Treat test collection as executable code. Inspect legacy integration modules for import-time network calls and `exit()` before broad discovery; record collection blockers and baseline failures without weakening trading gates or deleting assertions merely to obtain green results.
- Before an authorized Git checkpoint, review exact paths and scan for credentials, private runtime outputs and caches. Preserve unrelated staged work; commit verified source, tests and necessary dependencies explicitly, report excluded work and the actual commit hash, and do not claim a whole-repository clean state unless checked.
- `bash -n` on every edited `.sh`; `py_compile` on every edited `.py`.
- Re-run any single-test/check the pipeline ships (e.g. `tests/checks/check_r7_staleness.py`) — it may assert the exact thing you changed.
- Confirm cron schedule changes via `hermes cron list` (`Schedule:` line + `Next run`).
- For a "feedback loop" change, pick a concrete field the next run WILL produce (e.g. `meta.corrections_applied`) so you can verify the loop actually closed — don't trust that it worked.

## References

- `references/canghai-cron-hygiene-20260831.md` — full worked session: 15-job canghai pipeline audit, 6 fixes (fetch 06:45, manifest-wait wrapper, chart_vision 06:50+fallback, R7 trading-day staleness, event-tracker cleanup, group rename, watch_pool 20–40).
