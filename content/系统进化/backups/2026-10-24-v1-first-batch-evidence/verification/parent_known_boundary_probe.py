"""Read-only source snapshot; replay independent safety probes offline."""
from pathlib import Path
from datetime import datetime, timezone
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parent
REPO = Path('/Users/chenyang/Downloads/demo/沧海巨浪')
REFERENCE = BASE / 'C1/after'
ROOT = BASE / ('parent-boundary-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8])
ROOT.mkdir()
(ROOT / 'fixtures').mkdir()
original_manifest = json.loads((REFERENCE / 'source-sha256.json').read_text())
manifest = {}
origins = {}
for rel in original_manifest:
    if rel == 'tests/test_f2_final_safety.py':
        src = REFERENCE / 'app' / rel
        origins[rel] = 'unchanged independent F2 test'
    else:
        src = REPO / rel
        origins[rel] = 'current_worktree'
    assert src.is_file() and not src.is_symlink(), rel
    blob = src.read_bytes()
    ast.parse(blob)
    dest = ROOT / 'app' / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(blob)
    manifest[rel] = hashlib.sha256(blob).hexdigest()
# Explicit empty package shims avoid importing production package side effects.
for directory in ['scripts', 'scripts/research', 'src', 'src/execute', 'src/plan',
                  'src/trading_agent', 'trading', 'trading/schema', 'trading/watcher',
                  'trading/order', 'trading/executors', 'tests']:
    target = ROOT / 'app' / directory / '__init__.py'
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('')
shutil.copyfile(REFERENCE / 'run_safe_tests.py', ROOT / 'run_safe_tests.py')
(ROOT / 'source-sha256.json').write_text(json.dumps(manifest, indent=2))
(ROOT / 'source-origins.json').write_text(json.dumps(origins, indent=2))
env = {k: v for k, v in os.environ.items() if k in ['PATH', 'HOME', 'LANG', 'LC_ALL']}
env.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(ROOT / 'fixtures'))
command = [sys.executable, '-B', str(ROOT / 'run_safe_tests.py'), 'f2']
with (ROOT / 'f2-stdout.log').open('w') as log:
    completed = subprocess.run(command, cwd=ROOT / 'app', env=env, stdout=log, stderr=subprocess.STDOUT)
rows = []
for case in ET.parse(ROOT / 'f2-junit.xml').iter('testcase'):
    status = next((s for s in ['failure', 'error', 'skipped'] if case.find(s) is not None), 'passed')
    row = {'identity': case.get('classname', '') + '::' + case.get('name', ''), 'status': status}
    if status != 'passed':
        row['detail'] = ''.join(case.find(status).itertext())
    rows.append(row)
assert len(rows) == len({r['identity'] for r in rows}), 'duplicate probe identity'
counts = {s: sum(r['status'] == s for r in rows) for s in ['passed', 'failure', 'error', 'skipped']}
failures = [r for r in rows if r['status'] != 'passed']
meta = json.loads((ROOT / 'f2-run.json').read_text())
drift = [rel for rel, expected in manifest.items() if origins[rel] == 'current_worktree' and hashlib.sha256((REPO / rel).read_bytes()).hexdigest() != expected]
result = dict(root=str(ROOT), command=command, actual_exit_code=completed.returncode,
              counts=counts, cases=len(rows), failures=failures,
              guard_violations=meta.get('violations'), current_source_drift=drift,
              synthetic_only=True, production_live_certified=False)
(ROOT / 'parent-boundary-summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps({k: result[k] for k in ['root', 'actual_exit_code', 'counts', 'cases', 'guard_violations', 'current_source_drift']}, ensure_ascii=False))
for failure in failures:
    print('KNOWN_BOUNDARY_FAILURE=' + failure['identity'])
# Do not erase the original test exit: these remain unresolved safety expectations.
raise SystemExit(completed.returncode)
