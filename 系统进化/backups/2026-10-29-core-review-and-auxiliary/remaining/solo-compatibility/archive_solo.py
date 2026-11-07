"""Archive the single-writer isolated repair, not production adoption."""
from pathlib import Path
from collections import Counter
from datetime import datetime
import ast
import difflib
import hashlib
import json
import shutil
import zipfile

ROOT = Path('/Users/chenyang/Downloads/demo/沧海巨浪')
SCRATCH = Path(__file__).parent
BASE = ROOT / 'chzl_kg/系统进化/backups/2026-10-29-core-review-and-auxiliary/remaining'
OUT = BASE / 'solo-compatibility'
PRIOR = BASE / 'd1-signed-implementation/final-acceptance'


def load(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identity(result):
    return Counter(case['id'] for case in result['cases'])


def assertions(node):
    return [ast.dump(n, include_attributes=False) for n in ast.walk(node) if isinstance(n, ast.Assert)]


current = load(SCRATCH / 'legacy-solo-current-joint/result.json')
old_legacy = load(SCRATCH / 'legacy-parent-final/result.json')
old_joint = load(PRIOR / 'parent-accepted-joint/result.json')
assert current['exit_code'] == 0 and current['source_unchanged'] and current['index_unchanged']
assert not current['guard_violations'] and not current['unguarded_native_children']
assert all(not c['failure'] and not c['error'] and not c['skipped'] for c in current['cases'])
old_ids = identity(old_legacy) + identity(old_joint)
new_ids = identity(current)
assert not (old_ids - new_ids), 'Original expanded cases lost'
added = new_ids - old_ids
assert sum(identity(old_legacy).values()) == 74
assert sum(identity(old_joint).values()) == 106
assert sum(new_ids.values()) == 184 and sum(added.values()) == 4

preserved = {}
for rel in ['tests/pipeline/test_safety_net_input_versions.py',
            'tests/pipeline/test_plan_interim_preservation.py']:
    before = ast.parse((OUT / 'before' / rel).read_text())
    after = ast.parse((ROOT / rel).read_text())
    newer = {n.name: n for n in after.body if isinstance(n, ast.FunctionDef)}
    names = []
    for node in before.body:
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith('test_'):
            continue
        candidate = newer[node.name]
        assert ast.dump(node.args) == ast.dump(candidate.args)
        assert [ast.dump(n) for n in node.decorator_list] == [ast.dump(n) for n in candidate.decorator_list]
        assert assertions(node) == assertions(candidate), node.name
        names.append(node.name)
    preserved[rel] = names

baseline = load(OUT / 'before-manifest.json')['source_sha256']
assert digest(ROOT / '.git/index') == baseline['.git/index']
fixture = 'tests/test_canghai_repair_plan_contracts_20261023.py'
assert digest(ROOT / fixture) == baseline[fixture]
ensure = 'scripts/plan/ensure_watchlist_plan.py'
before_tree = ast.parse((OUT / 'before' / ensure).read_text())
after_tree = ast.parse((ROOT / ensure).read_text())
for tree in [before_tree, after_tree]:
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name == 'retry_llm':
            n.body = []
assert ast.dump(before_tree) == ast.dump(after_tree), 'Unrelated production AST changed'

source_before = load(OUT / 'current-source-before.json')
source_after = load(OUT / 'current-source-after.json')
assert source_before == source_after
assert all(digest(ROOT / rel) == sha for rel, sha in source_after.items())
for rel, sha in source_after.items():
    target = OUT / 'tested-source' / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / rel, target)
    assert digest(target) == sha

price_dir = BASE / 'd1-signed-implementation/price-final'
price = load(price_dir / 'closure.json')
price_sources = {rec['path'].removeprefix('tested-source/'): rec['sha256']
                 for rec in price['files'] if rec['path'].startswith('tested-source/')}
assert len(price_sources) == 32
assert all(digest(ROOT / rel) == sha for rel, sha in price_sources.items())

# Read-only comparison against the already audited, explicit local sources.
# No new source discovery, credentials, databases, network or production run.
adoption = load(BASE / 'adoption/chart-health-evidence.json')
adoption_rows = []
for rec in adoption['source_manifest']:
    path = ROOT / rec['path']
    assert path.name != '.env' and path.suffix not in {'.sqlite', '.db'}
    exists = path.is_file()
    sha = digest(path) if exists else None
    adoption_rows.append({'path': rec['path'], 'baseline_sha256': rec['sha256'],
                          'current_sha256': sha, 'unchanged': sha == rec['sha256']})
business = [rec for rec in adoption_rows if rec['path'].startswith('data/')]
assert business and all(rec['unchanged'] for rec in business)
(OUT / 'existing-business-version-check.json').write_text(json.dumps({
    'checked_at': datetime.now().astimezone().isoformat(),
    'scope': 'Existing explicit audit source list only; same bytes are not new adoption',
    'records': adoption_rows,
    'business_sources_unchanged': len(business),
    'new_business_adoption_proved': False,
}, ensure_ascii=False, indent=2))

for label in ['legacy-solo-fixture-red', 'legacy-solo-owner-red', 'legacy-solo-current-joint']:
    source = SCRATCH / label
    target = OUT / 'runs' / label
    target.mkdir(parents=True, exist_ok=True)
    for name in ['command.json', 'junit.xml', 'pytest.log', 'result.json',
                 'source-before.json', 'source-after.json', 'sitecustomize.py',
                 'legacy_paths.py', 'fixture-path-relocation.json']:
        p = source / name
        if p.is_file():
            shutil.copyfile(p, target / name)
    shutil.copytree(source / 'guards', target / 'guards', dirs_exist_ok=True)
for name in ['run_acceptance.py', 'parent_run_acceptance.py', 'archive_solo.py']:
    shutil.copyfile(SCRATCH / name, OUT / name)

diff = ''
for rel in [ensure, *preserved]:
    diff += ''.join(difflib.unified_diff(
        (OUT / 'before' / rel).read_text().splitlines(keepends=True),
        (ROOT / rel).read_text().splitlines(keepends=True),
        fromfile='before/' + rel, tofile='current/' + rel))
(OUT / 'solo-only.patch').write_text(diff)
verified_at = load(OUT / 'joint-driver.json')['verified_at']
closure = {
    'verified_at': verified_at,
    'scope': 'Single-writer completion of the known direct-caller compatibility debt; isolated repair only',
    'agent_or_real_model_run': False,
    'production_account_database_or_trade_run': False,
    'joint': {
        'passed': len(current['cases']), 'failed': 0, 'errors': 0, 'skipped': 0,
        'original106_preserved': True, 'original74_preserved_and_now_pass': True,
        'new_cases': list(added.elements()),
        'source_count': len(source_after), 'source_drift': [],
        'guard_violations': [], 'guard_processes': len(current['guard_pids']),
        'synthetic_child_processes': len(current['native_child_pids']),
        'unguarded_native_children': [], 'index_unchanged': True,
        'groups': dict(Counter(c['id'].split('::')[0] for c in current['cases'])),
    },
    'preserved_original_test_functions_arguments_decorators_and_assertions': preserved,
    'shared_legacy_fixture_unchanged': True,
    'production_change_only_in_retry_llm': True,
    'production_fix': 'Ownerless standalone delivery is not a reusable research identity; owned receipt failures remain fatal',
    'earlier29_failure_diagnosis': '27 resolved by current explicit synthetic auxiliary binding; two ownerless valid-delivery cases exposed an actual receipt regression, now repaired',
    'original_red_results_preserved': True,
    'source_sha256': source_after,
    'price163_evidence': '../d1-signed-implementation/price-final/closure.json',
    'price163_all32_sources_still_match': True,
    'price163_not_rerun_or_added_to_joint_count': True,
    'original_task_counts': {'total': 13, 'limited_completed': 8,
                             'waiting_business_evidence': 5, 'implementation_in_progress': 0},
    'business_pending': {
        'CHART-02': 'Post-fix natural selection/request/result/profile-consumption evidence absent',
        'PRICE-02': 'Actual instrument/day reference and price-band evidence not certified',
        'REASSESS-01': 'Real supplement/model reassessment/downstream natural use not run',
        'DATA-01': 'Explicit alert coverage, compliance scope, fund conflict decision and formal review still missing',
        'HEALTH-01': 'Post-fix real samples and individually bound historical recovery receipts absent',
    },
    'limits': ['Not a production rerun or proof of model understanding',
               'No changed trading policies, numerical thresholds, budgets or permissions',
               'No retroactive identity or self-binding of old production inputs',
               'Not an all-repository test claim; dependency-bound evidence, not a standalone package'],
}
closure['files'] = [{'path': str(p.relative_to(OUT)), 'bytes': p.stat().st_size, 'sha256': digest(p)}
                    for p in sorted(OUT.rglob('*')) if p.is_file() and p.name != 'closure.json']
(OUT / 'closure.json').write_text(json.dumps(closure, ensure_ascii=False, indent=2))
print(json.dumps({k: v for k, v in closure.items() if k in
                  {'verified_at', 'joint', 'original_task_counts', 'business_pending',
                   'price163_all32_sources_still_match'}}, ensure_ascii=False, indent=2))
