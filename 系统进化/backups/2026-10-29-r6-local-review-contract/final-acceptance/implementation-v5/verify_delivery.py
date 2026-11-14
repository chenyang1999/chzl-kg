"""Bounded artifact verification; no model, app import, or production data."""
from pathlib import Path
import ast, collections, difflib, hashlib, json, shutil, subprocess
import xml.etree.ElementTree as ET
R=Path('/Users/chenyang/Downloads/demo/沧海巨浪')
S=Path('/Users/chenyang/.hermes/cache/scratch')
O=S/'r6-local-delivery-20261029-v5'
V=S/'r6-local-delivery-20261029-v3'
B=S/'r6-local-delivery-20261029-v4/before'
P=S/'r6-parent-review-20261029'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def nodes(p):
    return [x.attrib.get('classname','')+'::'+x.attrib['name'] for x in ET.parse(p).getroot().iter('testcase')]
def functions(p):
    return {x.name:x for x in ast.parse(p.read_text()).body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef)) and x.name.startswith('test_')}
def asserts(node): return [ast.dump(x,include_attributes=False) for x in ast.walk(node) if isinstance(x,ast.Assert)]
before=json.loads((O/'source-before.json').read_text())
after=json.loads((O/'source-after.json').read_text())
current={p:sha(R/p) for p in after}
assert before==after==current
old=nodes(V/'junit.xml');new=nodes(O/'junit.xml')
assert len(set(old))==len(old) and len(set(new))==len(new)
assert set(old)<=set(new)
oldfunctions=functions(B/'tests/pipeline/test_r6_local_revision.py')
newfunctions=functions(R/'tests/pipeline/test_r6_local_revision.py')
for name,node in oldfunctions.items():
    assert name in newfunctions
    other=newfunctions[name]
    assert asserts(node)==asserts(other),name
    assert [ast.dump(x) for x in node.decorator_list]==[ast.dump(x) for x in other.decorator_list],name
    assert ast.dump(node.args)==ast.dump(other.args),name
parents=functions(P/'parent_cases.py')
for name,node in parents.items():assert ast.dump(node)==ast.dump(newfunctions[name]),name
# Preserve identities and original red evidence; do not rewrite them.
history=[V/'result.json',V/'junit.xml',V/'source-after.json',V/'repair-only.patch',
         P/'parent_cases.py',P/'first-parent-red/junit.xml',P/'count-parent-red/junit.xml',
         S/'r6-local-delivery-20261029-v4/result.json',S/'r6-local-delivery-20261029-v4/junit.xml']
history_manifest={str(p):sha(p) for p in history}
changed=[p for p in current if sha(B/p)!=current[p]]
assert set(changed)=={'scripts/research/pipeline_artifacts.py','scripts/research/pipeline_state.py','tests/pipeline/test_r6_local_revision.py'}
patch=[]
for path in changed:
    patch.extend(difflib.unified_diff((B/path).read_text().splitlines(keepends=True),
        (R/path).read_text().splitlines(keepends=True),fromfile='a/'+path,tofile='b/'+path))
(O/'v3-to-final.patch').write_text(''.join(patch))
# Cumulative approved-original patch must reproduce exact current source bytes.
a=json.loads((R/'chzl_kg/系统进化/backups/2026-10-29-r6-local-review-contract/approval.json').read_text())
source=[x['path'] for x in a['code_baseline']]
replay=O/'patch-replay';replay.mkdir(exist_ok=False)
for path in source:
    target=replay/path;target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(R/'chzl_kg/系统进化/backups/2026-10-29-r6-local-review-contract/implementation-before'/path,target)
commands=[]
for opts in (['--check'],[]):
    cmd=['/usr/bin/git','apply',*opts,str(O/'repair-only.patch')]
    result=subprocess.run(cmd,cwd=replay,capture_output=True,text=True)
    commands.append({'argv':cmd,'cwd':str(replay),'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
    assert result.returncode==0
replayed={p:sha(replay/p) for p in source+['tests/pipeline/test_r6_local_revision.py']}
assert all(current[p]==s for p,s in replayed.items())
assert sha(O/'sitecustomize.py')==sha(V/'sitecustomize.py')
counts=dict(collections.Counter(n.split('::')[0] for n in new))
result={'junit_total':len(new),'junit_groups':counts,'original_v3_identities':len(old),
        'missing_v3_identities':sorted(set(old)-set(new)),'added_identities':sorted(set(new)-set(old)),
        'original_assertions_decorators_signatures_preserved':True,
        'parent_original_functions_ast_equal':sorted(parents),'source_current_unchanged':current==after,
        'changed_since_v3':changed,'source_sha256':current,'history_sha256':history_manifest,
        'cumulative_patch_sha256':sha(O/'repair-only.patch'),'v3_delta_patch_sha256':sha(O/'v3-to-final.patch'),
        'guard_bootstrap_exact_v3':True,'index_sha256':sha(R/'.git/index'),
        'patch_replay':commands,'replayed_sha256':replayed}
(O/'delivery-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in result.items() if k not in {'source_sha256','history_sha256','patch_replay','replayed_sha256','added_identities'}},ensure_ascii=False,indent=2))
