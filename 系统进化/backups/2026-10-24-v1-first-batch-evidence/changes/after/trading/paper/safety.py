"""Exists-only paper buy kill check shared by both offline entrypoints.

No file contents, settings, environment, broker or database access. The caller
supplies its application root; only the already-defined canonical token works.
Legal sells deliberately remain independent of this new-entry veto.
"""
from pathlib import Path


def kill_snapshot(plan, at, root):
    risk = plan.get('risk_limits', {})
    if not isinstance(risk, dict):
        return {'configured': True, 'status': 'invalid_risk_section'}, ['invalid_risk_section']
    explicit = 'kill_switch_file' in risk
    approved = Path(root) / 'data/runtime/KILL_SWITCH'
    token = risk.get('kill_switch_file', 'data/runtime/KILL_SWITCH')
    base = {'configured': True, 'observed_at': at.isoformat()}
    if token not in ['data/runtime/KILL_SWITCH', str(approved)]:
        return dict(base, status='unknown_path'), ['unknown_kill_switch_path']
    if approved.is_symlink() or approved.parent.resolve() != approved.parent:
        return dict(base, status='unsafe_path'), ['unsafe_kill_switch_path']
    try:
        exists = approved.exists()  # Never open/read the stop file.
    except OSError:
        return dict(base, status='unknown_exists'), ['unknown_kill_switch_state']
    return dict(base, path=str(approved), exists=exists,
                configuration_source='canonical' if explicit else 'schema_default',
                status='owner_exists_snapshot'), []
