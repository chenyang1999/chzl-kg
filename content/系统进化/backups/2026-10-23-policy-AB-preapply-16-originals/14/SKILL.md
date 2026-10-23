---
name: analyze_style_v1
description: R1 风格 Agent — 判断今日市场风格(5选1)、情绪浓度、主线数量、仓位上限；不出板块/个股
agent_owner: R1
version: v1
status: draft
category: research/R1
created: 2026-07-03
updated: 2026-07-05
spec: docs/agents/R1-风格Agent.md
---

# analyze_style_v1 · R1 风格 Agent

**跑动时点**: 07:30（与 R3、R4、R7 并行）  
**权威规格**: `docs/agents/R1-风格Agent.md`  
**产出路径**: `data/research/YYYYMMDD/R1_style.json`

---

## 唯一职责

判断**今日市场是什么风格、能不能做、做什么方向**。只输出 200–400 字量级的一句话结论 + 明确的「今日能否交易 / 仓位上限」判断。

**禁止**: 推板块、推个股、技术分析、估值、买卖点。

---

## 输入（pull-based，先读本地再按需 MCP）

### 必需 · 本地 `data/raw/YYYYMMDD/`

| 文件 | 用途 |
|------|------|
| `manifest.json` | 全局 severity、各源存活状态 |
| `wechat_official_20.jsonl` | 20 号公众号昨夜观点 |
| `wechat_cli_5groups.jsonl` | 5 群消息；**优先**筛 `颜晓滨震荡慢牛市投研群V` 的 KOL 方向句 |
| `mcp_health.json` | Tushare / XTick 是否可用 |

### 按需 · MCP / `_shared/`（主源 Tushare，备源 XTick / hithink）

| 源 | 接口 / skill | 用途 |
|-----|------|------|
| Tushare MCP | `limit_list_d` / `limit_step` | 涨停/跌停家数、连板天梯 |
| Tushare MCP | `index_daily` | 上证/创业板涨跌幅 |
| `@hithink-market-query` | `skills/_shared/hithink-market-query` | 指数/涨跌停快照补查（勿重写查询逻辑） |
| `@hithink-zhishu-query` | `skills/_shared/hithink-zhishu-query` | 知数/指数结构备用 |
| XTick MCP | `/doc/hot/emotion` | Tushare 死时的涨停/连板/炸板率补充 |

### vibe-trading MCP 补充（2026-08-06 新增 · 替代慢速 hithink/hithink-zhishu）

**目的**：涨停家数/炸板率/连板天梯等客观量化数据，用 vibe-trading MCP 替代 hithink CLI 调用，速度更快。

| 工具 | 调用方式 | 典型问句 | 返回字段 |
|------|---------|---------|---------|
| `vibe_trading__iwencai_search` | NL 问句 | `今日全市场涨停家数、炸板率、连板高度板数量` | 表格(股票代码/名称/连板天数) |
| `vibe_trading__iwencai_search` | NL 问句 | `近10日风格切换频率：TMT/消费/周期/金融 各涨停家数` | 各风格涨停家数统计 |
| `vibe_trading__iwencai_search` | NL 问句 | `全市场昨日涨停今日溢价率中位数` | 溢价率% |

**调用时序**：Step 1（客观量化）先行使 vibe-trading，Step 2（舆情）hithink 仅作交叉验证。  
**降级**：若 `vibe_trading__iwencai_search` 返回 error，降级到 `@hithink-market-query` + `@hithink-zhishu-query`（旧路径，速度慢）。

### 可选

- `weflow_snapshot.json`（仅作 KOL 情绪交叉，**不得**据此推板块名）
- 若 `data/raw/YYYYMMDD/hotlist_signals.json` 已存在，可读 `distribution_alert` 作退潮风险提示（不作正向信号）

---

## 执行步骤（按序完成）

### Step 0 · 解析交易日

从 orchestrator 传入的 `trade_date`（`YYYYMMDD`）读取 `manifest.json`。若 `global_severity >= 3`，进入降级模式并在产出中标注。

### Step 1 · 客观量化（Tushare 优先）

拉取**上一交易日**（或 manifest 指定的 resolved trade date）：

1. **涨停家数 / 跌停家数 / 炸板率**（`limit_list_d`）
2. **连板天梯**（`limit_step`）：最高连板高度、各高度家数
3. **大盘**（`index_daily`）：上证、创业板指涨跌幅
4. **跨资产 + 宏观**（v1.1 · 2026-08-06 新增 · `@全球宏观分析框架`）：黄金/铜/原油/汇率月度动量，建立"软着陆/降息预期/衰退"3 档宏观环境坐标。R1 红线 1/2 仍优先——只读跨资产**作为情绪前置**，不据此推板块/个股

记录原始数字到 `evidence[]`，不得编造。

### Step 2 · KOL 文本（本地）

从 `wechat_cli_5groups.jsonl` 提取颜晓滨群**昨夜**含「情绪/主线/仓位/连板/资金」等关键词的长文本（过滤 `[图片]`、`[链接/文件]`、用户自发言）。  
从 `wechat_official_20.jsonl` 补充宏观/情绪表述。  
**只摘要观点倾向，不得提取或输出具体板块名、个股名**（对齐 spec §7 红线）。

### Step 2.5 · 情绪周期阶段定位（v1.1 · 2026-09-04 新增 · `@emotion_cycle_v1`）

**在五维判定之前**，先回答「今天处于情绪周期哪一段」——这是风格判定的背景框架，也是 D1 决定"该做什么"的依据。

1. 调 `@emotion_cycle_v1`（`skills/emotion_cycle_v1/SKILL.md` + `src/research/emotion_cycle.py`）：
   - 计算或读取 `premium`（昨日涨停溢价）、`ladder`（连板高度）、`break_rate`（炸板率）、`limit_up_count`
   - 若 `data/research/YYYYMMDD/emotion_cycle.json` 已存在（由 `compute_cycle_metrics.py` 预计算），直接消费
2. 把阶段写入 R1 产出新字段：
   - `emotion_cycle_phase`: `low_test` / `main_up` / `high_chop` / `main_down`
   - `emotion_cycle_action`: 该阶段该做什么（主升猛干龙头 / 震荡控仓做补涨 / 主跌空仓）
3. **联动规则**（与 3.1 风格分类互相校验）：
   - 风格=崩溃退潮型 且 阶段=主跌 → 双确认，仓位下限压到最低
   - 风格=连板情绪型 但 阶段=高位震荡（炸板率>25% 未反映在风格表里）→ **以情绪周期阶段为准**，下调仓位上限（风格表只看涨停/高度，会漏掉炸板率>40%的分歧）

**关键**: 风格分类（3.1）用的是"涨停家数+高度+炸板率"阈值，但它的炸板率阈值（<20% / >50%）与情绪周期的炸板率判据（≥25% 分歧 / ≥40% 退潮）**不一致**。当两者冲突时，**情绪周期阶段优先**——因为它才是"该做什么"的依据，风格只是描述。

### Step 3 · 五维判定

#### 3.1 风格分类（**5 选 1，禁止「混合型」**）

| 风格 | 关键特征（满足主条件即归入） |
|------|------------------------------|
| **连板情绪型** | 连板高度≥6 + 涨停≥50 + 炸板率<20% |
| **主线扩散型** | 涨停 30–50 + 连板高度 3–5 + 有明确梯队 |
| **震荡分化型** | 涨停 20–40 分散 + 无明显连板龙头 |
| **防御观望型** | 涨停<20 + 大盘缩量走平 |
| **崩溃退潮型** | 跌停多 + 炸板率>50% + 大盘明显下跌 |

写入 `style` + `style_classification_note`（说明命中哪几条判据）。

#### 3.2 情绪浓度 `sentiment_score`（0–100）

综合：涨停家数、连板高度、炸板率、指数涨跌。  
必须在 `evidence` 或单独字段给出计算依据，不得拍脑袋。

**v1.1 · 2026-08-06 新增 · `@市场情绪分析` 5 维度加权法**（作为 reference 校验用）：

```
score ≈ 0.25 × 涨停强度 + 0.20 × 跌停压制 + 0.20 × 连板结构
      + 0.15 × (100 - 4×炸板率) + 0.20 × 杠杆外资中位
```

| 分值区间 | 情绪判定 | position_cap_suggestion 联动 |
|----------|---------|---------------------------|
| 0-20 | 极恐 | 0.50-0.60（逆向买入窗口） |
| 20-40 | 恐惧 | 0.55-0.65 |
| 40-60 | 中性 | 0.60-0.70 |
| 60-80 | 贪婪 | 0.65-0.75 |
| **80-100** | **极贪** | **0.50-0.60（逆向卖出窗口 · 2026-08-05 实测分 85.2）** |

**注意**: `sentiment_score` 字段本身仍由 R1 内部综合 4 维度计算（涨停/连板/炸板/指数），不直接照搬 5 维度加权法；5 维度法作为**反向校验**——若两者差 > 15 分，在 `sentiment_score_basis` 字段说明。

#### 3.3 主线数量 `main_lines_count` + `main_lines_label`

枚举：`独主线(1)` / `双主线` / `三主线以上` / `无主线`。  
R1 **不能**等 R2；可用 `limit_cpt_list` 中 `up_nums>=8` 的板块数作**近似代理**，在 `main_lines_note` 中注明「非 R2 真实判定」。

#### 3.4 仓位上限 `position_cap_suggestion`（0–0.80）

结合风格 + 情绪浓度，给出今日**总仓上限**小数（如 `0.70` = 70%）。

#### 3.5 一句话结论 `conclusion`

模板示例（**不得含具体板块/个股名**）：

> 今日 **连板情绪型** + 情绪浓度 **75** + **双主线**，建议仓位上限 **60–70%**，只做各主线龙一/龙二。

### Step 4 · 风险与降级

- `risks[]`：盘中分歧转弱、尾盘炸板率上升等触发降档条件
- Tushare 死 → XTick emotion；公众号死 → 仅 wechat-cli；全死 → 仅指数 + `fetch_global_severity` 标注

### Step 5 · 自评置信度

`confidence` 0.5–1.0（正常）；单源降级 0.3–0.5；严重降级 <0.3。写入 `confidence_rationale`。

---

## 产出 JSON 契约

写入 **`data/research/YYYYMMDD/R1_style.json`**（UTF-8，合法 JSON）：

```json
{
  "schema_version": "research_unit_v1",
  "agent": "R1",
  "trade_date": "20260704",
  "generated_at": "2026-07-04T07:35:00+08:00",
  "status": "complete",
  "confidence": 0.75,
  "fetch_global_severity": 0,
  "inputs": {
    "fetch_manifest": "data/raw/20260704/manifest.json",
    "wechat_official_20": "data/raw/20260704/wechat_official_20.jsonl",
    "wechat_cli_5groups": "data/raw/20260704/wechat_cli_5groups.jsonl"
  },
  "style": "连板情绪型",
  "sentiment_score": 75,
  "main_lines_count": 2,
  "main_lines_label": "双主线",
  "main_lines_note": "limit_cpt_list 近似，非 R2 判定",
  "position_cap_suggestion": 0.70,
  "conclusion": "今日 连板情绪型 + 情绪浓度 75 + 双主线，建议仓位上限 60-70%。",
  "style_classification_note": "满足:连板高度≥6 + 涨停≥50 + 炸板率<20%",
  "evidence": ["连板天梯:...", "涨停家数:...", "大盘:..."],
  "risks": ["若盘中分歧转弱，迅速降级到震荡分化型"],
  "data_sources_used": ["tushare.limit_list_d", "tushare.limit_step", "tushare.index_daily"],
  "resolved_trade_date": "20260703",
  "method": "llm_v1",
  "confidence_rationale": "..."
}
```

`status` 枚举：`complete` / `degraded` / `failed`。降级仍须产出五维字段，不得留空。

---

## 红线（违反即无效产出）

1. ❌ 输出中**不得出现**具体板块名称、个股代码/名称  
2. ❌ 不做 K 线形态、支撑阻力、技术指标  
3. ❌ 不做 PE/PB/估值  
4. ❌ 不给买卖点  
5. ✅ `style` 必须落在 5 个枚举之一  

---

## 消费者

| 下游 | 字段 |
|------|------|
| R2 | `style`, `main_lines_count`, `position_cap_suggestion` |
| R3 | `sentiment_score`（基准，若 R3 与 R1 并行则 R3 可读磁盘已落盘版或自算基准） |
| R6 | 与 R2 一致性反证 |
| D1 | `position_cap_suggestion` → exec_pool 总仓上限 |

---

## chzl_kg 人读 md 落盘（必需 · @render_kg_md_v1）

**契约来源**: `skills/_shared/render_kg_md_v1/SKILL.md`

除机读 JSON 落盘之外，本 skill 必须**同时**渲染一份人读 md 到 chzl_kg 供用户当日审阅。

### 落盘路径

```
chzl_kg/投研交易/风格研判/{trade_date}.md
```

（目录若不存在，`mkdir -p` 创建。）

### frontmatter（必填，UTF-8 · Unix 换行）

```yaml
---
date: {trade_date YYYY-MM-DD}
agent: R1-style-analysis
skill_version: analyze_style_v1@1.0
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
# {trade_date 中文日期} · **风格研判**

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
- skill: analyze_style_v1
- artifact: data/.../{...}.json
- 生成耗时: N 秒
- model: {model 名}
```

### 落盘规则

1. **atomic write**: 先写 `.tmp` → `mv` 到目标（避免 Obsidian 抓半写）
2. **overwrite**: 同日重跑覆盖；若目标已存在先备份为 `.md.bak`
3. **失败不阻塞**: md 渲染失败**不**回滚 JSON artifact 落盘；skill status 写 `partial` 并在汇报中标注

### 验收

盘后 `test -f chzl_kg/投研交易/风格研判/{trade_date}.md` 必须为 true；前 30 行满足 frontmatter schema。

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

- v1 (2026-07-06): 加入沧海写作契约 · 覆盖 R1-R7 + D1
