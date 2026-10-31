"""Opt-in assembly of existing model prose and same-plan shared table views.

Not wired into D1 shell/skills. No model, price engine, DB, schema normalization
or permissions changes. Callers must supply the matching finalized JSON and its
original narrative; this module cannot verify that prose and JSON agree.

Pure API: ``assemble_plan_report(plan, narrative) -> str``.
File API: ``assemble_plan_report_files(plan_path=..., narrative_path=...,
out_path=...) -> Path``. All paths are mandatory; no production defaults or
import-time I/O. The output may explicitly equal the raw narrative path.

Only ORIGINAL narrative is accepted: a reserved assembly marker causes rejection
rather than stripping headings or guessing which user text belongs to old tables.
Reusing the same original narrative gives identical output; reusing assembled
output fails without writing. Keep a separate original if repeated updates matter.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
import stat
import tempfile

from scripts.plan.render_plan_tables import render_plan_tables_md
from src.plan.quick_reference import decision_origin, text

_ASSEMBLY_MARKER = '<!-- canghai:explicit-plan-report-assembly:v1 -->'


def assemble_plan_report(plan: dict, narrative: str) -> str:
    """Preserve prose verbatim, append existing shared views, never infer values.

    JSON decision_origin is authoritative even if the preserved prose claims
    another source. The displayed SHA-256 identifies canonical UTF-8 JSON
    (sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False),
    not its on-disk formatting. This is provenance, not schema/trading approval.
    """
    if not isinstance(plan, dict):
        raise TypeError('plan must be a JSON object')
    if not isinstance(narrative, str):
        raise TypeError('narrative must be original text')
    if not narrative.strip():
        raise ValueError('原始散文不能为空')
    if _ASSEMBLY_MARKER in narrative:
        raise ValueError('需要原始 raw 散文；不得再次组装已有组装报告')
    canonical = json.dumps(plan, ensure_ascii=False, sort_keys=True,
                           separators=(',', ':'), allow_nan=False).encode('utf-8')
    digest = hashlib.sha256(canonical).hexdigest()
    source, fallback = decision_origin(plan)
    raw_date = plan.get('trade_date')
    date = None
    if (isinstance(raw_date, str) and len(raw_date) == 8
            and raw_date.isascii() and raw_date.isdecimal()):
        try:
            date = datetime.strptime(raw_date, '%Y%m%d').strftime('%Y-%m-%d')
        except ValueError:
            pass
    metadata = {'date': date, 'decision_source': source,
                'assembly_kind': 'explicit_read_only', 'plan_sha256': digest}
    header = [
        # Keep report metadata first; the preserved raw frontmatter is prose,
        # not an opportunity to override the JSON's decision source.
        '---', *(f'{key}: {json.dumps(value, ensure_ascii=False)}'
                 for key, value in metadata.items()), '---', '',
        _ASSEMBLY_MARKER,
        '# 显式组装报告（非重新推理）', '',
        '> 决策来源（JSON）：' + text(source),
        '> 同版 JSON SHA-256（规范化内容）：' + digest,
        '> 以下散文为调用方提供的模型原文，完整保留、未经重新推理；'
        '原文自述不是来源验证，不得覆盖 JSON 禁令、权限或缺口。',
        '> 表格直接复用既有共享 renderer；只读展示，不构成开仓或自动交易授权。',
    ]
    if fallback:
        header += ['> 🚨 Python FALLBACK · 非大模型决策，不可据此下单；正文自报 LLM 不覆盖此警报。']
    header += ['', '## 模型原文（非重新推理）', '']
    # Do not strip, normalize newlines, parse headings or rebuild model prose.
    return ('\n'.join(header) + '\n' + narrative +
            '\n\n## 同版 JSON 共享表格（只读附录）\n\n' + render_plan_tables_md(plan))


def assemble_plan_report_files(*, plan_path: str | Path,
                               narrative_path: str | Path,
                               out_path: str | Path) -> Path:
    """Read both explicit inputs fully, then atomically replace explicit output.

    Parent directory must already exist. Never overwrite JSON (including aliases)
    or follow output symlinks. In-place raw MD assembly is allowed explicitly;
    validation/render/write/replace failures leave that report untouched. Temporary
    files are removed on failure. No backup/default companion files are generated.
    """
    plan_path, narrative_path, out_path = map(Path, (plan_path, narrative_path, out_path))
    if out_path.is_symlink():
        raise ValueError('output symlinks are not supported')
    if (out_path.resolve() == plan_path.resolve() or
            (out_path.exists() and plan_path.exists() and out_path.samefile(plan_path))):
        raise ValueError('output must not overwrite plan JSON')
    # Bytes preserve CRLF/BOM/trailing whitespace in the original prose.
    plan_bytes = plan_path.read_bytes()
    narrative_bytes = narrative_path.read_bytes()
    plan = json.loads(plan_bytes)
    narrative = narrative_bytes.decode('utf-8')
    output = assemble_plan_report(plan, narrative).encode('utf-8')
    mode = stat.S_IMODE(out_path.stat().st_mode) if out_path.exists() else None
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='wb', dir=out_path.parent,
                                         prefix='.' + out_path.name + '.',
                                         suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(output)
            stream.flush()
            if mode is not None:
                os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
        os.replace(temporary, out_path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return out_path
