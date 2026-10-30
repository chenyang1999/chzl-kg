"""Reuse full child isolation; normalize monitor paths for native nodeids."""
from pathlib import Path
source = Path(__file__).with_name("run_acceptance.py")
text = source.read_text()
old = "monitor=['scripts/plan/ensure_watchlist_plan.py',*tests,"
new = "monitor=['scripts/plan/ensure_watchlist_plan.py',*dict.fromkeys(t.split('::',1)[0] for t in tests),"
assert text.count(old) == 1
exec(compile(text.replace(old, new, 1), str(source), "exec"))
