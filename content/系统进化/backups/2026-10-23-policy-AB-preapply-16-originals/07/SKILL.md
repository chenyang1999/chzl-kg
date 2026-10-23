---
name: research_orchestrator_v1
description: canghai-research 主控 — delegate_task 调度 R1-R7，收集 artifact 路径，产出 research_summary.json
agent_owner: canghai-research
version: v2
status: P0-T1prime
category: research/orchestrator
created: 2026-07-04
updated: 2026-07-05
tested_with: ["20260704 delegation smoke", "appendix-C batch limits"]
---

# research_orchestrator_v1

**归属**: `canghai-research` profile 主控（调度层，不是任何单一 R* 单元）  
**目的**: 按当前启用的盘前任务日程，读取 `data/raw/YYYYMMDD/` 与 manifest，依实际输入依赖派发 R1–R7，收集并核验单元产物，写 **`data/research/YYYYMMDD/research_summary.json`** 供计划端消费；本技能中的示例时刻不覆盖运行配置。

**架构依据**: `docs/01-系统现状全景.md` §5 · `docs/10-契约-研究汇总.md`
**Cron 模式**: Hermes **agent + skill**（主路径 = LLM + delegation；**禁止** `--no-agent` Python orchestrator）

---

## Purpose

主控 **不做分析、不直接调 MCP**，只做:

1. 校验 fetch 上游 manifest
2. `delegate_task` 按硬约束时序派发 R1–R7
3. 收集 sub-agent 回传的 artifact 路径 + schema 校验结果
4. 写 `research_summary.json`

Sub-agent 的中间 tool call **不进主控 context** — 只回传最终 artifact 路径。

---

## Execution Prompt（Agent 加载本 skill 后按序执行）

### Step 0 · 初始化

```text
trade_date = 今日 YYYYMMDD（上海时区，或 cron 指定）
raw_dir    = data/raw/{trade_date}/
out_dir    = data/research/{trade_date}/
```

读取并缓存:

```
data/raw/{trade_date}/manifest.json          # 必需；缺则 orchestrator_status=failed，告警退出
data/user_preferences.yaml                   # 只读，传给各 sub-agent
data/human_thesis/active/*.md                # 只读，传给各 sub-agent
```

记录 `fetch_global_severity = manifest.global_severity`（0–3）。

**禁止**:
- ❌ 主控直接调用 tushare / xtick / weflow / wechat MCP
- ❌ 修改 `user_preferences.yaml` / `human_thesis/`
- ❌ 调用 `scripts/research/run_research_orchestrator.py` 或 `src/research/orchestrator.py`（T1' Python fallback 冻结）

### Step 1 · Sub-agent 映射（skill + agent spec）

每个 `delegate_task` 的 `prompt` 必须指向对应 **流水线 skill** 与 **agent spec**（schema 冻结在 spec + 各 R*.json 契约）:

| 单元 | delegate 加载 skill | Agent Spec（必读契约） |
|------|---------------------|------------------------|
| R1 | `analyze_style_v1` | `docs/agents/R1-风格Agent.md` |
| R2 | `analyze_main_sectors_v1`, `filter_leader_v1` | `docs/agents/R2-主线板块Agent.md` |
| R3 | `analyze_sentiment_resonance_v1`, `hotlist_rank_signal_v1` | `docs/agents/R3-情绪与热度Agent.md` |
| R4 | `analyze_news_impact_v1` | `docs/agents/R4-消息面Agent.md` |
| R5 | `analyze_stock_profile_v1`, `serenity_analyst` | `docs/agents/R5-情报深挖Agent.md` |
| R6 | `analyze_devil_advocate_v1` | `docs/agents/R6-反证Agent.md` |
| R7 | `analyze_capital_flow_v1`, `detect_seesaw_pairs_v1`, `hot_money_synergy_v1` | `docs/agents/R7-资金面Agent.md` |

横切 `_shared/` skill 由各 R* skill 内 `@` 引用 — 见 `docs/01-系统现状全景.md` §1.2；**主控不重写** hithink/news/估值逻辑。

**各 sub-agent 统一输入上下文**（写入 delegate prompt）:

```yaml
trade_date: YYYYMMDD
raw_dir: data/raw/YYYYMMDD/
manifest: data/raw/YYYYMMDD/manifest.json
preferences: data/user_preferences.yaml          # 只读
thesis: data/human_thesis/active/*.md            # 只读
output_path: data/research/YYYYMMDD/R{N}_*.json  # 见下表
```

| 单元 | 默认 output_path |
|------|------------------|
| R1 | `data/research/YYYYMMDD/R1_style.json` |
| R2 | `data/research/YYYYMMDD/R2_main_sectors.json` |
| R3 | `data/research/YYYYMMDD/R3_sentiment.json` |
| R4 | `data/research/YYYYMMDD/R4_news.json` |
| R5 | `data/research/YYYYMMDD/R5_stock_profiles.json` |
| R6 | `data/research/YYYYMMDD/R6_devil_advocate.json` |
| R7 | `data/research/YYYYMMDD/R7_capital_flow.json` |

### Step 2 · 按实际依赖分批，按完成结果交接

先辨认当前启用入口：shell 控制层逐单元启动 LLM，与纯 Python 代替研究决策不是同一回事；不得因看到 shell/状态记录程序就擅自改回另一条主路径。若使用 delegation，按当前运行时的异步返回约定处理，不沿用历史保活轮询经验。

按输入依赖执行：

```text
Batch 1: R1 / R4 / R7，独立任务在实际可用并发槽内运行
Batch 2: R3，读取本交易日已核验的 R1 基线
Batch 3: R2，读取已核验的 R1 / R3 / R4 / R7
Batch 4: R5，读取本次 R2 候选及其缺口
Batch 5: R6，只读本次 R1-R5 / R7，不抓新行情
最后: 收集完整结果与契约检查，写 research_summary.json
```

- 按当前可用并发槽拆批；提交成功不等于释放并发槽，也不等于依赖完成。
- 完成结果到达后，再核对该单元的本次 run/attempt、交易日、JSON 与承诺的人读报告；不要用旧同日文件存在代替当前任务终态。
- 不用 sleep/文件或转录轮询等待异步子任务；遵守当前工具的完成通知机制，依赖未就绪不启动消费者。
- 读完整回传，包括剩余问题；用任务与产物版本去重迟到通知，已审阅整合的结果不重复运行或补写。
- 超时预算从当前任务配置、交付截止点及实测关键路径取得；不能把历史测试耗时当永久运行时上限。到点按实际缺口写 partial/failed，不默许消费者读半成品。
- 研究汇总交给计划端消费；D1 必须由 `canghai-plan` 启动，研究身份不得替写计划、触发价或运行副本。

### Step 3 · 消费依赖硬约束

| 阶段 | 动作 | 必需证据 |
|------|------|----------|
| 基础研究 | 并行 R1 / R4 / R7 | 本交易日 raw 与 manifest；缺口显式保留 |
| 情绪研究 | R3 | 本次 R1 基线已就绪，不能自动换成昨日或固定默认值 |
| 主线研究 | R2 | 本次 R1 / R3 / R4 / R7 已核验 |
| 个股画像 | R5 | 本次 R2 候选或明确的空池原因 |
| 反证 | R6 | 本次 R1-R5 / R7；唯一硬否决权来源不变 |
| 汇总交接 | 写 research_summary.json | 单元路径、质量状态、缺口及交付结果 |

实际时刻以启用的任务日程和交付截止点为准；本技能不授权修改 cron、模型、并发配置或交易门控。

### Step 4 · 收集 artifact

对每个 R* sub-agent 回传:

1. 使用 Step 1 的显式主产物映射，不把 evidence/validation/draft 文件当研究单元
2. 核对本次 run/attempt、交易日、合法 JSON 和对应实际存在的 schema/契约校验器；校验器缺失或报错必须记录，不能自报全通过
3. 分别核验 JSON 可消费性、数据质量和承诺的人读报告交付；可用 JSON 不掩盖 MD 缺交付，降级也不自动等于执行失败

| 结果 | 处理 |
|------|------|
| ✅ 校验通过 | 写入真实 `artifacts.R{N}` 与原稿 confidence；保留有效零值，缺失按实际契约显式标未知，不默补固定置信度 |
| 🟡 partial/degraded | 保留可消费的主研究及其原始缺口，不当 skeleton，也不改成完整通过 |
| ⏸️ 合法 skipped | 核对理由和前置条件（如 R2 确实无候选），保留跳过说明及应交付的人读报告；不强凑画像 |
| ❌ 超时/失败 | 记 `timeouts: ["R{N}"]` 与实际错误；**不写**非法或陈旧路径冒充本次 artifacts |
| ⚠️ skeleton | 明确标记不可用于完整研究结论，`orchestrator_status=partial` |

**R6 特殊**: 从 `R6_devil_advocate.json` 提取 `severity: hard_reject` 条目 → 填入 `hard_rejects[]`（schema 见 `docs/10-契约-研究汇总.md` §4）。

**Fallback（T1' 软降级）**: 某 R* 失败时可读 **昨日** 同路径 artifact 作替代，`confidence=0`，`timeouts` 标注 — **不**调用 Python `src/research/r*.py`。

### Step 5 · 写 research_summary.json

路径: `data/research/YYYYMMDD/research_summary.json`

契约: **`docs/10-契约-研究汇总.md`**（字段冻结，pydantic 校验不过 → 不写盘，告警）

```json
{
  "schema_version": "research_summary_v1",
  "trade_date": "YYYYMMDD",
  "generated_at": "ISO8601+08:00",
  "orchestrator_status": "complete|partial|failed",
  "fetch_manifest": "data/raw/YYYYMMDD/manifest.json",
  "fetch_global_severity": 0,
  "artifacts": {
    "R1": "data/research/YYYYMMDD/R1_style.json",
    "R2": "data/research/YYYYMMDD/R2_main_sectors.json",
    "R3": "data/research/YYYYMMDD/R3_sentiment.json",
    "R4": "data/research/YYYYMMDD/R4_news.json",
    "R5": "data/research/YYYYMMDD/R5_stock_profiles.json",
    "R6": "data/research/YYYYMMDD/R6_devil_advocate.json",
    "R7": "data/research/YYYYMMDD/R7_capital_flow.json"
  },
  "confidence": {"R1": 0.0, "R2": 0.0, "R3": 0.0, "R4": 0.0, "R5": 0.0, "R6": 0.0, "R7": 0.0},
  "hard_rejects": [],
  "timeouts": [],
  "completed_by": "08:00"
}
```

**Report 模板**（cron deliver）:

```
【research_orchestrator_v1 · YYYYMMDD】
orchestrator_status: {complete|partial|failed}
fetch_global_severity: {0-3}
delegation_batches: {实际批次} · {N} 轮

units:
  R1: {ok|timeout} · confidence={x}
  ...
  R7: {ok|timeout} · confidence={x}

hard_rejects: {count} 条（来源 R6）
timeouts: [{...}]

summary: data/research/YYYYMMDD/research_summary.json
```

---

## Inputs

| 输入 | 路径 |
|------|------|
| Fetch manifest | `data/raw/YYYYMMDD/manifest.json` |
| Raw artifacts | `data/raw/YYYYMMDD/wechat_official_20.jsonl`, `wechat_cli_5groups.jsonl`, `weflow_snapshot.json`, `mcp_health.json` |
| 用户先验 | `data/user_preferences.yaml`（只读） |
| 临时视角 | `data/human_thesis/active/*.md`（只读） |

## Outputs

| 产出 | 路径 |
|------|------|
| R1–R7 单元 JSON | `data/research/YYYYMMDD/R1_style.json` … `R7_capital_flow.json` |
| 各 R* 人读报告 | 各单元技能与已批准 SOUL 指定的 `chzl_kg/投研交易/` 目标；不得把已承诺的 MD 交付擅改为可选 |
| **契约 3 汇总** | `data/research/YYYYMMDD/research_summary.json` |

## Rules & Constraints

### 主控 toolsets（SOUL 白名单）

- ✅ `file`, `delegation`
- ❌ 直接 MCP（tushare / xtick / weflow / wechat / datapro / hithink …）

### Sub-agent toolsets（文档约束 · 附录 C 实测为软约束）

| 单元 | 期望 toolsets |
|------|---------------|
| R1 | file, tushare, xtick |
| R2 | file, tushare, datapro, hithink |
| R3 | file, weflow, hotlist |
| R4 | file, wechat, tushare |
| R5 | file, tushare, serenity-alpha, valuation-suite |
| R6 | **file only**（反证禁 MCP — 靠 R6 skill prompt 约束） |
| R7 | file, tushare, xtick, datapro |

> 不把文档中的 toolset 列表当作隔离证明；启动时核验当前运行权限。R6 即使能看到行情工具，也必须遵守只读上游产物、禁止行情 MCP 的研究边界。

### Step 6 · 契约校验（v2.1 新增 · 2026-08-10）

所有单元 artifact 落盘后、summary 最终写盘前，**必须**运行契约校验脚本。

**调用方式**：

```python
from src.research.contract_checks import run_research_checks
# 读回各单元 JSON
contract_failures = run_research_checks(unit_data, trade_date)
```

**校验范围**（来自 P0/P1 修复的硬约束）：

| 单元 | 校验项 | 对应修复 | 级别 |
|------|--------|---------|------|
| R2 | cross_validation 字段 + consensus_themes | P0-3 | P0 |
| R5 | 非空候选分支核验候选数量及降级标记；经 R2 理由与空池证据核验的合法 skipped 单列，不当画像执行失败 | 候选契约 | P0 |
| R7 | staleness 状态机 + resolved_trade_date | P0-2 | P0 |
| R4 | top_pick_logic + stop_loss | P1-3 | P1 |

**失败处理**：
- P0 级失败 → `orchestrator_status` 从 `complete` 降级为 `partial`
- P1 级失败 → 记入 `contract_failures`，不降级
- 所有失败写入 `research_summary.contract_failures` 字段（格式 `{unit: [error_strings]}`）
- 新增 `contract_checks_passed: bool` 字段（全部通过 = true）

**失败不阻塞流水线**：宁可有瑕疵的研究输出，也不能因为校验失败导致 D1 无数据可用。D1 消费时检查 `contract_checks_passed` 字段自行决定仓位策略。

---

### 其他铁律

- artifact 之间 **只通过磁盘 pull**，不共享 LLM context
- δ 层数据（QMT 报价/持仓）**不进** R1–R7 — 见 `docs/03-数据源与降级.md`
- 主控仅写研究汇总；各 R* 的 JSON 与人读报告按本次已批准的 Ownership 白名单执行，技能加载本身不新增权限。研究端不写 raw、计划、执行状态或 runtime 副本。

## Fallback Behavior

| 场景 | 行为 |
|------|------|
| manifest 缺失 | `orchestrator_status=failed`，不写 summary，告警 |
| 单 R* 超时 | 昨日 artifact + `confidence=0` + `timeouts` |
| R6 超时 | D1 视为「无反证」保守处理；**不可**自行放宽 R6 约束 |
| Hermes delegation 全失败 | 告警 + 空池；**不**跑 Python orchestrator（T1' 冻结） |
| **LLM quota 超限** | 保留已验证研究并明确失败单元、实际错误与可恢复状态；D1 交由计划端及已授权安全网处理，研究端不写计划/触发价，不自动切换模型 |

兜底不得冒充 LLM 主决策，也不得因合法空池覆盖已有 LLM 计划。研究端只交付真实输入和缺口，不能跨身份拼造交易预案。

## `_shared/` 引用（主控不直接调）

主控 **不** `@` 横切 skill。各 R* 实装时在自身 SKILL.md 内引用 — 完整映射见 `docs/01-系统现状全景.md` §1.2:

| R* | 主要 `@` skills |
|----|-----------------|
| R2 | `@hithink-sector-selector`, `@hithink-industry-query`, `@hithink-market-query`, `@iwencai-query` |
| R3 | （weflow MCP 为主；横切少） |
| R4 | `@hithink-event-query`, `@news-search`, `@announcement-search` |
| R5 | `@serenity-alpha`, `@bayesian-intrinsic-growth-valuation`, `@tam-adj-peg`, `@gf-dma-health-index`, `@buy-side-equity-research-memo`, `@report-search`, `@hithink-insresearch-query`, `@hithink-management-query`, `@hithink-business-query` |
| R6 | `@announcement-search`（核验用，禁行情 MCP） |
| R7 | `@hithink-market-query` |

## Version History

- **v2.1 (2026-08-10)**: Step 6 契约校验 — `src.research.contract_checks` 模块集成，P0/P1 硬约束自动检测 + 失败降级
- **v2 (2026-07-05)**: T1' Hermes 主路径 — `delegate_task` + 方案 A/B 批次 + `research_summary.json`；移除 Python orchestrator 为主入口
- v1 (2026-07-04): T1 skeleton（Python artifact-first，已降级为后置 fallback）
