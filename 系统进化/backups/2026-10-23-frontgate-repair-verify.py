"""Parent acceptance: relocated real sources, explicit tests, offline audit hook."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

REPO = Path('/Users/chenyang/Downloads/demo/沧海巨浪')
SCRATCH = Path('/Users/chenyang/.hermes/cache/scratch')
PYTHON = REPO / '.venv/bin/python'
NEW_TESTS = [
    'tests/test_canghai_repair_plan_contracts_20261023.py',
    'tests/test_canghai_repair_reversal_breadth_20261023.py',
    'tests/test_canghai_repair_B_parent_review_20261023.py',
    'tests/test_canghai_repair_auction_overseas_20261023.py',
    'tests/test_canghai_repair_announcements_ledger_20261023.py',
]
EXISTING_TESTS = [
    'tests/health/test_datasource_ledger.py',
    'tests/pipeline/test_plan_staging_freshness.py',
]
SCRIPT_FILES = [
    'scripts/research/pipeline_artifacts.py',
    'scripts/research/build_research_summary.py',
    'scripts/plan/ensure_watchlist_plan.py',
    'scripts/fetch/run_auction_snapshot.py',
    'scripts/plan/render_auction_judgment.py',
    'scripts/fetch/run_overseas_snapshot.py',
    'scripts/intraday/run_intraday_snapshot.py',
    'scripts/intraday/append_intraday_md.py',
    'scripts/plan/run_retreat_reversal.py',
    'scripts/health/datasource_ledger.py',
]
GUARD = r'''import json,os,sys,traceback,socket
from pathlib import Path
# urllib3 otherwise probes IPv6 by binding ::1:0 during import. Stub only
# this capability bit before import; keep all actual sockets blocked.
socket.has_ipv6=False
ROOT=Path(__file__).resolve().parent
SCRATCH=Path('/Users/chenyang/.hermes/cache/scratch').resolve()
REAL=Path('/Users/chenyang/Downloads/demo/沧海巨浪').resolve()
PRIVATE=Path('/Users/chenyang/.hermes').resolve()
violations=[]
def deny(reason):
    violations.append({'reason':reason,'test':os.environ.get('PYTEST_CURRENT_TEST'),'stack':traceback.format_stack(limit=12)})
    raise AssertionError('acceptance boundary: '+reason)
def guard(event,args):
    if event in {'socket.connect','socket.connect_ex','socket.bind','subprocess.Popen','os.system'}:
        deny(event)
    if event=='sqlite3.connect':
        value=str(args[0])
        if value!=':memory:':
            p=Path(value.removeprefix('file:').split('?',1)[0]).resolve()
            if not p.is_relative_to(SCRATCH):deny('real DB:'+str(p))
    if event=='open':
        value,mode,flags=args
        if not isinstance(value,(str,bytes,os.PathLike)):return
        p=Path(os.fsdecode(value)).resolve()
        write=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or (isinstance(flags,int) and flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
        if write and p!=Path(os.devnull) and not p.is_relative_to(SCRATCH):deny('outside write:'+str(p))
        if not write and not p.is_relative_to(SCRATCH):
            if p.is_relative_to(PRIVATE) or p.is_relative_to(REAL/'data') or p.is_relative_to(REAL/'chzl_kg') or p.name=='.env':deny('private read:'+str(p))
    if event in {'os.mkdir','os.remove','os.rmdir','os.rename','os.replace'}:
        for value in args[:2 if event in {'os.rename','os.replace'} else 1]:
            if isinstance(value,(str,bytes,os.PathLike)):
                p=Path(os.fsdecode(value)).resolve()
                if not p.is_relative_to(SCRATCH):deny('outside mutation:'+str(p))
sys.addaudithook(guard)
def pytest_sessionfinish(session,exitstatus):
    out=Path(os.environ['CANGHAI_ACCEPTANCE_GUARD'])
    out.write_text(json.dumps({'violations':violations,'exitstatus_before_guard':int(exitstatus)},ensure_ascii=False,indent=2))
    if violations:session.exitstatus=1
'''

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--phase',choices=['acd','all'],default='all')
    parser.add_argument('--label',default='final')
    args=parser.parse_args()
    destination=SCRATCH/f'canghai_repair_parent_acceptance_20261023_{args.label}'
    destination.mkdir(parents=True,exist_ok=False)
    overlay=destination/'repo'
    overlay.mkdir()
    copied={}
    def copy(rel):
        p=REPO/rel
        if p.is_symlink() or not p.resolve().is_relative_to(REPO):
            raise RuntimeError('refuse source symlink:'+str(p))
        q=overlay/rel
        q.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(p,q)
        copied[rel]=hashlib.sha256(q.read_bytes()).hexdigest()
    for package in ('src','trading'):
        for p in (REPO/package).rglob('*.py'):
            if not p.is_symlink():copy(str(p.relative_to(REPO)))
    tests=[p for p in NEW_TESTS if args.phase=='all' or 'reversal_breadth' not in p]+EXISTING_TESTS
    for rel in SCRIPT_FILES+tests+['tests/conftest.py']:
        copy(rel)
    for rel in ['scripts/__init__.py','scripts/research/__init__.py','scripts/plan/__init__.py','scripts/fetch/__init__.py','scripts/health/__init__.py','scripts/intraday/__init__.py']:
        p=overlay/rel
        p.parent.mkdir(parents=True,exist_ok=True)
        p.touch()
    (overlay/'_acceptance_guard.py').write_text(GUARD)
    guard_path=destination/'guard.json'
    env={k:os.environ[k] for k in ['HOME','PATH','LANG','LC_ALL','SYSTEMROOT'] if k in os.environ}
    env.update(PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONNOUSERSITE='1',TMPDIR=str(destination),PYTHONPATH=str(overlay),CANGHAI_ACCEPTANCE_GUARD=str(guard_path))
    cmd=[str(PYTHON),'-B','-m','pytest','-p','no:cacheprovider','-p','_acceptance_guard','--basetemp='+str(destination/'pytest'),'-q','--tb=short','--junitxml='+str(destination/'acceptance.xml')]+tests
    result=subprocess.run(cmd,cwd=overlay,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=180)
    (destination/'acceptance.log').write_text(result.stdout)
    document=ET.parse(destination/'acceptance.xml').getroot() if (destination/'acceptance.xml').exists() else None
    cases=document.findall('.//testcase') if document is not None else []
    totals={'testcases':len(cases),'failed':sum(bool(c.findall('failure')) for c in cases),'errors':sum(bool(c.findall('error')) for c in cases),'skipped':sum(bool(c.findall('skipped')) for c in cases)}
    guard=json.loads(guard_path.read_text()) if guard_path.exists() else {'violations':['guard never ran']}
    changed=[rel for rel,sha in copied.items() if hashlib.sha256((REPO/rel).read_bytes()).hexdigest()!=sha]
    index=subprocess.check_output(['git','ls-files','--stage','-z'],cwd=REPO)
    payload={'argv':cmd,'cwd':str(overlay),'exit_code':result.returncode,'totals':totals,'guard':guard,'tests':tests,'copied_source_sha256':copied,'source_changed_during_run':changed,'index_unchanged':hashlib.sha256(index).hexdigest()=='c24736dd938685a85db19301280d8b9fdafdf6fb2bab56a056068dc026df152b','log':str(destination/'acceptance.log'),'junit':str(destination/'acceptance.xml')}
    (destination/'acceptance_evidence.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in payload.items() if k!='copied_source_sha256'},ensure_ascii=False,indent=2))
    print(result.stdout[-18000:])
    return result.returncode or int(bool(guard['violations']) or not payload['index_unchanged'])

if __name__=='__main__':raise SystemExit(main())
