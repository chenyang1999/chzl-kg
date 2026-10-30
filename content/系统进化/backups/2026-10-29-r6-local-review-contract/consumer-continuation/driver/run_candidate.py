"""Reuse the existing guarded cohort for a named source candidate only."""
from pathlib import Path
import sys
source=Path('/Users/chenyang/.hermes/cache/scratch/d1-selective-20261029/run_acceptance.py')
candidate=Path(__file__).with_name('ensure.candidate.py')
text=source.read_text()
old="monitor=['scripts/plan/ensure_watchlist_plan.py',*tests,"
new="monitor=['scripts/plan/ensure_watchlist_plan.py',*dict.fromkeys(t.split('::',1)[0] for t in tests),"
assert text.count(old)==1
text=text.replace(old,new,1)
needle="env['D1_BASELINE_SOURCE']=str(O/'ensure.before.py')"
addition="""
env['D1_SELECTIVE_SOURCE'] = CANDIDATE
with (out/'sitecustomize.py').open('a') as stream:
 stream.write('''
# Explicit tested-source overlay only; never redirect business I/O.
import shutil
_copy_source = shutil.copyfile
def _candidate_copy(src, dst, *args, **kwargs):
    if Path(src).absolute() == REPO/'scripts/plan/ensure_watchlist_plan.py':
        src = os.environ['D1_SELECTIVE_SOURCE']
    return _copy_source(src, dst, *args, **kwargs)
shutil.copyfile = _candidate_copy
''')
"""
assert text.count(needle)==1
text=text.replace(needle,needle+addition,1)
# Distinct artifact: root source remains another writer's frozen version.
text=text.replace("def manifest():return", "monitor.append(CANDIDATE)\ndef manifest():return",1)
CANDIDATE=str(candidate)
exec(compile(text,str(source),'exec'),globals())
