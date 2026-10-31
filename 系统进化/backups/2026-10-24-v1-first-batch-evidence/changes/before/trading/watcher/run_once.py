from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from src.settings import DATA_DIR, ROOT
from trading.entry_selector import scan_entry_opportunities
from trading.load_plan import run_load_plan
from trading.order.qmt_context import QMTContext
from trading.positions_state import PositionsStateStore
from trading.schema.watchlist_plan import WatchlistPlan
from trading.watcher.dispatch import dispatch_plan
from trading.watcher.session_context import clear_session, set_scan_result

RUNTIME_DIR = DATA_DIR / "runtime"


def loaded_plan_path(trade_date: str) -> Path:
    loaded = RUNTIME_DIR / f"watchlist_plan_{trade_date}.loaded.json"
    if loaded.exists():
        return loaded
    return RUNTIME_DIR / f"watchlist_plan_{trade_date}.json"


def run_intraday_once(
    trade_date: str,
    *,
    mode: str | None = None,
    reload: bool = False,
) -> dict:
    if reload:
        prep = run_load_plan(trade_date, mode=mode or "dry_run", simulate=False)
        trade_date = prep["trade_date"]

    path = loaded_plan_path(trade_date)
    if not path.exists():
        raise FileNotFoundError(f"no loaded plan at {path}; run load_plan first")

    plan = WatchlistPlan.model_validate(json.loads(path.read_text(encoding="utf-8")))
    effective_mode = mode or plan.mode
    dry_run = effective_mode == "dry_run"

    qmt_ctx = QMTContext(
        trade_date=trade_date,
        dry_run=dry_run,
        kill_switch_file=plan.risk_limits.kill_switch_file,
    )
    qmt_ctx.refresh_holdings(allow_file_fallback=True)

    positions = PositionsStateStore.for_mode(trade_date=trade_date, dry_run=dry_run)
    positions.load()
    positions.ensure_from_holdings(
        qmt_ctx.holdings,
        base_mobile_ratio=0.7,
    )

    clear_session()
    held = {code for code, row in qmt_ctx.holdings.items() if int(row.get("total_qty") or 0) > 0}
    scan = scan_entry_opportunities(
        plan,
        trade_date=trade_date,
        cash=float(qmt_ctx.cash or 0),
        held_codes=held,
        limit=30,
    )
    set_scan_result(scan)

    report = dispatch_plan(plan, qmt_ctx, positions, simulate=False)
    positions.save()

    manifest_path = RUNTIME_DIR / f"intraday_manifest_{trade_date}.json"
    payload = {
        "trade_date": trade_date,
        "generated_at": datetime.now().isoformat(),
        "mode": effective_mode,
        "plan_path": str(path.relative_to(ROOT)),
        "entry_scan": {
            "pool_size": scan.get("pool_size"),
            "buy_ready_count": scan.get("buy_ready_count"),
            "top_buy": scan.get("top_buy"),
            "path": f"data/runtime/entry_opportunities_{trade_date}.json",
        },
        "entry_results": report.entry_results,
        "exit_results": report.exit_results,
        "watch_started": report.watch_started,
        "skipped": report.skipped,
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "ok": True,
        "trade_date": trade_date,
        "manifest_path": str(manifest_path),
        "entry_count": len(report.entry_results),
        "exit_count": len(report.exit_results),
        "buy_ready_count": scan.get("buy_ready_count", 0),
        "candidate_pool_size": scan.get("pool_size", 0),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one intraday dispatch pass from loaded plan")
    parser.add_argument("--date", dest="trade_date", default=datetime.now().strftime("%Y%m%d"))
    parser.add_argument("--mode", choices=["live", "dry_run"], default=None)
    parser.add_argument("--reload", action="store_true", help="re-run load_plan before dispatch")
    args = parser.parse_args(argv)
    result = run_intraday_once(args.trade_date.replace("-", ""), mode=args.mode, reload=args.reload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
