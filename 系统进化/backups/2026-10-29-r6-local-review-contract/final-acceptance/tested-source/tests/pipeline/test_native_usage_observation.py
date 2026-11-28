"""Native machine usage: synthetic paths, real isolated process/state chain."""
from __future__ import annotations
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
import re
import pytest
from scripts.research import pipeline_state as s

DATE = '20400102'
RUN = 'native-synthetic-run'
REPO = Path(__file__).resolve().parents[2]


def report(**changes):
    result = dict(input_tokens=10, output_tokens=5, cache_read_tokens=3,
                  cache_write_tokens=2, reasoning_tokens=4, total_tokens=20,
                  api_calls=1, model='synthetic-model', provider='synthetic-provider',
                  session_id='synthetic-session', completed=True, failed=False,
                  partial=False, interrupted=False,
                  auxiliary=dict(input_tokens=7, output_tokens=2, cache_read_tokens=1,
                                 cache_write_tokens=0, reasoning_tokens=1, api_calls=1,
                                 estimated_cost_usd=0.0, total_tokens=9,
                                 by_task={'vision': dict(input_tokens=7, output_tokens=2,
                                     cache_read_tokens=1, cache_write_tokens=0,
                                     reasoning_tokens=1, api_calls=1, estimated_cost_usd=0.0)}),
                  total_including_auxiliary=dict(total_tokens=29, api_calls=2,
                                                 estimated_cost_usd=0.0))
    result.update(changes)
    return result


def observation(root):
    return s.read_object(s.state_path(root, DATE))['resource_observation']


def begin(root):
    s.start(root, DATE, RUN, os.getpid(), 'running')
    s.stage(root, DATE, RUN, 'R1', 'running', attempt=1)


def capture(root, *, channel='research_shell', run=RUN, stage='R1', attempt=1):
    from scripts.research import native_usage as n
    return n.prepare(root, DATE, run, stage, attempt, channel=channel,
                     command=['fake-hermes', '-p', 'test'])


def settle(root, binding, payload=None, rc=0):
    from scripts.research import native_usage as n
    if payload is not None:
        (root / binding['path']).write_text(json.dumps(payload))
    n.process_started(root, DATE, binding, os.getpid())
    n.complete(root, DATE, binding, rc, 'returned')


def test_native_totals_separate_reported_subtotal_from_unprovable_authority(tmp_path):
    begin(tmp_path)
    binding = capture(tmp_path)
    settle(tmp_path, binding, report())
    obs = observation(tmp_path)
    record = obs['attempts'][s.attempt_key(RUN, 'R1', 1)]
    assert record['usage']['native_reported_total_tokens'] == 29
    assert record['usage']['main']['total_tokens'] == 20
    assert record['usage']['auxiliary']['total_tokens'] == 9
    assert obs['native_reported_total_tokens'] == 29
    assert obs['known_total_tokens'] is None
    assert obs['coverage'] == 'partial' and obs['target_comparison'] == 'unknown'
    receipt = record['native_usage_receipt']
    assert receipt['first_read_ns'] >= binding['registered_ns']
    assert len(receipt['sha256']) == 64 and receipt['process_pid'] == os.getpid()
    assert receipt['run_id'] == RUN and receipt['stage'] == 'R1' and receipt['attempt'] == 1
    assert record['process_exit_code'] is None  # wrapper result is separate
    assert record['child_process_exit_code'] == 0
    assert s.read_object(s.state_path(tmp_path, DATE))['status'] == 'running'


@pytest.mark.parametrize('payload', [None, {}, {'total_tokens': 999}, report(input_tokens=True),
    report(total_tokens=-1), report(api_calls=None), report(session_id=''),
    report(total_including_auxiliary={'total_tokens': 999, 'api_calls': 2})])
def test_absent_bad_partial_fields_never_become_zero(tmp_path, payload):
    begin(tmp_path)
    binding = capture(tmp_path)
    settle(tmp_path, binding, payload, rc=17)
    obs = observation(tmp_path)
    assert obs['native_reported_total_tokens'] is None
    record = next(iter(obs['attempts'].values()))
    assert record['usage'] is None and record['usage_status'] == 'usage_unknown'
    assert record['child_process_exit_code'] == 17
    assert record['native_usage_error']
    assert obs['known_total_tokens'] is None


def test_failed_partial_run_keeps_nonzero_known_report_but_not_complete_coverage(tmp_path):
    begin(tmp_path)
    binding = capture(tmp_path)
    settle(tmp_path, binding, report(failed=True, completed=False, partial=True), rc=2)
    obs = observation(tmp_path)
    assert obs['native_reported_total_tokens'] == 29
    assert obs['coverage'] == 'partial'
    record = next(iter(obs['attempts'].values()))
    assert record['usage']['completed'] is False and record['child_process_exit_code'] == 2


def test_legal_zero_is_preserved_without_asserting_usage_coverage(tmp_path):
    begin(tmp_path)
    binding = capture(tmp_path)
    payload = report(input_tokens=0, output_tokens=0, cache_read_tokens=0,
                     cache_write_tokens=0, reasoning_tokens=0, total_tokens=0, api_calls=0)
    payload.pop('auxiliary'); payload.pop('total_including_auxiliary')
    settle(tmp_path, binding, payload)
    assert observation(tmp_path)['native_reported_total_tokens'] == 0
    assert observation(tmp_path)['known_total_tokens'] is None
    assert observation(tmp_path)['target_comparison'] == 'unknown'


def test_same_binding_idempotent_conflicting_report_rejected(tmp_path):
    from scripts.research import native_usage as n
    begin(tmp_path); binding = capture(tmp_path); settle(tmp_path, binding, report())
    before = s.state_path(tmp_path, DATE).read_bytes()
    n.complete(tmp_path, DATE, binding, 0, 'returned')
    assert observation(tmp_path)['native_reported_total_tokens'] == 29
    (tmp_path / binding['path']).write_text(json.dumps(report(total_tokens=21,
        total_including_auxiliary=dict(total_tokens=30, api_calls=2))))
    with pytest.raises(ValueError, match='conflict|changed'):
        n.complete(tmp_path, DATE, binding, 0, 'returned')
    assert observation(tmp_path)['native_reported_total_tokens'] == 29


def test_superseded_attempt_and_run_cannot_accept_report(tmp_path):
    from scripts.research import native_usage as n
    begin(tmp_path); binding = capture(tmp_path)
    (tmp_path / binding['path']).write_text(json.dumps(report()))
    s.stage(tmp_path, DATE, RUN, 'R1', 'running', attempt=2)
    with pytest.raises(ValueError, match='superseded'):
        n.complete(tmp_path, DATE, binding, 0, 'returned')
    assert observation(tmp_path)['native_reported_total_tokens'] is None


def test_stale_and_replayed_session_not_counted(tmp_path):
    begin(tmp_path); binding = capture(tmp_path)
    path = tmp_path / binding['path']; path.write_text(json.dumps(report()))
    os.utime(path, ns=(1, 1))
    settle(tmp_path, binding)
    assert observation(tmp_path)['native_reported_total_tokens'] is None
    s.stage(tmp_path, DATE, RUN, 'R1', 'running', attempt=2)
    b2 = capture(tmp_path, attempt=2); settle(tmp_path, b2, report())
    s.stage(tmp_path, DATE, RUN, 'R1', 'running', attempt=3)
    b3 = capture(tmp_path, attempt=3); settle(tmp_path, b3, report())
    assert observation(tmp_path)['native_reported_total_tokens'] == 29
    assert 'replay' in observation(tmp_path)['attempts'][s.attempt_key(RUN, 'R1', 3)]['native_usage_error']


def test_payload_cannot_grant_binding_or_policy_authority(tmp_path):
    begin(tmp_path); binding = capture(tmp_path)
    settle(tmp_path, binding, report(run_id='forged', stage='D1', attempt=999,
        hard_token_limit=1, completed=True, coverage='complete', authoritative=True,
        total_tokens=50_000_001,
        total_including_auxiliary=dict(total_tokens=50_000_010, api_calls=2)))
    h = s.read_object(s.state_path(tmp_path, DATE))
    assert h['resource_policy']['hard_token_limit'] is None and h['status'] == 'running'
    assert h['resource_observation']['target_comparison'] == 'reported_subtotal_exceeds_target_total_unknown'
    assert h['resource_observation']['known_total_tokens'] is None


def test_safety_net_observation_without_pipeline_does_not_invent_business_success(tmp_path):
    binding = capture(tmp_path, channel='safety_net', run='', stage='D1_safety_net')
    settle(tmp_path, binding, report(), rc=75)
    h = s.read_object(s.state_path(tmp_path, DATE))
    assert 'status' not in h and 'stages' not in h and 'contract_results' not in h
    assert h['resource_observation']['native_reported_total_tokens'] == 29
    s.start(tmp_path, DATE, RUN, os.getpid(), 'running')
    assert observation(tmp_path)['native_reported_total_tokens'] == 29


def test_safety_observation_terminal_pipeline_preserves_business_bytes(tmp_path):
    begin(tmp_path); s.attempt_result(tmp_path, DATE, RUN, 'R1', 1, 17)
    s.finish(tmp_path, DATE, RUN, 17)
    before=s.read_object(s.state_path(tmp_path, DATE))
    binding=capture(tmp_path, channel='safety_net', stage='D1_safety_net')
    settle(tmp_path, binding, report())
    after=s.read_object(s.state_path(tmp_path, DATE))
    assert {k:v for k,v in after.items() if k!='resource_observation'} == {k:v for k,v in before.items() if k!='resource_observation'}


def test_real_isolated_launcher_pid_argv_and_nonzero_report(tmp_path):
    begin(tmp_path)
    fake = tmp_path/'fake-hermes.py'
    fake.write_text('''import json, os, sys
from pathlib import Path
argv=sys.argv[1:]
assert '-z' in argv and '--usage-file' in argv and '--max-turns' in argv
assert argv[argv.index('-p')+1]=='synthetic-profile'
Path(argv[argv.index('--usage-file')+1]).write_text(json.dumps(PAYLOAD))
print('tokens: 999999999; not machine usage')
raise SystemExit(75)
'''.replace('PAYLOAD', repr(report())))
    # A Python executable fixture keeps the process guard strict.
    from scripts.research import native_usage as n
    binding = n.prepare(tmp_path, DATE, RUN, 'R1', 1, channel='research_shell',
                        command=[sys.executable, str(fake)])
    cmd = [sys.executable, str(fake), '-p', 'synthetic-profile', '--usage-file',
           str(tmp_path/binding['path']), '-z', 'synthetic prompt', 'chat',
           '--yolo', '-s', 'synthetic-skill', '--max-turns', '7']
    rc = n.execute(tmp_path, DATE, binding, cmd, timeout_s=10)
    assert rc == 75
    record = observation(tmp_path)['attempts'][s.attempt_key(RUN,'R1',1)]
    assert record['child_process_exit_code'] == 75
    assert record['native_usage_receipt']['process_pid'] != os.getpid()
    assert observation(tmp_path)['native_reported_total_tokens'] == 29


def test_state_errors_are_not_swallowed_as_usage_unknown(tmp_path):
    begin(tmp_path); binding=capture(tmp_path)
    s.state_path(tmp_path,DATE).write_text('{bad')
    from scripts.research import native_usage as n
    with pytest.raises(ValueError):
        n.complete(tmp_path,DATE,binding,0,'returned')


@pytest.mark.parametrize('raw', ['{bad', '{"total_tokens":0,"total_tokens":1}',
                                 '{"input_tokens":NaN}'])
def test_malformed_machine_bytes_get_receipt_not_zero(tmp_path, raw):
    begin(tmp_path); binding=capture(tmp_path)
    (tmp_path/binding['path']).write_text(raw)
    settle(tmp_path,binding)
    record=observation(tmp_path)['attempts'][s.attempt_key(RUN,'R1',1)]
    assert record['usage'] is None and record['native_usage_error']
    assert len(record['native_usage_receipt']['sha256'])==64
    assert observation(tmp_path)['native_reported_total_tokens'] is None


@pytest.mark.parametrize('rc', [0, 75])
def test_safety_net_actual_transport_invokes_meter_and_records_child(tmp_path, monkeypatch, rc):
    from scripts.plan import ensure_watchlist_plan as ensure
    from scripts.research import build_research_summary as builder
    monkeypatch.setattr(ensure,'ROOT',tmp_path)
    from trading import load_plan
    monkeypatch.setattr(load_plan,'DATA_DIR',tmp_path/'data')
    monkeypatch.setattr(load_plan,'RUNTIME_DIR',tmp_path/'data/runtime')
    monkeypatch.delenv('CHZL_RESEARCH_RUN_ID',raising=False)
    monkeypatch.setenv('SANDBOX_ROOT',str(tmp_path))
    # Existing version-preflight tests exercise its real contracts. This fixture
    # isolates the newly wired safety transport, without fabricating delivery.
    monkeypatch.setattr(builder,'verify_saved_inputs',lambda *a,**k: ('synthetic-input-version',{'artifacts':{'R1':'fixture'}}))
    for name in ('native_usage.py','pipeline_state.py','pipeline_artifacts.py'):
        target=tmp_path/'scripts/research'/name
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(REPO/'scripts/research'/name,target)
    fake=tmp_path/'python3'
    fake.write_text('#!'+sys.executable+'\n'+'''import json,sys
from pathlib import Path
assert '--usage-file' in sys.argv and '-z' in sys.argv
assert sys.argv[sys.argv.index('-p')+1]=='canghai-plan'
assert sys.argv[sys.argv.index('-s')+1]=='main_decision_v1'
Path(sys.argv[sys.argv.index('--usage-file')+1]).write_text(json.dumps(PAYLOAD))
if RC == 0:
    root=Path.cwd()
    plan=PLAN
    canonical=root/'data/plans'/'20400102'/'watchlist_plan.json'
    canonical.parent.mkdir(parents=True,exist_ok=True)
    canonical.write_text(json.dumps(plan))
    md=root/'chzl_kg/投研交易/盘前预案'/'20400102.md'
    md.parent.mkdir(parents=True,exist_ok=True)
    md.write_text('synthetic no_trade fixture\\n'*6)
raise SystemExit(RC)
'''.replace('PAYLOAD',repr(report())).replace('RC',str(rc)).replace('PLAN',repr({
    'schema_version':'1.0','trade_date':DATE,'generated_at':'2040-01-02T09:01:00+08:00',
    'decision_source':'llm','execution_pool':[],'watch_pool':[],'mode':'dry_run','no_trade':True,
    'risk_limits':{'target_total_position_pct':0},'autonomous_trading_enabled':False,
    'requires_user_confirmation':True})))
    fake.chmod(0o755)
    monkeypatch.setattr(ensure,'_hermes_bin',lambda:str(fake))
    ok,note=ensure.retry_llm(DATE,timeout_s=10)
    assert ok is (rc==0),note
    if rc:
        assert str(rc) in note
    else:
        runtime=s.read_object(tmp_path/'data/runtime'/f'watchlist_plan_{DATE}.json')
        assert runtime['no_trade'] is True and runtime['risk_limits']['target_total_position_pct']==0
        assert runtime['autonomous_trading_enabled'] is False and runtime['requires_user_confirmation'] is True
    obs=observation(tmp_path)
    assert obs['native_reported_total_tokens']==29
    record=next(iter(obs['attempts'].values()))
    assert record['stage']=='D1_safety_net' and record['channel']=='safety_net'
    assert record['process_exit_code']==record['child_process_exit_code']==rc
    assert record['native_usage_receipt']['process_pid']!=os.getpid()
    assert len(record['native_usage_receipt']['argv_sha256'])==64
    h=s.read_object(s.state_path(tmp_path,DATE))
    assert 'status' not in h and 'contract_results' not in h


def test_timeout_records_actual_child_signal_not_fake_token_zero(tmp_path):
    begin(tmp_path)
    from scripts.research import native_usage as n
    fake=tmp_path/'long.py'; fake.write_text('import time\ntime.sleep(20)\n')
    binding=capture(tmp_path)
    rc=n.execute(tmp_path,DATE,binding,[sys.executable,str(fake)],timeout_s=1)
    assert rc==124
    record=observation(tmp_path)['attempts'][s.attempt_key(RUN,'R1',1)]
    assert record['child_process_exit_code']==-9 and record['native_process_outcome']=='timeout'
    assert record['usage'] is None and observation(tmp_path)['native_reported_total_tokens'] is None


@pytest.mark.parametrize('mode,metered_attempts',[('permanent',7),('transient',21)])
def test_exact_shell_candidate_uses_native_channel_on_each_attempt(tmp_path, mode, metered_attempts):
    research=tmp_path/'scripts/research'; research.mkdir(parents=True)
    for name in ('native_usage.py','pipeline_state.py','pipeline_artifacts.py','retry_policy.py'):
        shutil.copyfile(REPO/'scripts/research'/name,research/name)
    (research/'build_research_summary.py').write_text('raise SystemExit(17)\n')
    (research/'reconcile_pipeline_status.py').write_text('raise SystemExit(17)\n')
    fetch=tmp_path/'scripts/fetch'; fetch.mkdir()
    (fetch/'run_chart_vision_snapshot.py').write_text('raise SystemExit(0)\n')
    python=tmp_path/'.venv/bin/python'; python.parent.mkdir(parents=True); python.symlink_to(sys.executable)
    fake=tmp_path/'python3'
    fake.write_text('#!'+sys.executable+'\n'+'''import json,os,sys
from pathlib import Path
args=sys.argv[1:]
assert '-z' in args and '--usage-file' in args
prompt=args[args.index('-z')+1]
assert 'token_effort_target' in prompt and '08:30:00' in prompt
path=Path(args[args.index('--usage-file')+1])
payload=PAYLOAD
payload['session_id']=path.stem
path.write_text(json.dumps(payload))
print('tokens consumed: 999999999; not accounting')
print('ERROR transport timeout' if os.environ['FAIL_MODE']=='transient' else 'ERROR HTTP 401 unauthorized')
raise SystemExit(75)
'''.replace('PAYLOAD',repr(report())))
    fake.chmod(0o755)
    # Before the sole shell owner applies the delta, explicitly test its exact
    # scratch candidate; after application the real repository script is used.
    candidate=Path(os.environ.get('CHZL_NATIVE_SHELL_CANDIDATE',str(REPO/'scripts/research/run_research_shell.sh')))
    source=candidate.read_text()
    assert '"$ROOT/scripts/research/native_usage.py" run' in source
    source,n=re.subn(r'^ROOT="[^"]*"$',f'ROOT="{tmp_path}"',source,flags=re.M); assert n==1
    source,n=re.subn(r'^HERMES_BIN="[^"]*"$',f'HERMES_BIN="{fake}"',source,flags=re.M); assert n==1
    shell=research/'run_research_shell.sh'; shell.write_text(source)
    bash_env=tmp_path/'bash-env'; bash_env.write_text('sleep() { :; }\n')
    env=dict(os.environ,SANDBOX_ROOT=str(tmp_path),FAIL_MODE=mode,CHZL_RESEARCH_RUN_ID=RUN,
             BASH_ENV=str(bash_env),HOME=str(tmp_path))
    proc=subprocess.run(['/bin/bash',str(shell),DATE],cwd=tmp_path,env=env,capture_output=True,text=True,timeout=120)
    assert proc.returncode!=0,proc.stdout+proc.stderr
    obs=observation(tmp_path)
    assert obs['native_reported_total_tokens']==metered_attempts*29
    assert obs['known_total_tokens'] is None and obs['coverage']=='partial'
    assert len(obs['attempts'])==metered_attempts+1
    measured=[record for record in obs['attempts'].values() if record.get('usage') is not None]
    assert len(measured)==metered_attempts
    assert all(record['process_exit_code']==record['child_process_exit_code']==75 for record in measured)
    assert all(record['native_usage_receipt']['process_pid']>1 for record in measured)
    d1=obs['attempts'][s.attempt_key(RUN,'D1',1)]
    assert d1['process_exit_code']==17 and d1['usage'] is None
    h=s.read_object(s.state_path(tmp_path,DATE))
    assert h['status']=='failed' and h['delivery_target']['result']=='failed'
    assert h['resource_policy']['hard_token_limit'] is None


@pytest.mark.parametrize('failure', ['pid_registration', 'wait'])
@pytest.mark.parametrize('settlement_fails', [False, True])
def test_started_process_state_io_failure_is_reaped_and_original_error_preserved(tmp_path, monkeypatch, failure, settlement_fails):
    from scripts.research import native_usage as n
    error = OSError('synthetic post-spawn state I/O failure')
    calls = []
    class Process:
        pid = 123456
        returncode = None
        def poll(self):
            return self.returncode
        def kill(self):
            calls.append('kill')
            self.returncode = -9
        def wait(self, timeout=None):
            calls.append('wait')
            if failure == 'wait' and self.returncode is None:
                raise error
            return self.returncode
    process = Process()
    monkeypatch.setattr(n.subprocess, 'Popen', lambda *a, **k: process)
    def started(*a, **k):
        if failure == 'pid_registration':
            raise error
    def settle(*args):
        calls.append(('settle', args[-2], args[-1]))
        if settlement_fails:
            raise RuntimeError('synthetic settlement state still unavailable')
    monkeypatch.setattr(n, 'process_started', started)
    monkeypatch.setattr(n, 'complete', settle)
    with pytest.raises(OSError) as caught:
        n.execute(tmp_path, DATE, {}, ['synthetic-only'], timeout_s=1)
    assert caught.value is error
    assert process.returncode == -9
    assert calls.index('kill') < len(calls) - 1
    assert calls[-1] == ('settle', -9, 'interrupted_or_state_failure')
    assert 'wait' in calls[calls.index('kill') + 1:]
    if settlement_fails:
        assert any('RuntimeError' in note for note in error.__notes__)


def test_actual_local_child_does_not_outlive_pid_registration_failure(tmp_path, monkeypatch):
    from scripts.research import native_usage as n
    begin(tmp_path)
    binding = capture(tmp_path)
    script = tmp_path/'synthetic-local-child.py'
    script.write_text('import time\ntime.sleep(20)\n')
    real_popen = n.subprocess.Popen
    children = []
    def popen(*args, **kwargs):
        child = real_popen(*args, **kwargs)
        children.append(child)
        return child
    error = OSError('synthetic PID receipt fsync failure')
    def fail_registration(*args, **kwargs):
        raise error
    monkeypatch.setattr(n.subprocess, 'Popen', popen)
    monkeypatch.setattr(n, 'process_started', fail_registration)
    try:
        with pytest.raises(OSError) as caught:
            n.execute(tmp_path, DATE, binding, [sys.executable, str(script)], timeout_s=2)
        assert caught.value is error
        assert len(children) == 1 and children[0].returncode == -9
        record = observation(tmp_path)['attempts'][s.attempt_key(RUN, 'R1', 1)]
        assert record['child_process_exit_code'] == -9
        assert record['native_process_outcome'] == 'interrupted_or_state_failure'
        assert record['usage'] is None
    finally:
        # Red runs must not reproduce the leak beyond this synthetic test.
        for child in children:
            if child.poll() is None:
                child.kill()
                child.wait()


def test_popen_itself_failure_remains_a_failed_launch_observation(tmp_path, monkeypatch):
    from scripts.research import native_usage as n
    begin(tmp_path)
    binding = capture(tmp_path)
    def unavailable(*args, **kwargs):
        raise FileNotFoundError('synthetic missing executable')
    monkeypatch.setattr(n.subprocess, 'Popen', unavailable)
    assert n.execute(tmp_path, DATE, binding, ['synthetic-missing-executable']) == 1
    record = observation(tmp_path)['attempts'][s.attempt_key(RUN, 'R1', 1)]
    assert record['native_process_outcome'] == 'launch_failed'
    assert record['child_process_exit_code'] is None and record['usage'] is None

