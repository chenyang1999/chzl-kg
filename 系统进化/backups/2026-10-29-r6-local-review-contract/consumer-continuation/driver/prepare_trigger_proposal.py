"""Prepare one precise operational-rule diff; do not apply or start a task."""
from pathlib import Path
import hashlib,json,difflib,datetime
root=Path('/Users/chenyang/Downloads/demo/沧海巨浪')
folder=root/'chzl_kg/系统进化/backups/2026-10-29-r6-local-review-contract'
path=root/'skills/main_decision_v1/SKILL.md'
raw=path.read_bytes()
assert hashlib.sha256(raw).hexdigest()=='3eb4f6695151edc5422ca3ffabccf84f2fce9b347406a46d5ec43193fe3bce5c'
text=raw.decode()
anchor='### Step 3.6 — 战术层短线信号'
assert text.count(anchor)==1
addition='''### 盘中缺审自动交接（运行变更候选，需独立签核后接线）

- 只使用现有翻多检测的正常触发，不新增任务或修改时刻。确认事件及既有研究/计划版本均合法后，普通调用程序可将原计划已列、同时属于原R2/R5研究范围的对象中尚未完成的模式1/2/6/7交给现有R6局部入口；D1模型不自己调R6、shell或另一模型。
- 其余六份保留原身份、字节和事实时点；缺少合法基线/终态接收或没有明确对象时保留具体缺口，不整批重跑、扩池或自造来源。
- 自动任务以原六份版本及原目标集合幂等，同一来源/对象集合只自动启动一次；部分完成或缺证不循环重模型。合法的不同人工指定补审请求仍按既有契约可继续，不新增“一天/一基线只能补审一次”的门槛。已有有效提案的交付失败仍仅重交付。
- 新R6及汇总合法交付后重新绑定本次事件，再由原计划角色按现有范围重评。相同市场观察遇到新的可信R6交付可以重评一次，先前事件/输入回执保留；同一事件和同一输入版本不重复模型。
- 审核完成不自动通过、入池或买入。仍不改变原池/entry/exit、有效零预算、账户/用户禁令、执行与确认身份；真实逐票硬否决与未审项保留。正式逐票重新准入不在此自动触发许可内。
- 本项批准只覆盖以上普通程序接线、隔离验证及后续正常既有任务的采用，不授权当前人工补跑、补抓、付费探针或交易，不修改profile、模型、SOUL、凭据或定时定义。未获签核不应用本段或激活自动调用。

'''
expected=text.replace(anchor,addition+anchor)
diff=''.join(difflib.unified_diff(text.splitlines(True),expected.splitlines(True),fromfile='a/skills/main_decision_v1/SKILL.md',tofile='b/skills/main_decision_v1/SKILL.md'))
for name in ('automatic-trigger.pending.diff','automatic-trigger.expected.md','automatic-trigger.proposal.json'):
    assert not (folder/name).exists()
(folder/'automatic-trigger.pending.diff').write_text(diff)
(folder/'automatic-trigger.expected.md').write_text(expected)
record={'prepared_at':datetime.datetime.now().astimezone().isoformat(),'status':'pending_not_applied','target':str(path.relative_to(root)),
        'before_sha256':hashlib.sha256(raw).hexdigest(),'candidate_sha256':hashlib.sha256(expected.encode()).hexdigest(),
        'diff_sha256':hashlib.sha256(diff.encode()).hexdigest(),'automatic_trigger_implemented':False,
        'production_or_model_or_account_started':False,'stock_readmission_permission_changed':False}
(folder/'automatic-trigger.proposal.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
assert path.read_bytes()==raw
print(json.dumps(record,ensure_ascii=False,indent=2))
print(diff)
