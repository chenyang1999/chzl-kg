"""Synthetic R6 revision, real state/receipt/summary/native transport.
No application imports during collection. All execution is relocated to scratch.
"""
from __future__ import annotations
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
import pytest

REPO = Path(__file__).resolve().parents[2]
DATE = '20990106'
A, B = '000001.SZ', '000002.SZ'


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


@pytest.fixture
def native(tmp_path):
    root = tmp_path / 'app'
    target = root / 'scripts/research'
    target.mkdir(parents=True)
    for name in ('pipeline_state.py', 'pipeline_artifacts.py', 'build_research_summary.py', 'native_usage.py', 'run_research_shell.sh'):
        shutil.copyfile(REPO/'scripts/research'/name, target/name)
    for rel in ('scripts/__init__.py', 'scripts/research/__init__.py'):
        (root/rel).write_text('')
    prefixes = ('scripts',)
    modules = {k:v for k,v in sys.modules.items() if k == 'scripts' or k.startswith('scripts.')}
    for k in modules: del sys.modules[k]
    old_path = list(sys.path)
    sys.path.insert(0, str(root))
    try:
        a = importlib.import_module('scripts.research.pipeline_artifacts')
        s = importlib.import_module('scripts.research.pipeline_state')
        b = importlib.import_module('scripts.research.build_research_summary')
        state = {'trade_date': DATE, 'run_id':'baseline-terminal', 'status':'completed', 'started_ns':1,
                 'stages':{}, 'contract_results':{}, 'finished_at':'2099-01-06T08:00:00+08:00'}
        fields = {'R1':{'style':'synthetic', 'position_cap_suggestion':0},
                  'R2':{'main_lines':[{'leaders':[{'ts_code':A},{'ts_code':B}]}]},
                  'R3':{'resonance_top_themes':[], 'alert':False}, 'R4':{'top_events':[], 'zero':0},
                  'R5':{'profiles':[{'ts_code':A},{'ts_code':B}]},
                  'R6':{'counter_arguments':[{'reject_id':'tail', 'severity':'strong_suggest','reason':'tail negative retained'}],
                        'hard_rejects':[{'ts_code':B,'reason':'existing financial veto'}],
                        'formal_review_completed':False, 'review_passed':False, 'patterns_status':{}},
                  'R7':{'main_force':{}}}
        for u, filename in a.UNIT_FILES.items():
            save(root/f'data/research/{DATE}/{filename}', {'trade_date':DATE, 'status':'partial', 'generated_at':'2099-01-05T15:00:00+08:00', **fields[u]})
            md = root/f'chzl_kg/投研交易/{a.MD_DIRS[u]}/{DATE}.md'
            md.parent.mkdir(parents=True, exist_ok=True)
            md.write_text('# original\noriginal negative\nthird\nfourth\nfifth\n')
            state['stages'][u] = {'status':'completed','attempt':1,'attempt_started_ns':1}
            state['contract_results'][u] = {k:{**a.file_version(root,p), 'passed':True,'run_id':state['run_id'],'attempt':1}
                for k,p in [('json',root/f'data/research/{DATE}/{filename}'),('md',md)]}
        sp = s.state_path(root,DATE)
        save(sp,state)
        artifacts = {u:f'data/research/{DATE}/{f}' for u,f in a.UNIT_FILES.items()}
        summary = {'schema_version':'research_summary_v1','trade_date':DATE,'run_id':state['run_id'],
                   'artifacts':artifacts,'orchestrator_status':'partial', 'contract_checks_passed':True,
                   'contract_failures':{},'missing_md':[], 'hard_rejects':fields['R6']['hard_rejects']}
        m = {'schema_version':b.MANIFEST_VERSION,'trade_date':DATE,'run_id':state['run_id'],
             'authorized_main_inputs':artifacts, 'units':{}}
        for u in artifacts:
            m['units'][u] = {k:{**state['contract_results'][u][k], 'receipt_binding':{'status':'verified','run_id':state['run_id'],'attempt':1,'receipt':state['contract_results'][u][k]}}
                             for k in ('json','md')}
        m['summary_projection_sha256'] = b._digest({k:summary.get(k) for k in b.SUMMARY_PROJECTION})
        m['sha256'] = b._digest(m)
        summary['input_manifest'] = m
        summary_path = root/f'data/research/{DATE}/research_summary.json'
        save(summary_path,summary)
        state['stages']['summary'] = {'attempt':1,'attempt_started_ns':1}
        state['contract_results']['summary'] = {**a.file_version(root,summary_path),'passed':True,'run_id':state['run_id'],'attempt':1}
        save(sp,state)
        assert set(b.consume_authorized_inputs(summary,root=root)) == set(a.UNIT_FILES)
        skill = root/'skills/analyze_devil_advocate_v1/SKILL.md'
        skill.parent.mkdir(parents=True)
        shutil.copyfile(REPO/'skills/analyze_devil_advocate_v1/SKILL.md',skill)
        py = root/'.venv/bin/python'
        py.parent.mkdir(parents=True)
        py.symlink_to(sys.executable)
        fake = root/'fake-hermes'
        fake.write_text('#!'+sys.executable+'\n'+FAKE_HERMES)
        fake.chmod(0o755)
        shell = target/'run_research_shell.sh'
        shell.write_text(shell.read_text().replace('LOCAL_ROOT="/Users/chenyang/Downloads/demo/沧海巨浪"',f'LOCAL_ROOT="{root}"'))
        yield SimpleNamespace(root=root,a=a,s=s,b=b,state=state,summary=summary,sp=sp,summary_path=summary_path,fake=fake)
    finally:
        sys.path[:] = old_path
        for k in list(sys.modules):
            if k == 'scripts' or k.startswith('scripts.'): del sys.modules[k]
        sys.modules.update(modules)


FAKE_HERMES = r'''
import json,sys,os,hashlib
from pathlib import Path
args=sys.argv[1:]
root=Path.cwd()
assert args[:2]==['-t','file']
args=args[2:]
assert len(args)==12 and args[:3]==['-p','canghai-research','--usage-file']
assert args[4]=='-z' and args[6:10]==['chat','--yolo','-s','analyze_devil_advocate_v1']
assert args[10]=='--max-turns'
ctx=json.loads(args[5].split('\n',1)[1])
contract=root/ctx['loaded_contract']['path']
assert hashlib.sha256(contract.read_bytes()).hexdigest()==ctx['loaded_contract']['sha256']
assert 'candidate_checks' in contract.read_text() and 'RFC 6901' in contract.read_text()
for u,x in ctx['bound_sources'].items():
    p=root/x['version']['path']
    assert hashlib.sha256(p.read_bytes()).hexdigest()==x['version']['sha256']
# Read actual contract, assert old canonical JSON/MD unmodified at model start.
assert hashlib.sha256((root/'data/research/20990106/R6_devil_advocate.json').read_bytes()).hexdigest()==ctx['request']['baseline_r6_sha256']
p=root/'model.count';p.write_text(str(int(p.read_text())+1 if p.exists() else 1))
(root/'actual.argv.json').write_text(json.dumps(args))
proposal=json.loads((root/'synthetic.proposal.json').read_text())
if os.environ.get('R6_FAKE_WRITE'):
    denied=[]
    local=root/'data/logs/research_shell/20990106'/('r6-revision.'+ctx['request']['revision_id'])
    for p in [root/'data/research/20990106/R6_devil_advocate.json',root/'chzl_kg/投研交易/反证/20990106.md',
              root/'data/health/research_pipeline_20990106.json',local/'state.json',local/'original.R6.json']:
        try:p.write_text('MODEL MUST NOT PUBLISH')
        except PermissionError:denied.append(str(p))
        else:raise AssertionError('model canonical/receipt write was not denied')
    (root/'os-write-denials.json').write_text(json.dumps(denied))
Path(args[3]).write_text(json.dumps(dict(input_tokens=3,output_tokens=2,cache_read_tokens=0,cache_write_tokens=0,reasoning_tokens=0,api_calls=1,total_tokens=5,completed=True,failed=False,model='synthetic-model',provider='synthetic',session_id='synthetic-'+root.parent.name)))
if os.environ.get('R6_FAKE_DRIFT'):
    (root/'data/research/20990106/R4_news.json').write_text('{}')
print(json.dumps(proposal))
'''


def proposal(codes=(A,), incomplete=()):
    refs = {1:[('R2','/main_lines/0/leaders/0'),('R4','/zero'),('R7','/main_force')],
            2:[('R1','/style'),('R2','/main_lines/0/leaders/0')],
            6:[('R2','/main_lines/0/leaders/0'),('R3','/alert')],7:[('R5','/profiles/0')]}
    entries=[]
    for c in codes:
        for m in (1,2,6,7):
            missing=(c,m) in incomplete
            entries.append({'mode_id':m,'ts_code':c,'completion':'incomplete' if missing else 'completed',
                'evidence_refs':[] if missing else [{'source':u,'json_pointer':p.replace('/leaders/0','/leaders/1').replace('/profiles/0','/profiles/1') if c==B else p} for u,p in refs[m]],
                'missing_evidence':['owner evidence still absent'] if missing else []})
    return {'candidate_checks':entries,'counter_arguments':[], 'hard_rejects':[], 'markdown':'本轮仅核指定缺项；原尾部反面证据仍有效。'}


def call(n, p=None, targets=None, retry=False, revision='local-one'):
    if p is not None: save(n.root/'synthetic.proposal.json',p)
    return n.s.run_r6_revision(n.root,DATE,revision,
        baseline_summary_sha256=n.state['contract_results']['summary']['sha256'],
        baseline_r6_sha256=n.state['contract_results']['R6']['json']['sha256'],
        targets=targets if targets is not None else {A:[1,2,6,7]},hermes=str(n.fake),retry_delivery=retry)


def install_r6_baseline(n, r6):
    path=n.root/n.summary['artifacts']['R6'];save(path,r6)
    record={**n.a.file_version(n.root,path),'passed':True,'run_id':n.state['run_id'],'attempt':1}
    n.state['contract_results']['R6']['json']=record
    entry=n.summary['input_manifest']['units']['R6']['json']
    entry.update(record);entry['receipt_binding']['receipt']=record
    m=n.summary['input_manifest'];m['sha256']=n.b._digest({k:v for k,v in m.items() if k!='sha256'})
    save(n.summary_path,n.summary)
    n.state['contract_results']['summary']={**n.a.file_version(n.root,n.summary_path),'passed':True,'run_id':n.state['run_id'],'attempt':1}
    save(n.sp,n.state)
    n.b.consume_authorized_inputs(n.summary,root=n.root)


def test_completed_and_untouched_cells_preserved_and_completed_target_no_launch(native):
    n=native
    old=n.a.read_object(n.root/n.summary['artifacts']['R6'])
    completed=proposal()['candidate_checks'][1]
    completed={k:v for k,v in completed.items() if k!='mode_id'}
    untouched={'ts_code':B,'completion':'incomplete','evidence_refs':[],'missing_evidence':['original absent evidence']}
    old['patterns_status']={'existing_mode2':{'mode_id':2,'candidate_checks':[completed,untouched],'status':'executed','tail':'negative stays'},
                            'legacy_auxiliary':{'status':'degraded','notes':'original auxiliary risk and gap'}}
    install_r6_baseline(n,old)
    with pytest.raises(ValueError,match='already completed'):call(n,proposal(),{A:[2]})
    assert not (n.root/'model.count').exists()
    p=proposal();p['candidate_checks']=[x for x in p['candidate_checks'] if x['mode_id']!=2]
    result=call(n,p,{A:[1,6,7]},revision='remaining-three')
    current=n.a.read_object(n.root/n.summary['artifacts']['R6'])
    assert current['patterns_status']['existing_mode2']==old['patterns_status']['existing_mode2']
    assert current['patterns_status']['legacy_auxiliary']==old['patterns_status']['legacy_auxiliary']
    assert result['coverage']['completed']==[A] and result['coverage']['incomplete']==[B]


@pytest.mark.parametrize('target',['proposal','backup','request'])
def test_retry_rejects_drift_of_saved_proposal_original_or_request(native,monkeypatch,target):
    n=native;original=n.s._replace_bytes;hit=[]
    def fail(path,raw):
        if path.name=='R6_devil_advocate.json' and not hit:hit.append(True);raise OSError('once')
        return original(path,raw)
    monkeypatch.setattr(n.s,'_replace_bytes',fail)
    with pytest.raises(OSError):call(n,proposal())
    directory=n.s.revision_directory(n.root,DATE,'local-one')
    if target=='proposal':(directory/'proposal.stdout').write_text(json.dumps(proposal())+' ')
    elif target=='backup':(directory/'original.R6.json').write_text('{}')
    with pytest.raises(ValueError):call(n,targets={A:[1]} if target=='request' else None,retry=True)
    assert (n.root/'model.count').read_text()=='1'
    assert n.a.read_object(n.root/n.summary['artifacts']['R6'])['hard_rejects']


def test_post_acceptance_failure_restores_only_own_bytes_and_invalidates_acceptance(native,monkeypatch):
    n=native;consume=n.b.consume_authorized_inputs;hit=[]
    def fail(summary,**kwargs):
        if summary.get('research_revision') and not hit:hit.append(True);raise OSError('read-back failure')
        return consume(summary,**kwargs)
    monkeypatch.setattr(n.b,'consume_authorized_inputs',fail)
    with pytest.raises(OSError):call(n,proposal())
    directory=n.s.revision_directory(n.root,DATE,'local-one')
    assert n.a.read_object(directory/'state.json')['status']=='validated'
    assert consume(n.summary,root=n.root)
    assert call(n,retry=True)['status']=='completed'
    assert (n.root/'model.count').read_text()=='1'


def test_concurrent_canonical_edit_never_rolled_back(native,monkeypatch):
    n=native;replace=n.s._replace_bytes;edited=[]
    path=n.root/n.summary['artifacts']['R6']
    def replace_then_edit(p,raw):
        if p==n.summary_path and not edited:
            edited.append(True);path.write_text('{"concurrent":"must survive"}');raise OSError('after concurrent edit')
        return replace(p,raw)
    monkeypatch.setattr(n.s,'_replace_bytes',replace_then_edit)
    with pytest.raises(OSError):call(n,proposal())
    assert n.a.read_object(path)=={'concurrent':'must survive'}
    with pytest.raises(ValueError):n.b.consume_authorized_inputs(n.summary,root=n.root)


@pytest.mark.parametrize('pointer, expected',[('/a~1b/~0/0',False),('/a~1b/~0/1',0),('',{'a/b':{'~':[False,0]}})])
def test_rfc6901_and_false_zero_preserved(native,pointer,expected):
    actual=native.a.json_pointer({'a/b':{'~':[False,0]}},pointer)
    assert actual==expected and type(actual) is type(expected)


def test_ordinary_start_check_summary_receipt_and_consumer_compatible(native):
    n=native;run='ordinary-new-run'
    n.s.start(n.root,DATE,run,os.getpid(),'running')
    for u,rel in n.summary['artifacts'].items():
        n.s.stage(n.root,DATE,run,u,'running',attempt=1)
        p=n.root/rel;raw=p.read_bytes();p.write_bytes(raw)
        md=n.root/n.state['contract_results'][u]['md']['path'];raw=md.read_bytes();md.write_bytes(raw)
        assert n.s.check(n.root,DATE,run,u)
        n.s.stage(n.root,DATE,run,u,'completed',attempt=1)
    state=n.a.read_object(n.sp)
    summary=json.loads(json.dumps(n.summary));summary['run_id']=run
    m=summary['input_manifest'];m['run_id']=run
    for u in n.a.UNIT_FILES:
        for kind in ('json','md'):
            record=state['contract_results'][u][kind]
            m['units'][u][kind].update(record)
            m['units'][u][kind]['receipt_binding']={'status':'verified','run_id':run,'attempt':1,'receipt':record}
    m['summary_projection_sha256']=n.b._digest({k:summary.get(k) for k in n.b.SUMMARY_PROJECTION})
    m['sha256']=n.b._digest({k:v for k,v in m.items() if k!='sha256'})
    n.s.stage(n.root,DATE,run,'summary','running',attempt=1)
    save(n.summary_path,summary)
    n.s.stage(n.root,DATE,run,'summary','completed',attempt=1)
    assert n.b.verify_saved_inputs(DATE,run_id=run,root=n.root)[1]==summary
    assert set(n.b.consume_authorized_inputs(summary,root=n.root))==set(n.a.UNIT_FILES)


@pytest.mark.parametrize('fault',['R6','R4','md','summary','acceptance'])
def test_accepted_revision_drift_is_never_consumable(native,fault):
    n=native;call(n,proposal())
    summary=n.a.read_object(n.summary_path)
    if fault in {'R6','R4'}:
        path=n.root/summary['artifacts'][fault];path.write_bytes(path.read_bytes()+b' ')
    elif fault=='md':
        path=n.root/f'chzl_kg/投研交易/反证/{DATE}.md';path.write_bytes(path.read_bytes()+b'edited')
    elif fault=='summary':
        path=n.summary_path;path.write_bytes(path.read_bytes()+b' ')
    else:
        path=n.s.revision_directory(n.root,DATE,'local-one')/'state.json'
        value=n.a.read_object(path);value['status']='validated';save(path,value)
    with pytest.raises(ValueError):n.b.consume_authorized_inputs(summary,root=n.root)


@pytest.mark.parametrize('fault',['null_value','unknown_completion','incomplete_without_gap','duplicate','unknown_pattern','no_md','new_hard_mode2'])
def test_invalid_coverage_or_delta_is_not_completion(native,fault):
    n=native;p=proposal();c=p['candidate_checks'][0]
    if fault=='null_value':
        source=n.a.read_object(n.root/n.summary['artifacts']['R1']);source['nil']=None
        # Pure structural/reference check on synthetic source, no baseline mutation.
        checks={'patterns_status':{'m':{'mode_id':1,'candidate_checks':[dict(c, evidence_refs=[{'source':'R1','json_pointer':'/nil'}])]}}}
        checks['patterns_status']['m']['candidate_checks'][0].pop('mode_id')
        with pytest.raises(ValueError,match='null evidence'):n.a.r6_coverage(checks,[A],{'R1':source})
        return
    if fault=='unknown_completion':c['completion']='unknown'
    elif fault=='incomplete_without_gap':c.update(completion='incomplete',missing_evidence=[])
    elif fault=='duplicate':p['candidate_checks'].append(dict(c))
    elif fault=='unknown_pattern':c.pop('mode_id')
    elif fault=='no_md':p['markdown']=''
    else:p['hard_rejects']=[{'mode_id':2,'ts_code':A,'reason':'unauthorized new hard rule'}]
    with pytest.raises(ValueError):call(n,p)
    assert n.a.read_object(n.root/n.summary['artifacts']['R6'])['formal_review_completed'] is False


def test_explicit_local_branch_precedes_full_batch():
    text = (REPO/'scripts/research/run_research_shell.sh').read_text()
    assert '--r6-local-review' in text
    assert text.index('--r6-local-review') < text.index('export HERMES_MEMORY_PROVIDER=')


def test_cross_terminal_revision_supported_without_restarting(native):
    assert callable(getattr(native.s, 'run_r6_revision', None))


def test_global_boolean_does_not_prove_per_stock_review(native):
    payload = {'formal_review_completed':True, 'review_passed':True,'hard_rejects':[]}
    assert native.a.r6_coverage(payload, [A,B], {})['completed'] == []


@pytest.mark.parametrize('complete_all',[False,True])
def test_terminal_baseline_real_consumer_and_preservation(native,complete_all):
    n=native
    oldstate=n.sp.read_bytes(); statefp=n.a.file_version(n.root,n.sp)
    oldr6=n.a.read_object(n.root/n.summary['artifacts']['R6'])
    oldmd=(n.root/f'chzl_kg/投研交易/反证/{DATE}.md').read_bytes()
    six={u:{k:n.a.file_version(n.root,n.root/n.state['contract_results'][u][k]['path']) for k in ('json','md')}
         for u in n.a.UNIT_FILES if u!='R6'}
    plan=n.root/f'data/plans/{DATE}/watchlist_plan.json'
    save(plan,{'no_trade':True,'risk_limits':{'target_total_position_pct':0},'execution_pool':[], 'watch_pool':[{'ts_code':A}]})
    planfp=n.a.file_version(n.root,plan)
    p=proposal((A,B),() if complete_all else ((B,7),))
    p['counter_arguments']=[{'ts_code':A,'mode_id':7,'severity':'strong_suggest','reason':'new negative at tail'}]
    result=call(n,p,{A:[1,2,6,7],B:[1,2,6,7]})
    assert result['coverage']['formal_review_completed'] is complete_all
    assert result['coverage']['completed']==([A,B] if complete_all else [A])
    summary=n.a.read_object(n.summary_path)
    payloads=n.b.consume_authorized_inputs(summary,root=n.root)
    r6=payloads['R6']
    assert r6['formal_review_completed'] is complete_all
    assert r6['counter_arguments'][:len(oldr6['counter_arguments'])]==oldr6['counter_arguments']
    assert r6['counter_arguments'][-1]['reason']=='new negative at tail'
    assert r6['hard_rejects']==oldr6['hard_rejects']==summary['hard_rejects']
    assert (n.root/f'chzl_kg/投研交易/反证/{DATE}.md').read_bytes().startswith(oldmd)
    assert n.sp.read_bytes()==oldstate and n.a.file_version(n.root,n.sp)==statefp
    assert n.a.file_version(n.root,plan)==planfp
    for u, kinds in six.items():
        for k,fp in kinds.items(): assert n.a.file_version(n.root,n.root/fp['path'])==fp
        assert summary['input_manifest']['units'][u]==n.summary['input_manifest']['units'][u]
    obs=result['resource_observation']
    assert obs['native_reported_total_tokens']==5 and len(obs['attempts'])==1
    assert result['accepted_at'] and result['baseline']['run_id']=='baseline-terminal'
    assert n.b.verify_saved_inputs(DATE,run_id='baseline-terminal',root=n.root)[1]==summary
    with pytest.raises(ValueError): n.b.consume_authorized_inputs(n.summary,root=n.root)
    assert call(n,targets={A:[1,2,6,7],B:[1,2,6,7]})==result
    assert (n.root/'model.count').read_text()=='1'


@pytest.mark.parametrize('bad',['scope','mode','bool_mode','missing_refs','missing_pointer','bad_escape','missing_evidence','global','extra','null'])
def test_bad_proposal_rejected_before_canonical_write(native,bad):
    n=native;p=proposal(); c=p['candidate_checks'][0]
    if bad=='scope': c['ts_code']=B
    elif bad=='mode': c['mode_id']=99
    elif bad=='bool_mode': c['mode_id']=True
    elif bad=='missing_refs': c['evidence_refs']=[]
    elif bad=='missing_pointer': c['evidence_refs'][0]['json_pointer']='/no_such_pointer'
    elif bad=='bad_escape': c['evidence_refs'][0]['json_pointer']='/~3'
    elif bad=='missing_evidence': c['missing_evidence']=['still missing']
    elif bad=='global': p['formal_review_completed']=True
    elif bad=='extra': p['execution_pool']=[]
    elif bad=='null': c['evidence_refs'][0]['source']='R6'
    originals={u:n.a.file_version(n.root,n.root/rel) for u,rel in n.summary['artifacts'].items()}
    with pytest.raises(ValueError): call(n,p)
    for u,fp in originals.items(): assert n.a.file_version(n.root,n.root/fp['path'])==fp
    d=n.s.revision_directory(n.root,DATE,'local-one')
    assert (d/'proposal.stdout').is_file() and (d/'last_failure.json').is_file()
    with pytest.raises(ValueError): call(n,retry=True)
    assert (n.root/'model.count').read_text()=='1'


@pytest.mark.parametrize('bad',['out_of_scope','bad_summary','bad_r6','bad_receipt','no_work'])
def test_bad_request_never_launches_model(native,bad):
    n=native
    if bad=='bad_receipt':
        n.state['contract_results']['R4']['json']['sha256']='0'*64;save(n.sp,n.state)
    kwargs={'targets':{'999999.SZ':[1]} if bad=='out_of_scope' else {} if bad=='no_work' else {A:[1,2,6,7]},
            'baseline_summary_sha256':'0'*64 if bad=='bad_summary' else n.state['contract_results']['summary']['sha256'],
            'baseline_r6_sha256':'0'*64 if bad=='bad_r6' else n.state['contract_results']['R6']['json']['sha256']}
    with pytest.raises(ValueError):
        n.s.run_r6_revision(n.root,DATE,'local-one',hermes=str(n.fake),**kwargs)
    assert not (n.root/'model.count').exists()


@pytest.mark.parametrize('fault',['json','md','summary','acceptance'])
def test_publication_failure_preserves_and_delivery_retry_no_model(native,monkeypatch,fault):
    n=native
    original=n.s._replace_bytes; original_atomic=n.s.atomic_json
    hit=[]
    def replace(path,raw):
        targets={'json':'R6_devil_advocate.json','md':DATE+'.md','summary':'research_summary.json'}
        if fault in targets and path.name==targets[fault] and not hit:
            hit.append(True);raise OSError('injected publication failure')
        return original(path,raw)
    def atomic(path,value):
        if fault=='acceptance' and path.name=='state.json' and value.get('status')=='completed' and not hit:
            hit.append(True);raise OSError('injected acceptance failure')
        return original_atomic(path,value)
    monkeypatch.setattr(n.s,'_replace_bytes',replace);monkeypatch.setattr(n.s,'atomic_json',atomic)
    originals={u:n.a.file_version(n.root,n.root/rel) for u,rel in n.summary['artifacts'].items()}
    with pytest.raises(OSError):call(n,proposal())
    assert hit
    for fp in originals.values():assert n.a.file_version(n.root,n.root/fp['path'])==fp
    assert set(n.b.consume_authorized_inputs(n.summary,root=n.root))==set(n.a.UNIT_FILES)
    result=call(n,retry=True)
    assert result['status']=='completed' and (n.root/'model.count').read_text()=='1'


def test_source_drift_preserved_not_overwritten(native,monkeypatch):
    n=native
    meter=importlib.import_module('scripts.research.native_usage');execute=meter.execute
    def concurrent_drift(*args,**kwargs):
        rc=execute(*args,**kwargs)
        (n.root/n.summary['artifacts']['R4']).write_text('{}')
        return rc
    monkeypatch.setattr(meter,'execute',concurrent_drift)
    original=(n.root/n.summary['artifacts']['R6']).read_bytes()
    with pytest.raises(ValueError,match='drift'):call(n,proposal())
    assert (n.root/n.summary['artifacts']['R6']).read_bytes()==original
    assert (n.root/n.summary['artifacts']['R4']).read_text()=='{}'
    with pytest.raises(ValueError):call(n,retry=True)
    assert (n.root/'model.count').read_text()=='1'


def test_delivery_only_retry_without_prior_proposal_never_launches_model(native):
    n=native
    with pytest.raises(ValueError,match='existing saved proposal'):call(n,retry=True)
    assert not (n.root/'model.count').exists()


def test_actual_child_os_policy_denies_canonical_and_receipt_writes(native,monkeypatch):
    n=native;monkeypatch.setenv('R6_FAKE_WRITE','1')
    result=call(n,proposal())
    assert result['status']=='completed'
    denied=n.a.read_object(n.s.revision_directory(n.root,DATE,'local-one')/'launch.json')
    assert denied['argv'][:2]==['/usr/bin/sandbox-exec','-p']
    assert len(json.loads((n.root/'os-write-denials.json').read_text()))==5


def test_actual_shell_entry_only_launches_r6(native):
    n=native;save(n.root/'synthetic.proposal.json',proposal())
    cmd=['/bin/bash',str(n.root/'scripts/research/run_research_shell.sh'),'--r6-local-review',
         '--date',DATE,'--revision-id','shell-local','--baseline-summary-sha256',n.state['contract_results']['summary']['sha256'],
         '--baseline-r6-sha256',n.state['contract_results']['R6']['json']['sha256'],
         '--targets-json',json.dumps({A:[1,2,6,7]}),'--hermes',str(n.fake)]
    result=subprocess.run(cmd,cwd=n.root,capture_output=True,text=True,timeout=20)
    assert result.returncode==0,result.stdout+result.stderr
    assert (n.root/'model.count').read_text()=='1'
    assert n.a.read_object(n.sp)==n.state
    assert 'Batch' not in result.stdout
