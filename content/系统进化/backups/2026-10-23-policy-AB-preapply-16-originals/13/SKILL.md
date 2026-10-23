---
name: analyze_stock_profile_v1
description: R5 情报深挖 — 对 R2 龙头逐票六维画像；@ 估值/研报横切 skill
agent_owner: R5
version: v1
status: P1-T1prime
category: research/R5
created: 2026-07-04
updated: 2026-07-05
spec: docs/agents/R5-情报深挖Agent.md
---

# analyze_stock_profile_v1 · R5 情报深挖 Agent

**跑动时点**: 07:45（R2 完成 + filter_leader 后；与 orchestrator 串行批次）  
**权威规格**: `docs/agents/R5-情报深挖Agent.md`  
**产出路径**: `data/research/YYYYMMDD/R5_stock_profiles.json` · 可选 `chzl_kg/个股/{code}/YYYYMMDD_画像.md`

---

## 唯一职责

对 **R2 圈定的龙头候选**（通常 6–15 只）逐票输出 **六维画像**，供 D1 execution_pool 与 R6 反证消费。

**禁止**: entry/exit 价格、全市场扫描、风格(R1)、板块排序(R2)。

---

## 输入

| 路径 | 用途 |
|------|------|
| `data/research/YYYYMMDD/R2_main_sectors.json` | 候选票清单（`leader_filter_applied: true`） |
| `data/research/YYYYMMDD/R4_news.json` | 催化背景 |
| `data/research/YYYYMMDD/R7_capital_flow.json` | 个股/板块资金验证 |
| `data/raw/YYYYMMDD/manifest.json` | severity |

### MCP / `@` 横切 skill（引用，勿重写逻辑）

| Skill | 用途 |
|-------|------|
| `@report-search` | 研报检索 |
| `@announcement-search` | 公告核验 |
| `@hithink-insresearch-query` | 机构观点摘要 |
| `@hithink-management-query` | 治理/管理层 |
| `@hithink-business-query` | 业务结构 |
| `@hithink-market-query` | 行情/资金快照 |
| `@iwencai-query` | NL 条件复核 |
| `@serenity-alpha` | 事件 Alpha 框架 |
| `@bayesian-intrinsic-growth-valuation` / `@tam-adj-peg` / `@gf-dma-health-index` | 估值维度（择一或组合） |
| `@buy-side-equity-research-memo` | 重点票 deep-dive 结构 |
| `@缠论形态识别`（v1.3 · 2026-08-06 新增） | **技术形态维度的补充方法论**——chart_vision 看图识别，缠论看结构判定。两者必须**同向**才标 `chanlun_confirmed=true`；反向 → 标 `chanlun_divergence=true` 进 R6 观察池 |
| `@大宗商品分析`（v1.3 新增） | **板块联动维度的商品→板块映射**——若候选股所属板块与某商品强联动（黄金股/铜业/油服/锂电/化工），输出 `commodity_linkage: {gold: +0.05, copper: -0.02, ...}` 作为加分 |
| `@行为金融分析`（v1.3 新增） | **认知偏差高发区识别**——若候选股命中以下任一模式，输出 `cognitive_bias_warnings: [...]`：`8 板+ 高度龙头` / `创业板 20cm 1 板` / `业绩预增高位` / `反复触板未 ST` |

Tushare MCP（按需）: `anns_d`, `top_list`, `top_inst`, `hm_list`, `daily`, `daily_basic`, `report_rc`, `stk_surv`

### 大资金独立证据面（v1.3 · 2026-08-31 改：tushare 主源，vibe-trading 降为可选交叉核验）

**问题背景**:R5 六维中的"筹码结构"维度此前仅靠 tushare `top_list` + `margin_detail`,存在覆盖盲区(大宗交易营业部席位/两融日度趋势/龙虎榜溢价率)。v1.2 引入 vibe-trading 作独立 eastmoney 通道交叉核验。**但 vibe-trading MCP 未配置(不在 hermes_mcp.json),导致 R5 长期静默降级。v1.3 改为 tushare 为主源,不再依赖未配置的 MCP。**

| 数据 | 主源(tushare,必调) | 交叉核验(可选,vibe-trading 可用时) |
|------|-------------------|----------------------------------|
| 大宗交易 | `block_trade`(近30日) → `chip_structure.block_trades` | `mcp__vibe_trading__get_block_trades(days=30)` |
| 两融趋势 | `margin_detail`(近15日) → `chip_structure.margin_15d_trend` | `mcp__vibe_trading__get_margin_trading(days=15)` |
| 龙虎榜 | `top_list`(orchestrator 层全市场每日1次) → `chip_structure.dragon_tiger_hit` | `mcp__vibe_trading__get_dragon_tiger` |

**硬约束(v1.3 调整)**:
- 每票 `chip_structure.block_trades` + `margin_15d_trend` **不得为 null**——用 tushare `block_trade`/`margin_detail` 兜底,只有 tushare 也失败才允许 null 并置 `vibe_trading_degraded=true`(该票 `composite_score` 上限扣 10 分)
- 大宗折价率 `< -5%` 或最近 3 日出现 `avg_premium_pct <= -8%` → flags 追加 `distribution_alert`(分销减持信号)
- 融资余额 15 日下降 > 10% + 融券余额上升 > 20% → flags 追加 `short_pressure`(空头压制)
- **不再把 vibe-trading 当每票必调**;vibe-trading 仅在有配置时作为双源交叉核实

### 图表 & 多模态层（v1.1 · 2026-07-07 强化 · v1.4 · 2026-09-30 改为先读快照）

**问题背景**:此前 R5 的"技术形态"维度纯靠文字描述,没有真实图表输入 LLM,导致"下降通道内反弹/放量突破"等判断浮空。需要每只候选票有 30 日 K + 多模态识图的输入。

**v1.4 改动（2026-09-30）**:流水线在 **R2 落盘后、R5 启动前**已用 R2 龙头票池**并发预渲染**快照
（`scripts/fetch/run_chart_vision_snapshot.py`，6 路并发，13 票约 90s）。
R5 **优先读快照**，只有未命中的票才逐票调 MCP —— 避免 12 票 × 42s 串行 ≈ 500s（R5 工具耗时 64%）。

| MCP 工具 | 何时调用 | 产出字段 |
|---------|---------|---------|
| **（优先）读文件** `data/raw/{trade_date}/chart_vision_snapshot.json` | **Step T 第一步**：读快照，命中即用，**不再调 MCP** | `technical.chart_vision` = 快照该票的 `{trend, pattern, key_levels, volume_signal}` |
| `mcp_canghai_charts_chart_vision_analyze` | **仅当**该票不在快照内（`results` 无此 ts_code 或带 `error`）时逐票调用 | 同上 |
| `mcp_canghai_charts_chart_lwc_render_kline` | 需要产出 PNG 供 md 引用时(挑 Top3 首推票) | `technical.chart_png_path` |
| `mcp_canghai_charts_chart_fast_render_kline` | 快速四周期拼图(15m/60m/日/周),用于形态确认 | `technical.multi_period_chart_path` |

**硬约束**:
- 每只候选票 `technical.chart_vision.pattern` 字段**不得为空字符串** · 空 = 判定 fail
- 读快照时**必须校验 `snapshot["date"] == trade_date`** —— `data/cache/chart_vision_latest.json` 是跨日指针，直接用会把**前一日**快照当当日（这是旧机制的原始 bug）
- 快照命中时在 `technical.chart_vision.source = "snapshot"`，MCP 直调则记 `"mcp_live"`，便于复盘统计真实节省
- 若 MCP 全域 DOWN 且快照未命中 → `technical.chart_vision=null` + `chart_degraded=true`,该票 `strength` 顶格 `medium`
- 首推票(每主线 Top1)必须产出 `chart_png_path` 供 md 里以 `![](path)` 语法引用

**读快照示例**:

```python
import json
snap = json.load(open(f"data/raw/{trade_date}/chart_vision_snapshot.json", encoding="utf-8"))
assert snap["date"] == trade_date, "快照非当日，拒绝使用（跨日指针陷阱）"
hits = {k: v for k, v in snap["results"].items() if not v.get("error")}

for stock in candidates:
    hit = hits.get(stock.ts_code)
    if hit:                                    # 快照命中 → 不调 MCP
        stock.technical.chart_vision = {**hit, "source": "snapshot"}
    else:                                      # 未命中 → 才逐票调（慢，但保证覆盖）
        vision = mcp_canghai_charts_chart_vision_analyze(
            ts_code=stock.ts_code, name=stock.name, fq=2,   # 前复权
        )
        stock.technical.chart_vision = {**vision.result, "source": "mcp_live"}
```

**注意**:chart_vision 的综述本体是 **Python 预渲染产物**（并发出图 + 一次 vision LLM 调用），
不是 R5 的量价判断 —— R5 对形态的**最终裁决**仍须由 LLM 结合快照 + kline + 板块自行做出，
禁止把快照字段直接抄成结论。

---

## 六维画像（每只候选）

1. **催化背景** — 来自 R4 + 群消息交叉  
2. **筹码结构** — 股东户数、龙虎榜 30 日、主力 5 日 + 大宗/两融(v1.2 硬约束)  
3. **板块联动** — 继承 R2 得分 + ETF/期货联动  
4. **财务与估值** — `@` 估值 skill 或 MCP 分位 · **v1.2 新增双层结构 + fundamental_flags 透传**  
5. **技术形态** — K 线结构;canghai-sise / charts MCP 每票必调  
6. **研报与机构** — `@report-search` / `@hithink-insresearch-query`

## 财务与估值维度契约(v1.2 · 2026-07-07 · 供 R6 模式七消费)

### 双层估值决策树(参考 vibe-trading `valuation-model`)

**决策树**(按行业选估值方法,不再"一律 PE 分位"):

| 行业类型 | 首选估值 | 备选 | 命中即降 severity |
|---------|---------|------|-------------------|
| 稳定现金流(消费/公用) | DCF | PE + DDM | V9 分红陷阱 |
| 高成长(半导体/AI/新能源) | PEG + PS | 相对估值 | V2 高 PEG + V6 一次性收益 |
| 周期(资源/化工/钢铁) | PB × ROE 四象限 | 席勒 PE | **V1 低 PE 陷阱** |
| 金融(银行/券商/保险) | PB × ROE | DDM | V3 商誉炸弹 |
| 集团/多元(SOTP) | 分部加总 | PB | V10 SOTP 加总陷阱 |
| ST/仙股 | N/A | — | **V7 港股仙股 / ST 三轴 hard_reject** |

`@` 三个自研估值 skill 作为**实现层**: `@bayesian-intrinsic-growth-valuation`(DCF/成长) · `@tam-adj-peg`(高成长) · `@gf-dma-health-index`(健康度综合)。R5 按行业选一到两个跑,不再一律全跑。

### fundamental_flags[] 透传契约(供 R6 模式七)

每票 `dimensions.valuation_safety.fundamental_flags[]` 必须列出命中的红旗编号(F1-F12 财报 · V1-V10 估值 · S1-S3 ST 三轴,对应 R6 附录 A checklist),格式:

```json
"fundamental_flags": [
  {"code": "F2", "detail": "商誉/净资产=42%", "source": "vibe-trading get_financial_statements", "severity": "strong"},
  {"code": "V1", "detail": "PE=7 但净利率处于 10 年 top 15% (周期顶)", "source": "R5 valuation_layer", "severity": "strong"},
  {"code": "F11", "detail": "控股股东质押率 76%", "source": "tushare pledge_stat", "severity": "strong"}
]
```

**硬约束**:
- 无红旗时字段为 `[]`(空数组),**不得省略**
- 命中 F12(审计非标) 或 S2/S3(ST 合规/临近) → R5 自身 `valuation_safety.score` 顶格扣至 30 以下,并在 notes 写 `to_be_hard_rejected_by_R6=true`
- R5 未透传此字段 → R6 模式七 `degraded` · orchestrator 记 warning

### 检出实现建议

1. F1-F12: 调 `mcp__vibe_trading__load_skill("financial-statement")` 拿 checklist,配合 `mcp__vibe_trading__get_financial_statements(period="quarter")` 拉数
2. V1-V10: 按上表决策树,只跑对应行业相关的 2-3 条陷阱检出
3. S1-S3: 优先读 tushare `stk_holdertrade`(质押) + `daily_basic`(市值) + `fina_indicator`(连亏),快速裁决

---

## 输出 JSON

`data/research/YYYYMMDD/R5_stock_profiles.json`:

```json
{
  "schema_version": "research_unit_v1",
  "agent": "R5",
  "trade_date": "YYYYMMDD",
  "generated_at": "ISO8601",
  "status": "complete",
  "profiles": [
    {
      "ts_code": "",
      "name": "",
      "sector": "",
      "one_liner": "",
      "dimensions": {
        "catalyst": {"score": 0, "summary": ""},
        "chip_structure": {"score": 0, "summary": ""},
        "sector_linkage": {"score": 0, "summary": ""},
        "valuation_safety": {"score": 0, "summary": "", "total_mv_yi": 0, "circ_mv_yi": 0},
        "technical_readiness": {"score": 0, "summary": "", "pullback_to_decision_line": false, "pullback_note": null, "ma50": null, "niu_xian": null, "xiong_xian": null},
        "institutional_interest": {"score": 0, "summary": ""}
      },
      "composite_score": 0,
      "alpha_grade": "B+",
      "risk_grade": "B",
      "flags": ["distribution_alert"],
      "data_sources_used": ["R4", "hithink-market-query"]
    }
  ]
}
```

---

## 档位字段 `alpha_grade` / `risk_grade`（必填 · 2026-09-30 硬约束）

D1 的风险闸门按 `position_cap` 分支消费这两个字段，且契约规定
**档位缺失时按 B 降级**（`main_decision_v1` §Step 3.5.5）。

事故背景：R5 长期只产出 `alpha_grade`、**从不产出 `risk_grade`**
（实测 30 个交易日 × 全部产出 = 0/330 有该字段），而 D1 一度把缺失档位
映射为 rank 0（比 C 还差），使 `position_cap ≥ 0.7` 时
`alpha≥B+ AND risk≥B-` 恒假 → **该类日期执行池被整体清空**。

规则：
- **两档均为每票必填**，不得省略、不得为 null。
- `alpha_grade`（进攻性，档位 A+ / A / A- / B+ / B / B- / C）：确定性、主线地位、
  资金持续性、催化硬度、龙头身位。
- `risk_grade`（风险度，档位 A / B+ / B / B- / C，**A 最安全**）：高位程度、
  是否霸榜出货、套牢盘、估值分位、筹码分散度、龙虎榜净卖。
- `flags` 含 `distribution_alert`（霸榜出货）→ `risk_grade` 不得优于 `B-`。
- 与 `R6` 分工：R6 是否决器（`hard_reject`），R5 是分档器，二者不可互相替代。

---

## 降级

- R2 无候选 → `status: skipped`, `profiles: []`  
- 单票 MCP 失败 → 该票 `partial: true`, 不阻塞其余票
- 档位确实无法判定 → 显式写 `"B"` 并在 `flags` 标注 `grade_defaulted`，
  **不得留空**（留空会触发 D1 侧降级路径，掩盖真实风险）

---

## chzl_kg 人读 md 落盘（必需 · @render_kg_md_v1）

**契约来源**: `skills/_shared/render_kg_md_v1/SKILL.md`

除机读 JSON 落盘之外，本 skill 必须**同时**渲染一份人读 md 到 chzl_kg 供用户当日审阅。

### 落盘路径

```
chzl_kg/投研交易/个股画像/{trade_date}.md
```

（目录若不存在，`mkdir -p` 创建。）

### frontmatter（必填，UTF-8 · Unix 换行）

```yaml
---
date: {trade_date YYYY-MM-DD}
agent: R5-stock-profiles
skill_version: analyze_stock_profile_v1@1.0
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
# {trade_date 中文日期} · **个股画像**

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
- skill: analyze_stock_profile_v1
- artifact: data/.../{...}.json
- 生成耗时: N 秒
- model: {model 名}
```

### 落盘规则

1. **atomic write**: 先写 `.tmp` → `mv` 到目标（避免 Obsidian 抓半写）
2. **overwrite**: 同日重跑覆盖；若目标已存在先备份为 `.md.bak`
3. **失败不阻塞**: md 渲染失败**不**回滚 JSON artifact 落盘；skill status 写 `partial` 并在汇报中标注

### 验收

盘后 `test -f chzl_kg/投研交易/个股画像/{trade_date}.md` 必须为 true；前 30 行满足 frontmatter schema。

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
- v1.4 (2026-08-07): R5 候选与 R2 主线脱钩修复 — 增加候选池扩池规则

---

## v1.4 新增 · R5 候选与 R2 主线脱钩修复（P0-1 修复）

**问题根因**: 2026-08-05 实盘跑中,R2 的 `main_lines.leaders[]` 仅输出 1 个候选(普冉股份),但 R2 自身 `all_scored_boards_top10` 还有 9 个 score >= 50 的板块未利用。R5 直接消费 R2 `leaders[]` → 当日候选池仅 1 只,无法支撑 D1 `execution_pool ≤ 5` 硬约束,导致 D1 反复走降级路径。

**v1.4 扩池规则**(硬约束,新增到 §输入 与 §六维画像之间):

```
# R5 启动时,先做"主候选池扩池"
candidates = r2_main_sectors.main_lines.leaders  # 原始 1-3 个 leaders

if len(candidates) < 3:
    # 从 R2.all_scored_boards_top10 中扩池(score >= 50)
    supplement = [
        {"ts_code": b["top_stock"]["ts_code"], "name": b["top_stock"]["name"],
         "source_sector": b["name"], "r2_score": b["score"]}
        for b in r2_main_sectors.all_scored_boards_top10
        if b["score"] >= 50
    ]
    # 按 r2_score 降序,去重
    seen = {c["ts_code"] for c in candidates}
    supplement = [s for s in supplement if s["ts_code"] not in seen]
    supplement.sort(key=lambda x: x["r2_score"], reverse=True)
    need = 5 - len(candidates)  # 至少保证 candidates >= 5
    candidates.extend(supplement[:need])

# 终态:candidates >= 5(若仍不够,记录 r2_expand_shortfall 到 JSON,告警)
assert len(candidates) >= 5, f"R5 candidate pool short: {len(candidates)} < 5"
```

**消费契约**:
- 扩池来源的票必须在 R5 JSON `stock_profiles[].provenance.source` 字段标 `"r2_expand_pool"`,区别于 `"r2_leader_pool"`
- 扩池票的 `composite_score` 起步分 -3(因为无 R2 leaders 强信号),但仍跑完整六维画像
- D1 消费时:`source == "r2_expand_pool"` 的票优先入 `watch_pool`,而非 `execution_pool`;除非 R5 给 `alpha_grade=A` 且 R6 无 `hard_reject`

**降级**:
- `R2_main_sectors.json` 缺失 `all_scored_boards_top10` 字段 → 视为 R2 schema 降级,本次跳过扩池,记录 `r2_schema_missing_top10=true` 到 R5 JSON 顶层,供 E1 复盘统计

**验收**:
- 盘后脚本 `tests/check_r5_candidate_pool.py` 必须通过(本 skill 在 §Rules 增加红线 11: R5 候选池 < 5 → `status: partial`)

---

## v1.5 新增 · 龙头判定维度（2026-08-20 · 用户方法论）

**背景**: 评价一只票不能只看个股 K 线 + 消息面，还要看**板块效应**。判龙头看两个维度：**高度**（连板数）+ **上榜时间**（封板早/首次上榜早）。上榜早=有带动性=龙头；上榜晚=跟风补涨。

**数据源**: tushare `limit_list_d`（打板/涨停专题，**含 first_time/last_time/open_times/limit_times**）+ `top_list` 历史（算首次上榜距今）。

### 每票必算 `leader_verdict`（六维中"板块联动"维度必填子块）

```python
ld = tushareMcp.limit_list_d(ts_code=stock.ts_code, trade_date=trade_date,
                             fields=["ts_code","name","first_time","last_time","open_times","limit_times","limit"])
first_seen = first_board_day(stock.ts_code, lookback=10)  # 板块这轮启动后第几天上榜
leader_verdict = {
  "height": ld.limit_times,          # 连板高度
  "first_board_time": ld.first_time, # 今日首次封板时间 (HH:MM, 越早越强)
  "open_times": ld.open_times,       # 开板次数 (越少越强/一致)
  "days_since_first_board": first_seen,  # 1=启动日=龙头
  "sector_breadth": r2_sector_zt_count,  # 板块内涨停家数 (板块效应)
}
```

### 龙头判定规则（硬约束）

1. **龙头信号**（进 execution_pool 加分）:
   - `height >= 2` + `first_board_time 早于 09:45` → `verdict: 龙头`
   - 或 `days_since_first_board == 1`（启动第一天上榜=带动性最强）→ `verdict: 龙头`
   - 且 `sector_breadth >= 3`（板块效应，板块内多只涨停）→ 龙头成立
2. **跟风/补涨**（降级，仅入 watch_pool）:
   - `days_since_first_board >= 3`（板块涨 3 天才上榜=跟风补涨）→ `verdict: 补涨/跟风`
   - 或 `open_times >= 4`（反复开板=分歧弱）→ `verdict: 分歧弱`
3. **无板块效应**（`sector_breadth == 1`，孤军涨停）→ `verdict: 孤军`, 龙头资格降级

**消费**: D1 优先 `verdict: 龙头` 进 execution_pool；`补涨/跟风`/`孤军` 仅入 watch_pool。R6 可据此挑 `分歧弱` 反向。
**version**: v1.5 (2026-08-20)

## Version History

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.4 | 2026-08-07 | P0-1 修复: R2 leaders < 3 时从 all_scored_boards_top10(score >= 50)扩池保证 candidates >= 5 |
| v1.5 | 2026-08-20 | 新增龙头判定维度(limit_list_d 高度/封板时间 + 板块效应 + 首次上榜): 龙头 vs 跟风/补涨 vs 孤军 |
