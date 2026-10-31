"""Bounded parent acceptance; full cohort once, installed wrapper once."""
from pathlib import Path
import datetime
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path('/Users/chenyang/Downloads/demo/沧海巨浪')
CHILD = Path('/Users/chenyang/.hermes/cache/scratch/d1-event-20261029-1039')
OUT = Path(__file__).resolve().parent
mode = 'wrapper' if sys.argv[1:] == ['wrapper'] else 'full'
result_path = OUT / ('parent-' + mode + '.json')
assert not result_path.exists(), 'do not overwrite or rerun an accepted checkpoint'
recorded = json.loads((CHILD / 'manifest.tested.json').read_text())
source_paths = [p for p in recorded if p not in ('.git/index', 'skills/main_decision_v1/SKILL.md')]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def snapshot():
    return {p: sha(ROOT / p) for p in source_paths}

def signed_section(path):
    text = path.read_text()
    return text[text.index('### Step 3.5.9 —'):text.index('### Step 3.6 —')]

policy = ROOT / 'skills/main_decision_v1/SKILL.md'
expected_policy = ROOT / 'chzl_kg/系统进化/backups/2026-10-29-event-reassessment-signed/main_decision_v1.expected.md'
assert signed_section(policy) == signed_section(expected_policy), 'approved section changed'
before = snapshot()
index = sha(ROOT / '.git/index')
assert index == 'ac7ff7479ac6a4bc2f9f0bdbb50b45e405e26164731dd8dfbe0a5f21ba950143'
changed_since_child = [p for p, value in before.items() if value != recorded[p]]
node = 'tests/pipeline/test_intraday_event_reassessment.py'
if mode == 'wrapper':
    node += '::test_proposed_wrapper_overlay_uses_real_detector_entry'
cmd = [str(ROOT / '.venv/bin/python'), '-B', '-m', 'pytest', node,
       '--noconftest', '-c', '/dev/null', '-p', 'no:cacheprovider',
       '--basetemp', str(OUT / ('base-' + mode)), '--junitxml', str(OUT / (mode + '.xml')),
       '-q', '--tb=short']
env = {'PATH': '/bin:/usr/bin', 'HOME': str(OUT), 'TMPDIR': str(OUT),
       'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1', 'PYTHONDONTWRITEBYTECODE': '1',
       'TZ': 'Asia/Shanghai', 'LANG': 'en_US.UTF-8'}
proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
(OUT / (mode + '.log')).write_text(proc.stdout + proc.stderr)
after = snapshot()
cases = ET.parse(OUT / (mode + '.xml')).findall('.//testcase')
names = [c.attrib['name'] for c in cases]
expected_names = [c.attrib['name'] for c in ET.parse(CHILD / 'pytest-final.xml').findall('.//testcase')]
bad = [c.attrib['name'] for c in cases if c.find('failure') is not None or c.find('error') is not None or c.find('skipped') is not None]
result = {'verified_at': datetime.datetime.now().astimezone().isoformat(),
          'mode': mode, 'command': cmd, 'environment': env, 'exit_code': proc.returncode,
          'case_count': len(cases), 'test_names': names, 'bad_cases': bad,
          'before': before, 'after': after, 'source_unchanged': before == after,
          'changed_since_child': changed_since_child,
          'index_unchanged': index == sha(ROOT / '.git/index'),
          'signed_section_unchanged': signed_section(policy) == signed_section(expected_policy),
          'current_whole_skill_sha256': sha(policy),
          'business_model_or_market_invocation': False}
result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(proc.stdout + proc.stderr)
print(json.dumps({k: v for k, v in result.items() if k not in ('before', 'after', 'test_names', 'environment')}, ensure_ascii=False, indent=2))
assert proc.returncode == 0 and not bad and before == after
assert result['index_unchanged'] and result['signed_section_unchanged']
if mode == 'full':
    assert len(names) == len(set(names)) and sorted(names) == sorted(expected_names)
else:
    assert names == ['test_proposed_wrapper_overlay_uses_real_detector_entry']
