"""Prepare a single approved-scope candidate; never writes the live identity."""
from pathlib import Path
import datetime
import difflib
import hashlib
import json

BASE = Path(__file__).resolve().parent
TARGET = Path('/Users/chenyang/.hermes/profiles/canghai-research/SOUL.md')
old = TARGET.read_text()
anchor = '盘前 07:30-07:55 完成 R1-R7 分析,输出 `research_summary.json` 供 D1(canghai-plan)消费。主控本身不做分析,只做 delegation 调度 + artifact 路径收集(见 `research_orchestrator_v1`)。11:35 R7 额外做一次盘中增量。'
replacement = '盘前 07:30-07:55 完成 R1-R7 分析,输出 `research_summary.json` 供 D1(canghai-plan)消费。整体编排时只做 delegation 调度 + artifact 路径收集(见 `research_orchestrator_v1`);单阶段研究按下节直接执行。11:35 R7 额外做一次盘中增量。'
section = '''
## Invocation Modes

- 既有确定性启动器以`-s/--skills`指定单项R1-R7研究技能时，本会话就是该阶段研究者，直接取证、分析与交付；“主控不分析/不直调MCP”只约束整体编排。单阶段仍遵守原阶段工具权限、Ownership与全部纪律。
- 单阶段不得通过Hermes CLI、`delegate_task`或另一模型会话再次执行同一阶段/技能；启动、等待和交付校验交给已有普通程序。原有数据工具、确定性辅助与获准图像通道保留；缺工具就报缺口，不靠重开同任务会话绕过。
- 仅未绑定单项研究技能且明确要求统筹全套研究时，使用`research_orchestrator_v1`编排身份。不改模型、时刻、写入边界或交易权限。
'''
assert old.count(anchor) == 1
assert '## Invocation Modes' not in old
candidate = old.replace(anchor, replacement + '\n' + section, 1)
# All existing boundaries after Ownership remain byte-for-byte identical.
assert candidate[candidate.index('## Ownership'):] == old[old.index('## Ownership'):]
for sub, text in [('baseline', old), ('candidate', candidate)]:
    root = BASE / sub
    root.mkdir(exist_ok=False)
    (root / 'SOUL.md').write_text(text)
patch = ''.join(difflib.unified_diff(old.splitlines(True), candidate.splitlines(True),
                                  fromfile=str(TARGET), tofile=str(TARGET)))
(BASE / 'pending-role-split.diff').write_text(patch)
manifest = {'prepared_at': datetime.datetime.now().astimezone().isoformat(),
            'target': str(TARGET),
            'before_sha256': hashlib.sha256(old.encode()).hexdigest(),
            'candidate_sha256': hashlib.sha256(candidate.encode()).hexdigest(),
            'patch_sha256': hashlib.sha256(patch.encode()).hexdigest(),
            'ownership_and_discipline_suffix_unchanged': True,
            'applied': False, 'status': 'pending_explicit_identity_sign_off'}
(BASE / 'role-candidate.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
print(json.dumps(manifest, ensure_ascii=False, indent=2))
print(patch)
