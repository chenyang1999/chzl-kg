"""Bounded parent reproductions using the handed-off pre-import guard."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT=Path('/Users/chenyang/Downloads/demo/沧海巨浪')
BASE=Path(__file__).resolve().parent
CHILD=Path('/Users/chenyang/.hermes/cache/scratch/r6-local-delivery-20261029-v3')
COUNT_ONLY = sys.argv[1:] == ['count-only']
OUT=BASE/('count-parent-red' if COUNT_ONLY else 'first-parent-red')
OUT.mkdir(exist_ok=False)
BOOT=OUT/'bootstrap'
BOOT.mkdir()
shutil.copyfile(CHILD/'sitecustomize.py',BOOT/'sitecustomize.py')
(OUT/'home').mkdir()
expected=json.loads((CHILD/'source-after.json').read_text())
def manifest(): return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in expected}
before=manifest()
assert before == expected, 'Shared source changed since handoff; do not overwrite or test a guessed checkpoint'
(OUT/'source-before.json').write_text(json.dumps(before,indent=2))
env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(OUT/'home'),
     'HERMES_HOME':str(OUT/'home/.hermes'),'XDG_CONFIG_HOME':str(OUT/'home/.config'),
     'TMPDIR':'/Users/chenyang/.hermes/cache/scratch','PYTHONPATH':str(BOOT)+os.pathsep+str(ROOT),
     'R6_GUARD_DIR':str(OUT/'guards'),'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1',
     'PYTHONDONTWRITEBYTECODE':'1','LANG':'en_US.UTF-8'}
selected = str(BASE/'parent_cases.py') + ('::test_partial_review_updates_explicit_zero_evaluated_count' if COUNT_ONLY else '')
cmd=[str(ROOT/'.venv/bin/python'),'-B','-m','pytest',selected,
     '--noconftest','-p','no:cacheprovider','--basetemp',str(OUT/'cases'),
     '--junitxml='+str(OUT/'junit.xml'),'--tb=short','-q']
(OUT/'command.json').write_text(json.dumps({'argv':cmd,'environment':env,'cwd':str(ROOT)},indent=2))
with (OUT/'pytest.log').open('wb') as log:
    result=subprocess.run(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=90)
after=manifest()
(OUT/'source-after.json').write_text(json.dumps(after,indent=2))
cases=[]
for x in ET.parse(OUT/'junit.xml').getroot().iter('testcase'):
    cases.append({'name':x.attrib['name'],'failed':x.find('failure') is not None,'error':x.find('error') is not None})
violations=[str(p) for p in (OUT/'guards').glob('violation-*.json')]
record={'exit_code':result.returncode,'cases':cases,'source_unchanged':before==after,'guard_violations':violations}
(OUT/'result.json').write_text(json.dumps(record,indent=2))
print(json.dumps(record,indent=2))
print((OUT/'pytest.log').read_text())
assert len(cases)==(1 if COUNT_ONLY else 3) and all(x['failed'] and not x['error'] for x in cases)
assert before==after and not violations
