"""Reuse the reviewed v5 runner for one current-source joint acceptance."""
from pathlib import Path
import ast
from collections import Counter
import json
import os
import xml.etree.ElementTree as ET

ROOT=Path('/Users/chenyang/Downloads/demo/沧海巨浪')
V5=Path('/Users/chenyang/.hermes/cache/scratch/r6-local-delivery-20261029-v5')
OUT=Path('/Users/chenyang/.hermes/cache/scratch/r6-parent-final-joint-20261029')
PEER=ROOT/'chzl_kg/系统进化/backups/2026-10-29-core-review-and-auxiliary/remaining/input54-shared-continue'
assert not OUT.exists(), 'Never replace an existing acceptance receipt'
peer=json.loads((PEER/'closure.json').read_text())
expected=json.loads((V5/'source-after.json').read_text())
text=(V5/'run_acceptance.py').read_text()
old="tests=['tests/pipeline/test_r6_local_revision.py','tests/pipeline/test_bound_auxiliary_inputs.py','tests/pipeline/test_native_usage_observation.py']"
new=old[:-1]+",'tests/pipeline/test_d1_auxiliary_caller_wiring.py','tests/pipeline/test_signed_input_review_contract.py']"
assert text.count(old)==1
text=text.replace(old,new,1)
old='def manifest():return {p:sha(REPO/p) for p in source+tests+contracts}'
new='MONITORED = '+repr(sorted(set(expected)|set(peer['source_sha256'])))+'\ndef manifest():return {p:sha(REPO/p) for p in MONITORED}'
assert text.count(old)==1
text=text.replace(old,new,1)
old='before=manifest();index=sha(REPO/\'.git/index\')'
new=old+'\nassert all(before[p] == v for p,v in '+repr(expected)+'.items()), "v5 handoff source drift"'
assert text.count(old)==1
text=text.replace(old,new,1)
old='selected=[tests[0],tests[1]]+'
assert text.count(old)==1
text=text.replace(old,'selected=[tests[0],tests[1],tests[3],tests[4]]+',1)
os.environ['R6_ACCEPTANCE_OUT']=str(OUT)
# The reused runner installs the handed-off guard before collection, scrubs
# credentials and records every native synthetic child plus before/after SHA.
exec(compile(text,str(V5/'run_acceptance.py'),'exec'),globals())
(OUT/'parent_joint_runner.py').write_bytes(Path(__file__).read_bytes())
(OUT/'effective_reused_runner.py').write_text(text)
result=json.loads((OUT/'result.json').read_text())
identities=[c['identity'] for c in result['cases']]
assert len(identities)==len(set(identities))
v5=json.loads((V5/'result.json').read_text())
assert set(c['identity'] for c in v5['cases']).issubset(identities)
# Existing auxiliary queue: preserve native names/parameters, not a made-up
# total or old empty classname. Its three source files are unchanged.
aux_files=['tests/pipeline/test_bound_auxiliary_inputs.py','tests/pipeline/test_d1_auxiliary_caller_wiring.py','tests/pipeline/test_signed_input_review_contract.py']
for p in aux_files: assert before[p]==peer['source_sha256'][p]
xmls=[]
for path in PEER.rglob('*.xml'):
    tree=ET.parse(path)
    cases=list(tree.getroot().iter('testcase'))
    if len(cases)==peer['cases'] and not any(c.find('failure') is not None or c.find('error') is not None for c in cases):
        xmls.append((path,Counter(c.attrib['name'] for c in cases)))
assert xmls, 'Missing original complete auxiliary queue identity evidence'
assert all(x[1]==xmls[0][1] for x in xmls)
aux_names=Counter(c['identity'].split('::',1)[1] for c in result['cases']
                  if any(c['identity'].split('::',1)[0].endswith(Path(p).stem) for p in aux_files))
assert aux_names==xmls[0][1]
parent_ast=ast.parse(Path('/Users/chenyang/.hermes/cache/scratch/r6-parent-review-20261029/parent_cases.py').read_text())
current_ast=ast.parse((ROOT/'tests/pipeline/test_r6_local_revision.py').read_text())
fn=lambda tree:{x.name:ast.dump(x,include_attributes=False) for x in tree.body if isinstance(x,ast.FunctionDef)}
old_fns,cur_fns=fn(parent_ast),fn(current_ast)
assert all(cur_fns[n]==body for n,body in old_fns.items())
groups=Counter(c['identity'].split('::',1)[0] for c in result['cases'])
closure={'status':'parent_current_joint_acceptance_passed','exit_code':result['exit_code'],
         'unique_case_count':len(identities),'groups':dict(groups),
         'all_v5_case_identities_retained':True,'full_auxiliary_case_names_retained':True,
         'original_parent_counterexample_functions_unchanged':sorted(old_fns),
         'source_before':before,'source_after':after,'source_unchanged':before==after,
         'index_unchanged':result['index_before']==result['index_after'],
         'guard_violations':result['guard_violations'],'native_child_count':result['native_child_count'],
         'unguarded_native_children':result['unguarded_native_children'],
         'contract_and_implementation_only':True,'natural_adoption_proven':False,
         'real_model_or_market_or_account_or_trade_run':False,'stock_readmission_implemented':False}
(OUT/'parent-closure.json').write_text(json.dumps(closure,ensure_ascii=False,indent=2))
print(json.dumps({k:v for k,v in closure.items() if k not in {'source_before','source_after'}},ensure_ascii=False,indent=2))
