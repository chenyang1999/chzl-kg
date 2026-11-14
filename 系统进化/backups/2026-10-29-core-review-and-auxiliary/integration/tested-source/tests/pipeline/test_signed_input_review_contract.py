"""Signed instruction contracts and real, synthetic version-bound input reads.

Prompt checks are not evidence that a business model followed the instructions.
No source collection, model call, account read or production replay occurs here.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import importlib
import json
import re
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
DATE = "20990106"
RUN = "synthetic-signed-input-review"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def native(tmp_path):
    root = tmp_path / "isolated-application"
    for name in ("scripts", "scripts/research"):
        package = root / name
        package.mkdir(parents=True, exist_ok=True)
        (package / "__init__.py").write_text("")
    for name in ("pipeline_artifacts.py", "build_research_summary.py"):
        shutil.copyfile(REPO / "scripts/research" / name, root / "scripts/research" / name)
    saved = {k: v for k, v in sys.modules.items() if k == "scripts" or k.startswith("scripts.")}
    old_path = list(sys.path)
    for name in saved:
        del sys.modules[name]
    sys.path.insert(0, str(root))
    try:
        b = importlib.import_module("scripts.research.build_research_summary")
        a = importlib.import_module("scripts.research.pipeline_artifacts")
        fields = {
            "R1": {"style": "synthetic", "position_cap_suggestion": 0},
            "R2": {"main_lines": [{"name": "synthetic", "leaders": [{"ts_code": "000001.SZ"}]}]},
            "R3": {"resonance_top_themes": []},
            "R4": {"top_events": []},
            "R5": {"profiles": [{"ts_code": "000001.SZ"}]},
            "R6": {"counter_arguments": [], "hard_rejects": [{"ts_code": "000001.SZ", "reason": "synthetic veto"}]},
            "R7": {"main_force": {}},
        }
        state = {"trade_date": DATE, "run_id": RUN, "stages": {}, "contract_results": {}}
        artifacts, units = {}, {}
        for unit, filename in a.UNIT_FILES.items():
            rel = f"data/research/{DATE}/{filename}"
            path = root / rel
            save(path, {"trade_date": DATE, "run_id": RUN, "attempt": 1,
                        "status": "partial" if unit == "R2" else "complete", **fields[unit]})
            _, _, fp = a.inspect_delivery(root, DATE, unit, "json")
            state["stages"][unit] = {"attempt": 1, "attempt_started_ns": fp["mtime_ns"] - 1}
            state["contract_results"][unit] = {"json": {**fp, "passed": True, "run_id": RUN, "attempt": 1}}
            units[unit] = {"json": {**fp, "receipt_binding": {"attempt": 1}}}
            artifacts[unit] = rel
        state_path = root / f"data/health/research_pipeline_{DATE}.json"
        save(state_path, state)
        summary = {"trade_date": DATE, "run_id": RUN, "artifacts": artifacts,
                   "confidence": {"R1": 0}, "hard_rejects": fields["R6"]["hard_rejects"]}
        manifest = {"schema_version": b.MANIFEST_VERSION, "trade_date": DATE, "run_id": RUN,
                    "authorized_main_inputs": deepcopy(artifacts), "units": units,
                    "summary_projection_sha256": b._digest({k: summary.get(k) for k in b.SUMMARY_PROJECTION})}
        manifest["sha256"] = b._digest(manifest)
        summary["input_manifest"] = manifest
        yield SimpleNamespace(a=a, b=b, root=root, summary=summary, state=state, state_path=state_path)
    finally:
        sys.path[:] = old_path
        for name in list(sys.modules):
            if name == "scripts" or name.startswith("scripts."):
                del sys.modules[name]
        sys.modules.update(saved)


def test_real_consumer_preserves_partial_objects_zero_and_veto(native):
    before = deepcopy(native.summary)
    result = native.b.consume_authorized_inputs(native.summary, root=native.root)
    assert set(result) == set(native.a.UNIT_FILES)
    assert result["R2"]["status"] == "partial"
    assert result["R2"]["main_lines"][0]["leaders"][0]["ts_code"] == "000001.SZ"
    assert result["R1"]["position_cap_suggestion"] == 0
    assert result["R6"]["hard_rejects"] == native.summary["hard_rejects"]
    assert native.summary == before
    assert "execution_pool" not in result


@pytest.mark.parametrize("fault", ["bytes", "run", "attempt", "receipt", "mapping", "projection"])
def test_real_consumer_rejects_version_or_identity_drift(native, fault):
    if fault == "bytes":
        path = native.root / native.summary["artifacts"]["R2"]
        save(path, {**json.loads(path.read_text()), "notes": "changed after binding"})
    elif fault in {"run", "attempt", "receipt"}:
        if fault == "run":
            native.state["run_id"] = "different-run"
        elif fault == "attempt":
            native.state["stages"]["R2"]["attempt"] = 2
        else:
            native.state["contract_results"]["R2"]["json"].pop("sha256")
        save(native.state_path, native.state)
    elif fault == "mapping":
        native.summary["artifacts"]["R2"] = "data/research/20990105/R2_main_sectors.json"
    else:
        native.summary["hard_rejects"] = []
    with pytest.raises(ValueError):
        native.b.consume_authorized_inputs(native.summary, root=native.root)


def test_auxiliary_default_does_not_read_and_opt_in_is_not_d1_permission(native, monkeypatch):
    seen = []
    original = native.b._snapshot

    def track(root, path):
        seen.append(str(path.relative_to(root)))
        return original(root, path)

    monkeypatch.setattr(native.b, "_snapshot", track)
    default = native.b.auxiliary_input_manifest(DATE, root=native.root)
    assert seen == []
    assert all(item["status"] == "pending_approval" and not item["authorized"] for item in default.values())
    rel = f"data/research/{DATE}/attention_signals.json"
    save(native.root / rel, {"synthetic": True})
    explicit = native.b.auxiliary_input_manifest(DATE, root=native.root, approved_paths={"attention": [rel]})
    assert seen == [rel]
    assert explicit["attention"]["status"] == "approved_adapter_only"
    assert explicit["attention"]["inputs"][0]["sha256"]
    seen.clear()
    summary = deepcopy(native.summary)
    summary["input_manifest"]["auxiliary_candidates"] = explicit
    summary["authorized"] = True  # A model's extra flag is not a caller authorization.
    manifest = summary["input_manifest"]
    manifest["sha256"] = native.b._digest({k: v for k, v in manifest.items() if k != "sha256"})
    result = native.b.consume_authorized_inputs(summary, root=native.root)
    assert rel not in seen
    assert set(result) == set(native.a.UNIT_FILES)


@pytest.mark.parametrize("path", ["../.env", "/outside/attention_signals.json", "data/unapproved.json"])
def test_auxiliary_adapter_rejects_outside_exact_candidate_scope(native, path):
    with pytest.raises(ValueError):
        native.b.auxiliary_input_manifest(DATE, root=native.root, approved_paths={"attention": [path]})


def launch_prompts():
    shell = (REPO / "scripts/research/run_research_shell.sh").read_text()
    matches = re.findall(r'^D1_PROMPT="([^\n]*)"$', shell, re.M)
    assert len(matches) == 1
    tree = ast.parse((REPO / "scripts/plan/ensure_watchlist_plan.py").read_text())
    nodes = [n.value for n in tree.body if isinstance(n, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == "_LLM_PROMPT" for t in n.targets)]
    assert len(nodes) == 1
    return matches[0].replace("${TRADE_DATE}", DATE), ast.literal_eval(nodes[0]).format(date=DATE)


@pytest.mark.parametrize("index", [0, 1], ids=["normal-shell", "safety-net"])
def test_actual_launch_prompts_keep_signed_read_and_write_boundaries(index):
    prompt = launch_prompts()[index]
    for text in ["input_manifest", "run/attempt/receipt/hash", "data/user_preferences.yaml",
                 "pending_approval", "approved_adapter_only", "不展开错题/观察通配符",
                 "不把未读当无风险", "读取许可不扩大写入范围或交易权限", "不写 runtime 副本"]:
        assert text in prompt
    assert DATE in prompt
    assert "canghai-plan" in (REPO / "scripts/research/run_research_shell.sh").read_text()


def test_normal_and_safety_net_use_the_same_signed_read_boundary():
    a, b = launch_prompts()
    assert a[a.index("主研究仅使用"):a.index("decision_source")] == b[b.index("主研究仅使用"):b.index("产出 data/plans/")]


def test_r6_signed_contract_removes_blanket_gate_but_not_final_permission():
    skill = (REPO / "skills/analyze_devil_advocate_v1/SKILL.md").read_text()
    scope = skill.split("### Step 1 · 加载 upstream + 可用性矩阵", 1)[1].split("### Step 2 ·", 1)[0]
    assert "包括 partial 中已有对象" in scope
    assert "`status == complete`" not in scope
    for text in ["缺 R1→R1", "不能用 R5 缺口跳过此模式", "alert 未提供不是 false",
                 "核心项目未完成时不得以局部已审替代正式审核", "有效 hard_reject 仍必须保留",
                 "不自动解除 no_trade、零预算或执行门禁"]:
        assert text in scope
    assert "否则明确“局部已审/仍有未完成”" in skill


def test_d1_signed_auxiliary_contract_preserves_separate_event_reassessment():
    skill = (REPO / "skills/main_decision_v1/SKILL.md").read_text()
    assert "本轮版本与辅助读取边界（优先于下文路径示例及历史必读条款）" in skill
    assert "模型或报告中的 authorized=true 也不能自签" in skill
    assert "事件日历尚无此轮已批准的规范输入路径" in skill
    assert "### Step 3.5.9 — 盘中事件差分重评" in skill
    assert "用户/账户预算、制度限制、真实逐票硬否决" in skill


def test_confirmed_required_review_scope_and_auxiliary_downgrade_are_explicit():
    skill = (REPO / "skills/analyze_devil_advocate_v1/SKILL.md").read_text()
    for label in ["| 资金与消息交叉 |", "| 风格一致性 |", "| 出货风险 |", "| 财务合规 |"]:
        assert label in skill
    assert "逐票先完成前述必需的模式1/2/6/7" in skill
    assert "任何对象仍缺必要项" in skill
    assert "仅辅助项目缺失时可完成必要审核" in skill
    assert "不因高位或晋级标签本身hard_reject" in skill
    assert "除模式六外 **不允许 hard_reject**" not in skill
    assert "与 5+ 板 100% 晋级叠加 → `hard_reject`" not in skill
    assert "资金与消息交叉" in (REPO / "docs/agents/R6-反证Agent.md").read_text()
    assert "模式六唯一硬否决" in (REPO / "docs/06-专题-反证机制.md").read_text()
    example = re.search(r"## 产出 JSON 契约\s+```json\s+(.*?)```", skill, re.S)
    assert example is not None
    payload = json.loads(example.group(1))
    assert payload["status"] == "partial"
    assert payload["formal_review_completed"] is False
    assert payload["review_passed"] is False
