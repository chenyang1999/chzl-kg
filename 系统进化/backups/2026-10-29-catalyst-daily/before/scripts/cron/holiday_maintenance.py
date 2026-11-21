#!/usr/bin/env python3
"""Holiday maintenance for 沧海巨浪 cron fleet.

Pause A-share market cron jobs across a market holiday and resume them on the
first trading day, without touching jobs that legitimately run through the
holiday.

Why this exists (2026-10-01):

* Hermes cron schedules match on day-of-week, not on the exchange calendar.
  ``0 6 * * 1-5`` fires Mon–Fri regardless of statutory holidays.
* During 国庆 (2026-10-01 .. 10-07, all closed) the A-share crons would fire
  5 of those 7 days — fetching nonexistent quotes, burning quota, writing
  empty artifacts.
* Hermes has no native "trading-day" concept, so the cheapest correct fix is
  to pause the fleet and resume it on the next open day.

Deliberately NOT paused:

* ``chzl-kg · 笔记站同步`` — knowledge-base sync, unrelated to the market.
* ``canghai-fetch · 美股晚间重抓`` — US equities trade normally; this job is
  the only correct overseas data path and must keep running.

Usage:

.. code-block:: bash

    python scripts/cron/holiday_maintenance.py --status
    python scripts/cron/holiday_maintenance.py --pause  --dry-run
    python scripts/cron/holiday_maintenance.py --pause
    python scripts/cron/holiday_maintenance.py --resume

The one-shot resume job (``canghai-holiday · 节后恢复``) is created by
``--install-resume`` and fires on the first trading day before the earliest
cron (06:00), calling this script with ``--resume``.

Exit codes: 0 ok / 1 user error / 3 unexpected.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERMES_HOME = Path(os.path.expanduser("~/.hermes"))
JOBS_PATH = HERMES_HOME / "cron" / "jobs.json"
AUDIT_DIR = Path(__file__).resolve().parents[2] / "data" / "evolution"

# Jobs matching any of these name fragments keep running through the holiday.
KEEP_RUNNING: tuple[str, ...] = (
    "chzl-kg",          # knowledge-base sync, market-agnostic
    "美股",              # US market is open
    "canghai-holiday",  # this tooling's own resume job
    "canghai-event-tracker",  # 公告日历没有休市日（2026-10-19）：放假期间照样有公告
    "canghai-weekend",        # 周末/假期情报包（群聊+公众号+新闻+公告窗口）
)

HERMES_BIN = shutil.which("hermes") or "hermes"


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #

def _load_jobs() -> list[dict]:
    return json.load(JOBS_PATH.open())["jobs"]


def _is_paused(j: dict) -> bool:
    return j.get("state") == "paused" or bool(j.get("paused_at"))


def _is_keep_running(j: dict) -> bool:
    name = j.get("name") or ""
    return any(frag in name for frag in KEEP_RUNNING)


def classify(jobs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return (market_jobs, kept_jobs) among currently-scheduled jobs."""
    market, kept = [], []
    for j in jobs:
        if _is_keep_running(j):
            kept.append(j)
        else:
            market.append(j)
    return market, kept


# --------------------------------------------------------------------------- #
# Action
# --------------------------------------------------------------------------- #

def _run_cli(action: str, job_id: str) -> tuple[bool, str]:
    proc = subprocess.run(
        [HERMES_BIN, "cron", action, job_id],
        capture_output=True, text=True, timeout=120,
    )
    return proc.returncode == 0, (proc.stdout + proc.stderr).strip()


def _audit(rows: list[dict]) -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    iso = datetime.now().isocalendar()
    path = AUDIT_DIR / f"{iso.year}-W{iso.week:02d}" / "holiday_pause_audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return path


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--pause", action="store_true", help="Pause market crons.")
    g.add_argument("--resume", action="store_true", help="Resume market crons.")
    g.add_argument("--status", action="store_true", help="Show current state.")
    g.add_argument("--install-resume", metavar="DATE",
                   help="Create one-shot resume job for DATE (YYYY-MM-DD).")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if args.install_resume:
        return _install_resume(args.install_resume, args.dry_run)

    jobs = _load_jobs()
    market, kept = classify(jobs)
    action = "pause" if args.pause else "resume" if args.resume else None
    target_state_paused = args.pause

    print(f"总 cron: {len(jobs)}  |  市场相关: {len(market)}  |  假期保留: {len(kept)}")
    print("\n假期保留运行的:")
    for j in kept:
        print(f"  [{'paused' if _is_paused(j) else 'active'}] {j.get('name')}")

    if args.status:
        print("\n市场相关 cron 状态:")
        for j in market:
            flag = "paused" if _is_paused(j) else "ACTIVE"
            print(f"  [{flag:6s}] {j.get('name')[:60]:60s} {j.get('schedule', {}).get('expr', '')}")
        n_active = sum(1 for j in market if not _is_paused(j))
        print(f"\n市场相关中仍 active: {n_active}")
        return 0

    # Which jobs actually need the transition?
    todo = [j for j in market if _is_paused(j) != target_state_paused]
    print(f"\n需要 {'暂停' if args.pause else '恢复'}: {len(todo)} 个")
    for j in todo:
        print(f"  {j['id']}  {j.get('name')}")

    if args.dry_run:
        print("\n[dry-run] 未执行任何变更。")
        return 0

    rows, failed = [], []
    for j in todo:
        ok, out = _run_cli(action, j["id"])
        rows.append({
            "ts": datetime.now().isoformat(timespec="seconds"),
            "action": action,
            "id": j["id"],
            "name": j.get("name"),
            "ok": ok,
        })
        if not ok:
            failed.append((j["id"], out))
        icon = "OK " if ok else "ERR"
        print(f"  {icon} {j['id']}  {j.get('name')}")

    audit_path = _audit(rows)
    print(f"\n审计: {audit_path}")
    if failed:
        print(f"\n失败 {len(failed)} 个:")
        for jid, out in failed:
            print(f"  {jid}: {out[:200]}")
        return 3

    # Verify by re-reading
    after = _load_jobs()
    still = [j for j in classify(after)[0] if _is_paused(j) != target_state_paused]
    if still:
        print(f"\n[验证失败] 仍有 {len(still)} 个未达目标状态:")
        for j in still:
            print(f"  {j['id']} {j.get('name')}")
        return 3
    print(f"[验证通过] {len(todo)} 个 job 已全部{'暂停' if args.pause else '恢复'}。")
    return 0


def _install_resume(date_str: str, dry_run: bool) -> int:
    """Create a one-shot job that resumes the fleet before the first cron."""
    script = "canghai_holiday_resume.sh"
    script_path = HERMES_HOME / "scripts" / script
    body = (
        "#!/usr/bin/env bash\n"
        "# Managed by scripts/cron/holiday_maintenance.py — resumes 沧海巨浪 market\n"
        "# crons on the first trading day after a market holiday.\n"
        "# Cron runs with a minimal PATH; hermes lives in ~/.local/bin.\n"
        'export PATH="/Users/chenyang/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"\n'
        'cd "/Users/chenyang/Downloads/demo/沧海巨浪" || exit 1\n'
        "exec python3 scripts/cron/holiday_maintenance.py --resume\n"
    )
    if not dry_run:
        script_path.parent.mkdir(parents=True, exist_ok=True)
        script_path.write_text(body)
        script_path.chmod(0o755)

    ts = f"{date_str}T04:30:00"
    cmd = [
        HERMES_BIN, "cron", "create", ts,
        "--name", "canghai-holiday · 节后恢复",
        "--script", script,
        "--no-agent",
        "--deliver", "local",
    ]
    print("将执行:", " ".join(cmd))
    if dry_run:
        print("\n[dry-run] 未创建。")
        return 0
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    print(proc.stdout + proc.stderr)
    return 0 if proc.returncode == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())