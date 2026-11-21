"""T2.1 execute daemon — 30–60s polling loop around trading.watcher.run_once."""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime, time as dtime
from pathlib import Path

from src.execute.amygdala import Amygdala
from src.execute.market_snapshot import build_snapshot
from src.execute.sector_stats import compute_sector_stats, output_path as sector_stats_output_path
from src.execute.plan_context import load_sector_map
from src.settings import DATA_DIR, ROOT
from trading.load_plan import plan_path, run_load_plan, stage_plan
from trading.watcher.run_once import run_intraday_once


def _in_session(now: datetime) -> bool:
    t = now.time()
    return dtime(9, 15) <= t <= dtime(15, 5)


def _resolve_trade_date(explicit: str | None) -> str:
    if explicit:
        return explicit.replace("-", "")
    return datetime.now().strftime("%Y%m%d")


def _ensure_plan_staged(trade_date: str) -> Path:
    """Use the same validated atomic handoff as the actual plan loader."""
    return stage_plan(trade_date)


def _read_kill_switch_file(trade_date: str) -> str:
    loaded = DATA_DIR / "runtime" / f"watchlist_plan_{trade_date}.loaded.json"
    staged = DATA_DIR / "runtime" / f"watchlist_plan_{trade_date}.json"
    canonical = plan_path(trade_date)
    for path in (loaded, staged, canonical):
        if not path.exists():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            risk = data.get("risk_limits") if isinstance(data, dict) else None
            ks = risk.get("kill_switch_file") if isinstance(risk, dict) else None
            if ks:
                return str(ks)
        except (json.JSONDecodeError, OSError):
            continue
    return "data/execution/KILL_SWITCH"


def _refresh_market_context(
    trade_date: str,
    *,
    snapshot_live: bool,
    full_market: bool,
    market_limit: int | None,
    write_sector_stats: bool,
) -> dict[str, object]:
    snap = build_snapshot(
        trade_date,
        dry_run=not snapshot_live,
        full_market=full_market,
        market_limit=market_limit,
    )
    sector_map = load_sector_map(trade_date)
    stats = compute_sector_stats(snap, sector_map=sector_map or None)
    out: dict[str, object] = {
        "bar_count": snap.bar_count,
        "symbol_count": len(snap.codes()),
        "source": snap.source,
        "sector_count": len(stats.sectors),
    }
    if write_sector_stats:
        payload = {
            **stats.to_dict(),
            "snapshot_source": snap.source,
            "snapshot_bar_count": snap.bar_count,
            "sector_map_count": len(sector_map),
            "status": "computed" if snap.bar_count else "stub",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "note": "watcher_daemon refresh",
        }
        path = sector_stats_output_path(trade_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        out["sector_stats_path"] = str(path.relative_to(ROOT))
    return out


def run_loop(
    trade_date: str,
    *,
    mode: str = "dry_run",
    interval_sec: float = 45.0,
    jitter_sec: float = 15.0,
    once: bool = False,
    outside_session: bool = False,
    refresh_snapshot_every: int = 0,
    snapshot_live: bool = False,
    full_market: bool = False,
    market_limit: int | None = None,
    max_passes: int = 0,
) -> int:
    trade_date = _resolve_trade_date(trade_date)
    # Missing startup input may arrive later. Validate/stage inside each pass,
    # not only once at process start, and fail that pass closed on bad input.
    staged = plan_path(trade_date)
    if not staged.exists():
        msg = f"no watchlist plan at {staged} or {plan_path(trade_date)}"
        if once:
            print(json.dumps({"ok": False, "error": msg}, ensure_ascii=False))
            return 1
        print(msg, file=sys.stderr)

    amy = Amygdala()
    passes = 0
    consecutive_errors = 0
    log_path = DATA_DIR / "execution" / trade_date / "watcher_daemon.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    runtime_dir = DATA_DIR / "runtime"
    decisions_prefix = "dry_run_decisions" if mode == "dry_run" else "decisions"

    while True:
        now = datetime.now()
        if not _in_session(now) and not once and not outside_session:
            time.sleep(min(interval_sec, 60.0))
            continue

        ks = amy.check_kill_switch(_read_kill_switch_file(trade_date))
        if not ks.allowed:
            record = {
                "at": now.isoformat(),
                "pass": passes,
                "ok": False,
                "skipped": "kill_switch",
                "reason": ks.reason,
                "code": ks.code,
            }
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            if once:
                print(json.dumps(record, ensure_ascii=False, indent=2))
                return 2
            sleep = interval_sec + random.uniform(-jitter_sec, jitter_sec)
            time.sleep(max(30.0, min(60.0, sleep)))
            continue

        record: dict[str, object]
        try:
            _ensure_plan_staged(trade_date)
            if refresh_snapshot_every > 0 and (passes == 0 or passes % refresh_snapshot_every == 0):
                record_snap = _refresh_market_context(
                    trade_date,
                    snapshot_live=snapshot_live,
                    full_market=full_market,
                    market_limit=market_limit,
                    write_sector_stats=True,
                )
            else:
                record_snap = None

            # run_load_plan refreshes .loaded.json every pass. Do not also use
            # reload=True below: loading already dispatches once.
            run_load_plan(trade_date, mode=mode, simulate=False)
            result = run_intraday_once(trade_date, mode=mode, reload=False)
            passes += 1
            consecutive_errors = 0
            record = {
                "at": now.isoformat(),
                "pass": passes,
                "ok": True,
                "mode": mode,
                "summary": result,
                "paths": {
                    "decisions": str((runtime_dir / f"{decisions_prefix}_{trade_date}.jsonl").relative_to(ROOT)),
                    "manifest": str((runtime_dir / f"intraday_manifest_{trade_date}.json").relative_to(ROOT)),
                    "watcher_log": str(log_path.relative_to(ROOT)),
                },
            }
            if record_snap:
                record["snapshot"] = record_snap
        except Exception as exc:  # noqa: BLE001 — daemon must survive single-pass errors
            consecutive_errors += 1
            record = {
                "at": now.isoformat(),
                "pass": passes,
                "ok": False,
                "error": str(exc),
                "consecutive_errors": consecutive_errors,
            }

        with log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

        if once:
            print(json.dumps(record, ensure_ascii=False, indent=2))
            return 0 if record.get("ok") else 1

        if max_passes and passes >= max_passes:
            return 0

        base = interval_sec + random.uniform(-jitter_sec, jitter_sec)
        base = max(30.0, min(60.0, base))
        if consecutive_errors:
            base = min(120.0, base * (1 + 0.5 * consecutive_errors))
        time.sleep(base)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Execute watcher daemon (T2.1 · 30–60s poll)")
    parser.add_argument("--date", dest="trade_date", default=None)
    parser.add_argument("--mode", choices=["live", "dry_run"], default="dry_run")
    parser.add_argument("--interval", type=float, default=45.0, help="target seconds between passes (30–60)")
    parser.add_argument("--once", action="store_true", help="single pass then exit")
    parser.add_argument(
        "--outside-session",
        action="store_true",
        help="allow passes outside 09:15–15:05 (smoke / keepalive)",
    )
    parser.add_argument(
        "--refresh-snapshot-every",
        type=int,
        default=0,
        metavar="N",
        help="refresh market_snapshot+sector_stats every N passes (0=off)",
    )
    parser.add_argument(
        "--snapshot-live",
        action="store_true",
        help="use live xtick/tushare when refreshing snapshot (needs API keys)",
    )
    parser.add_argument(
        "--full-market",
        action="store_true",
        help="include full A-share universe in snapshot refresh (batched; use --market-limit)",
    )
    parser.add_argument(
        "--market-limit",
        type=int,
        default=None,
        help="cap full-market codes per refresh (default: plan universe only)",
    )
    parser.add_argument("--max-passes", type=int, default=0, help="exit after N successful passes (0=infinite)")
    args = parser.parse_args(argv)
    return run_loop(
        _resolve_trade_date(args.trade_date),
        mode=args.mode,
        interval_sec=args.interval,
        once=args.once,
        outside_session=args.outside_session,
        refresh_snapshot_every=args.refresh_snapshot_every,
        snapshot_live=args.snapshot_live,
        full_market=args.full_market,
        market_limit=args.market_limit,
        max_passes=args.max_passes,
    )


if __name__ == "__main__":
    raise SystemExit(main())
