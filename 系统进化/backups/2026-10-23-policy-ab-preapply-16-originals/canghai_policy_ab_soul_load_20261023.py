from pathlib import Path
import os, sys, json, hashlib, io, contextlib
SCRATCH=Path('/Users/chenyang/.hermes/cache/scratch')
HOME=SCRATCH/'canghai_policy_AB_hermes_load_home_20261023'
HOME.mkdir(exist_ok=True)
os.environ['HERMES_HOME']=str(HOME)
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
sys.path.insert(0,'/Users/chenyang/.hermes/hermes-agent')
violations=[]
allowed_readonly_subprocesses=[]
def audit(event,args):
    if event=='subprocess.Popen' and list(args[1]) == ['git', 'rev-parse', 'HEAD'] and args[2] == '/Users/chenyang/.hermes/hermes-agent':
        allowed_readonly_subprocesses.append({'argv':['git','rev-parse','HEAD'],'cwd':args[2]})
        return
    path=None
    if event=='open':
        name,mode,flags=args
        if isinstance(name,(str,bytes,os.PathLike)) and ((isinstance(mode,str) and any(c in mode for c in 'wax+')) or isinstance(flags,int) and flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)):
            path=Path(os.fsdecode(name)).absolute()
    elif event in {'os.mkdir','os.remove','os.rmdir','os.chmod','os.rename'}:
        path=Path(os.fsdecode(args[0])).absolute()
        if event=='os.rename':
            dest=Path(os.fsdecode(args[1])).absolute()
            if not dest.is_relative_to(SCRATCH):
                violations.append([event,str(dest)]); raise PermissionError('outside scratch rename denied')
    elif event in {'socket.connect','subprocess.Popen','os.system'}:
        import traceback
        violations.append([event, traceback.format_stack(limit=12)]); raise PermissionError(event)
    if path is not None and not path.is_relative_to(SCRATCH):
        violations.append([event,str(path)]); raise PermissionError('outside scratch write denied')
sys.addaudithook(audit)
from agent.prompt_builder import load_soul_md
rows=[]
captured=io.StringIO()
with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
    for profile in ['canghai-research','canghai-plan']:
        home=Path('/Users/chenyang/.hermes/profiles')/profile
        source=(home/'SOUL.md').read_text().strip()
        loaded=load_soul_md(context_length=200000,home_override=home)
        assert loaded and loaded==source,(profile,'did not load exact profile SOUL')
        rows.append(dict(profile=profile,path=str(home/'SOUL.md'),loaded=True,exact_stripped_source=True,characters=len(loaded),file_sha256=hashlib.sha256((home/'SOUL.md').read_bytes()).hexdigest(),loaded_sha256=hashlib.sha256(loaded.encode()).hexdigest()))
assert not violations, violations
result=dict(loader='agent.prompt_builder.load_soul_md',loader_source='/Users/chenyang/.hermes/hermes-agent/agent/prompt_builder.py',interpreter=sys.executable,home_override_used=True,ambient_home=str(HOME),profile_content_printed=False,profiles=rows,outside_scratch_write_or_network_violations=violations,allowed_readonly_subprocesses=allowed_readonly_subprocesses,scope='loader acceptance only; no production session or research launched')
out=SCRATCH/'canghai_policy_AB_soul_load_20261023.json'
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
