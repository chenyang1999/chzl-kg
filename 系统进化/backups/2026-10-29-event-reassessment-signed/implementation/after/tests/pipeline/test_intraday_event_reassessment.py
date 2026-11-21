"""Bounded, relocated CLI cohort. No repository/settings/data imports at collection.

The only external substitutions are detector market acquisition, QMT/executor
construction and the Hermes executable. Validator, input binding, lock, usage,
canonical publisher and runtime stage_plan are the actual source files.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]

STARTUP = r'''
import sys, os, types, json
from pathlib import Path
root = Path(os.environ['EVENT_SANDBOX'])
production = Path(os.environ['EVENT_PRODUCTION'])
def guard(event, args):
    if event == 'os.rename' and os.environ.get('EVENT_FAULT') in {'json_io','md_io','json_io_other_md','json_io_new_json'}:
        suffix = '/watchlist_plan.json' if os.environ['EVENT_FAULT']=='json_io' else '/盘前预案/'+__import__('datetime').datetime.now().strftime('%Y%m%d')+'.md'
        if os.environ['EVENT_FAULT'].startswith('json_io_'):suffix='/watchlist_plan.json'
        if str(args[1]).endswith(suffix) and '/validated/' not in str(args[1]):
            if os.environ['EVENT_FAULT']=='json_io_other_md':
                (root/('chzl_kg/投研交易/盘前预案/'+__import__('datetime').datetime.now().strftime('%Y%m%d')+'.md')).write_text('# other writer\na\nb\nc\nd\n')
            if os.environ['EVENT_FAULT']=='json_io_new_json':
                Path(args[1]).write_bytes(Path(args[0]).read_bytes())
            raise OSError('injected canonical replacement failure')
    if event == 'os.rename' and os.environ.get('EVENT_FAULT') == 'publish_io' and str(args[1]).endswith('.json') and '/data/runtime/watchlist_plan_' in str(args[1]):
        raise OSError('injected runtime atomic replacement failure')
    if event in {'socket.connect', 'socket.bind', 'sqlite3.connect'}:
        raise RuntimeError('forbidden external boundary: '+event)
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        p = Path(os.fsdecode(args[0])).absolute()
        if p.name == '.env' or (p.is_relative_to(production) and not p.is_relative_to(production/'.venv')):
            raise RuntimeError('forbidden production/config read: '+str(p))
    if event in {'os.remove','os.rmdir','os.mkdir','os.rename','os.link','os.symlink'}:
        for v in args[:2] if event in {'os.rename','os.link'} else args[:1]:
            if isinstance(v, (str,bytes,os.PathLike)):
                p=Path(os.fsdecode(v)).absolute()
                if not p.is_relative_to(root):
                    raise RuntimeError('forbidden write: '+str(p))
sys.addaudithook(guard)
settings=types.ModuleType('src.settings'); settings.ROOT=root; settings.DATA_DIR=root/'data'
sys.modules['src.settings']=settings
def forbidden(*a,**kw): raise RuntimeError('real account/executor forbidden')
q=types.ModuleType('trading.order.qmt_context');q.QMTContext=forbidden
sys.modules[q.__name__]=q
reg=types.ModuleType('trading.executors.registry')
reg.all_entry_types=lambda: ['trend_pullback_buy','leader_breakout','daban_confirm','low_absorption_intraday','t_add_pullback']
reg.all_exit_types=lambda: ['exit_at_open','exit_if_no_new_high','t_reduce_resistance','stop_loss_break','take_profit_hit','sector_switch_exit','intraday_break_exit','volume_price_divergence']
sys.modules[reg.__name__]=reg
dis=types.ModuleType('trading.watcher.dispatch');dis.dispatch_plan=forbidden;dis.simulate_all_rule_types=forbidden
sys.modules[dis.__name__]=dis
m=types.ModuleType('src.research.retreat_reversal')
class Verdict:
    def to_dict(self): return json.loads((root/'verdict.json').read_text())
m.detect=lambda *a,**kw: Verdict()
sys.modules[m.__name__]=m
# Substitute only executable discovery, not the transport or CLI implementation.
import scripts.plan.ensure_watchlist_plan as owner
owner._hermes_bin=lambda: str(root/'fake-hermes')
(root/('guard-'+str(os.getpid())+'.ok')).write_text('installed before application imports')
'''

FAKE = r'''
import sys,os,json
from pathlib import Path
args=sys.argv[1:]; root=Path(os.environ['EVENT_SANDBOX'])
assert args[args.index('-p')+1]=='canghai-plan'
assert args[args.index('-s')+1]=='main_decision_v1'
assert args[args.index('--toolsets')+1]=='bot_room'
assert '-q' not in args
context=json.loads(args[args.index('-z')+1].split('\n',1)[1])
(root/'argv.json').write_text(json.dumps(args))
(root/'prompt-context.json').write_text(json.dumps(context))
mode=os.environ.get('EVENT_FAULT','')
if mode=='exit': sys.exit(17)
if mode=='empty': sys.exit(0)
p={'event_version':context['event']['event_version'],
   'base_plan_sha256':context['bound_versions']['plan']['sha256'],
   'updates':{'no_trade':False},
   'adjudications':[{'target':t,'status':'unresolved' if t.startswith('stock:') else 'superseded',
      'evidence':'bound event + original research; incomplete item remains pending',
      'window':context['event']['checked_at']} for t in context['required_targets']],
   'report_markdown':'# Intraday reassessment\n'+context['event']['event_version']+'\nOriginal research retained\nNo budget authority added\nMissing stock review: pending\n'}
if mode=='protected': p['updates']['risk_limits']={}
if mode=='old': p['base_plan_sha256']='0'*64
if mode=='missing_md':p['report_markdown']='short'
if mode=='coverage':p['adjudications']=p['adjudications'][:1]
if mode=='all_pass':
    for row in p['adjudications']:row['status']='superseded'
conditions=context['base_plan'].get('no_trade_conditions',[])
if conditions:
    p['updates']['no_trade_conditions']=[{**r,'active':False} if r.get('code') in {'R1_NO_NEW_POSITION','NO_CONFIRMED_TRADABLE_MAINLINE'} else r for r in conditions]
    for row in p['adjudications']:
        if row['target'].startswith('condition:') and row['target'] not in context.get('condition_sources',{}):row['status']='retained'
if mode=='partial':p['updates'].pop('no_trade',None)
if mode=='retain':
    p['updates']={}
    for row in p['adjudications']:row['status']='retained'
if mode=='partial':
    for row in p['adjudications']:
        if row['target']=='condition:2':row['status']='unresolved'
if mode=='drift':
    q=root/context['summary']['artifacts']['R1'];q.write_text(q.read_text()+' ')
usage={'input_tokens':1,'output_tokens':1,'cache_read_tokens':0,'cache_write_tokens':0,
       'reasoning_tokens':0,'api_calls':1,'total_tokens':2,'model':'synthetic-transport',
       'provider':'offline','session_id':str(os.getpid()),'completed':True,'failed':False}
Path(args[args.index('--usage-file')+1]).write_text(json.dumps(usage))
print(json.dumps(p))
'''

FILES = ['scripts/plan/ensure_watchlist_plan.py','scripts/plan/run_retreat_reversal.py',
         'scripts/research/native_usage.py','scripts/research/pipeline_artifacts.py',
         'scripts/research/pipeline_state.py','scripts/research/build_research_summary.py',
         'trading/load_plan.py','trading/account_config.py','trading/execution_authorization.py',
         'trading/positions_state.py','trading/schema/normalize.py','trading/schema/watchlist_plan.py',
         'src/trading_agent/models.py','src/fetch/price_limits.py',
         'src/plan/report_assembly.py','src/plan/quick_reference.py','scripts/plan/render_plan_tables.py']

@pytest.fixture
def box(tmp_path):
    from datetime import datetime, timezone, timedelta
    root=tmp_path/'app';root.mkdir()
    for name in FILES:
        src=ROOT/name;dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
    (root/'sitecustomize.py').write_text(STARTUP)
    exe=root/'fake-hermes';exe.write_text('#!'+sys.executable+'\n'+FAKE);exe.chmod(0o700)
    env={k:v for k,v in os.environ.items() if not any(token in k.upper() for token in ('TOKEN','SECRET','PASSWORD','API_KEY'))}
    env.update(EVENT_SANDBOX=str(root),EVENT_PRODUCTION=str(ROOT),PYTHONPATH=str(root),
               PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(tmp_path),HERMES_MEMORY_PROVIDER='none')
    now=datetime.now(timezone(timedelta(hours=8)));date=now.strftime('%Y%m%d')
    def write(rel,value):
        p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value));return p
    source={'kind':'daily_market','owner':'canghai-plan','trade_date':date,'unit':'R1'}
    base={'schema_version':'1.0','trade_date':date,'mode':'dry_run','decision_source':'llm',
          'autonomous_trading_enabled':False,'requires_user_confirmation':True,'no_trade':True,
          'generated_at':now.replace(hour=9,minute=0,second=0,microsecond=0).isoformat(),
          'execution_pool':[],'watch_pool':[{'ts_code':'600000.SH','name':'fixture','score':70}],
          'no_trade_conditions':[{'code':'R1_NO_NEW_POSITION','description':'R1 permission','active':True}],
          'risk_limits':{'target_total_position_pct':0},'meta':{}}
    canonical=write(f'data/plans/{date}/watchlist_plan.json',base)
    human=root/f'chzl_kg/投研交易/盘前预案/{date}.md';human.parent.mkdir(parents=True);human.write_text('# Base\na\nb\nc\nd\n')
    stamp=(now-timedelta(minutes=1)).isoformat()
    quote={'source_time_min':stamp,'source_time_max':stamp,'breadth':0.7,'valid_n':100}
    verdict={'trade_date':date,'prev_date':'20261028','checked_at':now.isoformat(),
             'state':'reversal_confirmed','suggested_cap':0.45,'cap_semantics':'reference',
             'trading_authorized':False,'data_quality_issues':[], 'is_retreat_baseline':{'reason':'fixture'},
             'breadth':quote,'yesterday_lu_quality':quote,'yesterday_lu_green_ratio':0.7,
             'index_pct':1.0,'actions':[],
             'source_time_quality':{'index':{'quote_age_min_seconds':60,'age_reference_at':now.isoformat()}}}
    write('verdict.json',verdict)
    # Build a real versioned partial summary without running any research algorithm.
    seed = r'''
from scripts.research import build_research_summary as b
from scripts.research.pipeline_artifacts import file_version
import json,os
from pathlib import Path
r=Path(os.environ['EVENT_SANDBOX']);date=__import__('datetime').datetime.now().strftime('%Y%m%d')
p=r/f'data/research/{date}/R1_style.json';p.parent.mkdir(parents=True);p.write_text(json.dumps({'trade_date':date,'style':'retreat','status':'complete','permission_layers':{'new_position_allowed':False}}))
fp=file_version(r,p);art={'R1':fp['path']}
s={'schema_version':'research_summary_v1','trade_date':date,'run_id':None,'artifacts':art,'orchestrator_status':'partial','hard_rejects':[]}
m={'schema_version':b.MANIFEST_VERSION,'trade_date':date,'run_id':None,'authorized_main_inputs':art,
   'summary_projection_sha256':b._digest({k:s.get(k) for k in b.SUMMARY_PROJECTION}),
   'units':{'R1':{'json':fp}}}
m['sha256']=b._digest(m);s['input_manifest']=m
(r/f'data/research/{date}/research_summary.json').write_text(json.dumps(s))
'''
    p=subprocess.run([sys.executable,'-B','-c',seed],cwd=root,env=env,capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    def run(fault='', detector=True, extra=()):
        e={**env,'EVENT_FAULT':fault}
        args=['scripts/plan/run_retreat_reversal.py','--date',date,'--reassess'] if detector else ['scripts/plan/ensure_watchlist_plan.py','--date',date,'--event',str(root/f'data/research/{date}/retreat_reversal.json')]
        return subprocess.run([sys.executable,'-B',*args,*extra],cwd=root,env=e,capture_output=True,text=True,timeout=30)
    return root,date,base,canonical,run,env


def test_real_detector_cli_to_runtime_and_duplicate(box):
    root,date,base,canonical,run,env=box
    p=run();assert p.returncode==0,p.stderr
    result=json.loads(canonical.read_text());assert result['no_trade'] is False
    for key in ('risk_limits','watch_pool','execution_pool','mode','autonomous_trading_enabled','requires_user_confirmation'):
        assert result[key]==base[key]
    runtime=root/f'data/runtime/watchlist_plan_{date}.json'
    assert runtime.read_bytes()==canonical.read_bytes()
    human=root/f'chzl_kg/投研交易/盘前预案/{date}.md'
    assert 'plan_sha256: "'+hashlib.sha256(json.dumps(result,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()+'"' in human.read_text()
    assert '## 同版 JSON 共享表格' in human.read_text()
    evidence=list((root/f'data/logs/research_shell/{date}').glob('D1_event_*'))
    assert len(evidence)==1
    assert (evidence[0]/'previous-main.md').read_bytes()==b'# Base\na\nb\nc\nd\n'
    assert (evidence[0]/'narrative.md').read_text() in human.read_text()
    before=canonical.read_bytes();argv=(root/'argv.json').read_bytes()
    p=run();assert p.returncode==0,p.stderr
    assert canonical.read_bytes()==before and (root/'argv.json').read_bytes()==argv
    assert len(list(root.glob('guard-*.ok')))>=3


@pytest.mark.parametrize('fault',['exit','empty','protected','old','missing_md','coverage','all_pass','drift'])
def test_cli_rejection_preserves_last_plan(box,fault):
    root,date,base,canonical,run,env=box
    before=canonical.read_bytes();human=root/f'chzl_kg/投研交易/盘前预案/{date}.md';md=human.read_bytes()
    p=run(fault);assert p.returncode==1,(p.stdout,p.stderr)
    assert canonical.read_bytes()==before and human.read_bytes()==md
    assert not (root/f'data/runtime/d1_event_reassessment_{date}.json').exists()
    if fault!='drift':
        p=run();assert p.returncode==0,p.stderr


@pytest.mark.parametrize('mutation',['future','wrong_day','unknown','source_drift','event_version'])
def test_direct_event_cli_refuses_bad_binding(box,mutation):
    root,date,base,canonical,run,env=box
    # Create event through the actual detector path, but fail only external CLI.
    p=run('exit');assert p.returncode==1
    event_path=root/f'data/research/{date}/retreat_reversal.json';event=json.loads(event_path.read_text())
    if mutation=='future':event['checked_at']='2099-01-01T10:00:00+08:00'
    if mutation=='wrong_day':event['trade_date']='20261028'
    if mutation=='event_version':event['event_version']='0'*64
    if mutation=='source_drift':
        q=root/f'data/research/{date}/R1_style.json';q.write_text(q.read_text()+' ')
    if mutation=='unknown':
        obj=json.loads(canonical.read_text());obj['no_trade_conditions'][0]['code']='UNKNOWN_USER_BAN';canonical.write_text(json.dumps(obj))
        # Rebind through actual detector; this tests the unknown-source update denial.
        before=canonical.read_bytes();p=run();assert p.returncode==1,p.stderr
        assert canonical.read_bytes()==before;return
    event_path.write_text(json.dumps(event));before=canonical.read_bytes()
    p=run(detector=False);assert p.returncode==1,p.stderr
    assert canonical.read_bytes()==before


def test_legacy_default_detector_never_launches_owner(box):
    root,date,base,canonical,run,env=box
    before=canonical.read_bytes()
    p=subprocess.run([sys.executable,'-B','scripts/plan/run_retreat_reversal.py','--date',date],cwd=root,env=env,capture_output=True,text=True)
    assert p.returncode==0,p.stderr
    assert canonical.read_bytes()==before and not (root/'argv.json').exists()


def test_validated_delivery_failure_retries_without_model(box):
    root,date,base,canonical,run,env=box
    p=run('publish_io');assert p.returncode==1,p.stderr
    receipt=root/f'data/runtime/d1_event_reassessment_{date}.json'
    assert next(iter(json.loads(receipt.read_text())['events'].values()))['status']=='validated'
    result=canonical.read_bytes();argv=(root/'argv.json').read_bytes()
    p=run();assert p.returncode==0,p.stderr
    assert canonical.read_bytes()==result and (root/'argv.json').read_bytes()==argv
    assert (root/f'data/runtime/watchlist_plan_{date}.json').read_bytes()==result


def test_proposed_wrapper_overlay_uses_real_detector_entry(box):
    root,date,base,canonical,run,env=box
    wrapper=(ROOT/'scripts/cron/canghai_retreat_reversal.sh').read_text()
    wrapper=wrapper.replace(str(ROOT),str(root))
    if '--reassess' not in wrapper:
        wrapper=wrapper.replace('--date "$TRADE_DATE"','--date "$TRADE_DATE" --reassess')
    script=root/'wrapper.sh';script.write_text(wrapper)
    home=root/'home';binpath=home/'.local/bin';binpath.mkdir(parents=True)
    python=binpath/'python3'
    python.write_text('#!'+sys.executable+'\nimport os,sys\nif len(sys.argv)>2 and sys.argv[1]=="-c" and "trade_cal" in sys.argv[2]: print(1)\nelse: os.execv(sys.executable,[sys.executable,"-B",*sys.argv[1:]])\n')
    python.chmod(0o700)
    p=subprocess.run(['/bin/bash',str(script)],cwd=root,env={**env,'HOME':str(home)},capture_output=True,text=True,timeout=30)
    assert p.returncode==0,p.stderr
    assert json.loads(canonical.read_text())['no_trade'] is False
    assert (root/f'data/runtime/watchlist_plan_{date}.json').read_bytes()==canonical.read_bytes()


def test_event_cli_future_weekend_is_rejected_before_lock(box):
    root,date,base,canonical,run,env=box
    p=run(detector=False,extra=('--date','20990103'))
    assert p.returncode != 0
    assert not (root/'data/runtime/d1_decision_20990103.lock').exists()


@pytest.mark.parametrize('broken',['{broken','[]','summary'])
def test_bad_plan_does_not_erase_detection(box,broken):
    root,date,base,canonical,run,env=box
    if broken=='summary':(root/f'data/research/{date}/research_summary.json').write_text('{broken')
    else:canonical.write_text(broken)
    p=run();assert p.returncode==1
    assert (root/f'data/research/{date}/retreat_reversal.json').exists()
    assert (root/f'chzl_kg/投研交易/翻多检测/{date}.md').exists()
    assert not (root/'argv.json').exists()


def test_missing_index_is_not_a_third_core_gate(box):
    root,date,base,canonical,run,env=box
    path=root/'verdict.json';v=json.loads(path.read_text())
    v['index_pct']=None;v['source_time_quality']['index']={}
    path.write_text(json.dumps(v))
    p=run();assert p.returncode==0,p.stderr
    event=json.loads((root/f'data/research/{date}/retreat_reversal.json').read_text())
    assert event['index_source_observed_at'] is None


def rebind_primaries(box, additions):
    root,date,base,canonical,run,env=box
    script="""
from scripts.research import build_research_summary as b
from scripts.research.pipeline_artifacts import file_version, UNIT_FILES
import json,sys
from pathlib import Path
r=Path.cwd();date=sys.argv[1]; additions=json.loads(sys.argv[2])
p=r/f'data/research/{date}/research_summary.json';s=json.loads(p.read_text())
for u,v in additions.items():
    q=r/f'data/research/{date}'/UNIT_FILES[u];q.write_text(json.dumps(v));s['artifacts'][u]=str(q.relative_to(r))
m=s['input_manifest'];m['authorized_main_inputs']=s['artifacts'];m['units']={u:{'json':file_version(r,r/v)} for u,v in s['artifacts'].items()}
m['summary_projection_sha256']=b._digest({k:s.get(k) for k in b.SUMMARY_PROJECTION});m['sha256']=b._digest({k:v for k,v in m.items() if k!='sha256'})
p.write_text(json.dumps(s))
"""
    p=subprocess.run([sys.executable,'-B','-c',script,date,json.dumps(additions)],cwd=root,env=env,capture_output=True,text=True)
    assert p.returncode==0,p.stderr


def test_real_shape_partial_and_negative_evidence_prompt(box):
    root,date,base,canonical,run,env=box
    base['no_trade_conditions']=[{'code':'USER_HOLIDAY','active':False},base['no_trade_conditions'][0],{'code':'R6_REVIEW_INCOMPLETE','active':True}]
    base['no_trade_conditions'] += [{'code':'NO_CONFIRMED_TRADABLE_MAINLINE','active':True}]+[{'code':c,'active':False} for c in ('R1_FAIL','R6_HARD_REJECT_OVERFLOW','R7_STALE','GLOBAL_SEVERITY_3','EMOTION_EXTREME_GREED')]
    canonical.write_text(json.dumps(base))
    rebind_primaries(box,{
        'R1':{'trade_date':date,'style':'retreat','permission_layers':{'new_position_allowed':False},'limitations':{'reason':'R1_NEGATIVE_MARKER'}},
        'R2':{'trade_date':date,'confirmed_tradable_main_lines_count':0,'main_lines':[{'sector':'fixture','limitation':'R2_NEGATIVE_MARKER'}]},
        'R5':{'trade_date':date,'profiles':[{'ts_code':'600000.SH','partial':True,'execution_eligible':False,'dimensions':{'warning':'R5_NEGATIVE_MARKER'}}]},
        'R6':{'trade_date':date,'permission_layers':{'formal_review_completed':False,'all_candidates_cleared':False,'new_position_allowed':False},'candidates_evaluated':0,'counter_arguments':[{'ts_code':'600000.SH','reason':'R6_NEGATIVE_MARKER'}],'research_diagnostics':{'review_gap':'GAP_MARKER'},'mode6_condition_audit':[{'ts_code':'600000.SH','formal_evaluated':False}]}})
    p=run('partial');assert p.returncode==0,p.stderr
    result=json.loads(canonical.read_text())
    assert result['no_trade'] is True
    assert result['no_trade_conditions'][0]==base['no_trade_conditions'][0]
    assert result['no_trade_conditions'][1]['active'] is False
    assert result['no_trade_conditions'][2]==base['no_trade_conditions'][2]
    assert len(result['no_trade_conditions'])==9 and result['no_trade_conditions'][3]['active'] is False
    judgments=result['meta']['event_reassessment']['adjudications']
    assert next(r for r in judgments if r['target']=='condition:2')['status']=='unresolved'
    prompt=(root/'prompt-context.json').read_text()
    assert all(m in prompt for m in ['R1_NEGATIVE_MARKER','R2_NEGATIVE_MARKER','R5_NEGATIVE_MARKER','R6_NEGATIVE_MARKER','GAP_MARKER'])
    assert len(list((root/f'data/logs/research_shell/{date}').glob('D1_event_*/proposal.json')))==1


@pytest.mark.parametrize('active',[False,True])
def test_inactive_protected_is_not_a_blocker(box,active):
    root,date,base,canonical,run,env=box
    base['no_trade_conditions'].append({'code':'USER_HOLIDAY','active':active})
    canonical.write_text(json.dumps(base));p=run()
    assert p.returncode==(1 if active else 0),p.stderr
    if not active:assert json.loads(canonical.read_text())['no_trade'] is False


def test_retained_is_not_new_stock_approval(box):
    root,date,base,canonical,run,env=box
    p=run('retain');assert p.returncode==0,p.stderr
    result=json.loads(canonical.read_text())
    assert result['watch_pool']==base['watch_pool'] and result['no_trade'] is True


@pytest.mark.parametrize('fault',['json_io','md_io'])
def test_canonical_write_failure_preserves_previous_pair(box,fault):
    root,date,base,canonical,run,env=box
    human=root/f'chzl_kg/投研交易/盘前预案/{date}.md'
    before=canonical.read_bytes();md=human.read_bytes()
    p=run(fault);assert p.returncode==1
    assert canonical.read_bytes()==before and human.read_bytes()==md
    assert 'injected canonical' in p.stderr


@pytest.mark.parametrize('status',['published','validated'])
def test_retry_rejects_tampered_result_md(box,status):
    root,date,base,canonical,run,env=box
    p=run('publish_io' if status=='validated' else '');assert p.returncode==(1 if status=='validated' else 0),p.stderr
    human=root/f'chzl_kg/投研交易/盘前预案/{date}.md'
    human.write_text('# altered\na\nb\nc\nd\n')
    argv=(root/'argv.json').read_bytes();p=run()
    assert p.returncode==1,p.stderr
    assert (root/'argv.json').read_bytes()==argv


@pytest.mark.parametrize('fault',['json_io_other_md','json_io_new_json'])
def test_failed_json_never_rolls_back_another_writer(box,fault):
    root,date,base,canonical,run,env=box
    p=run(fault);assert p.returncode==1,p.stderr
    human=root/f'chzl_kg/投研交易/盘前预案/{date}.md'
    if fault=='json_io_other_md':assert human.read_text()=='# other writer\na\nb\nc\nd\n'
    else:
        result=json.loads(canonical.read_text());assert result['no_trade'] is False
        assert result['meta']['event_reassessment']['event_version'] in human.read_text()
        assert 'plan_sha256' in human.read_text()


def test_all_known_market_conditions_clear_without_budget_expansion(box):
    root,date,base,canonical,run,env=box
    base['no_trade_conditions'] += [{'code':'NO_CONFIRMED_TRADABLE_MAINLINE','active':True},{'code':'USER_HOLIDAY','active':False}]
    base['risk_limits']['max_buy_orders_per_day']=0
    canonical.write_text(json.dumps(base))
    rebind_primaries(box,{'R2':{'trade_date':date,'confirmed_tradable_main_lines_count':0,'main_lines':[]}})
    p=run();assert p.returncode==0,p.stderr
    result=json.loads(canonical.read_text())
    assert result['no_trade'] is False and all(r['active'] is False for r in result['no_trade_conditions'])
    for key in ('risk_limits','watch_pool','execution_pool','mode','autonomous_trading_enabled','requires_user_confirmation'):
        assert result[key]==base[key]
    assert 'market_judgment_sources' not in result['meta']
    context=json.loads((root/'prompt-context.json').read_text())
    assert context['condition_sources']['condition:1']['field']=='confirmed_tradable_main_lines_count'
    assert context['condition_sources']['condition:0']['version']==context['bound_versions']['primaries']['R1']


@pytest.mark.parametrize('evidence',[
    {'counter_arguments':[{'severity':'hard_reject','target':'600000.SH'}]},
    {'permission_layers':{'formal_review_completed':False,'all_candidates_cleared':False,'new_position_allowed':False},'research_diagnostics':{'all_passed':True}},
])
def test_real_r6_rejection_or_review_gap_cannot_clear(box,evidence):
    root,date,base,canonical,run,env=box
    rebind_primaries(box,{'R6':{'trade_date':date,**evidence}})
    before=canonical.read_bytes();p=run();assert p.returncode==1,p.stderr
    assert 'R6 rejection/review gap' in p.stderr and canonical.read_bytes()==before


@pytest.mark.parametrize('section',['breadth','yesterday_lu_quality','index'])
def test_event_time_quality_is_core_first_but_future_index_rejected(box,section):
    root,date,base,canonical,run,env=box
    path=root/'verdict.json';v=json.loads(path.read_text())
    if section=='index':v['source_time_quality']['index']['quote_age_min_seconds']=-60
    else:v[section]['source_time_max']='2099-01-01T10:00:00+08:00'
    path.write_text(json.dumps(v));before=canonical.read_bytes()
    p=run();assert p.returncode==1,p.stderr
    assert canonical.read_bytes()==before and not (root/'argv.json').exists()
    assert (root/f'data/research/{date}/retreat_reversal.json').exists()


def test_r6_formal_audit_not_r5_invented_status_controls_coverage(box):
    root,date,base,canonical,run,env=box
    rebind_primaries(box,{'R6':{'trade_date':date,'permission_layers':{'formal_review_completed':True,'all_candidates_cleared':True,'new_position_allowed':True},'candidates_evaluated':1,'mode6_condition_audit':[{'ts_code':'600000.SH','formal_evaluated':True}]},
                         'R5':{'trade_date':date,'profiles':[{'ts_code':'600000.SH','partial':True,'execution_eligible':False}]}})
    p=run('all_pass');assert p.returncode==0,p.stderr
    result=json.loads(canonical.read_text())
    assert result['watch_pool']==base['watch_pool'] and result['execution_pool']==base['execution_pool']


def test_failed_raw_proposal_is_retained(box):
    root,date,base,canonical,run,env=box
    p=run('protected');assert p.returncode==1
    logs=root/f'data/logs/research_shell/{date}'
    proposals=list(logs.glob('D1_event_*/proposal.json'))
    assert len(proposals)==1
    assert 'risk_limits' in proposals[0].read_text()
    assert (proposals[0].parent/'binding.json').exists()

