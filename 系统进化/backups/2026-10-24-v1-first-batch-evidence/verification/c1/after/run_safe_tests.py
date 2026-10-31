"""Audited C1 runner: fixed collection, frozen source, synthetic transport."""
from pathlib import Path
import sys, os, json, hashlib, tempfile, fcntl
B=Path(__file__).resolve().parent
APP=B/'app'; FIX=B/'fixtures'
P=Path('/Users/chenyang/Downloads/demo/沧海巨浪')
LIB=P/'.venv/lib/python3.11/site-packages'
sys.dont_write_bytecode=True
sys.path[:]=[str(APP),str(APP/'tests')]+[x for x in sys.path if x and not Path(x).resolve().is_relative_to(P)]
if LIB.is_dir():sys.path.append(str(LIB))
os.environ.update(PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(FIX),TMP=str(FIX),TEMP=str(FIX))
os.chdir(APP);tempfile.tempdir=str(FIX)
violations=[]
allowed_lib=[Path(sys.base_prefix).resolve(),Path(sys.prefix).resolve(),LIB.resolve()]
def check(value,write=False,dir_fd=None):
    if value is None or isinstance(value,int) or not isinstance(value,(str,bytes,os.PathLike)):return
    token=os.fsdecode(value)
    if dir_fd is not None and dir_fd != -1 and not Path(token).is_absolute():
        parent=os.fsdecode(fcntl.fcntl(dir_fd,50,b'\0'*1024).split(b'\0',1)[0]);token=str(Path(parent)/token)
    path=Path(token).resolve()
    if path.name.startswith('.env') or 'credential' in str(path).lower():raise AssertionError('credential access forbidden')
    if path.is_relative_to(P) and not path.is_relative_to(LIB):raise AssertionError('production access:'+str(path))
    if write and not path.is_relative_to(B) and str(path)!='/dev/null':raise AssertionError('outside C1 stage write:'+str(path))
    if not write and not (path.is_relative_to(B) or any(path.is_relative_to(p) for p in allowed_lib) or str(path) in ('/dev/null','/dev/urandom','/System/Library/CoreServices/SystemVersion.plist')):raise AssertionError('outside closure/library read:'+str(path))
def audit(event,args):
    try:
        if event=='open':
            value,mode,flags=args
            write=(isinstance(mode,str) and any(c in mode for c in 'wax+')) or bool((flags or 0)&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND))
            check(value,write)
        elif event in ('os.mkdir','os.remove','os.rmdir'):check(args[0],True,args[-1])
        elif event in ('os.chmod','os.utime','os.truncate'):check(args[0],True)
        elif event in ('os.rename','os.link','os.symlink'):check(args[0],True);check(args[1],True)
        elif event in ('sqlite3.connect','subprocess.Popen','os.system','os.posix_spawn','os.exec','os.fork','socket.connect','socket.connect_ex','socket.bind','socket.getaddrinfo'):raise AssertionError('external effect:'+event)
        elif event=='import':
            name=args[0]
            if name=='src.settings' or 'qmt_client' in name or name.startswith(('src.collectors','dotenv','ibapi','ib_insync')):raise AssertionError('forbidden dependency:'+name)
    except AssertionError as exc:
        violations.append(dict(event=event,reason=str(exc)));raise
sys.addaudithook(audit)
manifest=json.loads((B/'source-sha256.json').read_text())
for rel,digest in manifest.items():assert hashlib.sha256((APP/rel).read_bytes()).hexdigest()==digest,rel
hashes={str(p.relative_to(B)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [*sorted(APP.rglob('*.py')),B/'run_safe_tests.py']}
(B/'tested-all-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
import pytest
suite=sys.argv[1]
TESTS={'f2':['tests/test_f2_final_safety.py'], 'c1':['tests/test_v1_scan_date_binding_20261024.py'], 'i1':['tests/test_v1_integration_authorization_20261024.py']}[suite]
counts={'f2':86,'c1':47,'i1':71}
collected=[]
class FixedCollection:
    def pytest_collection_modifyitems(self,items):
        collected.extend(item.nodeid for item in items)
        assert len(collected)==counts[suite],(suite,len(collected),counts[suite])
        assert len(set(collected))==len(collected)
        (B/(suite+'-collection.json')).write_text(json.dumps(collected,indent=2)+'\n')
argv=TESTS+['-q','--noconftest','-p','no:cacheprovider','--basetemp',str(FIX/suite),'--junitxml',str(B/(suite+'-junit.xml'))]
rc=99
try:rc=pytest.main(argv,plugins=[FixedCollection()])
finally:
    (B/(suite+'-run.json')).write_text(json.dumps(dict(command=[sys.executable,'-B',str(Path(__file__).resolve()),suite],pytest_argv=argv,exit_code=int(rc),violations=violations,collected=len(collected),synthetic_only=True,production_live_certified=False),indent=2)+'\n')
raise SystemExit(98 if violations else rc)
