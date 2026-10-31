"""Chart candidate routing with copied sources and synthetic I/O only.

Run with the pre-collection audit guard, --noconftest and scratch basetemp.
No renderer, model, network, production data or credential access is needed.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
from types import ModuleType, SimpleNamespace

import pytest

REPO = Path(os.environ.get("CHART_POOL_SOURCE_ROOT", Path(__file__).resolve().parents[2]))
SCRATCH = Path.home() / ".hermes/cache/scratch"
DATE = "20261029"
SOURCE_FILES = (
    "src/research/candidate_pool.py",
    "src/research/r5_stock_profiles.py",
    "scripts/fetch/run_chart_vision_snapshot.py",
)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def env(tmp_path, monkeypatch):
    assert tmp_path.resolve().is_relative_to(SCRATCH.resolve())
    root = tmp_path / "app"
    for rel in SOURCE_FILES:
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO / rel, target)
    names = [n for n in sys.modules if n == "src" or n.startswith("src.")]
    saved = {n: sys.modules.pop(n) for n in names}
    for name, path in (("src", root / "src"), ("src.research", root / "src/research")):
        package = ModuleType(name)
        package.__file__ = "<isolated namespace>"
        package.__path__ = [str(path)]
        monkeypatch.setitem(sys.modules, name, package)
    transport = ModuleType("src.research.data_sources")
    transport.__file__ = "<denied research transport>"
    def deny(*args, **kwargs):
        pytest.fail("chart routing must not construct research clients")
    setattr(transport, "TushareResearchClient", deny)
    monkeypatch.setitem(sys.modules, transport.__name__, transport)
    dotenv = ModuleType("dotenv")
    dotenv.__file__ = "<synthetic dotenv>"
    setattr(dotenv, "load_dotenv", lambda *args, **kwargs: False)
    monkeypatch.setitem(sys.modules, "dotenv", dotenv)
    monkeypatch.syspath_prepend(str(root))
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-offline-test")
    try:
        pool = load_module("src.research.candidate_pool", root / SOURCE_FILES[0])
        r5 = load_module("src.research.r5_stock_profiles", root / SOURCE_FILES[1])
        chart = load_module("isolated_chart_routing", root / SOURCE_FILES[2])
        yield SimpleNamespace(root=root, pool=pool, r5=r5, chart=chart)
    finally:
        for name in list(sys.modules):
            if name == "src" or name.startswith("src.") or name == "isolated_chart_routing":
                sys.modules.pop(name, None)
        sys.modules.update(saved)


def research(status="partial", leaders=None):
    return {
        "trade_date": DATE, "status": status, "no_trade": True,
        "trading_permission": False, "execution_pool": [],
        "main_lines": [{"name": "fixture-sector", "score": 80, "leaders": leaders if leaders is not None else [
            {"ts_code": "000001.SZ", "name": "fixture-one", "role": "龙一", "execution_eligible": False},
            {"ts_code": "000002.SZ", "name": "fixture-two", "role": "龙二", "execution_eligible": False},
        ]}],
    }


def save_research(env, payload):
    path = env.root / f"data/research/{DATE}/R2_main_sectors.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))
    return path


def save_snapshot(env, results, date=DATE):
    path = env.root / f"data/raw/{DATE}/chart_vision_snapshot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"date": date, "generated_at": "fixture", "results": results}))
    return path


@pytest.mark.parametrize("status", ["complete", "partial"])
def test_real_research_candidates_survive_status_without_trading_permission(env, status):
    payload = research(status)
    path = save_research(env, payload)
    original = path.read_bytes()
    pool, meta = env.pool.derive_from_file(DATE)
    expected = [(x["ts_code"], x["name"]) for x in env.r5._collect_leaders(payload)]
    assert pool == expected
    assert meta["count"] == 2
    assert env.chart._pool_from_r2(DATE) == expected
    assert path.read_bytes() == original
    assert payload["no_trade"] and not payload["trading_permission"]
    assert all(not x["execution_eligible"] for x in payload["main_lines"][0]["leaders"])


@pytest.mark.parametrize("status", ["failed", "skeleton", None])
def test_unusable_research_never_substitutes_a_default_universe(env, status):
    save_research(env, research(status))
    assert env.chart._pool_from_r2(DATE) == []


@pytest.mark.parametrize("kind", ["missing", "empty", "bad_json", "wrong_shape"])
def test_missing_or_empty_candidates_never_render_unrelated_symbols(env, kind):
    if kind == "empty":
        save_research(env, research("complete", leaders=[]))
    elif kind == "bad_json":
        save_research(env, research()).write_text("{")
    elif kind == "wrong_shape":
        save_research(env, [])
    assert env.chart._pool_from_r2(DATE) == []


def test_deduplication_role_and_input_permissions_stay_unchanged(env):
    payload = research("partial")
    payload["main_lines"].append({"name": "another-sector", "leaders": [
        {"ts_code": "000002.SZ", "name": "fixture-two", "role": "龙一"},
        {"ts_code": "000001.SZ", "name": "fixture-one", "role": "候补"},
    ]})
    original = copy.deepcopy(payload)
    save_research(env, payload)
    assert env.pool.derive_from_file(DATE)[0] == [("000001.SZ", "fixture-one"), ("000002.SZ", "fixture-two")]
    assert payload == original


def test_main_requests_current_partial_candidates_not_old_defaults(env, monkeypatch):
    save_research(env, research())
    requested = []
    async def synthetic_run(universe, concurrency):
        requested.extend(universe)
        return [{"ts_code": code, "name": name, "error": None, "pattern": "fixture-only"} for code, name in universe]
    monkeypatch.setattr(env.chart, "_run_all", synthetic_run)
    monkeypatch.setattr(sys, "argv", ["chart", "--date", DATE])
    assert env.chart.main() == 0
    assert requested == [("000001.SZ", "fixture-one"), ("000002.SZ", "fixture-two")]
    saved = json.loads((env.root / f"data/raw/{DATE}/chart_vision_snapshot.json").read_text())
    assert set(saved["results"]) == {"000001.SZ", "000002.SZ"}


def test_snapshot_failure_stays_on_the_selected_symbol(env, monkeypatch):
    save_research(env, research())
    requested = []
    async def synthetic_run(universe, concurrency):
        requested.extend(universe)
        return [{"ts_code": code, "name": name, "error": "synthetic-render-failure" if code == "000001.SZ" else None} for code, name in universe]
    monkeypatch.setattr(env.chart, "_run_all", synthetic_run)
    monkeypatch.setattr(sys, "argv", ["chart", "--date", DATE])
    assert env.chart.main() == 1
    assert requested == [("000001.SZ", "fixture-one"), ("000002.SZ", "fixture-two")]
    saved = json.loads((env.root / f"data/raw/{DATE}/chart_vision_snapshot.json").read_text())
    assert saved["results"]["000001.SZ"]["error"] == "synthetic-render-failure"
    assert saved["fail"] == 1 and saved["ok"] == 1


def test_empty_main_has_no_model_call_and_preserves_prior_snapshot(env, monkeypatch):
    save_research(env, research("complete", leaders=[]))
    prior = save_snapshot(env, {"000003.SZ": {"ts_code": "000003.SZ", "error": None}})
    original = prior.read_bytes()
    async def deny(*args):
        pytest.fail("empty current candidates must not call renderer/model")
    monkeypatch.setattr(env.chart, "_run_all", deny)
    monkeypatch.setattr(sys, "argv", ["chart", "--date", DATE])
    assert env.chart.main() == 0
    assert prior.read_bytes() == original


def test_existing_snapshot_only_renders_missing_candidates(env, monkeypatch):
    save_research(env, research())
    save_snapshot(env, {"000001.SZ": {"ts_code": "000001.SZ", "error": None}})
    requested = []
    async def synthetic_run(universe, concurrency):
        requested.extend(universe)
        return [{"ts_code": code, "name": name, "error": None} for code, name in universe]
    monkeypatch.setattr(env.chart, "_run_all", synthetic_run)
    monkeypatch.setattr(sys, "argv", ["chart", "--date", DATE])
    assert env.chart.main() == 0
    assert requested == [("000002.SZ", "fixture-two")]
    saved = json.loads((env.root / f"data/raw/{DATE}/chart_vision_snapshot.json").read_text())
    assert set(saved["results"]) == {"000001.SZ", "000002.SZ"}
