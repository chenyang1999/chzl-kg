from pathlib import Path
import hashlib,json,os,subprocess,sys,shutil,difflib,xml.etree.ElementTree as ET
REPO=Path('/Users/chenyang/Downloads/demo/沧海巨浪')
SCRATCH=Path('/Users/chenyang/.hermes/cache/scratch')
OUT=SCRATCH/'r6-local-delivery-20261029-v3'
OUT.mkdir(exist_ok=True)
APPROVAL=REPO/'chzl_kg/系统进化/backups/2026-10-29-r6-local-review-contract'
a=json.loads((APPROVAL/'approval.json').read_text())
source=[r['path'] for r in a['code_baseline']]
tests=['tests/pipeline/test_r6_local_revision.py','tests/pipeline/test_bound_auxiliary_inputs.py','tests/pipeline/test_native_usage_observation.py']
contracts=[x['target'] for x in a['targets']]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def manifest():return {p:sha(REPO/p) for p in source+tests+contracts}
before=manifest();index=sha(REPO/'.git/index')
for item in a['targets']:assert before[item['target']]==item['candidate_sha256']
assert index==a['index_sha256']
(OUT/'source-before.json').write_text(json.dumps(before,indent=2,ensure_ascii=False))
patch=[]
for path in source:
    old=(APPROVAL/'implementation-before'/path).read_text().splitlines(keepends=True)
    new=(REPO/path).read_text().splitlines(keepends=True)
    assert sha(APPROVAL/'implementation-before'/path)==next(x['sha256'] for x in a['code_baseline'] if x['path']==path)
    patch.extend(difflib.unified_diff(old,new,fromfile='a/'+path,tofile='b/'+path))
path=tests[0]
patch.extend(difflib.unified_diff([], (REPO/path).read_text().splitlines(keepends=True),fromfile='/dev/null',tofile='b/'+path))
(OUT/'repair-only.patch').write_text(''.join(patch))
for path in source+[tests[0]]:
    dest=OUT/'tested-source'/path;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(REPO/path,dest)
for path in ('sitecustomize.py','guard_selftest.py'):
    shutil.copyfile(SCRATCH/'r6-local-bootstrap'/path,OUT/path)
(OUT/'home').mkdir(exist_ok=True)
env={'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','HOME':str(OUT/'home'),'HERMES_HOME':str(OUT/'home/.hermes'),
     'XDG_CONFIG_HOME':str(OUT/'home/.config'),'TMPDIR':str(SCRATCH),
     'PYTHONPATH':str(SCRATCH/'r6-local-bootstrap'),'R6_GUARD_DIR':str(OUT/'guards'),
     'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1','PYTHONDONTWRITEBYTECODE':'1','LANG':'en_US.UTF-8'}
native_names=['test_native_totals_separate_reported_subtotal_from_unprovable_authority','test_legal_zero_is_preserved_without_asserting_usage_coverage',
              'test_same_binding_idempotent_conflicting_report_rejected','test_superseded_attempt_and_run_cannot_accept_report',
              'test_safety_net_observation_without_pipeline_does_not_invent_business_success',
              'test_safety_observation_terminal_pipeline_preserves_business_bytes',
              'test_real_isolated_launcher_pid_argv_and_nonzero_report',
              'test_actual_local_child_does_not_outlive_pid_registration_failure','test_popen_itself_failure_remains_a_failed_launch_observation']
selected=[tests[0],tests[1]]+[tests[2]+'::'+name for name in native_names]
cmd=[str(REPO/'.venv/bin/python'),'-B','-m','pytest',*selected,'--noconftest','-p','no:cacheprovider',
     '--basetemp',str(OUT/'cases'),'--junitxml='+str(OUT/'junit.xml'),'--tb=short','-q']
(OUT/'command.json').write_text(json.dumps({'argv':cmd,'environment':env,'cwd':str(REPO)},ensure_ascii=False,indent=2))
with (OUT/'pytest.log').open('wb') as log:
    run=subprocess.run(cmd,cwd=REPO,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=150)
after=manifest();(OUT/'source-after.json').write_text(json.dumps(after,ensure_ascii=False,indent=2))
violations=list((OUT/'guards').glob('violation-*.json'))
guards={int(p.stem.split('-')[1]) for p in (OUT/'guards').glob('guard-*.json')}
# Every actual native synthetic child must have inherited the startup guard.
children=set()
for p in (OUT/'cases').rglob('state.json'):
    value=json.loads(p.read_text())
    for rec in value.get('resource_observation',{}).get('attempts',{}).values():
        if rec.get('native_process'):children.add(rec['native_process']['pid'])
children_unguarded=sorted(children-guards)
cases=[]
if (OUT/'junit.xml').exists():
    for case in ET.parse(OUT/'junit.xml').getroot().iter('testcase'):
        cases.append({'identity':case.attrib.get('classname','')+'::'+case.attrib['name'],
                      'failed':case.find('failure') is not None,'error':case.find('error') is not None,
                      'skipped':case.find('skipped') is not None})
result={'exit_code':run.returncode,'cases':cases,'case_count':len(cases),'failure_count':sum(c['failed'] for c in cases),
        'error_count':sum(c['error'] for c in cases),'skip_count':sum(c['skipped'] for c in cases),
        'source_unchanged':before==after,'index_before':index,'index_after':sha(REPO/'.git/index'),
        'guard_process_count':len(guards),'native_child_count':len(children),'unguarded_native_children':children_unguarded,
        'guard_violations':[str(p) for p in violations], 'repair_patch_sha256':sha(OUT/'repair-only.patch'),
        'production_model_or_market_run':False,'natural_adoption_verified':False}
(OUT/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in result.items() if k!='cases'},ensure_ascii=False,indent=2))
assert run.returncode==0 and before==after and index==sha(REPO/'.git/index') and not violations and not children_unguarded
