"""Verify the approved live identity, retaining known blocked init probes."""
from pathlib import Path
import datetime
import hashlib
import json
import os
import sys

BASE = Path(__file__).resolve().parent
RUNTIME = Path('/Users/chenyang/.hermes/hermes-agent')
ARCHIVE = Path('/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/系统进化/backups/2026-10-29-research-role-split')
LIVE = Path('/Users/chenyang/.hermes/profiles/canghai-research/SOUL.md')
ROOT = Path('/Users/chenyang/Downloads/demo/沧海巨浪')
approval = json.loads((ARCHIVE / 'approval.json').read_text())
expected = (ARCHIVE / 'SOUL.expected.md').read_bytes()
before = (ARCHIVE / 'SOUL.before.md').read_bytes()
actual = LIVE.read_bytes()
assert hashlib.sha256(expected).hexdigest() == approval['candidate_sha256']
assert actual == expected
assert actual[actual.index(b'## Ownership'):] == before[before.index(b'## Ownership'):]
os.environ['HOME'] = str(BASE / 'isolated-home')
os.environ['HERMES_HOME'] = str(BASE / 'candidate')
os.environ['TMPDIR'] = '/Users/chenyang/.hermes/cache/scratch'
sys.path.insert(0, str(RUNTIME))
blocked_init = []
violations = []


def guard(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'subprocess.Popen'}:
        is_version_probe = (event == 'subprocess.Popen' and len(args[1]) == 3
                            and Path(str(args[1][0])).name == 'git'
                            and list(args[1][1:]) == ['rev-parse', 'HEAD'])
        (blocked_init if is_version_probe else violations).append({'event': event, 'kind': 'git_version_probe' if is_version_probe else 'forbidden_process_or_network'})
        raise PermissionError('Isolated identity check: process/network blocked')
    if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
        return
    path = Path(os.fsdecode(args[0])).absolute()
    mode, flags = args[1:3]
    writing = (isinstance(mode, str) and any(x in mode for x in 'wax+')) or (
        isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)))
    is_scratch_env_probe = path == BASE / 'candidate/.env' and not writing
    is_env = path.name == '.env' or path.name.startswith('.env.')
    real_settings = (str(path).startswith('/Users/chenyang/.hermes/')
                     and not path.is_relative_to(RUNTIME) and not path.is_relative_to(BASE)
                     and path != LIVE)
    if is_env or real_settings:
        (blocked_init if is_scratch_env_probe else violations).append({'event':event, 'kind':'scratch_env_probe' if is_scratch_env_probe else 'forbidden_real_settings'})
        raise PermissionError('Isolated identity check: settings/credentials blocked')
    receipts = {ARCHIVE / 'application.json', ARCHIVE / 'SOUL.applied.md'}
    if writing and not path.is_relative_to(BASE) and path not in receipts:
        violations.append({'event':event, 'kind':'forbidden_write'})
        raise PermissionError('Isolated identity check: write blocked')


sys.addaudithook(guard)
from agent.prompt_builder import load_soul_md
loaded = load_soul_md(context_length=100000, home_override=LIVE.parent)
result = {'at':datetime.datetime.now().astimezone().isoformat(),
          'target':str(LIVE), 'user_approval':approval['user_response'],
          'actual_sha256':hashlib.sha256(actual).hexdigest(),
          'equals_approved_candidate':actual == expected,
          'ownership_and_discipline_unchanged':True,
          'native_loader_reads_actual_target':loaded == expected.decode().strip(),
          'known_initialization_probes_blocked':blocked_init,
          'unexpected_guard_violations':violations,
          'index_unchanged':hashlib.sha256((ROOT / '.git/index').read_bytes()).hexdigest() == approval['index_sha256'],
          'models_network_or_business_run':False,
          'process_level_recursion_prevention_proven':False,
          'natural_adoption_proven':False,
          'effective_on':'new research sessions; no hot reload',
          'earlier_strict_preflight_failures_retained':True}
result['applied_and_verified'] = bool(result['native_loader_reads_actual_target'] and result['index_unchanged'] and not violations)
(ARCHIVE / 'SOUL.applied.md').write_bytes(actual)
(ARCHIVE / 'application.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False,indent=2))
raise SystemExit(0 if result['applied_and_verified'] else 1)
