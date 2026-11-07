#!/usr/bin/env python3
"""Launcher-bound Hermes --usage-file observations, never billing/permission gates.

Only the starter chooses the file. Native counters are reported observations, not
an authoritative all-provider total: usage-less responses, estimates, auxiliary
collection failures, remote MCP/tool spend and previous runs can be invisible.
No model prose, config, credentials or session database is read here.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
COUNTERS = ('input_tokens', 'output_tokens', 'cache_read_tokens',
            'cache_write_tokens', 'reasoning_tokens', 'api_calls')
GAPS = ['native_counters_may_omit_or_estimate_usage', 'auxiliary_collection_not_certified',
        'remote_mcp_and_unreported_tool_models', 'prior_unobserved_runs',
        'gateway_execution_after_cli_detach_not_certified',
        'continuous_task_cross_business_date_total_not_certified']


def _state():
    from scripts.research import pipeline_state
    return pipeline_state


def _nonnegative(value, field):
    if type(value) is not int or value < 0:
        raise ValueError(f'invalid native usage {field}')
    return value


def parse_report(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError('native usage must be an object')
    main = {key: _nonnegative(payload.get(key), key) for key in (*COUNTERS, 'total_tokens')}
    for key in ('completed', 'failed'):
        if type(payload.get(key)) is not bool:
            raise ValueError(f'invalid native usage {key}')
    for key in ('partial', 'interrupted'):
        if payload.get(key) is not None and type(payload[key]) is not bool:
            raise ValueError(f'invalid native usage {key}')
    for key in ('model', 'provider', 'session_id'):
        if not isinstance(payload.get(key), str) or not payload[key].strip():
            raise ValueError(f'native usage missing {key}')
    result = {key: payload.get(key) for key in ('model', 'provider', 'session_id',
              'completed', 'failed', 'partial', 'interrupted', 'turn_exit_reason')}
    result.update(main=main, auxiliary=None, native_reported_total_tokens=main['total_tokens'],
                  basis='native_reported_not_provider_verified', coverage='partial')
    if 'auxiliary' in payload:
        aux = payload['auxiliary']
        if not isinstance(aux, dict) or not isinstance(aux.get('by_task'), dict):
            raise ValueError('invalid native auxiliary block')
        counters = {key: _nonnegative(aux.get(key), 'auxiliary.' + key) for key in COUNTERS}
        for key in COUNTERS:
            values = [_nonnegative(task.get(key), 'auxiliary.by_task.' + key)
                      for task in aux['by_task'].values() if isinstance(task, dict)]
            if len(values) != len(aux['by_task']) or sum(values) != counters[key]:
                raise ValueError('native auxiliary by_task mismatch')
        aux_total = _nonnegative(aux.get('total_tokens'), 'auxiliary.total_tokens')
        # Native oneshot.py defines auxiliary total as input+output, unlike the
        # main canonical total (which can include cache buckets). Do not add
        # cache/reasoning to either reported total a second time.
        if aux_total != counters['input_tokens'] + counters['output_tokens']:
            raise ValueError('native auxiliary total mismatch')
        grand = payload.get('total_including_auxiliary')
        if not isinstance(grand, dict):
            raise ValueError('native grand total missing')
        total = _nonnegative(grand.get('total_tokens'), 'total_including_auxiliary.total_tokens')
        if total != main['total_tokens'] + aux_total:
            raise ValueError('native grand total conflict')
        if _nonnegative(grand.get('api_calls'), 'total_including_auxiliary.api_calls') != main['api_calls'] + counters['api_calls']:
            raise ValueError('native grand api_calls conflict')
        result.update(auxiliary={**counters, 'total_tokens': aux_total,
                                 'by_task': {name: {key: task[key] for key in COUNTERS}
                                             for name, task in aux['by_task'].items()}},
                      native_reported_total_tokens=total)
    elif 'total_including_auxiliary' in payload:
        raise ValueError('native grand total without auxiliary breakdown')
    return result


def _observation(state: dict, date: str) -> dict:
    obs = state.setdefault('resource_observation', {
        'trade_date': date, 'known_total_tokens': None, 'native_reported_total_tokens': None,
        'usage_status': 'usage_unknown', 'coverage': 'insufficient',
        'target_comparison': 'unknown', 'attempts': {},
        'metering': 'native_usage_file_launcher_bound', 'coverage_gaps': list(GAPS),
        'observed_scope': 'registered_research_and_safety_net_invocations_only',
    })
    if (not isinstance(obs, dict) or obs.get('trade_date') != date
            or not isinstance(obs.get('attempts'), dict)):
        raise ValueError('invalid day resource observation; refusing silent reset')
    return obs


def _verify_owner(state: dict, date: str, binding: dict) -> None:
    s = _state()
    if binding['trade_date'] != date or state.get('trade_date') != date:
        raise ValueError('usage date mismatch')
    if state.get('run_id', '') != binding['research_run_id']:
        raise ValueError('usage belongs to superseded run')
    if binding['channel'] == 'research_shell':
        if state.get('status') not in {'started', 'running'}:
            raise ValueError('usage belongs to terminal run')
        if s.attempt_identity(state, binding['stage'])[:2] != (binding['run_id'], binding['attempt']):
            raise ValueError('usage belongs to superseded attempt')
    record = _observation(state, date)['attempts'].get(binding['key'])
    if not isinstance(record, dict) or record.get('native_usage_binding') != binding:
        raise ValueError('native usage binding conflict')


def prepare(root: Path, date: str, run_id: str, stage: str, attempt: int, *,
            channel: str, command: list[str]) -> dict:
    s = _state()
    s.validate_date(date)
    if channel not in {'research_shell', 'safety_net'} or type(attempt) is not int or attempt < 1:
        raise ValueError('invalid usage channel/attempt')
    if not isinstance(stage, str) or not stage or not isinstance(run_id, str):
        raise ValueError('invalid usage run/stage')
    nonce = uuid.uuid4().hex
    owner_run = run_id if channel == 'research_shell' else 'safety-net-' + nonce
    key = s.attempt_key(owner_run, stage, attempt)
    directory = s.safe_artifact_path(root, root/'data/logs/research_shell'/date)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'{channel}.{nonce}.attempt-{attempt}.usage.json'
    if path.exists() or path.is_symlink():
        raise ValueError('native usage path already exists')
    binding = dict(trade_date=date, run_id=owner_run, research_run_id=run_id,
                   stage=stage, attempt=attempt, channel=channel, key=key,
                   path=str(path.relative_to(root)), registered_ns=time.time_ns(),
                   launcher_pid=os.getpid(), invocation_id=nonce,
                   command_sha256=hashlib.sha256(json.dumps(command, ensure_ascii=False).encode()).hexdigest())
    with s.locked_state(root, date) as state:
        if not state and channel == 'safety_net' and not run_id:
            state.update(trade_date=date)  # observation only; no fictitious business run
        if state.get('run_id', '') != run_id or state.get('trade_date') != date:
            raise ValueError('usage belongs to superseded run')
        obs = _observation(state, date)
        if channel == 'research_shell':
            if state.get('status') not in {'started', 'running'} or s.attempt_identity(state, stage)[:2] != (run_id, attempt):
                raise ValueError('usage belongs to superseded/terminal attempt')
            record = obs['attempts'].get(key)
            if not isinstance(record, dict):
                raise ValueError('usage requires registered attempt lifecycle')
        else:
            record: dict = dict(run_id=owner_run, stage=stage, attempt=attempt, started_at=s.now(),
                          usage=None, usage_status='usage_unknown', process_exit_code=None,
                          outcome='running', channel=channel)
            obs['attempts'][key] = record
        if 'native_usage_binding' in record:
            raise ValueError('native usage already bound; allocate a new attempt')
        record['native_usage_binding'] = binding
        obs.update(metering='native_usage_file_launcher_bound',
                   observed_scope='registered_research_and_safety_net_invocations_only')
        obs.setdefault('native_reported_total_tokens', None)
        obs['coverage_gaps'] = list(dict.fromkeys([*obs.get('coverage_gaps', []), *GAPS]))
    return binding


def process_started(root: Path, date: str, binding: dict, pid: int, *, command: list[str] | None = None) -> None:
    if type(pid) is not int or pid < 1:
        raise ValueError('invalid native process pid')
    s = _state()
    with s.locked_state(root, date) as state:
        _verify_owner(state, date, binding)
        record = state['resource_observation']['attempts'][binding['key']]
        if record.get('native_process') is not None:
            if record['native_process']['pid'] != pid:
                raise ValueError('conflicting native process identity')
            return
        record['native_process'] = dict(pid=pid, launched_ns=time.time_ns(),
                                        launcher_pid=binding['launcher_pid'],
                                        invocation_id=binding['invocation_id'],
                                        argv_sha256=(hashlib.sha256(json.dumps(command, ensure_ascii=False).encode()).hexdigest()
                                                     if command is not None else None))


def _snapshot(root: Path, binding: dict) -> tuple[dict, dict | None, str | None]:
    s = _state()
    receipt = {key: binding[key] for key in ('path', 'run_id', 'stage', 'attempt',
               'channel', 'launcher_pid', 'registered_ns', 'invocation_id', 'command_sha256')}
    receipt['first_read_ns'] = time.time_ns()
    try:
        path = s.safe_artifact_path(root, root/binding['path'])
        if path.is_symlink():
            raise ValueError('native usage symlink rejected')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as fh:
            before = os.fstat(fh.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > 4_000_000:
                raise ValueError('native usage must be a bounded regular file')
            raw = fh.read(4_000_001)
            after = os.fstat(fh.fileno())
        receipt.update(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw),
                       mtime_ns=before.st_mtime_ns, inode=before.st_ino)
        if ((before.st_ino, before.st_size, before.st_mtime_ns) !=
                (after.st_ino, after.st_size, after.st_mtime_ns)):
            raise ValueError('native usage changed during first read')
        if before.st_mtime_ns < binding['registered_ns']:
            raise ValueError('stale native usage file')
        def unique(pairs):
            obj = {}
            for key, value in pairs:
                if key in obj:
                    raise ValueError('duplicate native usage JSON key')
                obj[key] = value
            return obj
        payload = json.loads(raw, object_pairs_hook=unique,
                             parse_constant=lambda v: (_ for _ in ()).throw(ValueError('nonfinite native usage')))
        return receipt, parse_report(payload), None
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        return receipt, None, str(exc)


def complete(root: Path, date: str, binding: dict, rc: int | None, outcome: str) -> None:
    if rc is not None and type(rc) is not int:
        raise ValueError('invalid native process exit')
    s = _state()
    # Validate ownership before reading, and again under the commit lock.
    with s.locked_state(root, date) as state:
        _verify_owner(state, date, binding)
    receipt, usage, error = _snapshot(root, binding)
    with s.locked_state(root, date) as state:
        _verify_owner(state, date, binding)
        obs = state['resource_observation']; record = obs['attempts'][binding['key']]
        if record.get('native_usage_receipt') is not None:
            old = record['native_usage_receipt']
            if (old.get('sha256') != receipt.get('sha256') or
                    old.get('bytes') != receipt.get('bytes') or
                    old.get('mtime_ns') != receipt.get('mtime_ns') or
                    record.get('child_process_exit_code') != rc or record.get('native_process_outcome') != outcome):
                raise ValueError('conflicting/changed native usage settlement')
            return
        process = record.get('native_process')
        if not process:
            usage, error = None, error or 'process identity unavailable; no usage attribution'
        else:
            receipt['process_pid'] = process['pid']
            receipt['process_launched_ns'] = process['launched_ns']
            receipt['argv_sha256'] = process.get('argv_sha256')
        if usage is not None:
            for other_key, other in obs['attempts'].items():
                previous = other.get('usage')
                if other_key != binding['key'] and isinstance(previous, dict) and previous.get('session_id') == usage['session_id']:
                    usage, error = None, 'replayed native session_id; no double counting'
                    break
        record.update(native_usage_receipt=receipt, usage=usage,
                      native_usage_error=error, usage_status='usage_partial' if usage is not None else 'usage_unknown',
                      child_process_exit_code=rc, native_process_outcome=outcome)
        if binding['channel'] == 'safety_net':
            record.update(process_exit_code=rc, outcome=outcome, observed_at=s.now())
        # Aggregate only this format's observations. Preserve legacy authoritative
        # fields verbatim: native reported totals cannot reclassify their authority.
        values = [r['usage']['native_reported_total_tokens'] for r in obs['attempts'].values()
                  if isinstance(r.get('usage'), dict) and r['usage'].get('basis') == 'native_reported_not_provider_verified']
        subtotal = sum(values) if values else None
        obs.update(native_reported_total_tokens=subtotal,
                   usage_status='usage_partial' if values else 'usage_unknown',
                   coverage='partial' if values else 'insufficient',
                   target_comparison=('reported_subtotal_exceeds_target_total_unknown'
                                      if subtotal is not None and subtotal > 50_000_000 else 'unknown'))


def execute(root: Path, date: str, binding: dict, cmd: list[str], *, timeout_s: int | None = None) -> int:
    rc, outcome, wrapper_rc = None, 'launch_failed', 1
    try:
        proc = subprocess.Popen(cmd, cwd=str(root))
    except OSError:
        # Only Popen itself can be a failed launch with no owned child to reap.
        complete(root, date, binding, rc, outcome)
        return wrapper_rc
    try:
        process_started(root, date, binding, proc.pid, command=cmd)
        try:
            rc = proc.wait(timeout=timeout_s)
            outcome, wrapper_rc = 'returned', rc
        except subprocess.TimeoutExpired:
            proc.kill(); rc = proc.wait()
            outcome, wrapper_rc = 'timeout', 124
    except BaseException as exc:
        # State/PID registration I/O can fail AFTER a successful spawn. Reap the
        # actual local CLI first; this says nothing about remote gateway workers.
        try:
            if proc.poll() is None:
                proc.kill()
            rc = proc.wait()
        except Exception as cleanup_error:
            exc.add_note('native child cleanup failed: ' + type(cleanup_error).__name__)
        try:
            complete(root, date, binding, rc, 'interrupted_or_state_failure')
        except Exception as settlement_error:
            exc.add_note('native usage failure settlement failed: ' + type(settlement_error).__name__)
        raise
    complete(root, date, binding, rc, outcome)
    return wrapper_rc


def hermes_command(hermes: str, profile: str, skill: str, turns: int, prompt: str, usage_path: Path) -> list[str]:
    # Local _parser.py declares --max-turns on chat only. A top-level -z is
    # dispatched BEFORE cmd_chat and forwards this parsed max_turns to gateway.
    # Do not append --usage-file to legacy chat -q: that path drops the option.
    return [hermes, '-p', profile, '--usage-file', str(usage_path), '-z', prompt,
            'chat', '--yolo', '-s', skill, '--max-turns', str(turns)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command', choices=['run'])
    ap.add_argument('--root', type=Path, default=ROOT)
    ap.add_argument('--date', required=True)
    ap.add_argument('--run-id', default='')
    ap.add_argument('--stage', required=True)
    ap.add_argument('--attempt', type=int, required=True)
    ap.add_argument('--channel', choices=['research_shell', 'safety_net'], required=True)
    ap.add_argument('--hermes', required=True)
    ap.add_argument('-p', '--profile', required=True)
    ap.add_argument('-s', '--skill', required=True)
    ap.add_argument('--max-turns', type=int, required=True)
    ap.add_argument('--prompt', required=True)
    ap.add_argument('--timeout', type=int)
    args = ap.parse_args()
    # Bind the actual intended Hermes argv (including its unique path).
    binding = prepare(args.root, args.date, args.run_id, args.stage, args.attempt,
                      channel=args.channel, command=[args.hermes, args.profile, args.skill,
                                                     str(args.max_turns), args.prompt])
    cmd = hermes_command(args.hermes, args.profile, args.skill, args.max_turns,
                         args.prompt, args.root/binding['path'])
    rc = execute(args.root, args.date, binding, cmd, timeout_s=args.timeout)
    # subprocess negative return codes are signals, not successful Python exits.
    return 128-rc if rc < 0 else rc


if __name__ == '__main__':
    raise SystemExit(main())
