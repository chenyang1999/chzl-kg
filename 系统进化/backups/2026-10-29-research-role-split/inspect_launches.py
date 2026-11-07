"""Read-only targeted launcher metadata; never prints prompts or credentials."""
from pathlib import Path
import datetime
import hashlib
import json
import re
import sqlite3

BASE = Path(__file__).resolve().parent
AUDIT = Path('/Users/chenyang/.hermes/cache/scratch/usage-audit-20261027-28-subagent')
DB = Path('/Users/chenyang/.hermes/profiles/canghai-research/state.db')
links = json.loads((AUDIT / 'metrics.json').read_text())['nested_cli_sessions']
con = sqlite3.connect(DB.as_uri() + '?mode=ro', uri=True)
con.row_factory = sqlite3.Row
SKILLS = {'R1':'analyze_style_v1','R2':'analyze_main_sectors_v1',
          'R3':'analyze_sentiment_resonance_v1','R4':'analyze_news_impact_v1',
          'R5':'analyze_stock_profile_v1','R7':'analyze_capital_flow_v1'}


def calls(value):
    if isinstance(value, list):
        for row in value:
            yield from calls(row)
    elif isinstance(value, dict):
        fn = value.get('function', value)
        if isinstance(fn, dict) and isinstance(fn.get('name'), str):
            args = fn.get('arguments', {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {}
            if isinstance(args, dict):
                yield fn['name'], args
                if isinstance(args.get('calls'), list):
                    yield from calls(args['calls'])


def summary(name, args, expected):
    if not name.endswith(('terminal', 'execute_code', 'tool_call')):
        return None
    text = args.get('command') if name.endswith('terminal') else args.get('code')
    if not isinstance(text, str) or 'hermes' not in text:
        return None
    invocations = list(re.finditer(r'(?:\bhermes|/[^\s\x22\x27]+/hermes)\s+', text))
    if not invocations:
        return None
    profiles = re.findall(r'(?:^|\s)(?:-p|--profile)[=\s]+[\x22\x27]?([a-zA-Z0-9_-]+)', text)
    skills = re.findall(r'(?:^|\s)(?:-s|--skills)[=\s]+[\x22\x27]?([a-zA-Z0-9_-]+)', text)
    flags = [flag for flag in ('-q', '-z', '--yolo', '--max-turns', '--model', '--provider')
             if re.search(r'(?<!\w)' + re.escape(flag) + r'(?=\s|=|$)', text)]
    return {'tool':name, 'command_sha256':hashlib.sha256(text.encode()).hexdigest(),
            'command_bytes':len(text.encode()), 'profile_flags':profiles,
            'skill_flags':skills, 'expected_skill':expected,
            'same_stage_explicit_skill':expected in skills,
            'has_query_argument':bool(set(flags) & {'-q','-z'}),
            'flags_present':flags, 'background':args.get('background'),
            'direct_terminal_request':name.endswith('terminal')}


results=[]
for link in links:
    outer, inner = link['outer_sid'], link['inner_sid']
    session = con.execute('SELECT id,started_at,parent_session_id,model,source FROM sessions WHERE id=?', (inner,)).fetchone()
    starts=[]
    for row in con.execute("SELECT id,timestamp,tool_calls FROM messages WHERE session_id=? AND role='assistant' AND tool_calls IS NOT NULL ORDER BY id", (outer,)):
        try:
            raw=json.loads(row['tool_calls'])
        except ValueError:
            continue
        for name,args in calls(raw):
            item=summary(name,args,SKILLS.get(link['stage']))
            if item:
                item.update(message_id=row['id'], timestamp=row['timestamp'],
                            child_start_minus_request_s=(session['started_at']-row['timestamp']) if session else None)
                starts.append(item)
    results.append({'day':link['day'],'stage':link['stage'],'outer_sid':outer,'inner_sid':inner,
                    'prior_link_strength':link['link_strength'],
                    'inner_session_metadata':dict(session) if session else None,
                    'launcher_candidates':starts})
con.close()
record={'generated_at':datetime.datetime.now().astimezone().isoformat(), 'database_mode':'read_only',
        'coverage':'only previously identified eleven outer/inner session pairs',
        'pair_count':len(results), 'pairs':results,
        'unique_launcher_message_ids':sorted({x['message_id'] for r in results for x in r['launcher_candidates']}),
        'raw_commands_prompts_or_credentials_exported':False}
(BASE/'launch-metadata.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
print(json.dumps(record,ensure_ascii=False,indent=2))
