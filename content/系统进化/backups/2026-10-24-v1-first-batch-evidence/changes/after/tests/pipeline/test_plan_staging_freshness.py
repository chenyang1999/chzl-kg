"""Isolated plan handoff regressions: no production paths, QMT or executors.

The daemon watcher entry point and every dispatch are replaced by recording
fakes. Only the real staging/loader and filesystem reads/writes run.
"""
from __future__ import annotations

import ast
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from trading.account_config import AccountConfig
from trading.watcher.dispatch import DispatchReport

loader = importlib.import_module("trading.load_plan")
daemon = importlib.import_module("src.execute.watcher_daemon")
consumer = importlib.import_module("trading.watcher.run_once")
DATE = "20261022"


def plan(**updates):
    data = {
        "schema_version": "watchlist_plan_v1",
        "trade_date": DATE,
        "mode": "dry_run",
        "autonomous_trading_enabled": False,
        "requires_user_confirmation": True,
        "no_trade": False,
        "generated_at": "2026-10-22T09:53:09+08:00",
        "status": "ok",
        "execution_pool": [],
        "watch_pool": [{"ts_code": "600000.SH", "name": "test", "score": 70}],
        "risk_limits": {"kill_switch_file": "test-kill-switch"},
    }
    data.update(updates)
    return data


def account(**updates):
    data: dict[str, Any] = dict(
        mode="live", autonomous_trading_enabled=True,
        requires_user_confirmation=False, risk_limits={},
        default_base_mobile_ratio=0.7, daban_max_symbols_per_day=2,
        daban_default_sealed_bid_threshold=50000,
    )
    data.update(updates)
    return AccountConfig(**data)


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    data = tmp_path / "data"
    runtime = data / "runtime"
    runtime.mkdir(parents=True)
    for module in (loader, daemon, consumer):
        monkeypatch.setattr(module, "DATA_DIR", data)
        monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(loader, "RUNTIME_DIR", runtime)
    monkeypatch.setattr(consumer, "RUNTIME_DIR", runtime)
    canonical = data / "plans" / DATE / "watchlist_plan.json"
    staged = runtime / f"watchlist_plan_{DATE}.json"
    loaded = runtime / f"watchlist_plan_{DATE}.loaded.json"
    calls = []

    def forbidden(*args, **kwargs):
        raise AssertionError("real watcher/QMT/executor is forbidden in isolated tests")

    # Fail hard if any dependency is accidentally not faked in a test.
    monkeypatch.setattr(loader, "QMTContext", forbidden)
    monkeypatch.setattr(loader, "PositionsStateStore", SimpleNamespace(for_mode=forbidden))
    monkeypatch.setattr(loader, "dispatch_plan", forbidden)
    monkeypatch.setattr(loader, "simulate_all_rule_types", forbidden)
    monkeypatch.setattr(loader, "load_account_config", forbidden)
    monkeypatch.setattr(daemon, "run_intraday_once", forbidden)
    monkeypatch.setattr(daemon, "Amygdala", forbidden)
    monkeypatch.setattr(daemon, "_refresh_market_context", forbidden)
    monkeypatch.setattr(consumer, "QMTContext", forbidden)
    monkeypatch.setattr(consumer, "dispatch_plan", forbidden)
    monkeypatch.setattr(consumer, "scan_entry_opportunities", forbidden)

    def write(path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path.read_bytes()

    def enable_loader_fakes():
        class FakeContext:
            def __init__(self, **kwargs):
                calls.append(("context", kwargs))
                self.holdings = {}
                self.orders_path = runtime / "fake-orders.jsonl"
                self.events_path = runtime / "fake-events.jsonl"

            def refresh_holdings(self, **kwargs):
                calls.append(("holdings", kwargs))

        class FakePositions:
            positions = {}

            def load(self):
                pass

            def reset_daily_t_state(self):
                pass

            def ensure_from_holdings(self, *args, **kwargs):
                pass

            def save(self):
                pass

        def dispatch(candidate, context, positions, *, simulate=False):
            calls.append(("dispatch", (candidate.model_dump(mode="json"), simulate)))
            return DispatchReport()

        monkeypatch.setattr(loader, "QMTContext", FakeContext)
        monkeypatch.setattr(loader, "PositionsStateStore", SimpleNamespace(for_mode=lambda **kw: FakePositions()))
        monkeypatch.setattr(loader, "dispatch_plan", dispatch)
        monkeypatch.setattr(loader, "simulate_all_rule_types", lambda p, q, s: dispatch(p, q, s, simulate=True))
        monkeypatch.setattr(loader, "load_account_config", lambda: account())

    return SimpleNamespace(
        root=tmp_path, data=data, runtime=runtime, canonical=canonical,
        staged=staged, loaded=loaded, write=write, calls=calls,
        enable_loader_fakes=enable_loader_fakes,
    )


def test_existing_runtime_replaced_by_new_canonical_even_if_mtime_older(sandbox):
    import os

    old = plan(meta={"python_fallback": True}, generated_at="2026-10-22T08:30:00+08:00", watch_pool=[])
    sandbox.write(sandbox.staged, old)
    expected = sandbox.write(sandbox.canonical, plan(meta={"python_fallback": False}))
    os.utime(sandbox.canonical, ns=(1, 1))
    result = daemon._ensure_plan_staged(DATE)
    assert result == sandbox.staged
    assert result.read_bytes() == expected
    assert sandbox.canonical.read_bytes() == expected
    assert not json.loads(result.read_bytes())["meta"]["python_fallback"]
    assert sandbox.calls == []


def test_staging_is_atomic_and_cleans_unique_temp_on_replace_failure(sandbox, monkeypatch):
    old = sandbox.write(sandbox.staged, plan(watch_pool=[]))
    new = sandbox.write(sandbox.canonical, plan())
    inode = sandbox.staged.stat().st_ino

    def fail_replace(src, dst):
        assert Path(src).parent == Path(dst).parent == sandbox.runtime
        assert Path(src).read_bytes() == new
        assert sandbox.staged.read_bytes() == old
        raise OSError("injected atomic replace failure")

    monkeypatch.setattr(loader.os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected atomic replace failure"):
        daemon._ensure_plan_staged(DATE)
    assert sandbox.staged.read_bytes() == old
    assert sandbox.staged.stat().st_ino == inode
    assert not list(sandbox.runtime.glob("*.tmp"))
    assert sandbox.canonical.read_bytes() == new


def test_fsync_failure_preserves_good_copy(sandbox, monkeypatch):
    old = sandbox.write(sandbox.staged, plan(watch_pool=[]))
    sandbox.write(sandbox.canonical, plan())

    def fail_fsync(fd):
        raise OSError("injected fsync failure")

    monkeypatch.setattr(loader.os, "fsync", fail_fsync)
    with pytest.raises(OSError, match="injected fsync failure"):
        loader.stage_plan(DATE)
    assert sandbox.staged.read_bytes() == old
    assert not list(sandbox.runtime.glob("*.tmp"))


def test_initial_atomic_failure_leaves_no_partial_runtime(sandbox, monkeypatch):
    sandbox.write(sandbox.canonical, plan())

    def fail_replace(src, dst):
        assert not Path(dst).exists()
        raise OSError("initial replace failure")

    monkeypatch.setattr(loader.os, "replace", fail_replace)
    with pytest.raises(OSError, match="initial replace failure"):
        loader.stage_plan(DATE)
    assert list(sandbox.runtime.iterdir()) == []


def test_authorized_live_to_live_content_refresh_does_not_change_flags(sandbox):
    previous = plan(mode="live", autonomous_trading_enabled=True, requires_user_confirmation=False)
    sandbox.write(sandbox.staged, previous)
    updated = {**previous, "generated_at": "new-live-plan"}
    expected = sandbox.write(sandbox.canonical, updated)
    assert loader.stage_plan(DATE).read_bytes() == expected


def test_bad_canonical_without_cache_never_creates_runtime(sandbox):
    sandbox.write(sandbox.canonical, plan(trade_date="20261021"))
    with pytest.raises(ValueError, match="trade_date mismatch"):
        loader.run_load_plan(DATE)
    assert list(sandbox.runtime.iterdir()) == []


def test_unchanged_input_is_idempotent_without_replace(sandbox, monkeypatch):
    expected = sandbox.write(sandbox.canonical, plan())
    daemon._ensure_plan_staged(DATE)
    before = sandbox.staged.stat()

    def unexpected(*args):
        pytest.fail("unchanged plan must not be rewritten")

    monkeypatch.setattr(loader.os, "replace", unexpected)
    for _ in range(3):
        assert daemon._ensure_plan_staged(DATE).read_bytes() == expected
    after = sandbox.staged.stat()
    assert (before.st_ino, before.st_mtime_ns) == (after.st_ino, after.st_mtime_ns)


BAD_INPUTS = [
    "{", "[]", "null",
    json.dumps(plan(trade_date="20261021")),
    json.dumps(plan(trade_date="20260230")),
    json.dumps(plan(schema_version="watchlist_plan_v999")),
    json.dumps(plan(schema_version=[])),
    json.dumps(plan(status="stub")),
    json.dumps(plan(mode="fallback")),
    json.dumps(plan(mode=[])),
    json.dumps(plan(autonomous_trading_enabled="false")),
    json.dumps(plan(requires_user_confirmation=[])),
    json.dumps(plan(no_trade="false")),
    json.dumps(plan(no_trade=True, mode="live")),
    json.dumps(plan(decision_status="no_trade", mode="live")),
    json.dumps(plan(risk_limits=[])),
    json.dumps(plan(execution_pool=["silently discarded row"])),
    json.dumps(plan(watch_pool={"bad": "shape"})),
    json.dumps(plan(watch_pool=[{"ts_code": "600000.SH", "name": "test", "score": 200}])),
    json.dumps(plan(watch_pool=[{"ts_code": "600000.SH", "name": "test", "auto_trade_enabled": 1}])),
    json.dumps(plan(watch_pool=[{"ts_code": "600000.SH", "name": "test", "entry_rules": ["bad"]}])),
    json.dumps(plan(watch_pool=[{"ts_code": "600000.SH", "name": "test", "entry_rules": [{"type": "unknown"}]}])),
    json.dumps(plan(watch_pool=[{"ts_code": "600000.SH", "name": "test", "exit_rules": [{"type": "unknown"}]}])),
    json.dumps({k: v for k, v in plan().items() if k != "autonomous_trading_enabled"}),
]


@pytest.mark.parametrize("bad", BAD_INPUTS)
def test_bad_canonical_never_overwrites_good_staged_or_loaded_or_contacts_qmt(sandbox, bad):
    old = sandbox.write(sandbox.staged, plan(watch_pool=[]))
    loaded_old = sandbox.write(sandbox.loaded, plan(watch_pool=[], generated_at="old-loaded"))
    sandbox.canonical.parent.mkdir(parents=True, exist_ok=True)
    sandbox.canonical.write_text(bad, encoding="utf-8")
    for operation in (daemon._ensure_plan_staged, loader.run_load_plan):
        with pytest.raises(ValueError):
            operation(DATE)
    assert sandbox.staged.read_bytes() == old
    assert sandbox.loaded.read_bytes() == loaded_old
    assert sandbox.calls == []


def test_runtime_only_legacy_same_day_plan_is_validated_and_not_rewritten(sandbox):
    expected = sandbox.write(sandbox.staged, plan(schema_version="1.0"))
    assert loader.stage_plan(DATE) == sandbox.staged
    assert sandbox.staged.read_bytes() == expected
    sandbox.write(sandbox.staged, plan(trade_date="20261021"))
    with pytest.raises(ValueError, match="trade_date mismatch"):
        loader.stage_plan(DATE)


def test_missing_plan_and_date_path_traversal_fail_before_writes(sandbox):
    with pytest.raises(FileNotFoundError):
        loader.stage_plan(DATE)
    with pytest.raises(ValueError, match="trade_date must"):
        loader.stage_plan("../../20261022")
    assert list(sandbox.runtime.iterdir()) == []


@pytest.mark.parametrize("old", [
    plan(), plan(no_trade=True),
    plan(mode="live", autonomous_trading_enabled=False, requires_user_confirmation=False),
    plan(mode="live", autonomous_trading_enabled=True, requires_user_confirmation=True),
])
def test_automatic_staging_cannot_promote_restricted_runtime_to_live(sandbox, old):
    original = sandbox.write(sandbox.staged, old)
    sandbox.write(sandbox.canonical, plan(mode="live", autonomous_trading_enabled=True, requires_user_confirmation=False))
    with pytest.raises(ValueError, match="cannot expand live authorization"):
        loader.run_load_plan(DATE, mode="live", account_config=account())
    assert sandbox.staged.read_bytes() == original
    assert sandbox.calls == []


@pytest.mark.parametrize("overrides", [
    {}, {"no_trade": True},
    {"mode": "live", "autonomous_trading_enabled": False, "requires_user_confirmation": False},
    {"mode": "live", "autonomous_trading_enabled": True, "requires_user_confirmation": True},
])
def test_request_live_never_overrides_source_restrictions(sandbox, overrides):
    sandbox.write(sandbox.canonical, plan(**overrides))
    with pytest.raises(ValueError, match="live"):
        loader.run_load_plan(DATE, mode="live", account_config=account())
    assert sandbox.calls == []
    assert not sandbox.loaded.exists()


@pytest.mark.parametrize("restriction", [
    {"mode": "dry_run"}, {"autonomous_trading_enabled": False}, {"requires_user_confirmation": True},
])
def test_request_live_never_overrides_account_restrictions(sandbox, restriction):
    sandbox.write(sandbox.canonical, plan(mode="live", autonomous_trading_enabled=True, requires_user_confirmation=False))
    with pytest.raises(ValueError, match="live"):
        loader.run_load_plan(DATE, mode="live", account_config=account(**restriction))
    assert sandbox.calls == []


@pytest.mark.parametrize("no_trade", [False, True])
def test_account_live_default_cannot_promote_dry_plan_and_preserves_no_trade(sandbox, no_trade):
    sandbox.write(sandbox.canonical, plan(no_trade=no_trade))
    sandbox.enable_loader_fakes()
    result = loader.run_load_plan(DATE, account_config=account())
    loaded = json.loads(sandbox.loaded.read_bytes())
    assert result["mode"] == loaded["mode"] == "dry_run"
    assert loaded["no_trade"] is no_trade
    assert loaded["autonomous_trading_enabled"] is False
    assert loaded["requires_user_confirmation"] is True
    assert [v["dry_run"] for kind, v in sandbox.calls if kind == "context"] == [True]
    assert [v[1] for kind, v in sandbox.calls if kind == "dispatch"] == [True]


def test_business_no_trade_status_is_also_a_safety_ceiling(sandbox):
    source = plan(decision_status="no_trade", autonomous_trading_enabled=True, requires_user_confirmation=False)
    sandbox.write(sandbox.canonical, source)
    sandbox.enable_loader_fakes()
    result = loader.run_load_plan(DATE, account_config=account())
    loaded = json.loads(sandbox.loaded.read_bytes())
    assert result["mode"] == loaded["mode"] == "dry_run"
    assert loaded["decision_status"] == "no_trade"
    assert loaded["autonomous_trading_enabled"] is False
    assert loaded["requires_user_confirmation"] is True


@pytest.mark.parametrize("mode,simulate,expected", [
    ("live", False, "live"), ("dry_run", False, "dry_run"), ("live", True, "dry_run"),
])
def test_authorized_live_and_explicit_dry_modes_are_preserved_without_real_dispatch(sandbox, mode, simulate, expected):
    sandbox.write(sandbox.canonical, plan(mode="live", autonomous_trading_enabled=True, requires_user_confirmation=False))
    sandbox.enable_loader_fakes()
    result = loader.run_load_plan(DATE, mode=mode, simulate=simulate, account_config=account())
    assert result["mode"] == expected
    loaded = json.loads(sandbox.loaded.read_bytes())
    assert loaded["mode"] == expected
    assert loaded["autonomous_trading_enabled"] is True
    assert loaded["requires_user_confirmation"] is False
    assert [v["dry_run"] for kind, v in sandbox.calls if kind == "context"] == [expected == "dry_run"]


def test_actual_loader_refreshes_staged_and_loaded_consumed_path_on_each_call(sandbox):
    sandbox.write(sandbox.staged, plan(watch_pool=[], meta={"python_fallback": True}))
    sandbox.write(sandbox.loaded, plan(watch_pool=[], generated_at="old-loaded"))
    sandbox.enable_loader_fakes()
    for index in range(2):
        new = plan(generated_at=f"2026-10-22T10:0{index}:00+08:00")
        new["watch_pool"][0]["score"] = 71 + index
        sandbox.write(sandbox.canonical, new)
        result = loader.run_load_plan("2026-10-22", mode="dry_run", account_config=account())
        assert result["trade_date"] == DATE
        assert Path(result["plan_path"]) == consumer.loaded_plan_path(DATE) == sandbox.loaded
        assert json.loads(sandbox.staged.read_bytes()) == new
        actual = json.loads(consumer.loaded_plan_path(DATE).read_bytes())
        assert actual["watch_pool"][0]["score"] == 71 + index
        assert actual["generated_at"] == new["generated_at"]
        assert actual["mode"] == "dry_run"
    assert len([c for c in sandbox.calls if c[0] == "dispatch"]) == 2


def test_loaded_write_is_atomic_on_failure(sandbox, monkeypatch):
    sandbox.write(sandbox.canonical, plan())
    loader.stage_plan(DATE)
    old = sandbox.write(sandbox.loaded, plan(watch_pool=[], generated_at="old"))
    sandbox.enable_loader_fakes()

    def fail_replace(src, dst):
        assert Path(dst) == sandbox.loaded
        assert sandbox.loaded.read_bytes() == old
        raise OSError("loaded replace failure")

    monkeypatch.setattr(loader.os, "replace", fail_replace)
    with pytest.raises(OSError, match="loaded replace failure"):
        loader.run_load_plan(DATE, mode="dry_run", account_config=account())
    assert sandbox.loaded.read_bytes() == old
    assert not list(sandbox.runtime.glob("*.tmp"))
    assert not [c for c in sandbox.calls if c[0] == "dispatch"]


def test_isolated_daemon_loop_refreshes_new_canonical_without_double_reload(sandbox, monkeypatch):
    sandbox.write(sandbox.staged, plan(watch_pool=[], meta={"python_fallback": True}))
    first = plan(generated_at="first")
    second = plan(generated_at="second")
    second["watch_pool"][0]["score"] = 99
    sandbox.write(sandbox.canonical, first)
    sandbox.enable_loader_fakes()
    monkeypatch.setattr(daemon, "Amygdala", lambda: SimpleNamespace(check_kill_switch=lambda _: SimpleNamespace(allowed=True)))
    observed = []
    prepare_results = []
    real_loader = daemon.run_load_plan
    real_watcher = consumer.run_intraday_once
    real_dispatch = importlib.import_module('trading.watcher.dispatch').dispatch_plan

    class WatcherContext:
        def __init__(self, **kwargs):
            sandbox.calls.append(('context', kwargs))
            self.holdings, self.quotes = {}, {}
            self.cash = self.total_asset = 100000.0  # Synthetic, no account reads.
        def refresh_holdings(self, **kwargs):
            pass
        def refresh_quotes(self, symbols):
            assert symbols == ['600000.SH']
        def log_event(self, event):
            assert event['event'] == 'watch_started'

    class WatcherPositions:
        def __init__(self):
            self.positions = {}
        def load(self):
            pass
        def ensure_from_holdings(self, holdings, **kwargs):
            assert holdings == {}
        def save(self):
            pass

    def prepare(td, **kwargs):
        assert kwargs['dispatch'] is False
        before = list(sandbox.calls)
        result = real_loader(td, **kwargs)
        assert result['dispatched'] is False
        assert sandbox.calls == before  # Preparation cannot create context/dispatch.
        prepare_results.append(result)
        return result

    def dispatch(candidate, context, positions, *, simulate=False):
        assert simulate is False
        sandbox.calls.append(('dispatch', (candidate.model_dump(mode='json'), simulate)))
        report = real_dispatch(candidate, context, positions, simulate=simulate)
        assert report.watch_started == ['600000.SH']
        return report

    monkeypatch.setattr(daemon, 'run_load_plan', prepare)
    monkeypatch.setattr(consumer, 'load_account_config', lambda: account())
    monkeypatch.setattr(consumer, 'QMTContext', WatcherContext)
    monkeypatch.setattr(consumer, 'PositionsStateStore', SimpleNamespace(for_mode=lambda **kw: WatcherPositions()))
    monkeypatch.setattr(consumer, 'scan_entry_opportunities', lambda *a, **kw: {
        'pool_size': 1, 'buy_ready_count': 0, 'opportunities': [], 'errors': []})
    monkeypatch.setattr(consumer, 'dispatch_plan', dispatch)

    def fake_watcher(td, *, mode, reload):
        assert reload is False
        loaded = json.loads(consumer.loaded_plan_path(td).read_bytes())
        observed.append((loaded["generated_at"], loaded["watch_pool"][0]["score"]))
        assert mode == loaded["mode"] == "dry_run"
        result = real_watcher(td, mode=mode, reload=reload)
        assert result['ok'] and result['candidate_pool_size'] == 1
        manifest = json.loads((sandbox.runtime / f'intraday_manifest_{td}.json').read_text())
        assert manifest['watch_started'] == ['600000.SH']
        return result

    sleep_calls = []
    def fake_sleep(seconds):
        sleep_calls.append(seconds)
        assert len(sleep_calls) == 1, 'daemon did not finish two successful passes'
        sandbox.write(sandbox.canonical, second)

    monkeypatch.setattr(daemon, "run_intraday_once", fake_watcher)
    monkeypatch.setattr(daemon.time, "sleep", fake_sleep)
    assert daemon.run_loop(DATE, mode="dry_run", outside_session=True, max_passes=2) == 0
    assert observed == [("first", 70), ("second", 99)]
    # One real watcher/dispatcher pass per iteration; loader only prepares.
    assert len([c for c in sandbox.calls if c[0] == "dispatch"]) == 2
    assert len(prepare_results) == 2
    contexts = [value for kind, value in sandbox.calls if kind == 'context']
    assert len(contexts) == 2 and all(value['dry_run'] is True for value in contexts)
    assert [value[0]['generated_at'] for kind, value in sandbox.calls if kind == 'dispatch'] == ['first', 'second']
    assert json.loads(sandbox.staged.read_bytes()) == second


@pytest.mark.parametrize("bad", [plan(trade_date="20261021"), [], {"risk_limits": []}])
def test_invalid_update_stops_isolated_daemon_before_loader_or_watcher(sandbox, monkeypatch, capsys, bad):
    old = sandbox.write(sandbox.staged, plan())
    sandbox.write(sandbox.canonical, bad)
    monkeypatch.setattr(daemon, "Amygdala", lambda: SimpleNamespace(check_kill_switch=lambda _: SimpleNamespace(allowed=True)))
    assert daemon.run_loop(DATE, mode="dry_run", once=True) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False
    assert sandbox.staged.read_bytes() == old
    assert sandbox.calls == []


def test_consumer_contract_reads_loaded_and_does_not_cache_plan_in_memory():
    # Read/parse source only; never start the real watcher or its dependencies.
    assert consumer.__file__ is not None
    source = Path(consumer.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "run_intraday_once")
    calls = [n for n in ast.walk(function) if isinstance(n, ast.Call)]
    assert any(isinstance(n.func, ast.Name) and n.func.id == "loaded_plan_path" for n in calls)
    assert any(isinstance(n.func, ast.Attribute) and n.func.attr == "read_text" for n in calls)
    assert any(isinstance(n.func, ast.Attribute) and n.func.attr == "model_validate" for n in calls)
