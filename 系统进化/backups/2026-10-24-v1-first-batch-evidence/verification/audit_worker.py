"""F1 child audit guard: only frozen source and synthetic fixture IO."""
from pathlib import Path
import sys, os, json, hashlib, fcntl, tempfile
ROOT=Path(__file__).resolve().parent
GROUP=sys.argv[1]
BASE=ROOT/GROUP;APP=BASE/'app';FIX=BASE/'fixtures'
PROD=Path('/Users/chenyang/Downloads/demo/沧海巨浪')
LIB=PROD/'.venv/lib/python3.11/site-packages'
sys.dont_write_bytecode=True
sys.path[:]=[str(APP)]+[p for p in sys.path if p and not Path(p).resolve().is_relative_to(PROD)]
if str(LIB) not in sys.path:sys.path.append(str(LIB))
os.chdir(APP);tempfile.tempdir=str(FIX)
violations=[]
allowed_lib=[Path(sys.base_prefix).resolve(),Path(sys.prefix).resolve(),LIB.resolve()]
def check(value,write=False,dir_fd=None,db=False):
    if value is None or isinstance(value,int) or not isinstance(value,(str,bytes,os.PathLike)):return
    token=os.fsdecode(value)
    if token.startswith('file:'):
        from urllib.parse import unquote,urlsplit
        token=unquote(urlsplit(token).path)
    if dir_fd is not None and dir_fd != -1 and not Path(token).is_absolute():
        parent=os.fsdecode(fcntl.fcntl(dir_fd,50,b'\0'*1024).split(b'\0',1)[0]);token=str(Path(parent)/token)
    path=Path(token).resolve()
    if path.name.startswith('.env') or 'credential' in str(path).lower():raise AssertionError('credential_io:'+str(path))
    if path.is_relative_to(PROD) and not path.is_relative_to(LIB):raise AssertionError('production_io:'+str(path))
    if write and not path.is_relative_to(BASE) and str(path)!='/dev/null':raise AssertionError('outside_group_write:'+str(path))
    if (db or path.suffix in ['.db','.sqlite','.sqlite3']) and not path.is_relative_to(FIX):raise AssertionError('database_not_synthetic_fixture:'+str(path))
    if not write and not (path.is_relative_to(ROOT) or any(path.is_relative_to(p) for p in allowed_lib) or str(path) in ['/dev/null','/dev/urandom','/System/Library/CoreServices/SystemVersion.plist']):raise AssertionError('outside_closure_library_read:'+str(path))
def audit(event,args):
    try:
        if event=='open':
            value,mode,flags=args
            write=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or bool((flags or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
            check(value,write)
        elif event=='sqlite3.connect':check(args[0],True,db=True)
        elif event in ['os.mkdir','os.remove','os.rmdir']:check(args[0],True,args[-1])
        elif event in ['os.chmod','os.utime','os.truncate']:check(args[0],True)
        elif event in ['os.rename','os.link','os.symlink']:check(args[0],True);check(args[1],True)
        elif event in ['subprocess.Popen','os.system','os.posix_spawn','os.exec','os.fork','socket.connect','socket.connect_ex','socket.bind','socket.getaddrinfo']:raise AssertionError('external_effect:'+event)
        elif event=='import':
            name=args[0]
            if name=='src.settings' or 'qmt_client' in name or name.startswith(('src.collectors','dotenv','ibapi','ib_insync')):raise AssertionError('real_settings_broker_import:'+name)
    except AssertionError as exc:violations.append(dict(event=event,reason=str(exc)));raise
sys.addaudithook(audit)
manifest=json.loads((ROOT/'source-manifest.json').read_text())
for rel,m in manifest.items():assert hashlib.sha256((APP/rel).read_bytes()).hexdigest()==m['sha256'],rel
import pytest
subtests=[]
collected=[]
failed_frames=[]
class FixturePaths:
    def pytest_runtest_makereport(self,item,call):
        if call.when=='call' and call.excinfo is not None:
            loc=call.excinfo.traceback[-1].frame.f_locals
            # Read-only receipts from synthetic tests; never change a result.
            failed_frames.append(dict(nodeid=item.nodeid,locals={
                k:repr(loc[k]) for k in ['result','r','report','ctx','side','book'] if k in loc}))
    def pytest_runtest_logreport(self,report):
        context=getattr(report,'context',None)
        if context is not None:
            subtests.append(dict(nodeid=report.nodeid,outcome=report.outcome,
                                 message=getattr(context,'msg',None),
                                 params=getattr(context,'kwargs',{})))
    def pytest_collection_modifyitems(self,items):
        collected.extend(item.nodeid for item in items)
        assert len(collected)==len(set(collected)), 'duplicate case identity'
        for item in items:
            mod=item.module
            if GROUP in ['paper','s2new','s2diagnostic','r1'] and hasattr(mod,'SCRATCH'):
                mod.SCRATCH=BASE if mod.__name__.endswith('paper_plan_driver_20261023') else FIX
            # Imported driver test fixture is not a collected test in these groups.
        driver=sys.modules.get('test_canghai_paper_plan_driver_20261023')
        if driver is not None:driver.SCRATCH=BASE

TESTS={
's1':['tests/test_v1_s1_execution_boundaries_20261024.py'],
'i1':['tests/test_v1_integration_authorization_20261024.py'],
'paper':['tests/test_canghai_paper_execution_20261023.py','tests/test_canghai_paper_parent_review_20261023.py','tests/test_canghai_paper_plan_driver_20261023.py'],
's2diagnostic':['tests/test_audit_d_diagnostics.py::test_pending_fractional_profit_exit_must_not_block_new_hard_stop','tests/test_audit_d_diagnostics.py::test_lowlevel_paper_execute_must_honor_same_default_kill_file'],
's2new':['tests/test_v1_s2_paper_exit_safety_20261024.py'],
'r1':['tests/test_v1_independent_contract_review_20261024.py'],
'staging':['tests/pipeline/test_plan_staging_freshness.py'],
's3':['tests/test_v1_s3_trigger_quote_safety_20261024.py'],
's3diagnostic':['tests/test_s3_ast_diagnostics.py'],
'f1':['tests/test_v1_final_joint_acceptance_20261024.py'],
'closeout':['tests/test_v1_regression_contract_closeout_20261024.py'],
'c1':['tests/test_v1_scan_date_binding_20261024.py'],
'rrparent':['tests/test_canghai_rr_parent_review_20261023.py'],
'rrscope':['tests/test_canghai_rr_scope_20261023.py']}[GROUP]
prime=None;finalizers=[]
if GROUP=='staging':
    import importlib.util
    from types import SimpleNamespace
    spec=importlib.util.spec_from_file_location('s1_isolation_fixture',APP/'tests/test_v1_s1_execution_boundaries_20261024.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    def mktemp(name):
        p=FIX/('primed-'+name);p.mkdir(parents=True,exist_ok=True);return p
    prime=mod.code.__wrapped__(SimpleNamespace(mktemp=mktemp),SimpleNamespace(addfinalizer=finalizers.append));next(prime);os.chdir(APP)
argv=TESTS+['-q','--noconftest','-p','no:cacheprovider','--basetemp',str(FIX/'pytest'),'--junitxml',str(BASE/'junit.xml')]
if '--collect-only' in sys.argv:argv+=['--collect-only']
rc=99
try:rc=pytest.main(argv,plugins=[FixturePaths()])
finally:
    if prime is not None:
        try:next(prime)
        except StopIteration:pass
        for fn in reversed(finalizers):fn()
    (BASE/'failure-receipts.json').write_text(json.dumps(failed_frames,ensure_ascii=False,indent=2))
    (BASE/'subtest-index.json').write_text(json.dumps(subtests,ensure_ascii=False,indent=2,default=repr))
    (BASE/'collected-nodeids.json').write_text(json.dumps(collected,ensure_ascii=False,indent=2))
    (BASE/'run.json').write_text(json.dumps(dict(command=[sys.executable,'-B',str(Path(__file__).resolve()),*sys.argv[1:]],pytest_argv=argv,exit_code=int(rc),violations=violations,synthetic_only=True,rr_adapt=False,subtest_count=len(subtests),collected_count=len(collected),collection_only='--collect-only' in sys.argv),indent=2))
raise SystemExit(98 if violations else rc)
