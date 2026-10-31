"""Bounded existing consumers; synthetic evidence, never financial certification."""
from copy import deepcopy
import json
import os
from pathlib import Path

import pytest
from test_intraday_event_reassessment import box, rebind_primaries
from test_d1_selective_reassessment import owner, revise
from test_r6_local_revision import native, save, DATE

EV_A, EV_B = '600000.SH', '600001.SH'


def event_matrix(box, *, missing=False, bad_ref=False, hard_target=None, legacy=False):
    root,date,base,canonical,run,env=box
    patterns={}
    for mode in (1,2,6,7):
        patterns[str(mode)]={'mode_id':mode,'candidate_checks':[
            {'ts_code':EV_A,'completion':'incomplete' if missing and mode==2 else 'completed',
             'evidence_refs':[{'source':'R1','json_pointer':'/missing' if bad_ref else '/permission_layers/new_position_allowed'}],
             'missing_evidence':['synthetic missing evidence'] if missing and mode==2 else []},
            {'ts_code':EV_B,'completion':'incomplete','evidence_refs':[],
             'missing_evidence':['synthetic other candidate remains incomplete']} ]}
    r6={'trade_date':date,'patterns_status':patterns,'formal_review_completed':False,
        'permission_layers':{'formal_review_completed':legacy,'new_position_allowed':False},
        'hard_rejects':([{'ts_code':hard_target,'reason':'retained synthetic hard veto'}] if hard_target else []),
        'counter_arguments':[{'ts_code':EV_B,'reason':'UNTRUNCATED_NEGATIVE_EVIDENCE'}]}
    if legacy:r6['mode6_condition_audit']=[{'ts_code':EV_A,'formal_evaluated':True}]
    rebind_primaries(box,{
        'R2':{'trade_date':date,'main_lines':[{'leaders':[{'ts_code':EV_A},{'ts_code':EV_B}]}]},
        'R5':{'trade_date':date,'profiles':[{'ts_code':EV_A},{'ts_code':EV_B}]},'R6':r6})
    # Model transport is the only substitute; keep global no_trade and all pools.
    fake=root/'fake-hermes'
    text=fake.read_text()
    needle="usage={'input_tokens':1"
    addition="""if mode=='typed':
    p['updates']={}
    for row in p['adjudications']:
        row['status']='superseded' if row['target']=='stock:600000.SH' else 'retained'
    p['report_markdown']='# Synthetic per-item review\\n'+context['event']['event_version']+'\\nOne item reviewed; others pending\\nOriginal negative evidence retained\\nNo buy or budget authority\\n'
"""
    assert text.count(needle)==1
    fake.write_text(text.replace(needle,addition+needle))


def test_typed_single_item_completion_is_consumed_without_global_pass(box):
    event_matrix(box,hard_target=EV_B)
    root,date,base,canonical,run,env=box
    p=run('typed')
    assert p.returncode==0,p.stderr
    result=json.loads(canonical.read_text())
    row=next(r for r in result['meta']['event_reassessment']['adjudications'] if r['target']=='stock:'+EV_A)
    assert row['status']=='superseded'
    for k in ('no_trade','risk_limits','execution_pool','watch_pool','no_trade_conditions','mode','autonomous_trading_enabled','requires_user_confirmation'):
        assert result[k]==base[k]
    context=json.loads((root/'prompt-context.json').read_text())
    assert context['review_coverage']['completed']==[EV_A]
    assert context['review_coverage']['incomplete']==[EV_B]
    assert context['review_coverage']['formal_review_completed'] is False
    assert 'UNTRUNCATED_NEGATIVE_EVIDENCE' in json.dumps(context)


@pytest.mark.parametrize('fault',['missing_mode','bad_ref','hard_veto'])
def test_typed_matrix_cannot_fall_back_to_legacy_positive_boolean(box,fault):
    event_matrix(box,missing=fault=='missing_mode',bad_ref=fault=='bad_ref',
                 hard_target=EV_A if fault=='hard_veto' else None,legacy=True)
    root,date,base,canonical,run,env=box
    before=canonical.read_bytes()
    p=run('typed')
    assert p.returncode==1,(p.stdout,p.stderr)
    assert canonical.read_bytes()==before
    if fault=='bad_ref':assert not (root/'argv.json').exists()


@pytest.fixture
def available_owner(native,request):
    payloads={
        'attention':{'trade_date':DATE,'zero':0,'unknown':None,'warnings':['FULL_AUXILIARY_NEGATIVE_EVIDENCE']},
        'emotion_cycle':{'trade_date':DATE,'confidence':0,'phase':None,'metrics_date':'20990105'}}
    for name,paths in native.b.approved_d1_auxiliary_paths(DATE).items():
        save(native.root/paths[0],payloads[name])
    # Initial D1 must really bind these bytes before local R6 changes, not a
    # test-only backfill of the old receipt after the fact.
    n=request.getfixturevalue('owner')
    n.expected_auxiliary=deepcopy(payloads)
    return n


def test_selective_owner_receives_actual_bound_auxiliary_payloads(available_owner):
    n=available_owner
    revise(n)
    assert n.e.ensure_plan(DATE)==1  # safe incomplete delivery, not buy permission
    ctx=n.a.read_object(n.root/'d1.context.json')
    assert {k:v['payload'] for k,v in ctx['auxiliary_inputs'].items()}==n.expected_auxiliary
    assert ctx['auxiliary_inputs']['emotion_cycle']['payload']['metrics_date']=='20990105'
    current=n.a.read_object(n.canonical)
    assert current['risk_limits']==n.base['risk_limits']
    assert current['execution_pool']==n.base['execution_pool']
    assert current['no_trade'] is True


def test_selective_owner_receives_unavailable_as_gaps_not_empty_success(owner):
    n=owner
    revise(n)
    assert n.e.ensure_plan(DATE)==1
    ctx=n.a.read_object(n.root/'d1.context.json')
    assert set(ctx['auxiliary_inputs'])=={'attention','emotion_cycle'}
    assert all(v['status']=='unavailable' and 'payload' not in v for v in ctx['auxiliary_inputs'].values())


def test_available_auxiliary_drift_still_prevents_model_transport(available_owner):
    n=available_owner
    revise(n)
    path=n.root/n.b.approved_d1_auxiliary_paths(DATE)['attention'][0]
    path.write_bytes(path.read_bytes()+b' ')
    assert n.e.ensure_plan(DATE)==1
    assert not (n.root/'d1.count').exists()
    assert n.canonical.read_bytes()==n.before
