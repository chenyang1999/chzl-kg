from pathlib import Path
import os,sys,json,hashlib,subprocess,xml.etree.ElementTree as ET,shutil
R=Path('/Users/chenyang/Downloads/demo/沧海巨浪'); O=Path(__file__).parent
label=sys.argv[1]; out=O/label;out.mkdir(exist_ok=False)
p=R/'chzl_kg/系统进化/backups/2026-10-29-r6-local-review-contract/final-acceptance/parent/sitecustomize.py'
# Complete inherited R6 bootstrap, not just its audit function.
text=p.read_text(); (out/'sitecustomize.py').write_text(text)
(out/'home').mkdir(); (out/'guards').mkdir()
# Bound processes only: real R6 synthetic native launcher, no arbitrary child.
with (out/'sitecustomize.py').open('a') as f:
 f.write('''
def bounded_processes(event,args):
    if event != 'subprocess.Popen': return
    exe=str(args[0]); argv=list(args[1]); cwd=Path(args[2] or Path.cwd()).absolute()
    if not cwd.is_relative_to(SCRATCH): reject('subprocess cwd',cwd)
    allowed=(Path(exe).absolute().is_relative_to(SCRATCH) or
             exe in {'/usr/bin/sandbox-exec','/bin/bash'} or
             Path(exe).resolve()==Path(sys.executable).resolve())
    if not allowed: reject('unbounded subprocess',exe)
sys.addaudithook(bounded_processes)
''')
env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(out/'home'),'HERMES_HOME':str(out/'home/.hermes'), 'XDG_CONFIG_HOME':str(out/'home/.config'),'TMPDIR':str(O),'PYTHONPATH':str(out),'R6_GUARD_DIR':str(out/'guards'),'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1','PYTHONDONTWRITEBYTECODE':'1','LANG':'en_US.UTF-8'}
env['D1_BASELINE_SOURCE']=str(O/'ensure.before.py')
tests=sys.argv[2:] or ['tests/pipeline/test_d1_selective_reassessment.py']
cmd=[str(R/'.venv/bin/python'),'-B','-m','pytest',*tests,'--noconftest','-p','no:cacheprovider','--basetemp',str(out/'cases'),'--junitxml='+str(out/'junit.xml'),'--tb=short','-q']
monitor=['scripts/plan/ensure_watchlist_plan.py',*tests,'scripts/research/pipeline_state.py','scripts/research/pipeline_artifacts.py','scripts/research/build_research_summary.py','scripts/research/native_usage.py','scripts/research/run_research_shell.sh','tests/pipeline/test_r6_local_revision.py']
if label.startswith('legacy'):
 with (out/'sitecustomize.py').open('a') as f:f.write('\n# Suppress urllib3 import-only IPv6 bind probe, not networking guards.\nimport socket\nsocket.has_ipv6=False\n')
 if label=='legacy-baseline':env['D1_LEGACY_SOURCE']=str(O/'ensure.before.py')
 (out/'legacy_paths.py').write_text('''from pathlib import Path
import json,os,shutil
original_copy=shutil.copyfile
def copy_source(src,dst,*a,**kw):
    if str(src).endswith('/scripts/plan/ensure_watchlist_plan.py') and os.environ.get('D1_LEGACY_SOURCE'):
        src=os.environ['D1_LEGACY_SOURCE']
    return original_copy(src,dst,*a,**kw)
shutil.copyfile=copy_source
def pytest_collection_modifyitems(items):
    changed=[]
    for item in items:
        legacy=getattr(item.module,'legacy',None)
        if legacy is not None:
            legacy.SCRATCH=Path('/Users/chenyang/.hermes/cache/scratch')
            changed.append(item.nodeid)
    (Path(os.environ['PYTHONPATH'])/'fixture-path-relocation.json').write_text(json.dumps({'only_change':'legacy.SCRATCH points to approved scratch, HOME remains isolated','nodeids':changed}))
''')
 cmd[5:5]=['-p','legacy_paths']
def manifest():return {p:hashlib.sha256((R/p).read_bytes()).hexdigest() for p in monitor}
before=manifest();index=hashlib.sha256((R/'.git/index').read_bytes()).hexdigest()
(out/'source-before.json').write_text(json.dumps(before,indent=2))
(out/'command.json').write_text(json.dumps({'argv':cmd,'environment':env,'cwd':str(R)},ensure_ascii=False,indent=2))
with (out/'pytest.log').open('wb') as f: p=subprocess.run(cmd,cwd=R,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=180)
after=manifest();(out/'source-after.json').write_text(json.dumps(after,indent=2))
cases=[{'id':c.attrib.get('classname','')+'::'+c.attrib['name'],'failure':c.find('failure') is not None,'error':c.find('error') is not None,'skipped':c.find('skipped') is not None} for c in ET.parse(out/'junit.xml').getroot().iter('testcase')]
guards={int(p.stem.split('-')[1]) for p in (out/'guards').glob('guard-*.json')};children=set()
for path in (out/'cases').rglob('*.json'):
 try:state=json.loads(path.read_text())
 except (ValueError,OSError):continue
 if not isinstance(state,dict):continue
 if path.name=='launch.json' and 'pid' in state:children.add(state['pid'])
 for rec in state.get('resource_observation',{}).get('attempts',{}).values():
  if rec.get('native_process'):children.add(rec['native_process']['pid'])
result={'exit_code':p.returncode,'cases':cases,'source_unchanged':before==after,'index_unchanged':index==hashlib.sha256((R/'.git/index').read_bytes()).hexdigest(),'guard_violations':[str(p) for p in (out/'guards').glob('violation-*.json')],'guard_pids':sorted(guards),'native_child_pids':sorted(children),'unguarded_native_children':sorted(children-guards)}
(out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2));print((out/'pytest.log').read_text());sys.exit(p.returncode)
