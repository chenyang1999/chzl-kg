---
name: analyze_devil_advocate_v1
description: R6 反证 Agent — 只读 R1-R5+R7 产出，六类反证模式，模式六霸榜出货为唯一 hard_reject
agent_owner: R6
version: v1
status: draft
category: research/R6
created: 2026-07-03
updated: 2026-07-05
spec: docs/agents/R6-反证Agent.md
detail_spec: docs/06-专题-反证机制.md
---

# analyze_devil_advocate_v1 · R6 反证 Agent

**跑动时点**: 07:55（R1–R5 + R7 完成后，D1 之前）  
**权威规格**: `docs/agents/R6-反证Agent.md` + `docs/06-专题-反证机制.md`  
**产出路径**: `data/research/YYYYMMDD/R6_devil_advocate.json`

---

## ⚠️ Toolsets 约束（附录 C · prompt-only）

Hermes 当前版本 **无法** per-child 硬拦截 MCP（`docs/01-系统现状全景.md` 附录 C.3）。  
R6 设计为 **`[file]` only — 禁 MCP、禁 shell 抓数**，本条靠 **本 prompt 自我约束** 执行：

- ✅ 仅允许：`read_file` / `write_file`（或等价 file 工具）读写 **`data/research/`**、**`data/raw/`**、**`data/reports/`** 下已有 artifact  
- ❌ **禁止**：Tushare / XTick / WeFlow / hithink / terminal 等一切 **主动拉新数据**  
- ❌ **禁止**：`delegate_task` 再派生子 agent  

`@announcement-search`：**默认禁止调用**。仅当 R4/R5 上游 JSON **已引用**某公告标题+代码，且 hard_reject 论证需核对**同一条**公告原文细节时，允许 **单次** `@announcement-search` 按 code 核验 — **不得**扩展搜索范围或发现新催化。

### vibe-trading MCP 补充（2026-08-06 新增 · 反证量化验证）

**目的**：R6 消费 R1-R5 的主观判断作反证，vibe-trading 提供独立量化证据（资金/大宗/研报）找漏洞。

| 工具 | 调用方式 | 典型问句 | 返回字段 |
|------|---------|---------|---------|
| `vibe_trading__iwencai_search` | NL 问句 | `近期大宗交易溢价率>5%的个股`（主力接盘 vs 利益输送） | 大宗交易表 |
| `vibe_trading__iwencai_search` | NL 问句 | `近期研报评级上调且目标价距离现价>30%的个股` | 研报复议表 |
| `vibe_trading__get_fund_flow` | ts_code | R6 反证对象的候选票，查近10日主力净流入 | 资金流序列 |
| `vibe_trading__get_block_trades` | ts_code | 查近20日大宗交易（折价 = 减持风险信号） | 大宗交易表 |
| `vibe_trading__get_research_reports` | ts_code | R6 反证对象，查研报评级分歧度（多空分歧） | 研报列表 |

**调用时序**：Step 2（硬证据扫描）阶段，对每个 R6 反证点调 `iwencai_search` + `get_block_trades` 找量化支撑。  
**注意**：R6 禁止主动拉数据——以上调用仅作为**验证已存在的 R1-R5 判断**的反证工具，不用于发现新票。  
**降级**：`vibe_trading__iwencai_search` 失败 → 跳过，仍用纯文本分析。

---

## 唯一职责

消费 R1–R5 + R7 全部产出，**反向找漏洞**，列出可能被证伪的点，供 D1 参考。  
**只给反面证据，不给正向结论。**

---

## 输入（只读 JSON · pull-based）

### 必需

| 路径 | 用途 |
|------|------|
| `data/research/YYYYMMDD/R2_main_sectors.json` | 反证对象（龙头/主线）；**缺失则降级「今日不出反证」** |
| `data/research/YYYYMMDD/R1_style.json` | 模式二：风格一致性 |
| `data/research/YYYYMMDD/R3_sentiment.json` | 模式一/六：共振、`distribution_alert` |
| `data/research/YYYYMMDD/R4_news.json` | 模式一：消息交叉 |
| `data/research/YYYYMMDD/R5_stock_profiles.json` | 模式三/六：估值、筹码资金 |
| `data/research/YYYYMMDD/R7_capital_flow.json` | 模式一：资金面交叉 |

### 可选

| 路径 | 用途 |
|------|------|
| `data/raw/YYYYMMDD/hotlist_signals.json` | 模式六补充（若 R3 未透传） |
| `data/reports/YYYYMMDD/observation_tracking.json` | 模式五：昨日反证兑现（E1 未上线则诚实降级） |
| `data/research/{prev_date}/R6_devil_advocate.json` | 模式五：昨日反证条目 |

**不读** markdown 版 `chzl_kg/投研交易/*`（若与 JSON 冲突以 JSON 为准）。

---

## 六类反证模式

| # | 模式 | 默认 severity | 说明 |
|---|------|---------------|------|
| 1 | 数据源冲突 | `soft_suggest` | R2 主线未获 R3 共振 / R4 消息 / R7 资金任一确认 |
| 2 | 一致性检查 | `strong_suggest` | R1 防御/退潮 vs R2 仍推多条高波动主线 |
| 3 | 估值×主线临界 | `strong_suggest` / `soft_suggest` | R5 估值 `极贵`/`偏贵` × 龙一/龙二 · 命中"10 大估值陷阱"任一即 `strong_suggest` |
| 4 | 历史类比 | `soft_suggest` | 依赖历史事件库 — **v1 无库则降级**，不编造 |
| 5 | 昨日预期错误连锁 | `strong_suggest` | 昨日 R6 反证已兑现 → 今日相似结构警报 |
| 6 | **霸榜出货硬约束** | **`hard_reject`** | **唯一硬否决权** — 见下节 |
| 7 | **基本面红旗**(v1.2 · 2026-07-07 新增) | `soft_suggest` / `strong_suggest` / `hard_reject` | vibe-trading `financial-statement` 12 红旗 + `ashare-pre-st-filter` 双轴,见附录 A |
| 8 | **解套盘假繁荣**(v1.3 · 2026-08-06 新增 · `@行为金融分析`) | `soft_suggest` / `strong_suggest` | 涨停 100+ 但其中解套盘比例 > 70%（按"封板量 vs 历史套牢区"估算）= 假繁荣；`high_suspicion=true` 时所有涨停板票的 `confidence` 上限 0.6 |
| 9 | **高位触板赌博标的**(v1.3 · 2026-08-06 新增 · `@行为金融分析`) | `strong_suggest` | 标的处于 8 板+ 高度龙头（参考 8/5 实测 002980 35 板、002222 25 板）→ 必在 `meta.bias_risk` 标 `extreme_tail_risk=true`；与 5+ 板 100% 晋级叠加 → `hard_reject` |
| 10 | **跨资产背离**(v1.3 · 2026-08-06 新增 · `@大宗商品分析`) | `soft_suggest` | 候选板块与对应大宗商品走势背离（如铜业股推但铜价跌 / 油服推但油价跌）→ 标 `commodity_divergence=true`；与基本面红旗模式七叠加 → `strong_suggest` |

### 模式六 · hard_reject 规则（D1 必须执行）

触发对象：R2 中 `execution_eligible` 的龙一/龙二（`filter_leader_v1` 已标注）。

**硬否决条件（同时满足）**：

1. 标的所属板块命中 R3 `hotlist_signals.distribution_alert`（霸榜出货高置信）  
2. R5 画像 `chip_structure.main_force_5d_net_wan < 0`（近 5 日主力净流出）

仅命中 (1) 未确认 (2) → 降级为 **`strong_suggest`**（D1 须显式处理，可覆盖）。

**否决后的出口(v1.2 · 2026-10-19 用户钦定, 取代"红线3保护")**:
- 龙一被 hard_reject 后只能从 execution_pool 剔除，可留研究观察并记录禁令/空池理由；不得以“等分歧买点”保留执行资格。strong_suggest 仍按原有显式处理/覆盖契约，不自动视为通过；不为数量递补杂毛
- ❌ **禁止用龙二/弹性核心/低位补涨票降级替补**——杂毛失去板块β时风险>龙头,补涨票不得因龙头被否而升位
- 已删除旧规则"候选<3只时hard_reject自动降级为strong_suggest"——该规则逼系统凑数,是辨识度问题的制度根源
- 否决"高位/一致"龙一必须同时给出具体证据(霸榜出货/资金净流出/身位崩塌),不得只因位置高就否决

`hard_rejects[]` 元素对齐 `docs/10-契约-研究汇总.md` §4：

```json
{
  "ts_code": "002050.SZ",
  "name": "三花智控",
  "reason": "霸榜出货：distribution_alert + 近5日主力净流出",
  "evidence": ["R6 mode-6", "R3 hotlist_signals.distribution_alert", "R5 chip_structure"],
  "source_agent": "R6",
  "suggestion": "hard_reject — 禁止纳入 execution_pool"
}
```

---

### 模式七 · 基本面红旗(v1.2 · 2026-07-07 新增)

**来源**: vibe-trading `financial-statement` skill 12 大红旗 + `ashare-pre-st-filter` 双轴风险 + `valuation-model` 10 大估值陷阱

**触发对象**: R2 中 `execution_eligible` 的龙一/龙二 + R5 `execution_pool` 候选

**数据依赖**: R5 六维中的"财务与估值"维度(要求 R5 每票新增 `fundamental_flags[]` 字段,若未透传则本模式 `degraded`)

**severity 判定**:
- 命中 **1 条** 红旗 → `soft_suggest`(记入 `r6_soft_notes`,不影响 D1)
- 命中 **2-3 条** 红旗 或 命中"P0 类"红旗 1 条 → `strong_suggest`(D1 须显式处理)
- 命中 **≥4 条** 红旗 或 命中"退市风险"(ST 双轴 `imminent`) → `hard_reject`(与模式六并列硬否决)

**否决后出口同模式六**: 允许空仓,禁止降级替补。

**产出**: `counter_arguments[]` 中每条模式七的元素 `evidence_against` 必须列出命中的红旗编号 + 检出方法。

---

## 执行步骤

### Step 1 · 加载 upstream + 可用性矩阵

先核本批输入的日期、run/attempt、交付回执与内容版本，再按模式、对象、证据项判可用；不得仅因整份报告 partial/degraded 就抹掉已核证据，也不得仅因字段存在或整份 complete 就判证据有效。failed/skeleton、错批或无法追溯的材料不能作为正式证据。

R2 中本批真实且结构合法的对象可进入审查，包括 partial 中已有对象；对象的主线/角色/适用窗口与缺口原样保留，不推定 execution_eligible。无对象时产出降级 JSON，`candidates_evaluated: 0`，并区分合法空对象与入口缺失。`upstream_usable` 保留为兼容摘要，不再承担逐模式“已通过”的含义。

| 模式 | 最小必要证据（逐项核版本、对象、观察窗口和语义） | 缺失的局部结果与回送 owner |
|---|---|---|
| 1 数据源冲突 | R2 实际主张；分别核 R3 共振、R4 消息、R7 适用资金的对应证据 | 缺哪个交哪个 R；其余分支照审。未提供确认不能写为已证明不确认，冲突须有可比的实际证据 |
| 2 一致性 | R1 风格判断与 R2 同窗口主线/风险主张 | 缺 R1→R1，缺对象/归属→R2；不能用 R5 缺口跳过此模式 |
| 3 估值×主线 | R2 原角色/主线及 R5 对应估值事实和原陷阱检出依据 | 缺 R2→R2，缺估值→R5；不补默认估值、不新增阈值 |
| 4 历史类比 | 已许可历史材料、真实样本与当前可比条件 | 无库/无读取许可继续 degraded，不编造；owner 为研究主控协调既有历史材料归属 |
| 5 昨日预期兑现 | 已许可、具原时点的昨日 R6 条目与 E1 兑现证据，以及今日相似结构 | 缺昨日反证→R6，缺兑现→E1，缺今日结构→R2；没有 E1 不影响模式二已核事实 |
| 6 霸榜出货 | R2 精确对象/板块关联；R3 显式 alert 证据；需要资金确认时核 R5 同票近5日主力净额与有效窗口 | alert 与净流出同时证实才按原规则 hard_reject；alert 已证实而资金未确认，仍按原条款 strong_suggest 并保留资金缺口；alert 未提供不是 false，更不是通过。缺 alert→R3，缺筹码资金→R5；R7 不默认替代 R5 口径 |
| 7–10 既有扩展模式 | 分别为 R5 财务红旗检出事实；有效封板量/历史套牢区与市场统计；高度及晋级事实；对应商品与候选走势 | 对应 R5、R1/R2（市场事实）、R4/R7（原有跨资产材料），由研究主控核实际生产归属，不扩读/补抓。证据不够局部 degraded；原有 severity 冲突保留待用户决定，不借本表新授或删除硬否决权 |

沿用 `patterns_status` 逐模式记录已核对象/证据定位、未完成项及 owner；个股结论沿用 `counter_arguments`。这是审计明细，不是新的交易许可字段。模式 executed 只表示该范围实际执行，不等于候选通过；部分结果保留，未完成仍 partial/degraded，不把整份标 complete。

`candidates_evaluated` 只计确已对至少一个适用模式完成有据审查的去重对象数，同时在 `patterns_status` 分列每模式覆盖；研究对象数、已审对象数、必需审核完成数和硬否决数不能混用。空 `hard_rejects` 只代表尚未形成否决，不代表全票审核通过；无对象/零评估不得写“全绿”。逐票正式审核须覆盖经用户确认的全部必需模式；未签清单时不得以局部已审替代现有完整审核门禁。

本变更只拆审查范围，不自动解除 no_trade、零预算或执行门禁；已形成的有效 hard_reject 仍必须保留并交 D1，不因其他模式降级而删除。R6 不给正向买入结论、不抓新数据、不扩读取范围。

### Step 2 · 逐模式扫描

按上表运行模式 1–6，每条产出：

```yaml
reject_id: R6_M1_01
mode_id: 1
mode_name: 数据源冲突
target: "R2主线「机器人」"
hypothesis_challenged: "R2判定机器人为核心主线(score 82)"
evidence_against:
  - {source: R3, detail: "未出现在 resonance_top_themes"}
severity: soft_suggest | strong_suggest | hard_reject
suggestion: "建议降级为观察池 / 下调仓位 / hard_reject..."
```

### Step 3 · 数量与质量

- 目标 **≥5 条** `counter_arguments`；不足则 `overall_conclusion: "今日反面证据不足(N条<5)，不硬凑"`  
- 只有声明的审查范围及全部必需证据确已完成时，才可在该范围写“未发现重大反面证据”；否则明确“局部已审/仍有未完成”，不写全票通过。  
- 模式 4 无历史库、模式 5 无 E1 → 在 `patterns_status` 标注 `degraded`，**不编造**

### Step 4 · 汇总 hard_rejects

从 `counter_arguments` 筛 `severity == hard_reject` → 写入根级 `hard_rejects[]`（供 orchestrator 写入 `research_summary.json`）。

### Step 5 · 写盘

`data/research/YYYYMMDD/R6_devil_advocate.json`

---

## 产出 JSON 契约

```json
{
  "schema_version": "research_unit_v1",
  "agent": "R6",
  "trade_date": "20260704",
  "generated_at": "2026-07-04T07:55:00+08:00",
  "status": "complete",
  "confidence": 0.85,
  "upstream_usable": {"R1": true, "R2": true, "R3": true, "R4": true, "R5": false, "R7": true},
  "overall_conclusion": "今日反证 severity 分布：hard_reject 1 / strong_suggest 2 / soft_suggest 3",
  "hard_rejects": [],
  "counter_arguments": [],
  "patterns_status": {
    "mode6_霸榜出货硬约束": {
      "severity_class": "hard_reject(唯一硬否决权)",
      "hard_reject_count": 0,
      "status": "executed"
    }
  },
  "candidates_evaluated": 6,
  "method": "llm_v1",
  "data_sources_used": [
    "data/research/*/R1_style.json",
    "data/research/*/R2_main_sectors.json",
    "data/research/*/R3_sentiment.json",
    "data/research/*/R4_news.json",
    "data/research/*/R5_stock_profiles.json",
    "data/research/*/R7_capital_flow.json"
  ]
}
```

---

## D1 消费规则（摘要）

| severity | D1 义务 |
|----------|---------|
| `hard_reject` | **强制**剔除 execution_pool，**无覆盖权** |
| `strong_suggest` | 必须接受或在 `meta.d1_override[]` 记录理由 |
| `soft_suggest` | 可选，记入 `r6_soft_notes` |

---

## 红线

1. ❌ **不抓新数据**（主路径；announcement 例外见上）  
2. ❌ **不给正向结论**  
3. ❌ 除模式六外 **不允许 hard_reject**  
4. ❌ 反证 <5 条时不硬凑  
5. ❌ hard_reject/strong_suggest 龙一后禁止用低位票替补(允许空仓)  
6. ✅ **必须每天产出**（含「无重大反面证据」）

---

## 降级（spec §6）

| 上游缺失 | 处理 |
|----------|------|
| R1 | 跳过模式二 |
| R2 | **无对象 → 不出反证** |
| R3 | 跳过共振/模式六 alert 面缩小 |
| R4 | 跳过消息一致性 |
| R5 | 跳过估值/模式六资金确认 |
| R1–R5 全缺 | 拒绝产出（orchestrator 记 failed） |

---

## 参考 · 软规则（`_archive/risk_manager` 合并）

以下仅作 **soft/strong_suggest**，**永不** hard_reject：

- 板块高潮追最后一棒 / 退潮期开新仓 / 无板块效应孤票  
- 「便宜所以买」「跌多该反弹」「从众」类逻辑  
- 流通市值 <20 亿、日成交额 <5000 万、减持公告期（超出 amygdala 硬规则的经验判断）

硬风控（单票≤15%、板块≤40%、ST 禁买）在 **execute 层 `amygdala.py`**，非 R6 职责。

---

## 附录 A · 12 财务红旗 + 10 估值陷阱 + ST 双轴 checklist(v1.2 · 2026-07-07)

**使用方式**: 模式七逐票扫描,命中即写入 `counter_arguments[].evidence_against`。R5 每票需在 `dimensions.valuation_safety.fundamental_flags[]` 透传检出结果供 R6 消费。若 R5 未透传 → 本附录 checklist 由 R6 通过 `mcp_vibe_trading_load_skill("financial-statement")` + `mcp_vibe_trading_get_financial_statements` 二次核验(**唯一例外·允许在此单次 MCP 调用**,与 announcement 例外并列)。

### A.1 · 财报三表 12 大红旗(vibe-trading `financial-statement`)

| # | 红旗名 | 检出方法 | P0? | 默认 severity |
|---|-------|----------|-----|---------------|
| F1 | 存贷双高 | 货币资金 > 20% 总资产 且 短期借款 > 20% 总资产 | ✅ P0 | `strong_suggest` |
| F2 | 商誉炸弹 | 商誉 / 净资产 > 30% | ✅ P0 | `strong_suggest` |
| F3 | 应收账款暴增 | 应收增速 > 收入增速 × 1.5 | | `soft_suggest` |
| F4 | 存货异常 | 存货增速 > 收入增速 × 1.5 且 存货周转率下降 | | `soft_suggest` |
| F5 | 资本化率过高 | 研发/开发支出资本化 > 50% | | `soft_suggest` |
| F6 | 一次性收益 | 非经常损益 / 净利润 > 30% | | `soft_suggest` |
| F7 | 关联交易占比高 | 关联交易 / 营收 > 20% | | `soft_suggest` |
| F8 | 经营现金流恶化 | CFO 连续 2 期为负 且 净利润为正(利润未变现) | ✅ P0 | `strong_suggest` |
| F9 | 应收/收入比异常 | 应收账款 / 营业收入 > 40% | | `soft_suggest` |
| F10 | 有息负债率高 | 有息负债 / 净资产 > 80% | | `soft_suggest` |
| F11 | 大股东质押 | 控股股东质押率 > 70% | ✅ P0 | `strong_suggest` |
| F12 | 审计师意见 | 保留意见 / 无法表示意见 / 强调事项 | ✅ P0(直接 hard_reject) | `hard_reject` |

**注**: F12 单条即 `hard_reject`(会计师非标意见 = 极高风险)。F1/F2/F8/F11 属"P0 类",单条即升级 `strong_suggest`。

### A.2 · 10 大估值陷阱(vibe-trading `valuation-model`)

| # | 陷阱名 | 检出方法 | 默认 severity |
|---|-------|----------|---------------|
| V1 | 周期股低 PE 陷阱 | 上游资源/化工/钢铁 × PE < 8 × 净利率处于历史 top 20% | `strong_suggest` |
| V2 | 高 PEG 陷阱 | PEG > 2 但增速依赖单次并购/一次性收益 | `strong_suggest` |
| V3 | 商誉炸弹陷阱 | PB < 1 但商誉 / 净资产 > 30% | `strong_suggest` |
| V4 | 应收陷阱 | ROE 高 但 CFO/净利润 < 0.5 | `soft_suggest` |
| V5 | 资本化陷阱 | ROIC 高 但研发资本化率 > 50% | `soft_suggest` |
| V6 | 一次性收益陷阱 | EPS 增速高 但 扣非 EPS 增速 < 0 | `strong_suggest` |
| V7 | 港股仙股陷阱 | 港股 × 市值 < 20 亿 × 日成交额 < 500 万 | `hard_reject`(A 股 N/A) |
| V8 | 关联交易估值虚高 | PS 高 但 关联交易 > 20% | `soft_suggest` |
| V9 | 分红陷阱(DDM) | 股息率 > 10% 但 CFO/净利润 < 0.8 | `soft_suggest` |
| V10 | SOTP 加总陷阱 | 分部估值总和 > 市值 2 倍 但子公司无独立现金流 | `soft_suggest` |

### A.3 · ST 双轴(vibe-trading `ashare-pre-st-filter`)

| 轴 | 触发条件 | severity |
|---|----------|----------|
| **财务轴** | 连亏 2 年 或 净资产 < 0 或 营收 < 1 亿 | `strong_suggest` |
| **合规轴** | 立案调查 / 重大违规 / 财务造假实锤 | `hard_reject` |
| **临近轴** | 已披露 *ST 预警 或 会计师非标意见 | **`hard_reject`(imminent)** |

### A.4 · checklist 输出契约

模式七每命中一项,`counter_arguments[]` 元素示例:

```json
{
  "reject_id": "R6_M7_01",
  "mode_id": 7,
  "mode_name": "基本面红旗",
  "target": "002050.SZ 三花智控",
  "hypothesis_challenged": "R5 判定财务与估值维度 score 78(安全)",
  "evidence_against": [
    {"flag": "F2", "detail": "商誉/净资产=42% (>30%)", "source": "vibe-trading get_financial_statements(balance)"},
    {"flag": "F11", "detail": "控股股东质押率 76% (>70%)", "source": "R5 chip_structure 透传"}
  ],
  "severity": "strong_suggest",
  "suggestion": "命中 P0 红旗 2 条(F2 商誉炸弹 + F11 大股东高质押) · 建议 D1 剔除或降仓至 5% 以下"
}
```

---

## chzl_kg 人读 md 落盘（必需 · @render_kg_md_v1）

**契约来源**: `skills/_shared/render_kg_md_v1/SKILL.md`

除机读 JSON 落盘之外，本 skill 必须**同时**渲染一份人读 md 到 chzl_kg 供用户当日审阅。

### 落盘路径

```
chzl_kg/投研交易/反证/{trade_date}.md
```

（目录若不存在，`mkdir -p` 创建。）

### frontmatter（必填，UTF-8 · Unix 换行）

```yaml
---
date: {trade_date YYYY-MM-DD}
agent: R6-devil-advocate
skill_version: analyze_devil_advocate_v1@1.0
generated_at: {ISO 8601 · 落盘时刻 · 含时区}
confidence: {从本 skill JSON artifact 读；缺则 null}
degraded: {true|false}
data_sources:
  - name: {源标识}
    path: {data/raw/... 或 MCP 名}
    status: {ok|error|timeout|stale}
    captured_at: {ISO 8601 或 null}
    record_count: {整数或 null}
    error: {可选 · 简短错误串}
input_freshness: {ok|partial|stale}
input_freshness_note: {任一源非 ok 时必填的说明}
---
```

### 正文（Markdown）

```markdown
# {trade_date 中文日期} · **反证 / Devil's Advocate**

> **数据源新鲜度**: {input_freshness}
> **降级状态**: {degraded}
> **置信度**: {confidence}

## 一句话结论
{≤ 60 字核心判断}

## 详细分析
{3-5 段主体}

## 关键证据
- 证据 1: {内容} · 来源 {data_source}
- 证据 2: ...
- 证据 3: ...

## 数据源审计
| 源 | 状态 | 抓取时间 | 记录数 | 备注 |
|---|---|---|---|---|
...

## 不确定性 / 反证
{自我批判段}

## 与其他 R/D/E 的关系
- 依赖: {上游 artifact 列表}
- 被消费: {下游 skill 列表}

## Sub-Agent 元数据
- skill: analyze_devil_advocate_v1
- artifact: data/.../{...}.json
- 生成耗时: N 秒
- model: {model 名}
```

### 落盘规则

1. **atomic write**: 先写 `.tmp` → `mv` 到目标（避免 Obsidian 抓半写）
2. **overwrite**: 同日重跑覆盖；若目标已存在先备份为 `.md.bak`
3. **失败不阻塞**: md 渲染失败**不**回滚 JSON artifact 落盘；skill status 写 `partial` 并在汇报中标注

### 验收

盘后 `test -f chzl_kg/投研交易/反证/{trade_date}.md` 必须为 true；前 30 行满足 frontmatter schema。

---

## 写作契约(v1 · 2026-07-06 硬约束升级)

本 skill 输出的 md **必须**遵循 `skills/_shared/canghai_writing_contract_v1.md`,该契约定义了:

1. **写作风格锚点** — 对标 `样例/20260630_pre_open_plan.md`,表格化 + emoji + 因果句 · 禁 python dump JSON / 群名裸露 / 时分秒
2. **必含 mermaid 图表**(≥1 张 · 节点 ≥ 8) — 本 skill 推荐类型见契约
3. **推理深度三问** — 每个 top 分析对象显式回答 `**大资金意图**` / `**为什么走强**` / `**逻辑够不够硬**`
4. **每票思维链**(≥4 段) — 首推票必附 `**买入理由**` / `**风险点**` / `**止损条件**` / `**可验证假设**`
5. **数据源审计表** — 三色 emoji · 日期无时分秒 · 群名匿名化 · 主源缺失即 degraded=true

**验收硬门槛**: md 落盘后逐条自检契约第六节六项,任一缺失即 skill 状态 `partial`,视为执行失败须重跑。

## Version History (writing contract)

- v1.2 (2026-07-07): 新增**模式七 · 基本面红旗** + 附录 A(12 财务红旗 + 10 估值陷阱 + ST 双轴 checklist)。F12(审计师非标意见)与 ST 合规轴/临近轴列为 hard_reject。
- v1.3 (2026-10-19): 删除红线3凑数保护;龙一被否后允许空仓、禁止杂毛替补
- v1 (2026-07-06): 加入沧海写作契约 · 覆盖 R1-R7 + D1
