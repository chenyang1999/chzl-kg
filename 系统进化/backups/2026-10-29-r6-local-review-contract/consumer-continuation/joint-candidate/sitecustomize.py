"""Isolated cohort bootstrap, inherited by every synthetic subprocess."""
import sys, os, types, json
from pathlib import Path
SCRATCH=Path('/Users/chenyang/.hermes/cache/scratch').resolve()
REPO=Path('/Users/chenyang/Downloads/demo/沧海巨浪').resolve()
HOME=Path('/Users/chenyang')
RECEIPTS=Path(os.environ.get('R6_GUARD_DIR',str(SCRATCH/'r6-local-guards')))
RECEIPTS.mkdir(exist_ok=True)
# Resolve directory descriptors before audit events lose that context. This
# macOS test bootstrap is not shipped as a production process sandbox.
import fcntl
def anchored(path, fd):
    if fd is None or not isinstance(path,(str,bytes,os.PathLike)) or Path(os.fsdecode(path)).is_absolute():return path
    directory=os.fsdecode(fcntl.fcntl(fd,50,b'\0'*1024).split(b'\0',1)[0])
    return str(Path(directory)/os.fsdecode(path))
def wrap_dirfd(name,key='dir_fd'):
    original=getattr(os,name)
    def wrapped(path,*args,**kw):
        fd=kw.pop(key,None)
        return original(anchored(path,fd),*args,**kw)
    setattr(os,name,wrapped)
for _name in ('open','mkdir','remove','unlink','rmdir','stat','lstat'):
    wrap_dirfd(_name)
for _name in ('rename','replace','link'):
    _original=getattr(os,_name)
    def _wrapped(src,dst,*args,_fn=_original,**kw):
        sfd=kw.pop('src_dir_fd',None);dfd=kw.pop('dst_dir_fd',None)
        return _fn(anchored(src,sfd),anchored(dst,dfd),*args,**kw)
    setattr(os,_name,_wrapped)
_original_symlink=os.symlink
def _symlink(src,dst,*args,**kw):
    return _original_symlink(src,anchored(dst,kw.pop('dir_fd',None)),*args,**kw)
os.symlink=_symlink
VIOLATIONS=[]
def reject(event,path):
    VIOLATIONS.append((event,str(path)))
    (RECEIPTS/('violation-'+str(os.getpid())+'.json')).write_text(json.dumps(VIOLATIONS))
    raise RuntimeError('R6 isolation blocked '+event+': '+str(path))
def checked(v,write=False):
    if not isinstance(v,(str,bytes,os.PathLike)): return
    p=Path(os.fsdecode(v)).absolute()
    if p == Path('/dev/null'): return
    resolved=p.resolve()
    if p.name=='.env' or p.suffix in {'.sqlite','.db'} or (resolved.is_relative_to(HOME/'.hermes') and not resolved.is_relative_to(SCRATCH)):
        reject('private/config/database',p)
    if resolved.is_relative_to(REPO) and not resolved.is_relative_to(REPO/'.venv'):
        if write or resolved.is_relative_to(REPO/'data') or resolved.is_relative_to(REPO/'chzl_kg') or resolved.is_relative_to(REPO/'.git'):
            reject('production IO',p)
    if write and not p.is_relative_to(SCRATCH): reject('write outside scratch',p)
def audit(event,args):
    if event in {'socket.connect','socket.bind','socket.getaddrinfo','sqlite3.connect'}:reject(event,args)
    if event=='open':
        flags=args[2] if len(args)>2 and isinstance(args[2],int) else 0
        mode=args[1] if len(args)>1 and isinstance(args[1],str) else ''
        checked(args[0], bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)) or any(c in mode for c in 'wax+'))
    if event in {'os.remove','os.rmdir','os.mkdir','os.rename','os.link','os.symlink'}:
        positions=(0,1) if event in {'os.rename','os.link'} else (1,) if event=='os.symlink' else (0,)
        for i in positions: checked(args[i],True)
    if event=='subprocess.Popen':
        exe=str(args[0])
        if 'hermes' in exe and not Path(exe).absolute().is_relative_to(SCRATCH):reject('real model',exe)
sys.addaudithook(audit)
settings=types.ModuleType('src.settings');settings.ROOT=Path.cwd();settings.DATA_DIR=Path.cwd()/'data'
sys.modules['src.settings']=settings
(RECEIPTS/('guard-'+str(os.getpid())+'.json')).write_text(json.dumps({'pid':os.getpid(),'cwd':str(Path.cwd()),'installed_before_import':True}))

def bounded_processes(event,args):
    if event != 'subprocess.Popen': return
    exe=str(args[0]); argv=list(args[1]); cwd=Path(args[2] or Path.cwd()).absolute()
    if not cwd.is_relative_to(SCRATCH): reject('subprocess cwd',cwd)
    allowed=(Path(exe).absolute().is_relative_to(SCRATCH) or
             exe in {'/usr/bin/sandbox-exec','/bin/bash'} or
             Path(exe).resolve()==Path(sys.executable).resolve())
    if not allowed: reject('unbounded subprocess',exe)
sys.addaudithook(bounded_processes)

# Explicit tested-source overlay only; never redirect business I/O.
import shutil
_copy_source = shutil.copyfile
def _candidate_copy(src, dst, *args, **kwargs):
    if Path(src).absolute() == REPO/'scripts/plan/ensure_watchlist_plan.py':
        src = os.environ['D1_SELECTIVE_SOURCE']
    return _copy_source(src, dst, *args, **kwargs)
shutil.copyfile = _candidate_copy

# Suppress urllib3 import-only IPv6 bind probe, not networking guards.
import socket
socket.has_ipv6=False
