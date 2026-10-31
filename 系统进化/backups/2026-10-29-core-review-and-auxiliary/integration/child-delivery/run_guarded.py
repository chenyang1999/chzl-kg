from pathlib import Path
import fcntl
import hashlib
import json
import os
import sys

ROOT = Path('/Users/chenyang/Downloads/demo/沧海巨浪').resolve()
SCRATCH = Path('/Users/chenyang/.hermes/cache/scratch').resolve()
OUT = SCRATCH / 'input01-bound-20261029'
PROTECTED = [ROOT / 'data', ROOT / 'kb', ROOT / 'accounts', Path.home() / '.hermes/profiles',
             Path.home() / '.ssh', Path.home() / '.aws']
violations = []

def reject(message):
    violations.append(message)
    raise PermissionError(message)

def check(value, writing=False, dir_fd=None, ancestors=False):
    if isinstance(value, int):
        value = fcntl.fcntl(value, 50, bytes(1024)).split(bytes([0]), 1)[0]
    if not isinstance(value, (str, bytes, os.PathLike)):
        return
    path = Path(os.fsdecode(value))
    if not path.is_absolute() and dir_fd not in (None, -1):
        base = fcntl.fcntl(dir_fd, 50, bytes(1024)).split(bytes([0]), 1)[0]
        path = Path(os.fsdecode(base)) / path
    path = path.absolute().resolve()
    if path == Path('/dev/null') or path.is_relative_to(SCRATCH):
        return
    forbidden = path.name.startswith('.env') or path.suffix in {'.db', '.sqlite', '.sqlite3'} or any(
        path == p or path.is_relative_to(p) or (ancestors and p.is_relative_to(path)) for p in PROTECTED)
    if forbidden or writing:
        reject({'kind': 'file', 'path': str(path), 'writing': writing})

def audit(event, args):
    if event.startswith('socket.') or event in {'subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.exec'}:
        reject({'kind': event})
    if event == 'open':
        mode, flags = args[1], args[2] or 0
        writing = (isinstance(mode, str) and any(x in mode for x in 'wax+')) or bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        check(args[0], writing)
    elif event in {'os.remove', 'os.rmdir', 'os.mkdir', 'os.chmod'}:
        check(args[0], True, args[-1] if isinstance(args[-1], int) else None, True)
    elif event in {'os.rename', 'os.link'}:
        check(args[0], True, args[2], True)
        check(args[1], True, args[3], True)
    elif event == 'os.symlink':
        # Check the link location, not the merely stored target string.
        check(args[1], True, args[2])

# Resolve dir_fd before CPython's open audit loses it.
original_open = os.open
def guarded_open(path, flags, mode=0o777, *, dir_fd=None):
    check(path, bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)), dir_fd)
    return original_open(path, flags, mode, dir_fd=dir_fd)
os.open = guarded_open
sys.dont_write_bytecode = True
os.environ.update(PYTHONDONTWRITEBYTECODE='1', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', TMPDIR=str(SCRATCH))
sys.addaudithook(audit)
# Positive and negative guard self-tests before collection. Synthetic denied
# paths contain no secrets or existing production fixture content.
probe = OUT / 'guard-probe.txt'
probe.write_text('scratch permitted')
assert probe.read_text() == 'scratch permitted'
for value, writing in [(ROOT / 'data' / 'INPUT01-SYNTHETIC-DO-NOT-READ.json', False),
                       (ROOT / '.env.INPUT01-SYNTHETIC', False),
                       (ROOT / 'INPUT01-SYNTHETIC-DO-NOT-WRITE', True)]:
    try:
        check(value, writing)
    except PermissionError:
        pass
    else:
        raise AssertionError('guard self-test failed')
selftest = list(violations)
violations.clear()
sources = [ROOT / 'scripts/research/build_research_summary.py', ROOT / 'scripts/research/pipeline_artifacts.py',
           ROOT / 'tests/pipeline/test_bound_auxiliary_inputs.py', ROOT / 'tests/pipeline/test_signed_input_review_contract.py']
def hashes():
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
before = hashes()
import pytest
rc = int(pytest.main(sys.argv[1:]))
after = hashes()
receipt = {'pytest_exit': rc, 'violations': violations, 'guard_selftest_denials': selftest,
           'source_sha_before': before, 'source_sha_after': after, 'source_drift': before != after}
(OUT / 'test_receipt.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
print('AUDIT_RESULT', json.dumps(receipt, ensure_ascii=False))
raise SystemExit(rc if not violations and before == after else 3)
