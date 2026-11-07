"""Selective D1: real ensure/retry, R6 state/receipt consumer and staging.

All sources/data are relocated; only model transport is explicitly synthetic.
Run with the inherited pre-collection R6 guard; no conftest/plugins/cache.
"""
from __future__ import annotations
import ast
from copy import deepcopy
from datetime import datetime
import importlib
import json
import os
from pathlib import Path
import shutil
import sys
from types import ModuleType, SimpleNamespace
import pytest
from test_r6_local_revision import native, call, proposal, save, A, B, DATE, REPO
from test_intraday_event_reassessment import FILES

FAKE_D1 = r'''
import json,sys,os
from pathlib import Path
r=Path.cwd();args=sys.argv[1:]
assert args[args.index('-p')+1]=='canghai-plan'
assert args[args.index('-s')+1]=='main_decision_v1'
assert args[args.index('--toolsets')+1]=='bot_room'
c=json.loads(args[args.index('-z')+1].split('\n',1)[1])
(r/'d1.context.json').write_text(json.dumps(c))
p=r/'d1.count';p.write_text(str(int(p.read_text())+1 if p.exists() else 1))
f=(r/'d1.fault').read_text() if (r/'d1.fault').exists() else ''
if f=='exit':sys.exit(17)
if f=='empty':sys.exit(0)
if f=='invalid_json':print('{not valid json');sys.exit(0)
if f=='timeout':__import__('time').sleep(2)
b=c['base_plan'];candidate=json.loads(json.dumps(b))
candidate['generated_at']=__import__('datetime').datetime.now().astimezone().isoformat()
candidate.setdefault('meta',{})['owner_analysis']='synthetic re-evaluation: one candidate still incomplete'
if f=='all_pass':
    candidate.update(production_ready=True,research_completion_passed=True,reassessment_required=False)
if f=='budget':candidate['risk_limits']['target_total_position_pct']=0.4
if f=='missing_budget':candidate['risk_limits'].pop('target_total_position_pct')
if f=='user_ban':candidate['no_trade_conditions']=[]
if f=='pool':candidate['watch_pool']=[]
if f=='exit_rule':candidate['execution_pool'][0]['exit_rules']=[]
if f=='entry_rule':candidate['execution_pool'][0]['entry_rules']=[{'type':'leader_breakout'}]
if f=='consent':candidate['autonomous_trading_enabled']=True
if f=='hard_reject':candidate['execution_pool'][0]['ts_code']='000002.SZ'
if f=='drift':
    p=r/c['summary']['artifacts']['R4'];p.write_bytes(p.read_bytes()+b' ')
if f=='base_drift':
    p=r/('data/plans/'+c['trade_date']+'/watchlist_plan.json');p.write_bytes(p.read_bytes()+b' ')
if f=='wrong_binding':c['binding']['summary']['sha256']='0'*64
if f=='owner_drift':
    p=r/('data/health/research_pipeline_'+c['trade_date']+'.json');s=json.loads(p.read_text());s['run_id']='new-owner';p.write_text(json.dumps(s))
if f=='old_generated':candidate['generated_at']=b['generated_at']
if f=='context_ban':candidate['market_context']={'account_buy_allowed':True}
usage=dict(input_tokens=1,output_tokens=1,cache_read_tokens=0,cache_write_tokens=0,reasoning_tokens=0,api_calls=1,total_tokens=2,completed=True,failed=False,model='synthetic',provider='offline',session_id=str(os.getpid()))
Path(args[args.index('--usage-file')+1]).write_text(json.dumps(usage))
print(json.dumps({'binding':c['binding'],'plan':candidate,'report_markdown':'# Synthetic D1\nNew local R6 receipt consumed\nOriginal sources retained\nMissing review remains pending\nNo new trading authority\n'}))
'''


@pytest.fixture
def owner(native, monkeypatch):
    n=native
    for rel in FILES:
        if rel.startswith('scripts/research/'):continue
        p=n.root/rel;p.parent.mkdir(parents=True,exist_ok=True)
        source=Path(os.environ.get('D1_SELECTIVE_SOURCE',str(REPO/rel))) if rel=='scripts/plan/ensure_watchlist_plan.py' else REPO/rel
        shutil.copyfile(source,p)
    for path in list(n.root.rglob('*.py')):
        parent=path.parent
        while parent!=n.root:
            (parent/'__init__.py').touch(exist_ok=True)
            parent=parent.parent
    (n.root/'scripts/plan/__init__.py').write_text('')
    old={k:v for k,v in sys.modules.items() if k.split('.')[0] in {'src','trading'}}
    for k in old:del sys.modules[k]
    settings=ModuleType('src.settings');settings.ROOT=n.root;settings.DATA_DIR=n.root/'data'
    monkeypatch.setitem(sys.modules,'src.settings',settings)
    def forbidden(*a,**kw):raise AssertionError('real account/executor forbidden')
    q=ModuleType('trading.order.qmt_context');q.QMTContext=forbidden
    monkeypatch.setitem(sys.modules,q.__name__,q)
    registry=ModuleType('trading.executors.registry')
    registry.all_entry_types=lambda:['trend_pullback_buy','leader_breakout']
    registry.all_exit_types=lambda:['stop_loss_break','take_profit_hit']
    monkeypatch.setitem(sys.modules,registry.__name__,registry)
    dispatch=ModuleType('trading.watcher.dispatch');setattr(dispatch,'dispatch_plan',forbidden);setattr(dispatch,'simulate_all_rule_types',forbidden)
    monkeypatch.setitem(sys.modules,dispatch.__name__,dispatch)
    try:
        n.e=importlib.import_module('scripts.plan.ensure_watchlist_plan')
        n.loader=importlib.import_module('trading.load_plan')
        # Bind the two approved absent optional snapshots, not invented payloads.
        m=n.summary['input_manifest']
        m['bound_auxiliary_inputs']=n.b._bind_auxiliary_inputs(m,root=n.root,approved_paths=n.b.approved_d1_auxiliary_paths(DATE))
        m['sha256']=n.b._digest({k:v for k,v in m.items() if k!='sha256'})
        save(n.summary_path,n.summary)
        n.state['contract_results']['summary']={**n.a.file_version(n.root,n.summary_path),'passed':True,'run_id':n.state['run_id'],'attempt':1}
        save(n.sp,n.state)
        n.canonical,n.runtime=n.e._plan_paths(DATE)
        n.md=n.root/f'chzl_kg/投研交易/盘前预案/{DATE}.md'
        n.base={'schema_version':'1.0','trade_date':DATE,'decision_source':'llm',
            'generated_at':datetime.now().astimezone().isoformat(),'mode':'dry_run',
            'autonomous_trading_enabled':False,'requires_user_confirmation':True,'no_trade':True,
            'production_ready':False,'research_completion_passed':False,'reassessment_required':True,
            'execution_pool':[{'ts_code':A,'name':'existing hold','score':70,'plan_status':'execution_pool_hold',
                'entry_rules':[],'exit_rules':[{'type':'stop_loss_break','trigger_price':9,'quantity_pct':1,'priority':1}]}],
            'watch_pool':[{'ts_code':B,'name':'existing hard rejection','score':60}],
            'no_trade_conditions':[{'code':'USER_HOLIDAY','description':'user ban retained','active':True},
                {'code':'ACCOUNT_BAN','description':'account ban retained','active':True}],
            'risk_limits':{'target_total_position_pct':0},'meta':{}}
        # The real initial retry records trusted checked input/output identity.
        # No research or receipt consumer is replaced.
        with monkeypatch.context() as mp:
            mp.setattr(n.e,'_hermes_bin',lambda:'/synthetic/initial-hermes')
            def initial(cmd,**kw):
                assert 'canghai-plan' in cmd and 'main_decision_v1' in cmd
                save(n.canonical,n.base)
                n.md.parent.mkdir(parents=True,exist_ok=True);n.md.write_text('# Initial owner\na\nb\nc\nd\n')
                return SimpleNamespace(returncode=0)
            mp.setattr(n.e.subprocess,'run',initial)
            accepted,detail=n.e.retry_llm(DATE)
            assert not accepted and '仍须重评' in detail
        assert n.a.read_object(n.runtime)==n.base
        n.before=n.canonical.read_bytes();n.before_md=n.md.read_bytes();n.before_runtime=n.runtime.read_bytes()
        n.six={u:deepcopy(n.summary['input_manifest']['units'][u]) for u in n.a.UNIT_FILES if u!='R6'}
        fake=n.root/'d1-fake-hermes';fake.write_text('#!'+sys.executable+'\n'+FAKE_D1);fake.chmod(0o700)
        monkeypatch.setattr(n.e,'_hermes_bin',lambda:str(fake))
        monkeypatch.delenv('CHZL_RESEARCH_RUN_ID',raising=False)
        yield n
    finally:
        for k in list(sys.modules):
            if k.split('.')[0] in {'src','trading'}:del sys.modules[k]
        sys.modules.update(old)


def revise(n):
    state=n.sp.read_bytes()
    result=call(n,proposal())
    assert result['status']=='completed'
    assert n.sp.read_bytes()==state
    current=n.a.read_object(n.summary_path)
    for u,v in n.six.items():assert current['input_manifest']['units'][u]==v
    assert n.b.consume_authorized_inputs(current,root=n.root)['R6']['formal_review_completed'] is False
    return result


def assert_old(n):
    assert n.canonical.read_bytes()==n.before
    assert n.md.read_bytes()==n.before_md
    assert n.runtime.read_bytes()==n.before_runtime


def test_old_six_and_trusted_local_r6_actually_reach_d1(owner):
    n=owner
    assert all((n.root/n.summary['artifacts'][u]).stat().st_mtime_ns<n.canonical.stat().st_mtime_ns for u in n.six)
    revise(n)
    assert n.e.ensure_plan(DATE)==1  # safe partial is a delivery, not completion
    assert (n.root/'d1.count').read_text()=='1'
    ctx=n.a.read_object(n.root/'d1.context.json')
    assert ctx['research_inputs']['R6']['formal_review_completed'] is False
    updated=n.a.read_object(n.canonical)
    assert updated['meta']['owner_analysis'].startswith('synthetic')
    for k in ('execution_pool','watch_pool','risk_limits','no_trade_conditions','mode','autonomous_trading_enabled','requires_user_confirmation','no_trade'):
        assert updated[k]==n.base[k]
    assert n.a.plan_reassessment_reasons(updated)
    assert n.a.read_object(n.runtime)==updated
    assert n.e.ensure_plan(DATE)==1
    assert (n.root/'d1.count').read_text()=='1'


@pytest.mark.parametrize('fault',['none','mtime','ready_summary','unbound_original','wrong_owner','forged_revision','R4_drift','receipt_drift','env_run'])
def test_unchanged_unbound_forged_or_drifted_never_transport(owner,monkeypatch,fault):
    n=owner
    if fault in {'forged_revision','R4_drift','receipt_drift'}:revise(n)
    if fault=='mtime':os.utime(n.root/n.summary['artifacts']['R6'],None)
    if fault=='ready_summary':
        s=n.a.read_object(n.summary_path);s.update(orchestrator_status='complete',production_ready=True);save(n.summary_path,s)
    if fault=='unbound_original':
        for p in (n.root/f'data/logs/research_shell/{DATE}').glob('D1_retry_*/receipt.json'):p.unlink()
    if fault=='wrong_owner':
        s=n.a.read_object(n.sp);s['run_id']='other-owner';save(n.sp,s)
    if fault=='forged_revision':
        p=n.s.revision_directory(n.root,DATE,'local-one')/'state.json';s=n.a.read_object(p);s['status']='validated';save(p,s)
    if fault=='R4_drift':
        p=n.root/n.summary['artifacts']['R4'];p.write_bytes(p.read_bytes()+b' ')
    if fault=='receipt_drift':
        s=n.a.read_object(n.sp);s['contract_results']['R4']['json']['attempt']=2;save(n.sp,s)
    if fault=='env_run':monkeypatch.setenv('CHZL_RESEARCH_RUN_ID','wrong-env')
    assert n.e.ensure_plan(DATE)==1
    assert not (n.root/'d1.count').exists()
    assert_old(n)


@pytest.mark.parametrize('fault',['exit','empty','invalid_json','all_pass','budget','missing_budget','user_ban','pool','exit_rule','entry_rule','consent','hard_reject','drift','owner_drift','old_generated','context_ban','wrong_binding'])
def test_failed_or_unauthorized_candidate_preserves_last_valid_plan(owner,fault):
    n=owner;revise(n);(n.root/'d1.fault').write_text(fault)
    assert n.e.ensure_plan(DATE)==1
    assert (n.root/'d1.count').read_text()=='1'
    assert_old(n)
    assert n.e.ensure_plan(DATE)==1
    assert (n.root/'d1.count').read_text()=='1'


@pytest.mark.parametrize('force',[False,True])
@pytest.mark.parametrize('no_llm',[False,True])
def test_complete_llm_no_trade_is_idempotent_under_force_and_no_llm(owner,force,no_llm):
    n=owner
    plan=deepcopy(n.base);plan.update(production_ready=True,research_completion_passed=True,reassessment_required=False)
    save(n.canonical,plan);before=n.canonical.read_bytes()
    assert n.e.ensure_plan(DATE,force=force,no_llm=no_llm)==0
    assert n.canonical.read_bytes()==before and not (n.root/'d1.count').exists()


def test_pending_no_llm_never_uses_python_or_model(owner):
    n=owner;revise(n)
    assert n.e.ensure_plan(DATE,force=True,no_llm=True)==1
    assert not (n.root/'d1.count').exists();assert_old(n)


@pytest.mark.parametrize('fault',['missing_original_attempt','original_input_drift','reissued_terminal','reissued_mtime_only'])
def test_original_identity_and_terminal_receipts_cannot_be_reinvented(owner,fault):
    n=owner
    receipt=next((n.root/f'data/logs/research_shell/{DATE}').glob('D1_retry_*/receipt.json'))
    inputs=receipt.parent/'inputs.json'
    if fault in {'missing_original_attempt','original_input_drift'}:
        request=n.a.read_object(inputs)
        if fault=='missing_original_attempt':
            request['saved']['input_manifest']['units']['R4']['json']['receipt_binding'].pop('attempt')
        else:request['saved']['input_manifest']['units']['R4']['json']['sha256']='0'*64
        save(inputs,request)
        if fault=='missing_original_attempt':
            r=n.a.read_object(receipt);r['inputs']=n.a.file_version(n.root,inputs);save(receipt,r)
        revise(n)
    else:
        # A synthetic adversarial direct write is NOT run_r6_revision. Even
        # fully rebound hashes must not reopen the completed research run.
        p=n.root/n.summary['artifacts']['R6'];raw=p.read_bytes()
        if fault=='reissued_terminal':
            payload=n.a.read_object(p);payload['owner_note']='not a local revision';save(p,payload)
        else:p.write_bytes(raw)
        r={**n.a.file_version(n.root,p),'passed':True,'run_id':n.state['run_id'],'attempt':1}
        n.state['contract_results']['R6']['json']=r
        item=n.summary['input_manifest']['units']['R6']['json'];item.update(r);item['receipt_binding']['receipt']=r
        m=n.summary['input_manifest'];m['sha256']=n.b._digest({k:v for k,v in m.items() if k!='sha256'})
        save(n.summary_path,n.summary)
        n.state['contract_results']['summary']={**n.a.file_version(n.root,n.summary_path),'passed':True,'run_id':n.state['run_id'],'attempt':1}
        save(n.sp,n.state)
        assert n.b.verify_saved_inputs(DATE,run_id=n.state['run_id'],root=n.root)
    assert n.e.ensure_plan(DATE)==1
    assert not (n.root/'d1.count').exists();assert_old(n)


@pytest.mark.parametrize('fault',['canonical','human','runtime'])
def test_selective_publication_io_failure_restores_only_own_artifacts(owner,monkeypatch,fault):
    n=owner;revise(n)
    target={'canonical':n.canonical,'human':n.md,'runtime':n.runtime}[fault]
    original=n.loader._atomic_write;hit=[]
    def fail(path,raw):
        if path==target and not hit:hit.append(True);raise OSError('synthetic publication failure')
        return original(path,raw)
    monkeypatch.setattr(n.loader,'_atomic_write',fail)
    assert n.e.ensure_plan(DATE)==1 and hit
    assert (n.root/'d1.count').read_text()=='1';assert_old(n)


def test_selective_timeout_kills_synthetic_child_and_retains_plan(owner,monkeypatch):
    n=owner;revise(n);(n.root/'d1.fault').write_text('timeout')
    real=n.e.retry_llm
    monkeypatch.setattr(n.e,'retry_llm',lambda date:real(date,timeout_s=0.3))
    assert n.e.ensure_plan(DATE)==1
    assert (n.root/'d1.count').read_text()=='1';assert_old(n)
    launch=next((n.root/f'data/logs/research_shell/{DATE}').glob('D1_retry_*/launch.json'))
    pid=n.a.read_object(launch)['pid']
    with pytest.raises(ProcessLookupError):os.kill(pid,0)


def test_original_event_branch_ast_and_dispatch_unchanged():
    baseline=os.environ.get('D1_BASELINE_SOURCE')
    if not baseline:pytest.fail('provide frozen D1_BASELINE_SOURCE for event equivalence')
    old=ast.parse(Path(baseline).read_text());new=ast.parse((REPO/'scripts/plan/ensure_watchlist_plan.py').read_text())
    functions=lambda t:{f.name:ast.dump(f,include_attributes=False) for f in t.body if isinstance(f,ast.FunctionDef)}
    a,b=functions(old),functions(new)
    for name in ('main','_event_now','_event_instant','_event_digest','event_inputs','reversal_event_id','allowed_event_targets','market_condition_sources','bind_reversal_event','reassess_event'):
        assert a[name]==b[name],name
