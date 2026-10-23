---
name: analyze_main_sectors_v1
description: R2 主线板块 — 从全市场挑 1-3 条主线，每条 3-5 只候选龙头；5 维打分
agent_owner: R2
version: v1
status: draft
category: research/R2
created: 2026-07-04
updated: 2026-07-05
spec: docs/agents/R2-主线板块Agent.md
---

# analyze_main_sectors_v1 · R2 主线板块 Agent

**跑动时点**: 07:45（**R1 / R3 / R4 / R7 完成后**）  
**权威规格**: `docs/agents/R2-主线板块Agent.md`  
**产出路径**: `data/research/YYYYMMDD/R2_main_sectors.json`  
**后续步骤**: 本 skill 完成后由 **`filter_leader_v1`** 做龙头硬过滤（同文件原地更新）

---

## 唯一职责

从全市场板块中挑选今日 **1–3 条主线**，每条给出 **3–5 只候选龙头**（龙一/龙二/候补）。  
**禁止**: 风格判断(R1)、买卖点(D1)、个股深度画像(R5)、技术形态。

## 因子面板选票器(v1.2 · 2026-07-07 新增 · 参考 vibe-trading `factor-research`)

**问题背景**: R2 当前用"tushare 板块涨跌 + R3 共振 + R4 催化 + R7 资金"四维定性排序,板块内个股排序缺乏**量化因子层**验证,易受当日噪音干扰。

**周日夜跑离线任务**: `scripts/factor/weekly_ir_scan.py --lookback 60 --top 5`
- 输入: A 股全池 · tushare `stock_factor`(动量/成交量/换手/波动 30+ 因子)
- 调用: `mcp_vibe_trading_factor_analysis(factor_csv, return_csv, output_dir, n_groups=5)`
- 输出: `data/factor_snapshot/YYYY-MM-DD/top_ir_factors.json`,含过去 60 日 **IR>0.5 且 IC>0.03** 的 top 5 因子及其符号

**R2 消费方式**: Step 3 板块内个股排序时,读取本周 `top_ir_factors.json`,对候选池按 top-5 因子的加权(IC 加权)计算 `factor_composite_score`,与原定性打分**并列**作为龙一/龙二裁决依据;两者冲突时以定性为主,但**必须在 notes 里显式标注 factor_score 排位**(供 R6 反证消费)。

**降级**: `top_ir_factors.json` 缺失或过期 >7 日 → R2 跳过因子层 · notes 记 `factor_layer_degraded=true`。

---

## 横切 skill（`@` 引用，禁止重写查询逻辑）

| Skill | 路径 | 用途 |
|-------|------|------|
| `@hithink-sector-selector` | `skills/_shared/hithink-sector-selector/` | 多条件板块筛选（热度/资金/涨幅组合） |
| `@hithink-industry-query` | `skills/_shared/hithink-industry-query/` | 行业结构、板块成分概览 |
| `@hithink-market-query` | `skills/_shared/hithink-market-query/` | 板块/个股行情快照、主力资金 |
| `@iwencai-query` | `skills/_shared/iwencai-query/` | NL 验证「某概念涨停家数/连板高度 top」 |

调用方式：读取对应 `SKILL.md` 并按其 CLI/API 执行；**不得**在本 prompt 内复述 hithink/iwencai 的实现细节。

---

## 输入

### 上游 research artifact（必需，先 `read_file`）

| 路径 | 字段 |
|------|------|
| `data/research/YYYYMMDD/R1_style.json` | `style`, `main_lines_count`, `position_cap_suggestion` |
| `data/research/YYYYMMDD/R3_sentiment.json` | `resonance_top_themes`, `hotlist_signals` |
| `data/research/YYYYMMDD/R4_news.json` | `sectors_catalyzed`, `top_events` |
| `data/research/YYYYMMDD/R7_capital_flow.json` | `main_force.top_inflow_sectors`（若 07:30 批次已产出） |

若某上游 `status != complete`，按 spec §6 降级并在 `notes` 标注；R7 缺失时资金维用 T-1 或 Tushare 直拉。

### 本地 raw（`data/raw/YYYYMMDD/`）

| 文件 | 用途 |
|------|------|
| `manifest.json` | severity |
| `wechat_official_20.jsonl` / `wechat_cli_5groups.jsonl` | 叙事维度补充 |
| `weflow_snapshot.json` | 可选，共振维度 |
| `hotlist_signals.json` | 若存在则读；否则自行用 Tushare `ths_hot`/`dc_hot` + 昨日 diff 计算 |

### 用户 context（只读）

- `data/user_preferences.yaml` → `sector_blacklist`, `sector_whitelist_priority`
- `data/human_thesis/active/*.md` → 长期主线笔记；得分 40–70 可进 `secondary_lines` 并标注「长期主线继承」
- `chzl_kg/主线/*.md`（若存在）

### MCP（按需，Tushare 为主）

`ths_hot`, `dc_hot`, `ths_member`, `dc_concept_cons`, `moneyflow_ind_ths`, `moneyflow_ind_dc`, `kpl_concept`, `limit_cpt_list`, `limit_list_d`, `limit_step`, `top_list`

### vibe-trading MCP 补充（2026-08-06 新增 · 核心增强）

**目的**：R2 板块内个股排序缺乏量化因子层，vibe-trading 提供快速问财 + 资金流 + 研报验证。

| 工具 | 调用方式 | 典型问句 | 返回字段 |
|------|---------|---------|---------|
| `vibe_trading__iwencai_search` | NL 问句 | `{板块名称}概念成分股，按市值倒序，取前20只` | 成分股列表 |
| `vibe_trading__iwencai_search` | NL 问句 | `{板块名称}近30日涨幅前10，验证资金共识` | 涨幅排行 |
| `vibe_trading__iwencai_search` | NL 问句 | `{概念} AND 市值>50亿 AND 股东户数连续2季减少` | 筹码集中度 |
| `vibe_trading__get_fund_flow` | ts_code | R2 候选池每只票，查主力净流入占比 | 主力净流入/占比 |
| `vibe_trading__get_research_reports` | ts_code | R2 候选池每只票，查近30日研报 | 研报标题/评级/目标价 |
| `vibe_trading__factor_analysis` | ts_code | 对候选池 top 10 做动量/换手率因子排名 | 因子综合分 |

**调用时序**：Step 2（候选板块初筛）→ `iwencai_search` 查成分股 → Step 3（个股排序）→ `factor_analysis` 综合打分。  
**节流**：候选板块 ≤ 5 个，每板块 iwencai 调用 ≤ 2 次，全 skill ≤ 10 次。  
**降级**：`vibe_trading__iwencai_search` 失败 → `@iwencai-query` CLI 替代。

---

## 执行步骤

### Step 1 · 读上游 + 定主线数量上限

- 读 R1：`main_lines_count` 与 `style` 约束今日主线条数（防御/退潮风格 → 倾向 0–1 条或只做最强一条）
- 读 R3：`resonance_top_themes` 中 `L1+L2+L3` / `L1+L2` 主题优先
- 读 R4：`sectors_catalyzed` 中 `strength=high` 板块加权
- 读 R7：资金净流入前十板块

### Step 2 · 构建候选板块池

1. `@hithink-sector-selector`：按「概念涨幅前 N + 主力净流入 + 涨停家数」筛一批候选  
2. Tushare `limit_cpt_list`：按涨停家数/连板统计取 top 20  
3. 合并去重；剔除 `sector_blacklist`；`sector_whitelist_priority` 得分 ×1.2

### Step 3 · 五维打分（每维 0–20，总分 100）

| 维度 | 数据源 |
|------|--------|
| **热度** | `ths_hot` + `dc_hot` 排名 |
| **资金** | `moneyflow_ind_dc` + R7；死则 DataPro 或 T-1 |
| **涨停** | `limit_cpt_list` + `kpl_concept` |
| **叙事** | R4 `sectors_catalyzed` + 公众号/wechat-cli 催化 |
| **共振** | R3 主题共振等级 + 热榜 `rank_momentum_up`；**霸榜第一不得加分**（见 R3 透传的 `distribution_alert`） |

- **主线核心**: score ≥ **70** → 进 top 1–3（硬上限 3 条）  
- **候选主线**: 50–70 → `secondary_lines`  
- **<50**: 丢弃

写入每条主线的 `score_dims` 与 `logic[]`（ bullet 依据）。

### 辨识度优先选股(v1.3 · 2026-10-19 用户钦定)

**原则(用户原话)**: 龙头风险 < 补涨杂毛——杂毛失去板块β无人接;题材一旦启动先做全市场"一听就知道"的票。
辨识度两层: ①跨平台热榜持续度(同花顺/开盘啦/东财) ②题材心智锚("一提福建板块就想到平潭发展"式的历史记忆)。

**必读数据**:
- `data/rules/theme_anchors/latest.json`(由 `scripts/research/build_theme_anchors.py` 每周/股性表更新后生成): 每题材锚定分 TOP8(妖性型/容量型标注)
- R3 `hotlist_signals`: 多平台在榜持续度;**高位赖榜+主力净卖出=霸榜出货,锚降级但不删除**

**Step 4 龙头候选排序改为**:
1. 题材被判定为主线后,该题材心智锚 TOP3 **默认入候选**(除非 ST/流通市值<20亿/霸榜出货hard_reject),不受当日截面资金排名影响
2. 辨识度裁决: 身位(连板板数/首封时序) > 热榜持续度 > 心智锚定分 > 当日资金流入
3. **龙一必须是当日板块内身位/封板时序/人气最强者**;补涨票(低位、未涨停、靠资金流入排名上位)只能标 `role: B计划补涨`,不得占执行池主位
4. 主跌→修复期: 聚焦**新题材首板/二板接力**(身位新、位置低),高位老龙不接;主升期才允许高度龙
5. 三通道(打板/半路/低吸)按当日赚钱效应选,不因情绪周期静态禁用某通道——通道选择写 `channel` 字段,主跌段是降低开仓数量/可整池为空,不是禁用龙头买点
6. **允许 execution_pool 为空**: 无合格龙一时输出空池+理由,禁止拿弹性核心/杂毛充数

**红线补充**: 禁止因"高位/一致"单独否决龙一后用低位票替补;龙头被否的合法出口只有空仓或等分歧(买点标注,不换票)。

---

## Step 4 · 龙头候选（每条 3–5 只）

筛选顺序（spec §3.3）：

1. 板块内今日/昨日涨停共振  
2. `@hithink-market-query` / Tushare moneyflow：主力资金流入 top5  
3. 近 5 日龙虎榜频次（`top_list`）  
4. 连板高度（`limit_step`）  
5. 流通市值 ≥ 50 亿；排除 ST/退市/风险警示  
6. `@iwencai-query` 可选验证：「{板块名} 涨停 连板高度 市值大于50亿」  

**板块前缀规则（2026-08-16 更新）**：300（创业板）/ 688（科创板）与主板**同权参与**龙一/龙二/中军竞争，**不得**因前缀自动降级为候补或加"需过滤"标注。仅 920（北交所）因流动性问题不进执行池推荐。20cm 票可按弹性角色（如"弹性龙二"）标注，但前缀本身不构成扣分项。

输出 `leaders[]`：`role` = 龙一/龙二/候补，`ts_code`, `name`, `pct_chg`, `limit_times`, `selection_basis`。

**本步产出的是候选池**；最终 execution 资格由 `filter_leader_v1` 裁定。

### Step 4.4 · 主线生命周期判定（2026-09-04 新增 · `@mainline_lifecycle_v1`）

**在选龙头之前**，先判定每条主线的生命周期阶段——因为「一条退潮期的主线，龙头再强也不该做」。

调 `@mainline_lifecycle_v1`（`src/research/mainline_lifecycle.py::locate_mainline_lifecycle`），对每条候选主线算：

| 指标 | 含义 | 数据源 |
|------|------|--------|
| `age_days` | 主线已运行交易日数（从首次涨停潮起） | `limit_cpt_list` 回看 N 日 |
| `leader_height` | 龙头连板高度 | `limit_step` |
| `money_persist_days` | 板块主力资金连续净流入天数 | `moneyflow_ind_dc` 近 N 日 |
| `break_rate` | 今日炸板率 | `limit_list_d` |

写入每条主线的 `stage` / `stage_name` / `stage_action` 字段（`formation`/`early_up`/`mid_up`/`climax`/`fade`）。

**联动规则（治"一日游"）**：
- `early_up`（主升早期）→ 最高优先级主线，龙头/龙二进 execution_pool
- `mid_up` → 可做，龙头分歧低吸或后排补涨，控仓
- `climax`（高潮分歧）→ **只做龙头或空仓等分歧**，禁追高缩量一字
- `fade`（退潮反抽）→ **降级次线**，不进主线主推；除非情绪周期=主升（超跌反弹博反抽）
- **禁止**：把已运行 ≥5 天 + 资金转出的主线当"新主线"推荐（这是"一日游陷阱"）

### Step 4.5 · 个股属性分类 + T+1 博弈推演（2026-09-04 用户方法论）

对每条主线的每个候选，除 role（龙一/龙二/候补）外，**必须**标注：

**1. 个股四分类**（`stock_type`）——不同属性对应不同操作节奏：
- `抱团型妖股`：高辨识度人气票，资金抱团，波动大，看情绪不看基本面
- `波段型趋势股`：沿均线/趋势上行，量能配合，可拿波段
- `连板妖股`：高度连板，T+1 博弈最激烈，隔日溢价/炸板风险双高
- `稳健防守股`：低波动、有资金防守逻辑的票（**不是**"死水高股息"）

**2. 板块攻守属性**（`sector_offensive`）：进攻（资金进攻主线）或 防守（防御避险/低位修复）——**不是静态标签**，随资金切换。农业/创新药等可从前防守转进攻。

**3. 龙头结构**（`leader_structure`）：谁是打高度的龙头（`height_leader`）、谁是容量的中军（`capacity_core`）——与流通市值相关；量能充沛时大盘股优先，量能萎缩时小盘股更受青睐。

**4. T+1 博弈推演**（`t1_game`）——A股 T+1 下每笔买入=押注次日有人接力，必须推演：
- **消息双面解读**：利好→高开低走（先手兑现）or 平开高走？利空→洗盘吸筹（低吸机会）or 真利空瀑布杀？
- **预期差/超预期**：赚钱效应来自预期差，不是消息本身
- **买点推演**（`buy_point_check`）：集合竞价/开盘是否已被先手资金兑现？有无好的进场节点（低吸/半路/打板）？追高是否接盘？
- **短线结构词汇**：用"卡位/弱转强/分离/联动/助攻/补涨"等描述资金博弈位置（详见 R2 横切短线方法论）

写入每个 leader 的 `stock_type`, `sector_offensive`, `leader_structure`, `t1_game` 字段。

---

### Step 5 · 风险 bullet

每条主线 `risks[]`：引用 R3 `distribution_alert`、R6 尚未跑时的待验证项等。

### Step 6 · 写盘 + 触发 filter_leader_v1

1. 写入 `R2_main_sectors.json`（见下 schema）  
2. **立即执行** `@filter_leader_v1` 对同一文件做龙头硬过滤

---

## 产出 JSON 契约

`data/research/YYYYMMDD/R2_main_sectors.json`：

```json
{
  "schema_version": "research_unit_v1",
  "agent": "R2",
  "trade_date": "20260704",
  "generated_at": "2026-07-04T07:50:00+08:00",
  "status": "complete",
  "confidence": 0.80,
  "fetch_global_severity": 0,
  "inputs": {
    "fetch_manifest": "data/raw/20260704/manifest.json",
    "upstream_artifacts": {
      "R1": "data/research/20260704/R1_style.json",
      "R3": "data/research/20260704/R3_sentiment.json",
      "R4": "data/research/20260704/R4_news.json",
      "R7": "data/research/20260704/R7_capital_flow.json"
    }
  },
  "main_lines_count": 2,
  "main_lines": [
    {
      "name": "机器人",
      "score": 82.0,
      "score_dims": {"热度": 18, "资金": 17, "涨停": 19, "叙事": 16, "共振": 12},
      "logic": ["R4: 特斯拉产线催化 high", "资金: 东财概念净流入第1"],
      "leaders": [
        {"role": "龙一", "ts_code": "002050.SZ", "name": "三花智控", "pct_chg": 10.0, "limit_times": 4, "selection_basis": "...", "stock_type": "波段型趋势股", "sector_offensive": "进攻", "leader_structure": {"height_leader": "002050.SZ", "capacity_core": "300750.SZ"}, "t1_game": {"消息解读": "...", "预期差判断": "...", "买点结论": "低吸", "短线结构标签": "卡位"}}
      ],
      "leaders_degraded": false,
      "leaders_degrade_reason": "",
      "risks": ["R3 distribution_alert 待 R6 验证"]
    }
  ],
  "secondary_lines": [{"name": "商业航天", "score": 62, "reason": "长期主线继承"}],
  "notes": "",
  "method": "llm_v1",
  "confidence_rationale": "..."
}
```

---

## 红线

1. ❌ 主线 **最多 3 条**  
2. ❌ 每条主线龙头 **最多 5 只**  
3. ❌ 不出买卖点、止损、仓位（D1 处理）  
4. ❌ 不做估值（R5 处理）  
5. ✅ 核心主线 score **必须 ≥70**  

---

## 降级路径（spec §6）

| 失效源 | 处理 |
|--------|------|
| moneyflow 死 | DataPro 或仅热度+涨停 |
| R3/R4 死 | 叙事/共振维留空或 0，在 `notes` 说明 |
| 全死 | `chzl_kg/主线/` 长期继承 + 涨停，`severity=3` |

---

## chzl_kg 人读 md 落盘（必需 · @render_kg_md_v1）

**契约来源**: `skills/_shared/render_kg_md_v1/SKILL.md`

除机读 JSON 落盘之外，本 skill 必须**同时**渲染一份人读 md 到 chzl_kg 供用户当日审阅。

### 落盘路径

```
chzl_kg/投研交易/主线研判/{trade_date}.md
```

（目录若不存在，`mkdir -p` 创建。）

### frontmatter（必填，UTF-8 · Unix 换行）

```yaml
---
date: {trade_date YYYY-MM-DD}
agent: R2-main-sectors
skill_version: analyze_main_sectors_v1@1.0
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
# {trade_date 中文日期} · **主线研判**

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
- skill: analyze_main_sectors_v1
- artifact: data/.../{...}.json
- 生成耗时: N 秒
- model: {model 名}
```

### 落盘规则

1. **atomic write**: 先写 `.tmp` → `mv` 到目标（避免 Obsidian 抓半写）
2. **overwrite**: 同日重跑覆盖；若目标已存在先备份为 `.md.bak`
3. **失败不阻塞**: md 渲染失败**不**回滚 JSON artifact 落盘；skill status 写 `partial` 并在汇报中标注

### 验收

盘后 `test -f chzl_kg/投研交易/主线研判/{trade_date}.md` 必须为 true；前 30 行满足 frontmatter schema。

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
- v1.2 (2026-08-07): R2/R3/R4/R7 cross_validation 交叉验证 + consensus_themes 共识主题

---

## v1.2 新增 · R2/R3/R4/R7 交叉验证（P0-3 修复）

**问题根因**: 2026-08-05/06 实盘跑中,R2 main_lines.leaders 输出后,无任何字段告诉 D1/R6 "这条主线 R3 共振了吗?R4 催化支持吗?R7 资金流入吗?"。R2 完全独立判断 → D1 在选 execution_pool 时**再次**人工交叉 R3/R4/R7,浪费时间且易遗漏。

**v1.2 交叉验证契约**(硬约束,新增到 §产出 JSON 契约 之前):

每条 main_line 必须新增字段:

```json
{
  "name": "机器人",
  "score": 82.0,
  "cross_validation": {
    "r3_resonance_match": true,        // R3.resonance_top_themes 包含"机器人"/L1-L3 主题
    "r4_catalyst_match": true,         // R4.sectors_catalyzed 包含"机器人"且 strength>=medium
    "r7_capital_match": false,         // R7.main_force.top_inflow_sectors 前 10 无"机器人"
    "cross_validation_score": 0.67,    // = sum(true) / 3,保留 2 位小数
    "r3_evidence": "L1+L2 共振,行业分析师群 3 个独立提及",
    "r4_evidence": "E20260805_002 特斯拉产线催化 high,首推三花智控",
    "r7_evidence": "主力净流入 0.5 亿,top_inflow 排名 #15(未进 top10)"
  },
  "consensus_themes": []               // 见下方说明
}
```

**consensus_themes 字段**(顶层):

```json
{
  "consensus_themes": [
    {
      "sector": "存储/HBM",
      "agreement_count": 4,            // 出现在 R2 ∩ R3 ∩ R4 ∩ R7
      "sources": ["R2_main_lines", "R3_resonance_top_themes", "R4_sectors_catalyzed", "R7_top_inflow_sectors"],
      "composite_score": 0.92           // = (r2_score + r3_resonance + r4_strength + r7_rank_score) / 4
    }
  ]
}
```

**计算逻辑**(R2 LLM 在 §Step 5 风险 bullet 之后,§Step 6 写盘前自动算):

```python
def cross_validate_main_line(line, r1, r3, r4, r7):
    cv = {
        "r3_resonance_match": any(
            line["name"] in t.get("sector", "") or t.get("theme", "") in line["name"]
            for t in r3.get("resonance_top_themes", [])
        ),
        "r4_catalyst_match": any(
            s["name"] == line["name"] and s.get("strength") in ("high", "medium")
            for s in r4.get("sectors_catalyzed", {}).values()
        ),
        "r7_capital_match": any(
            line["name"] in s.get("name", "") or s.get("name", "") in line["name"]
            for s in r7.get("main_force", {}).get("top_inflow_sectors", [])[:10]
        ),
    }
    cv["cross_validation_score"] = round(sum(cv.values()) / 3, 2)
    return cv

def compute_consensus_themes(r2_main_lines, r3, r4, r7):
    r3_themes = {t.get("sector", "") for t in r3.get("resonance_top_themes", [])}
    r4_sectors = {s.get("name", "") for s in r4.get("sectors_catalyzed", {}).values()}
    r7_sectors = {s.get("name", "") for s in r7.get("main_force", {}).get("top_inflow_sectors", [])[:10]}
    
    consensus = []
    for line in r2_main_lines:
        n = line["name"]
        in_r3 = n in r3_themes
        in_r4 = n in r4_sectors
        in_r7 = n in r7_sectors
        count = sum([in_r3, in_r4, in_r7]) + 1  # +1 for R2 itself
        if count >= 3:  # 至少 3 源共识
            consensus.append({
                "sector": n,
                "agreement_count": count,
                "sources": ["R2_main_lines"] + 
                           (["R3_resonance_top_themes"] if in_r3 else []) +
                           (["R4_sectors_catalyzed"] if in_r4 else []) +
                           (["R7_top_inflow_sectors"] if in_r7 else []),
                "composite_score": 0.0  # 留给 Step 7 计算
            })
    return consensus
```

**消费契约**(供 D1 / R6):
- D1 选 execution_pool 时,**`cross_validation_score >= 0.67` 的主线优先**;`< 0.34` 的主线必须降级到 watch_pool
- D1 写入 `meta.cross_validation_summary`,列出当日 consensus_themes 数量
- R6 反证时:`cross_validation_score` 已为 0 的主线,直接给 `strong_suggest` 警告"主线无跨源支撑"

**降级**:
- R3 缺失 → `r3_resonance_match=null` 视为不参与分母,`cross_validation_score = sum(non_null) / len(non_null)`
- R4/R7 缺失同上
- 任一上游缺失 → JSON 顶层加 `cross_validation_degraded=true` 字段,让 E1 复盘能识别

**验收**:
- 盘后 `tests/check_r2_cross_validation.py` 校验每条 main_line 含 `cross_validation` 字段、`consensus_themes` 字段存在、4 源交集阈值生效
- 缺任一字段 → orchestrator 标 R2 失败

---

## Version History

| 版本 | 日期 | 说明 |
|------|------|------|
| v1 | 2026-07-04 | 骨架建立 |
| v1.1 | 2026-08-06 | vibe-trading MCP 补充(候选板块扩池) |
| v1.2 | 2026-08-07 | P0-3 修复: cross_validation 字段(3 源验证) + consensus_themes(4 源交集) |
| v1.3 | 2026-10-19 | 辨识度优先: 题材心智锚+热榜持续度入主排序;龙一独占执行池;允许空仓;通道动态化 |
