"""Approved A/B policy acceptance: read-only contracts + AST pure functions.

Run this file's scratch copy with pytest --noconftest and plugin autoload disabled.
No production imports, jobs, databases, network or account clients are used.
Text assertions establish policy contracts, not a real LLM production cycle.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import Any

import pytest

ROOT = Path('/Users/chenyang/Downloads/demo/沧海巨浪')
SCRATCH = Path('/Users/chenyang/.hermes/cache/scratch')
MANIFEST = SCRATCH / 'canghai_policy_AB_preapply_20261023.json'


def text(relative):
    return (ROOT / relative).read_text(encoding='utf-8')


def pure_functions(relative, names, **extra):
    tree = ast.parse(text(relative))
    selected = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    assert {n.name for n in selected} == set(names)
    namespace = {'Any': Any, 'Path': Path, 're': re, 'math': math, 'TOLERANCE': 0.02, **extra}
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), *selected], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(ROOT / relative), 'exec'), namespace)
    return namespace


@pytest.mark.parametrize('row', json.loads(MANIFEST.read_text())['files'], ids=lambda r: r['path'])
def test_all_16_final_hashes_and_rollback_originals(row):
    assert hashlib.sha256(Path(row['path']).read_bytes()).hexdigest() == row['after_sha256']
    assert hashlib.sha256(Path(row['backup_path']).read_bytes()).hexdigest() == row['before_sha256']


def test_no_trade_retains_evidenced_research_but_never_buy_permission():
    d1 = text('skills/main_decision_v1/SKILL.md')
    line = next(l for l in d1.splitlines() if l.startswith('- 任一 `active: true`'))
    for required in ['no_trade: true', 'autonomous_trading_enabled: false', 'requires_user_confirmation: true', 'execution_pool: []', '不再因禁交易清空研究观察', 'auto_trade_enabled: false', 'entry_rules: []', '无对象仍可空', 'P1/P2 不得凭观察身份或 promote 自动解禁']:
        assert required in line
    assert '`watch_pool: []`' not in line
    r2 = text('skills/analyze_main_sectors_v1/SKILL.md')
    r5 = text('skills/analyze_stock_profile_v1/SKILL.md')
    soul = Path('/Users/chenyang/.hermes/profiles/canghai-research/SOUL.md').read_text()
    assert '不能据此停止研究或预先清空研究观察对象' in r2
    assert '禁新仓/零预算本身不是“无研究候选”' in r5
    assert '存在真实研究观察对象时继续画像' in r5
    assert '不因禁新仓停止研究' in soul
    assert 'assert len(candidates) >= 5' not in r5


@pytest.mark.parametrize('status', ['complete', 'degraded', 'partial', 'failed', None])
def test_real_pure_position_cap_preserves_explicit_zero(status):
    fn = pure_functions('src/plan/d1_algorithm.py', ['step1_position_cap'])['step1_position_cap']
    assert fn({'status': status, 'position_cap_suggestion': 0.0}, {}) == 0.0


@pytest.mark.parametrize('status,expected', [('complete', True), ('partial', False), ('degraded', False), ('skipped', False), ('failed', False), (None, False)])
def test_r6_real_usable_predicate_remains_complete_only(status, expected):
    fn = pure_functions('src/research/r6_devil_advocate.py', ['_is_usable'])['_is_usable']
    assert fn({'status': status}) is expected
    assert fn(None) is False


def test_r6_zero_objects_and_hard_reject_not_passed_or_downgraded():
    s = text('skills/analyze_devil_advocate_v1/SKILL.md')
    for phrase in ['`status == complete`', '`candidates_evaluated: 0`', '不代表全票审核通过', '不把 skipped/degraded 自动改 complete', 'hard_reject 后只能从 execution_pool 剔除', '不得以“等分歧买点”保留执行资格', '与模式六并列硬否决']:
        assert phrase in s
    d1 = text('skills/main_decision_v1/SKILL.md')
    assert '**不得** override R6 `hard_reject`，无例外' in d1
    assert '不抬有效零预算' in d1
    assert '无保底参与额度' in d1


@pytest.mark.parametrize('value', ['null', 'NULL', '~', '0.0', '0.75'])
def test_md_nullable_and_valid_numeric_synthetic_only(tmp_path, value):
    assert tmp_path.is_relative_to(SCRATCH)
    path = tmp_path / '20261023.md'
    path.write_text(f'---\ndate: 2026-10-23\nconfidence: {value}\n---\nfixture\n')
    f = pure_functions('tests/checks/check_md_namespace.py', ['parse_frontmatter', 'check_confidence', 'check_namespace'])
    assert f['check_confidence'](path) == []
    assert f['check_namespace'](path) == []


def test_md_actual_none_and_namespace_mismatch_are_independent(tmp_path):
    path = tmp_path / '20261023.md'
    path.write_text('---\ndate: 2026-10-22\n---\nfixture\n')
    f = pure_functions('tests/checks/check_md_namespace.py', ['parse_frontmatter', 'check_confidence', 'check_namespace'])
    assert f['check_namespace'](path)
    f['parse_frontmatter'] = lambda content: {'confidence': None}
    assert f['check_confidence'](path) == []


@pytest.mark.parametrize('value', ['nonsense', 'false'])
def test_md_invalid_confidence_still_rejected(tmp_path, value):
    path = tmp_path / '20261023.md'
    path.write_text(f'---\nconfidence: {value}\n---\n')
    f = pure_functions('tests/checks/check_md_namespace.py', ['parse_frontmatter', 'check_confidence'])
    assert f['check_confidence'](path)


def test_original_budget_numbers_and_rr_text_unchanged():
    m = json.loads(MANIFEST.read_text())
    rows = {r['path']: r for r in m['files']}
    for rel in ['skills/main_decision_v1/SKILL.md', 'skills/trade_discipline_v1/SKILL.md']:
        current = text(rel)
        original = Path(rows[str(ROOT / rel)]['backup_path']).read_text()
        before = [l for l in original.splitlines() if 'RR' in l or 'risk_reward_ratio <' in l]
        after = [l for l in current.splitlines() if 'RR' in l or 'risk_reward_ratio <' in l]
        assert after == before
    d1 = text('skills/main_decision_v1/SKILL.md')
    for phrase in ['cap × 0.75', 'cap × 0.4', 'cap × 0.5', '原 ≤2 只或空', '≤ 0.15', '≤ 0.40']:
        assert phrase in d1
