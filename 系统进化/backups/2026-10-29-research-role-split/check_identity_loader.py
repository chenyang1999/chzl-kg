"""Exercise the installed SOUL loader on scratch, without models or real settings."""
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback

BASE = Path(__file__).resolve().parent
RUNTIME = Path('/Users/chenyang/.hermes/hermes-agent')
os.environ['HERMES_HOME'] = str(BASE / 'candidate')
os.environ['HOME'] = str(BASE / 'isolated-home')
os.environ['TMPDIR'] = '/Users/chenyang/.hermes/cache/scratch'
sys.path.insert(0, str(RUNTIME))
violations = []


def guard(event, args):
    if event in {'socket.connect', 'socket.getaddrinfo', 'subprocess.Popen'}:
        entry = {'event': event, 'stack': [{'file': Path(x.filename).name, 'function': x.name, 'line': x.lineno} for x in traceback.extract_stack()[-8:-1]]}
        if event == 'subprocess.Popen':
            entry['executable'] = Path(os.fsdecode(args[0])).name
            entry['argument_flags'] = [x for x in args[1] if isinstance(x, str) and x in {'git', '--version', 'rev-parse', '--short', 'HEAD', '--show-toplevel'}]
        violations.append(entry)
        raise PermissionError('No network or process launch in identity-load check')
    if event != 'open' or not isinstance(args[0], (str, bytes, os.PathLike)):
        return
    path = Path(os.fsdecode(args[0])).absolute()
    hidden_real_home = (str(path).startswith('/Users/chenyang/.hermes/')
                        and not path.is_relative_to(RUNTIME)
                        and not path.is_relative_to(BASE))
    if path.name == '.env' or path.name.startswith('.env.') or hidden_real_home:
        violations.append({'event': event, 'path': str(path), 'mode': args[1], 'flags': args[2], 'stack': [{'file': Path(x.filename).name, 'function': x.name, 'line': x.lineno} for x in traceback.extract_stack()[-8:-1]]})
        raise PermissionError('No real settings or credentials in identity-load check')
    mode, flags = args[1:3]
    writing = (isinstance(mode, str) and any(c in mode for c in 'wax+')) or (
        isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)))
    if writing and not path.is_relative_to(BASE):
        violations.append({'event': event, 'basename': path.name, 'write': True})
        raise PermissionError('No writes outside identity-check scratch')


sys.addaudithook(guard)
from agent.prompt_builder import load_soul_md

records = []
for mode in ('baseline', 'candidate'):
    home = BASE / mode
    expected = (home / 'SOUL.md').read_text().strip()
    actual = load_soul_md(context_length=100000, home_override=home)
    record = {'mode': mode, 'loaded': actual is not None,
              'exact_stripped_text_match': actual == expected,
              'source_sha256': hashlib.sha256((home / 'SOUL.md').read_bytes()).hexdigest(),
              'loaded_chars': len(actual) if actual else None,
              'invocation_mode_present': bool(actual and '## Invocation Modes' in actual)}
    records.append(record)
result = {'checks': records, 'violations': violations, 'paid_model_calls': 0,
          'network_calls': 0, 'live_profile_written': False,
          'passed': not violations and all(x['exact_stripped_text_match'] for x in records)}
(BASE / 'role-loader-preflight-2.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result['passed'] else 1)
