"""Exercise actual run_agent prompt assembly without starting research helpers."""
from pathlib import Path
import os
import subprocess
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRATCH = Path('/Users/chenyang/.hermes/cache/scratch')
STAGES = [
    ('R1', 'analyze_style_v1'), ('R2', 'analyze_main_sectors_v1'),
    ('R3', 'analyze_sentiment_resonance_v1'), ('R4', 'analyze_news_impact_v1'),
    ('R5', 'analyze_stock_profile_v1'), ('R6', 'analyze_devil_advocate_v1'),
    ('R7', 'analyze_capital_flow_v1'), ('D1', 'main_decision_v1'),
]


@pytest.mark.parametrize('stage,skill', STAGES)
@pytest.mark.parametrize('policy', ['', 'synthetic-policy'])
def test_each_stage_direct_session_prompt_preserves_role_and_limits(stage, skill, policy):
    text = (ROOT / 'scripts/research/run_research_shell.sh').read_text()
    start = text.index('run_agent() {\n')
    end = text.index('\n}\n', start) + len('\n}')
    function = text[start:end]
    profile = 'canghai-plan' if stage == 'D1' else 'canghai-research'
    with tempfile.TemporaryDirectory(prefix='single-session-prompt-', dir=SCRATCH) as temp:
        # Only the real function is sourced; production mkdir/state/top-level
        # batches never execute. Every accidental helper path is nonfunctional.
        script = '\n'.join([
            'set -euo pipefail',
            'ROOT="$PWD"', 'LOG_DIR="$PWD"', 'DRY_RUN=dry-run',
            'HERMES_BIN=/nonexistent/offline-hermes', 'PYTHON=/usr/bin/false',
            'state() { return 70; }', function,
            'run_agent "$1" "$2" "$ROOT/synthetic.json" "synthetic-task" "$3"',
        ])
        env = {'PATH': '/usr/bin:/bin', 'HOME': temp, 'TMPDIR': str(SCRATCH),
               'PIPELINE_POLICY_CONTEXT': policy, 'AGENT_MAX_TURNS': '60'}
        proc = subprocess.run(['/bin/bash', '-c', script, 'offline-prompt', stage, skill, profile],
                              cwd=temp, env=env, capture_output=True, text=True, timeout=10)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert f'-p {profile} chat -Q --yolo -s {skill}' in proc.stdout
        assert 'synthetic-task 当前会话就是本阶段唯一研究/决策执行者' in proc.stdout
        assert '不得再次启动 Hermes CLI、delegate_task 或其他模型会话来执行同一阶段/同一技能' in proc.stdout
        assert '允许既有数据工具、确定性辅助脚本及既有图像证据通道' in proc.stdout
        assert '不得把本限制扩大为减少候选来源、风险或反证' in proc.stdout
        assert ('不改变有效零交易预算、不交易决定或既有交易授权与保护' in proc.stdout) == bool(policy)
        assert list(Path(temp).iterdir()) == []
