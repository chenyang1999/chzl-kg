---
name: main_decision_v1
description: D1 主决策 Agent 核心 skill — fresh context LLM 消费 research_summary.json，出 pydantic-valid watchlist_plan.json + 盘前预案 md
agent_owner: D1
version: v1.9
status: P0
category: plan/D1
created: 2026-07-04
updated: 2026-10-17
tested_with: ["20260704 (skeleton dry_run)"]
---

# main_decision_v1

**归属 Agent**: D1 主决策 Agent（canghai-plan profile，08:00 fresh context）
**权威 Spec**: `docs/agents/D1-主决策Agent.md`
**契约**: `docs/11-契约-盘前预案.md` · `docs/10-契约-研究汇总.md`
**用户铁律**: `data/user_preferences.yaml`

## Purpose

D1 是全局唯一决策者：**不抓原始数据、不委派子 Agent、不携带 R1–R7 中间推理**。fresh context 只读最终 artifact，综合裁决后写出当日唯一 `watchlist_plan.json`。

> **T1' 执行路径**：本 skill 由 **LLM fresh context 直接决策**（主路径）。
> **禁止**将 `src/plan/d1_algorithm.py` 或 `src/plan/main_decision.py` 当作主路径调用；它们仅为规则版对照/回归，供人工 diff，不得替代本 skill 的推理与落盘。

## When to Run

| 时点 | 前置条件 |
|------|---------|
| 08:00（盘前批次） | 同日 `data/research/YYYYMMDD/research_summary.json` 已存在且 `orchestrator_status` ≠ `failed` |

若 research 主控未完成，**拒绝出 plan**，告警用户，不写半成品 JSON。

---

## Inputs（全部 pull-based，只读）

### 必填

| 路径 | 用途 |
|------|------|
| `data/research/YYYYMMDD/research_summary.json` | **主入口**；含 `artifacts` 指针、`hard_rejects`、`confidence`、`fetch_global_severity` |
| `data/user_preferences.yaml` | 仓位铁律、龙一龙二池、合规过滤、观察池规模 |

### 按需 pull（经 `research_summary.artifacts`）

| 键 | 默认路径 | 消费内容 |
|----|---------|---------|
| R1 | `data/research/YYYYMMDD/R1_style.json` | 风格模式 → `position_cap` |
| R2 | `data/research/YYYYMMDD/R2_main_sectors.json` | 主线板块 + 龙头候选 |
| R3 | `data/research/YYYYMMDD/R3_sentiment.json` | 情绪共振（可选维度） |
| R4 | `data/research/YYYYMMDD/R4_news.json` | 消息催化（可选维度） |
| R5 | `data/research/YYYYMMDD/R5_stock_profiles.json` | 六维画像、`alpha_grade`、`risk_grade` |
| R6 | `data/research/YYYYMMDD/R6_devil_advocate.json` | `hard_reject` / `strong_suggest` / `soft_note` |
| R7 | `data/research/YYYYMMDD/R7_capital_flow.json` | 资金面确认 |

### 可选

| 路径 | 用途 |
|------|------|
| `data/human_thesis/active/*.md` | 用户当前视角 |
| `data/reports/YYYY-MM-DD/observation_tracking.json` | 昨日观察票，避免重复否决 |
| QMT 持仓（`user-agentqmt_qmt` MCP 或 REST） | 决定 `plan_status`（持有/加仓/减仓） |

---

## Outputs

| 路径 | 说明 |
|------|------|
| `data/plans/YYYYMMDD/watchlist_plan.json` | **核心契约**；必须通过 pydantic 校验后才写盘 |
| `data/plans/YYYYMMDD/plan.md` | 机读版 md（与 KG 版同内容） |
| `chzl_kg/投研交易/盘前预案/YYYYMMDD.md` | 用户阅读的盘前预案 |

写盘前确保目录存在：

```bash
mkdir -p data/plans/YYYYMMDD
mkdir -p chzl_kg/投研交易/盘前预案
```

---

## LLM Prompt 结构（fresh context 主路径）

按顺序执行以下 **7 步**，每步只引用 artifact 字段，不复述子 Agent 推理链。

### Step 0 — 契约与健康度门禁

1. 读取 `research_summary.json`，校验：
   - `schema_version == "research_summary_v1"`
   - `trade_date == YYYYMMDD`（当日）
   - `artifacts` 含 R1–R7 且路径文件存在
2. 读取 `data/user_preferences.yaml` 全文
3. 若 `orchestrator_status == "failed"` 或 R2 artifact 缺失 → **中止**，不写 plan
4. 若 `fetch_global_severity >= 3` → 仍可出 plan，但 `mode` 必须为 `dry_run`，`autonomous_trading_enabled=false`

### Step 0.4 — 近期错题本注入（快回路 · 2026-08-31 新增）

开盘决策前，**必须**读近期错题本，把 E1 沉淀的同类错误带进今天判断（防同类错误重犯，这是错题本从「记分牌」变「训练器」的关键）：

1. 读 `data/corrections/20*/error_case_*.md`（最近 3 周，优先同 `category` 的 high/medium 条目；用 `scripts/trading_tools.py --action get_all_corrections` 可直接取结构化版）
2. 对命中本日情景的错题，明确回答「今天的判断是否避开/覆盖了该错题」：
   - **R2 主线遗漏类**（`error_case_001_main_line_rotation` / `error_case_20260831_001`）→ 强制交叉 R1 `sise_sector_ranking` top 共振板块 + 盘初板块涨停潮（≥3 家）即时补线
   - **R6 无差别反证类**（`error_case_002_r6_blanket_bearcase` / `error_case_20260831_002`）→ 情绪回暖日 R6 反证只决定仓位上限、不构成「不参与」依据
   - **P2 午盘强判类**（`error_case_20260831_003`）→ 强主线龙头午盘分歧 ≠ 上攻乏力，留「午后催化」不确定项
3. 采纳/不采纳都要在 plan `meta` 记一行 `corrections_applied`（`case_id` + 是否规避/覆盖理由）

### Step 0.5 — 宏观 + 情绪 + 行为金融 周期定位（v1.3 · 2026-08-06 新增 · 不阻塞）

**触发条件**: R1/R3 完整 + 跨资产数据可用时执行。**任一缺失** → 跳过整段，进入 Step 1。

1. **宏观环境判定**（`@全球宏观分析框架` 3 档）：
   - 软着陆/降息预期：金/铜同涨 + USDCNH 月升值 > 0.5% + Fed 9 月降息概率 > 50%
   - 衰退担忧：金涨 + 油跌 + 股市高位 + 美元强
   - 滞胀：金涨 + 油涨 + 股市横盘 + 美元强

2. **情绪周期定位**（`@行为金融分析` 7 阶段）：
   - 冷静(涨停<50) / 乐观(50-80) / 兴奋(80-100) / **贪婪(涨停 100+ + 5+ 板 100% 晋级)** / 狂热(涨停 150+) / 焦虑(炸板率>25%) / 恐慌(跌停 100+)
   - **2026-08-05 实况**: 涨停 104 + 5+ 板 100% 晋级 = 贪婪阶段

2.5. **情绪周期四阶段定位（硬接入 · v1.7 · 2026-09-04 新增 · `@emotion_cycle_v1`）**：
   - 读 `data/research/YYYYMMDD/emotion_cycle.json`（由 `compute_cycle_metrics.py` 预计算）或调 `@emotion_cycle_v1` 现场算
   - 四阶段：`low_test` 低位试错 / `main_up` 主升 / `high_chop` 高位震荡 / `main_down` 主跌
   - **阶段 → 该做什么（硬规则，写入 plan）**：

| 阶段 | 该做什么 | execution_pool | 仓位 |
|------|---------|----------------|------|
| `main_up` 主升 | 猛干龙头，任何位置进都对 | 龙头/龙二满配 | 按 R1 cap 上限执行 |
| `high_chop` 高位震荡 | 落袋为安，控仓；只做龙头分歧低吸或低位补涨 | 减半，只留最强主线 | cap × 0.75 |
| `main_down` 主跌 | 空仓/切换新题材一日游；连跌2天尾盘试错 | **≤2 只**或空 | cap × 0.4，或 mode=no_trade |
| `low_test` 低位试错 | 打首板/低位补涨，轻仓试错 | 小仓试错 | cap × 0.5 |

   - **优先级**: 本四阶段 > Step 0.5 的 7 阶段（7 阶段偏描述性，四阶段直接给操作）。两者冲突时以四阶段为准
   - 写入 `meta.emotion_cycle_phase` + `meta.emotion_cycle_action`

3. **跨资产→板块映射**（`@大宗商品分析` commodity→sector）：
   - 黄金 +3% → 黄金股加分（+0.05）
   - 铜 +3% → 铜业/锂电加分（+0.05）
   - 油 -2% → 油服/上游减分（-0.05）

### Step 0.55 — 大事件前夜 · 买点后置硬闸门（2026-09-14 新增 · 用户钦定 · 强制 gate）

**背景（错题本 004 固化）**：2026-09-14 高位光模块（新易盛 -4.99% / 长飞 -3.02%）在"美联储 9/17 凌晨决议前"被 AI 三巨头"呼吁放缓 AI 开发"利空闷杀——R4 把 Amodei 呼吁归类为"Anthropic IPO+盈利"利好（polarity=正面），未识别行业级利空；执行池在加息落地前仍持有高位 AI 硬件。**用户钦定纪律：买点后置——大事件落地前不抢跑，等确定性信号。**

**Step 0.55 Gate（不可覆盖，除非用户显式 sign-off）**：

1. **事件日历扫描**（`@催化剂日历` 或手动）：未来 **≤3 个交易日内**是否有以下大事件：
   - 美联储利率决议 / CPI / PPI / 非农 / 议息会议
   - 中国重磅宏观数据（金融数据 / 社融 / 经济数据 / LPR / 政治局会议）
   - 地缘重大升级（战争 / 制裁 / 关税 / 科技出口管制）
   - 龙头公司重大事件（发布日 / 财报 / 定增 / 减持 / 监管调查）
   - AI 巨头联合声明 / 行业级监管表态（如 2026-09-14 三巨头呼吁放缓 AI 开发类）

2. **若命中大事件** → 执行**买点后置**硬规则：
   - `execution_pool` 中**高位票**（近 10 日涨幅 > 30% 或连板 ≥ 3）**默认降级 watch**；确需保留的必须逐票写"为什么这次例外"且经用户 sign-off
   - 新增买入**全部后置到事件落地后**：预案中 `entry_rules` 标注 `post_event_only: true`，触发条件改为"事件落地 + 竞价/开盘确认"，不得在落地前按预案价抢跑
   - 高位持仓相关：预案提示"事件落地前高位持仓只减不加，破位即走"
   - 仓位：若事件偏负面（如三巨头呼吁放缓类），`position_cap` 额外 × 0.6

3. **写入 plan**：`meta.event_premarket_gate = {"event": "...", "event_date": "YYYYMMDD", "post_event_only": true/false, "high_pool_reduced": true/false, "rationale": "..."}`

4. **与 Step 0.5 联动**：大事件前夜即使情绪周期判 `main_up`，也以本 Gate 的买点后置优先（防"情绪好就抢跑"）。两者冲突以本 Gate 为准。

**约束**：本 Gate 不是禁止交易，是**禁止在事件落地前对高位票抢跑**；事件落地后回归正常买点逻辑。

### vibe-trading MCP 补充（2026-08-06 新增 · D1 决策增强）

**目的**：D1 整合 R1-R7 + 用户意图做最终决策，vibe-trading 提供候选池量化验证 + iwencai 概念纯度二次确认。

| 工具 | 调用方式 | 典型问句 | 返回字段 |
|------|---------|---------|---------|
| `vibe_trading__iwencai_search` | NL 问句 | `Execution候选池：{候选代码} 30日换手率>10% AND 近1年无重组` | 候选池过滤表 |
| `vibe_trading__iwencai_search` | NL 问句 | `验证叙事纯度：{概念}成分股中纯正主业占比>80%` | 概念纯度报告 |
| `vibe_trading__get_market_data` | ts_code | D1 候选池每只，查近5日K线（验证近因） | OHLCV |
| `vibe_trading__get_fund_flow` | ts_code | 候选票，查主力净流入占比（与 R7 交叉验证） | 资金流 |
| `vibe_trading__pattern_recognition` | ts_code | 候选票，查"突破"、"回踩"等形态（辅助买点判断） | 形态信号 |
| `vibe_trading__search_symbol` | name | 用户输入"XX科技"→ ts_code（处理用户自然语言输入） | 标准代码 |

**调用时序**：Step 1（R1 风格）→ Step 2（R2 候选过滤）→ **D1 vibe-trading 验证**→ Step 3（风控硬过滤）。  
**关键**：D1 必须在最终 `execution_pool` 每只票上调用至少 1 次 vibe-trading 工具（`iwencai_search` 或 `get_market_data`），确保候选池不只是 R2 的定性判断，而是有独立量化证据。  
**节流**：execution_pool ≤ 15 只，每只 1 次，全 D1 ≤ 15 次调用。  
**降级**：`vibe_trading__iwencai_search` 失败 → 直接用 R2/R7 的判断结果。

4. **position_cap 联动**（`@市场情绪分析` 5 维度法）：
   - 情绪分 80-100（贪婪）→ 强制 position_cap ≤ 0.60（即使 R1 给 0.70）
   - 情绪分 0-20（极恐）→ 强制 position_cap ≥ 0.55（即使 R1 给 0.40）
   - 情绪分 20-80 → 跟随 R1

5. **写入 `market_context.emotion_cycle`**:
   ```json
   "market_context": {
     "structure": "...",
     "emotion_cycle": {
       "phase": "贪婪",
       "score_5d": 85.2,
       "r1_sentiment_score": 75,
       "gap": 10.2,
       "commodity_signal": "金+3.4% 铜+3% 油-1.9% 人民币升值",
       "macro_regime": "软着陆+降息预期"
     }
   }
   ```

> D1 红线 7：**Step 0.5 不得**作为 hard_reject 触发器——仅是 position_cap / 加分 / 减分参考，不 override R6 模式六。

### Step 1 — 风格与仓位上限（R1）

从 R1 读取今日风格结论，映射 `position_cap`（写入 `risk_limits.target_total_position_pct` 与 `meta.position_cap_pct`）：

| R1 风格信号 | position_cap |
|------------|--------------|
| 防御观望 / 情绪冰点 | ≤ 0.40 |
| 震荡分化 | ≤ 0.60 |
| 主线进攻 / 情绪扩散 | ≤ 0.75–0.80 |

降级：R1 超时或 `confidence.R1 == 0` → 默认震荡分化，`position_cap = 0.50`。

**v1.3 · 2026-08-06 新增 · Step 0.5 情绪分硬联动**:

```
final_position_cap = MIN(R1_position_cap, 情绪联动上限)
```

| R1 sentiment_score | 情绪分 5 维度 | Step 0.5 联动 | 强制 position_cap 上限 |
|-------------------|--------------|--------------|---------------------|
| ≤ 20 (极恐) | ≤ 20 | **逆向买入** | **≥ 0.55**（不允许 R1 给的 0.40） |
| 20-40 | 20-40 | 跟随 R1 | 跟随 R1 |
| 40-60 | 40-60 | 跟随 R1 | 跟随 R1 |
| 60-80 | 60-80 | 跟随 R1 | 跟随 R1 |
| **≥ 80 (贪婪)** | **≥ 80** | **逆向卖出** | **≤ 0.60**（不允许 R1 给的 0.80） |

**2026-08-05 实况**: R1 sentiment_score=75 + 5 维度分 85.2 = Step 0.5 强制 position_cap ≤ 0.60。

写入 `meta.position_cap_pct` 和 `meta.position_cap_source: "R1-style with emotion_5d_override"`。

### Step 2 — R6 硬否决（不可覆盖）

1. 合并 `research_summary.hard_rejects` 与 R6 内 `severity: hard_reject` 条目
2. 对应 `ts_code` **永久剔除** execution_pool 候选；可进入 `watch_pool`（`watch_reason_code=distribution_alert`）或 `rejected`
3. 记录到 `meta.r6_devil_advocate.hard_rejects_applied`

> 红线：D1 **不得** override R6 `hard_reject`，无例外。

### Step 2.5 — 主线第一天参与原则（硬规则 · 2026-08-31 新增，错题本 001/002 固化）

打板/情绪驱动行情下（R1 情绪回暖日 **或** R2 主线 `stage=early` 且当日板块涨停家数 ≥3），**主线第一天的参与优先级高于 R6 反证**：

1. **R6 反证只决定仓位上限，不构成「不参与」依据**：
   - 情绪回暖日（炸板率收敛 + 涨停家数扩张），R6 的出货/退潮类反证置信度整体打折（×0.5）
   - 「基本面亏损 / 资金面弱 / 估值高」→ 只压仓位（如 ≤3%），**禁止**直接把主线龙头降为「只观察不参与」
   - 唯一硬例外：R6 `hard_reject`（模式六霸榜出货等）仍不可覆盖
2. **主线龙一/龙二必须至少进 execution_pool（轻仓）或 watch_pool 最高观察级**：
   - 主线 `stage=early` 且涨停潮启动 → 龙一给最小仓位（≥3%）参与，龙二观察
   - 龙一一字锁仓买不进 → 顺势切龙二/候补的参与机会，**而不是放弃整条线**
3. 本原则写入 `meta.mainline_participation_applied`，供 E1 复盘核对是否被执行

### Step 3 — 合规 + 龙一龙二筛选（R2 + R5 + user_preferences）

对 R2 候选逐票过滤（顺序从最严到最宽）：

1. **合规**：**自 2026-08-06 起,300/688/920 全部解禁**(用户确认全系统已支持创业板/科创板/北交所)。残留风控:`st_filter`(ST 摘帽期)、停牌、退市警示 → execution 剔除,watch 可保留。**特殊规则**(v1.1):300/688 因涨跌幅 20%,止损/止盈阈值自动按 1.2x 系数调整(可在 `user_preferences.yaml` 里 override)
2. **R6 hard_reject**（Step 2 已剔）
3. **人气维度（2026-09-14 新增 · 用户钦定"人气=潜力核心" · 必读 `attention_signals.json`）**：
   - 读 `data/research/YYYYMMDD/attention_signals.json`：`persistent`（90日持续人气）/ `surge`（今日跳升/首次进榜）/ `cross_platform`（多平台合力）/ `today.dc_renqi_top` + `today.ths_stock_top`
   - **加分**（进 execution 时写入 `attention_score`）：持续人气 `days_on_list ≥ 10` + 今日仍在前排 → 人气分 +1；`surge` 跳升股（首次进榜/排名跳升≥15）→ 标记 `attention_surge=true`（配合弱转强/超预期买点）
   - **警告**：持续无人气（90日从未上榜）却单日大涨/涨停的票 → 标 `attention_cold=true`，**警惕无合力/庄股**，默认降级 watch（需用户 sign-off 才进 execution）
   - **联动**：人气股 ∩ 主线龙头（R2 龙一龙二）→ 最高优先级；人气掉出榜（`L2_dropped` 类）的票 → 检查是否该卖出/降级
4. **龙一龙二池**（`leader_preference`）：
   - 每板块仅龙一、龙二可进 execution_pool
   - 龙一：板块涨停家数 top1 **或** 主力 5 日累计 top1 **或** 连板高度 top1
   - 龙二：板块综合评分 top2
   - 龙三及以下 → watch_pool（除非龙一被 R6 hard_reject，龙二递补）
   - **杂毛过滤**（满足 ≥2 项即剔除 execution）：主力排名 top3 外、龙虎榜 30 日无机构席位、连板高度 < 龙头-2、换手率 < 板块 median 50%
5. **风险等级**（R5 `alpha_grade` / `risk_grade` × position_cap）：
   - `position_cap ≤ 0.4`：仅 `alpha_grade=A` 且 `risk_grade≤B`
   - `position_cap ≤ 0.6`：A 全留 + 部分 B+
   - `position_cap ≥ 0.7`：B+ 以上
   - **档位缺失必须套契约默认值 B**（`_effective_grades`）。缺失档位若按 rank 0 处理，
     会比 C 更差，使 `risk_grade≥B-` 的 AND 分支恒假 → 该类日期执行池被整体清空。
     R5 实际长期未产出 `risk_grade`（2026-09-30 实测 30 日 0/330），故此项为硬要求。
6. **数量硬约束**：`execution_pool` ≤ `position_hard_rules.max_positions`（**5**，覆盖 `watchlist_policy.execution_pool_size_range` 上限）
7. **单票/板块/总仓**：`max_position_pct ≤ 0.15`，单板块累计 ≤ 0.40，总仓 ≤ position_cap

降级：R5 缺失 → `alpha_grade` 默认 B，`risk_grade` 默认 B。

### Step 3.5.6 — 入口通道按 regime 选择（2026-09-30 修 · 禁止固定单通道）

**背景（事故）**：执行池原先只认 `trend_pullback_buy`（决策线 MA50 回踩）单通道。
强势打板行情里龙头距 MA50 常差 20-30%，回踩条件数学上永不成立
→ **越是点火行情，执行池越必然为空**（20260930 六只候选全落 watch、exec=0）。
这与用户三通道体系（打板/强势低吸/跟单）直接冲突：打板是其数据中 64% 胜率的正 α 通道，
却在前瞻层被结构性排除。

**规则**：入口通道由 R1 风格 regime 决定（`d1_algorithm.step_regime_channels`）：

| R1 style | 可用通道 | ignition |
|---|---|---|
| 连板情绪型 / 主升 | `trend_pullback_buy` + `leader_breakout` | ✅ |
| 主线扩散型 | `trend_pullback_buy` + `leader_breakout` | ❌ |
| 震荡分化型 | `trend_pullback_buy` | ❌ |
| 崩溃退潮型 / 退潮 | `trend_pullback_buy` | ❌ |
| 缺失 / 未匹配 | `trend_pullback_buy`（保守回退） | ❌ |

- `leader_breakout` 口径：平开或小幅高开 + 放量突破昨日涨停价/20日前高跟随买入；
  高开 >7% 不追。
- **一字板不得被静默吞掉**：仍入执行池，但 `entry_rule.one_word_no_chase=True`
  且不给竞价挂单价（挂单必然落空，制造"假买点"），语义为"等开板分歧承接"。
- 每份 plan 必须落 `data_sources.entry_channels`（style/channels/ignition/raw_candidates/reason），
  使 exec=0 时能一眼区分"regime 未开放通道"与"候选被过滤"。

### Step 3.5.7 — 候选不得静默消失（2026-09-30 修 · 硬约束）

**事故**：`step3_execution_candidates` 用裸 `continue` 淘汰候选，被淘汰的票
**既不在执行池也不在观察池**，在预案里彻底不可见。R2 明确选出的 6 只龙一/龙二
曾有 4 只这样消失（20260930：新华传媒 6连板龙一、超声电子 PCB人气王龙一、
依顿电子龙二、广汽集团龙二），用户只能看到"票没了"，无法分辨原因。

**规则**：
- 任何淘汰必须写入 `gate_log` → plan `data_sources.grade_gate_drops`，
  含 `ts_code/name/role/stage/reason`（档位闸门 / R6否决 / 禁买前缀 / 非龙一龙二）。
- 被淘汰的**龙一/龙二必须回灌观察池**（`watch_reason_code=grade_gate_dropped`），
  保证"要么在执行池，要么在观察池，要么在否决清单"——不得三处皆无。
- 档位闸门淘汰原因文案必须提示"risk 为缺省补 B，需核 R5 是否漏产出"，
  避免把上游数据缺失误读为"票不够好"。

### Step 3.5.8 — 兜底 plan 的时序陈旧判定（2026-09-30 修）

**事故**：08:30 兜底 plan 生成时 R5(08:33:51)/R6(08:52:36) 尚未落盘 → 空池；
而安全网（`scripts/plan/ensure_watchlist_plan.py`）只按"文件存在"判幂等，
09:20 再跑也不重建 → 全链一整天读陈旧空池。

**规则**：安全网判幂等时，除"文件存在"外还必须校验**兜底 plan 是否早于
关键上游（R5/R6）落盘**；若是则用完整上游重建。LLM 主路径产物一律不覆盖。

### Step 3.6 — 战术层短线信号(2026-09-04 新增 · 硬闸门 · v1.7)

在 Step 3.5 三大闸门通过后,每只 execution 候选**还必须**经过"买点级"硬约束(三项可独立调用,任一失败 → 降级 watch):

**关4 · 板型识别**(`@tactical_signal_v1` · `src/research/board_pattern.py::classify_pattern`):
- 输入: limit_list_d 字段(first_time/last_time/open_times/amount/limit_amount/limit_times/sector_limit_up_count)
- 写出 `pattern` / `time_window` / `pattern_action`
- **硬规则**:
  - 板型=`尾盘投机板(14:30+)` → 拒绝(北京炒家 §1.5.4: 几乎不碰)
  - 板型=`回封板(多次开板)`(open_times≥2) → 拒绝(§1.5.2: 不碰)
  - 板型=`秒拉板` AND 板块涨停<3 → 拒绝(§1.5.1: 无板块效应不封)
  - 板型=`秒拉板` AND 板块涨停≥3 → 排板不冲(§1.5.1 排板优于冲)
  - 板型=`换手板(午前)` → 可扫; 时段 10:00-11:30 合适(§1.5.3 半小时级横盘)
  - 板型=`中军板(午前)` → 可做(§1.5.5 行业一提就想到)
  - `time_window ∈ {尾盘封板(14:00-14:30), 尾盘投机(14:30+)}` → 警告(§1.5.4: 少打)

**关5 · 弱转强/强转弱**(同上函数):
- 输入: prev_open_times/prev_pct_chg/today_pct_chg
- `is_weak_to_strong=true`(烂板+今涨停) → 推荐(92科比 §3.3.27: 烂板后买盘凶=弱转强)
- `is_strong_to_weak=true`(昨涨停+今<5%) → 卖点(§3.3.30: 第三天可能强转弱)

**关6 · 总龙开关**(`src/research/dragon_switch.py::judge_dragon_switch`):
- 输入: 当日市场总龙 ts_code + yesterday/today pct_chg/limit + consecutive_halts
- 写出 `dragon_status` / `dragon_action`
- **硬规则**:
  - `status=second_halt`(总龙第二次被关) → D1 总仓上限 cap ×0.5(陈小群 §10)
  - `status=first_yin_crushed`(首阴被按) → cap ×0.6(§8 准备调整)
  - `status=faded`(连续大跌) → cap ×0.3 或空仓(§10 退潮)
  - `status=alive` + `sector_follower≥3` → 维持 cap(§52 合力强)

**关7 · 禁止清单过滤**(`src/research/forbidden_filter.py::check_forbidden`):
- 14 项硬规则独立可测(中位股/计划外/梭哈/手风不顺隔夜等)
- 任一命中 → 移出 execution_pool
- 关键规则: `mid_laggard` / `non_mainstream` / `late_speculation` / `all_in_learning` / `plan_outside_scan` 是高频硬拦

写入每只票: `tactical_signals.pattern` / `dragon_status` / `forbidden_hits[]` 字段。

### Step 3.5 — 核心判定 + 盈亏比 + 纪律自检（2026-09-04 新增 · 硬闸门）

对通过 Step 3 的每只候选，在进 execution_pool 前**必须**跑三关（任何一关拒绝 → 剔出）：

**关1 · 个股核心判定**（`@core_judge` · `src/research/core_judge.py`）：
- 输入：个股/板块/大盘 20 日日收益率（`daily`）+ 连板高度 + 板块内排名 + 主力净流入
- 输出 `is_core` / `core_grade` / `resonance_type`
- **硬规则**：`resonance_type=anti_rotation`（逆势抱团/控盘）→ 降级 watch，不进 execution（可能是庄股非合力）
- `core_grade ∈ {laggard, watch}` → 不进 execution（跟风/无地位）

**关2 · 盈亏比判断**（`@risk_reward` · `src/plan/risk_reward.py`）：
- 输入：买点（`buy_price`）+ 止盈（`take_price`）+ 止损（`stop_price`）+ 情绪阶段 + 是否核心
- 输出 `risk_reward_ratio` + `position_suggestion_pct` + `grade_check`
- **硬规则**：`risk_reward_ratio < 1` → 拒绝开仓（纪律铁律6: 盈亏比优先于胜率）
- 仓位按 `position_suggestion_pct` 写（主升核心可 15%，主跌只试仓）

**关2.5 · R4 利空 × 候选打击面交叉（2026-09-14 新增 · 错题本 004 固化）**：
- 读 `R4_news.json` 全部 `top_events`，取 `polarity=负面` 且 `bearish_scope=行业级/板块级` 的事件及其 `bearish_impact_sectors[]`
- 对每只候选票：所在板块 ∈ `bearish_impact_sectors` → **降级 watch 或要求竞价反证**；命中行业级 → 默认剔出 execution_pool（除非用户显式 sign-off）
- 输出每只票：`bearish_hit: {event_id, scope, sector, action}`（保留/降级/剔出/竞价反证）
- **若 R4 有行业级利空但 execution_pool 仍保留该板块高位票 → 必须有用户 sign-off 记录**，否则判定违反 Gate

**关3 · 纪律自检**（`@trade_discipline_v1`）：
- 跑十条铁律 + 开仓资格 checklist + 禁止清单
- **硬规则**：命中任一禁止项 → 写入 `rejected`（reason_code 记编号）；违反铁律 → 降仓或剔出

写入每只票：`core_judge` / `risk_reward` / `discipline` 三段字段。

### Step 4 — 观察池（板块核心 + 近10日涨停 + R2 余票 + R6 修正 + 昨日观察）

组装 `watch_pool`（`watchlist_policy.min_watch_pool_size`–`max_watch_pool_size`，**20–40 只**），来源优先级（2026-08-31 用户钦定扩容口径）：

1. **板块核心个股**：R2 主线/次线 `sector_core_watchlist` 全部 + 每条主线前 3 核心票（含未入选 execution 的龙三及以下）
2. **近 10 交易日涨停股**：tushare `limit_list_d` 拉最近 10 个交易日涨停/炸板名单，保留其中属于当日主线/次线板块、或有资金关注（龙虎榜/主力净流入）的票——**10 日内有过涨停 = 有人气的观察候选，必须覆盖**
3. R6 `strong_suggest` 降级票（须写 `meta.r6_devil_advocate` 采纳/覆盖理由）
4. 昨日 `observation_tracking` 中未成交观察票 + 长期主线未启动票（`sector_off_line`）

每只须含合法 `role`（`watch` / `watch_elastic`）与 `plan_status`（`watch_pool_only` / `watch_pool_wait_for_entry`）。
**观察池宁多勿漏**：上限 40 只，用于盘中扫描与次日回看，不进 execution、不参与自动交易。

### Step 4.5 — 买点推演 + T+1 博弈（2026-09-04 用户方法论 · 硬要求）

A股 **T+1** 制度下，当天买入不可卖，每一笔买入=**押注次日有人接力**。因此 execution_pool 每只票在定 entry_rules 前，**必须**先做博弈推演（写入 `t1_game_analysis`，作为 entry_rules 的推导依据）：

**1. 消息双面解读**（对应 R4 催化 + 盘前公告）：
- 利好：高开低走（先手资金兑现）or 平开高走（预期差发酵）？——**若高开幅度已被先手兑现，禁止推荐"竞价追高"**
- 利空：洗盘吸筹（给低吸机会）or 真利空瀑布杀？——上升趋势中的利空洗盘=上车机会

**2. 预期差/超预期**：赚钱效应来自**预期差**，不是消息本身。判断市场对该消息的定价是否已充分。

**3. 买点类型与先手风险**（结合 `trading_time_preference`）：
- 集合竞价/开盘：是否已被先手兑现 → 禁追高
- 低吸（用户口径：预判涨停、相对涨停价仍低、高开 5 点也可买；**≠抄底接飞刀**）
- 半路（平开+放量突破压力位跟随）——用户数据显示半路是负 α（35% 胜率），**谨慎给此买点**
- 打板（`leader_breakout`）——用户数据显示打板正 α（64% 胜率）

**4. 短线结构词汇**（判断资金博弈位置）：
- **卡位**：个股争夺板块内身位（先于龙一封板/连板追平），卡住辨识度
- **弱转强**：前一日分歧/炸板，次日转强（高开秒板/低开拉板），分歧转一致信号
- **分离**：个股走势与板块/龙头分离（板块回调它逆势走强），独立资金运作，可能走独立行情
- **联动/助攻**：板块内同涨同跌；助攻=低位票先封板为龙头打开空间
- **补涨**：龙头拉高后低位/滞涨同板块票跟随，行情扩散末段信号（追补涨需谨慎）

**产出**：每只 execution 票写入 `t1_game_analysis`：`消息解读` / `预期差判断` / `买点结论`（竞价/低吸/半路/打板 + 先手风险） / `短线结构标签`。**买点结论必须与 Step 5 entry_rules 一致**；若推演显示"追高被兑现"→ 该票降级 watch 或改低吸节点。

---

### Step 4.8 — 跷跷板 / 对手盘 B 计划（2026-09-17 新增 · 用户钦定 · 硬要求）

**背景**：预案只写"买什么"是单向剧本。**预案票不及预期时，资金会去别的方向**——这是 A 股存量博弈的必然（钱不会消失，只会搬家）。用户钦定：预案必须写"如果这些票不及预期，我可以考虑做哪些跷跷板/对手盘机会"。

**产出**：`plan.seesaw_plan`（B 计划章节，每份预案必有）：

```json
{
  "trigger_conditions": ["触发1: 执行池≥2票竞价不及预期(高开<预期位或低开破位)", "触发2: 主线板块资金净流出且无承接", "触发3: 龙头断板/炸板率>25%"],
  "seesaw_directions": [
    {
      "direction": "防守/高股息", "source_evidence": "R2 次线银行/高股息 + R7 资金流向",
      "candidates": [{"name": "工商银行", "ts_code": "601398.SH", "role": "次线观察", "entry_note": "科技不及预期且指数走弱时启动"}],
      "trigger": "科技主线竞价集体低开 + 炸板率上升"
    },
    {
      "direction": "主线内部高低切(光通信→存储→低位补涨)", "source_evidence": "R2 主线分级 + R7 板块资金",
      "candidates": [...],
      "trigger": "主线高位票买不进/兑现，低位分支承接"
    },
    {
      "direction": "逆势新题材/次线", "source_evidence": "attention surge + R4 事件",
      "candidates": [...],
      "trigger": "surge 票竞价超预期 + 主线不及预期"
    }
  ],
  "opposite_side_note": "反向提示：若 B 计划方向也同步走弱 → 全市场降档，执行池全部后置/空仓"
}
```

**B 计划素材来源（按优先级）**：
1. **R7 `seesaw_pairs[]`**（板块跷跷板配对，20日相关<-0.6）——有配对直接用；空则用 R2 次线
2. **R2 次线板块**（国产算力/卫星/银行高股息等）+ 观察池票
3. **attention_signals 的 surge 票**（今日跳升=资金新去向的候选）
4. 预案里已列但没进 execution 的票（如"高开不追"的票→不及预期时的承接对象）

**触发判定（盘中 P2 会用）**：执行池≥2票竞价不及预期（高开低于预期位或低开破位）、或主线板块资金净流出无承接、或龙头断板——任一命中 → 切 B 计划，预案内已备好方向，不临时起意。

**约束**：B 计划是"预案内备选"，不是"盘中新开计划外仓"——所有候选必须在盘前预案里点名，触发后才按纪律执行（铁律 8：计划外不出手）。

---

## 硬价位完整性(2026-10-21 用户钦定 · Step 5 前置硬规则)

**价位不得由模型凭感觉写——必须先跑规则引擎拿基准值**（引擎：`src/plan/price_levels.py`）:

```bash
.venv/bin/python scripts/plan/apply_price_levels.py --date YYYYMMDD --write-json
```

引擎口径（可复算）:
- **买区**: ①均线回踩 `[min(MA50,牛线)×0.99, MA50×1.01]`,区间>7%收窄至基准±1.5% ②分歧回踩(强势票,现价距MA10>8%) `[昨收×0.92, 昨收×0.97]` ③突破/打板 `pivot=max(昨收,20日高)`,买区 `[pivot×0.995, pivot×(1+1.5~3%)]`
- **止损**: 以**买入价(买区上沿)**为基准, `买价×(1-5%主板/8%20cm)` 与 `熊线×0.99`、`MA10×0.99` 取最高,且必须低于买区下沿
- **止盈**: 2R = 买价 + 2×(买价−止损);若20日高点在 2R 之下且高于买价5% → 取前高
- **RR** < 1.8 → `RR_FAIL`,不参与

**LLM 的义务**: 在引擎值上做事件/情绪/身位微调,但:
- 偏离引擎买区 >10% 必须在 `derivation_reason` 写明依据(如事件未落地后移买点)
- 不得无依据地凭空写数——引擎算不出的情况(一字板/无价格数据)必须显式说明

**每只票(execution_pool/watch_pool/seesaw_plan 候选)必须带数字价位,禁止只写条件**:
- buy_zone(可买区间两个数字)、trigger_price、stop_loss、take_profit
- "高开≤3%+竞价放量+板块≥3家涨停"只能作为确认条件,不能替代买区——用户无法据此判断具体多少钱买
- 纯观察票若确无买区(如温度计/禁买锚),必须显式标注原因,不能留空字段让人误以为漏了
- 昨收缺失的票从 kb/research.db market_daily_bars 补,但买区必须在本步骤写好,不靠渲染阶段反推

**价位推导交付物**: `chzl_kg/投研交易/盘前预案/YYYYMMDD_价位推导.md`——每票一行价位表 + 逐票公式(止损/买区/止盈/RR/技术位),用户要看到"为什么是这个价"。

**引擎会自动做的事**(不用 LLM 手工处理):
- `RR<1.8` 的票自动写入 `no_trade_conditions.RR_FAIL` 并标记 active → 当日不可开仓
- 买区在现价上方 10%+ 自动标 `above_price`（"需上破 x% 站上才成立，不是现在能买"）
- 区间过宽 (>7%) 自动收窄到基准线 ±1.5%
- 一字板自动清空 trigger（无有效买点，等开板）

### Step 5.0 — 管线顺序(固定, 2026-10-21 用户钦定)

D1 写完 JSON 后**必须按序跑完三步**, 少一步就是交付事故:

```bash
# 1) 价位引擎: 补全缺价位票 + 给 D1 原值做偏离校验 + RR_FAIL 写 no_trade
.venv/bin/python scripts/plan/apply_price_levels.py --date YYYYMMDD --write-json
# 2) 点位表版人读预案（用户审阅默认看这份）
.venv/bin/python scripts/plan/render_plan_tables.py --date YYYYMMDD
# 3) 散文版（已内嵌价位速查表）
python -c "import json,sys;sys.path.insert(0,'src');from src.plan.render_markdown import render_watchlist_plan_md as r;from pathlib import Path;Path('chzl_kg/投研交易/盘前预案/YYYYMMDD_散文版.md').write_text(r(json.load(open('data/plans/YYYYMMDD/watchlist_plan.json'))),encoding='utf-8')"
```

交付给用户时给这三份 + 价位推导明细, 并明确说哪些票 RR_FAIL/不可买。

**禁用**: `scripts/plan/backfill_plan_prices.py` 已废弃(5日线简化口径会算错), 调它会退出码 3。

### Step 5.1 — 点位表版人读预案(必做)

JSON 落盘后必须渲染点位表版(不是散文版):
```bash
.venv/bin/python scripts/plan/render_plan_tables.py --date YYYYMMDD
```
产出 `chzl_kg/投研交易/盘前预案/YYYYMMDD_点位表.md`:全局约束+no_trade清单;执行池每票三表(买点价位/确认条件/卖点价位)+竞价四档;B计划逐方向触发条件+候选表;观察池逐票点位表;禁入名单。用户审阅/对比预案时默认给这个文件。

**散文版内置速查表**: `src/plan/render_markdown.py` 已自动在执行池/观察池段内插入价位速查表(买区/触发价/止损/止盈/RR),缺价位的票显示 `⚠️未给` 而不是静默留空。

**漏价位兜底(历史 JSON 专用)**: D1 未填 buy_zone 时,可用技术位补算(标 `price_src=tech_backfill`,md 里显式写"技术位补算·非D1原值"):
```bash
.venv/bin/python scripts/plan/backfill_plan_prices.py --date YYYYMMDD --inplace
```
补算只是可读性兜底,同时须在当日 meta 记一条遗漏(同一字段一周内复发→写错题本)。

### Step 5 — entry_rules / exit_rules（D1 独有输出）

对 execution_pool 每只票：

**entry_rules**（偏好 `trading_time_preference.prefer_pullback_over_breakout`）：
- 类型枚举：`trend_pullback_buy` / `leader_breakout`（**禁止** `daban_confirm`）
- 含 `trigger_price`、`buy_zone`、`max_premium_pct`、`position_pct`、`execution_logic`
- 已持仓不加仓 → `entry_rules: []`

**auction_expectation（竞价预期三档 · 2026-09-17 用户钦定 · 每票必填）**：

> 用户要求：预案必须预先定义"集合竞价开出来多少算符合预期、多少算超预期、多少算不及预期，各怎么办"——09:27 竞价数据一到，机械对照执行，不靠盘中临场判断。

```json
"auction_expectation": {
  "base_close": 190.0,                // 昨日收盘
  "expected_open_band": [188.0, 193.0],  // 预期竞价区间(±1.5~2%内), 用昨收×板块强度+人气修正
  "bands": {
    "below_expected":  {"open_pct": "<-1.5%", "action": "低开破位→放弃/竞价后撤单, 不接(除非弱转强模型: 低开快速翻红才参与)", "action_type": "skip_or_weak_to_strong"},
    "in_expected":     {"open_pct": "-1.5%~+2%", "action": "按预案执行: 竞价/开盘按 buy_zone 承接", "action_type": "execute_plan"},
    "above_expected":  {"open_pct": "+2%~+5%", "action": "超预期→竞价强则半路/打板确认, 高开≤max_premium 可追, 超限不追", "action_type": "over_expected_confirm"},
    "far_above":       {"open_pct": ">+5%", "action": "高开过度→不追(兑现风险), 等回踩或放弃", "action_type": "skip"}
  }
}
```

**三档判定规则（写进每票，禁止只写文字不写区间）**：
- `expected_open_band` 必须有**具体数字区间**（不是"高开不追"这种话）——昨收 × (1±板块强度修正)，人气股可 +1~2%
- 20cm 票（300/688）区间按 1.2x 系数放宽
- 每档必须给 `action`（动作）+ `action_type`（枚举，P1 直接映射）
- **涨停价=基准的票**（预判一字）：only 两档——一字（放弃/等回封）vs 未一字（按 buy_zone）
- 预案 md 渲染时输出成表格：`竞价区间 | 判定 | 动作`

**exit_rules**（每只至少 1 条 `stop_loss_break`，`priority=1`）：
- 硬止损：`trigger_price = reference_close × (1 - drop_loss_threshold)`
- 技术破位：`intraday_break_exit`（收盘跌破 MA10）
- 板块降级：`sector_switch_exit` 或条件描述
- R6 `distribution_alert` → `distribution_confirmed` 减仓 50%
- 可选止盈：`take_profit_hit`，`trigger_price = reference_close × 1.15`，`quantity_pct=0.5`

**波段锁仓档 exit_rule（2026-09-05 新增 · 用户方法论）**：

> 用户原话: "对于做主线龙头来说, 其实也本身不太依赖于做T, 这种基本上就是做大波段锁仓的居多"

每只 execution 票按 `hold_style` 选择对应档位（`intraday` / `short` / `wave_main` / `wave_final`）:
- `hold_style=wave_main`(波段锁仓): 调 `@wave_exit_v1`（`src/plan/wave_exit.py::judge_wave_exit`）
  - 输出 4 个卖出信号 + 仓位档（一浪试仓 8% / 二浪加仓 18% / 三浪拉满 25%）
  - 止损 = 跌破20日均线 -12% (波段硬止损)
  - 禁止: 做 T、首阴加仓、跌破 20 日均线还拿
- `hold_style=wave_final`(鱼尾): 持仓 0%, 必清不贪
- `hold_style=short`(短线): 沿用 `-7%~-10%` 硬止损 (现有路径)
- `hold_style=intraday`(日内): T+0 强制平仓

每只 execution 票必须显式标注 `hold_style` 字段, 缺失则默认 `short`(系统 fallback 到短线档)。

**主升三浪映射（hold_style 推导依据）**：
- `mainline_lifecycle` stage=启动 → 一浪 → wave_main (持仓 8%)
- stage=主升早 → 一浪末/二浪初 → wave_main
- stage=主升中 → 二浪/三浪 → wave_main (加仓至 18-25%)
- stage=高潮 → 三浪(高潮前期) → wave_main; 但若 S3/S4 触发 → wave_final
- stage=退潮 → 鱼尾 → wave_final (持仓 0%)

**价格规范（v1.4 · 2026-08-16 新增 · 硬约束）**：
- `reference_close` 是 Python 侧注入的 **T-1 前复权收盘价**，已统一处理复权类型
- **禁止** agent 自行调用任何外部工具获取收盘价
- 所有止损/止盈/买入触发价必须基于 `reference_close` 计算

### 买卖节点合理性带（v1.6 硬约束 · 2026-08-20）

**背景**: 回测发现 33% 的 `take_profit` 设在买入价下方（脏/过期价）、低吸买入价设在中位 -28.6% 深回踩（=抄底非低吸）。D1 输出前必须对每只 execution 票做**节点合理性校验**，越界即判 invalid（剔除出 execution_pool 或标 `node_invalid` 降级 watch）：

```python
def validate_nodes(buy_px, stop, take, ref_close):
    errs = []
    if not (0.95 <= buy_px/ref_close <= 1.05):            # 买入价必须在现价 ±5% 内
        errs.append("buy_out_of_band")
    if take <= buy_px:                                     # 止盈必须 > 买入价
        errs.append("take_below_buy")
    if not (0.90 <= stop/buy_px <= 0.95):                  # 止损必须在买入价 -5%~-10%
        errs.append("stop_out_of_band")
    return errs
```

**硬规则**:
1. `take_below_buy` / `buy_out_of_band` → 该票 `node_invalid: true`，**移出 execution_pool**（降 watch_pool），并记入 `meta.node_invalid_count`
2. `stop_out_of_band`（止损太远 = 等于没止损）→ 强制止损 = `buy_px × 0.93`（-7%），并记 warning
3. 低吸节点（`trend_pullback_buy`）的 `trigger_price` 若低于现价 5% → 视为**抄底**（非低吸），改按现价附近执行或标 invalid（用户口径: 低吸=买强势票相对涨停仍低，非等大跌接飞刀）
4. 全部节点通过 → 该票 `node_valid: true`，才可进 execution_pool

**验收**: D1 JSON `meta` 须含 `node_invalid_count`；execution_pool 每只票须 `node_valid: true` 或已降级。
**version**: v1.6 (2026-08-20)

- 若 `reference_close` 为 null，该股票必须降级到观察池并标注 `price_source: "missing"`

**version**: v1.7 (2026-10-16) · R6 strong_suggest 个股级闭环

**根因**: R6.M3（估值×主线临界）落盘的 strong_suggest 含个股 ts_code（如 605058.SH 澳弘电子），D1 v1 之前只把 R6.M5/主线级 strong_suggest 当记录参考（`strong_suggests_overridden`），个股级强 suggest 走了 reject 路径（即便票在 R2 候选里也被打掉）。这是 P5 闭环没接上的最后一环。

**变更**:
- `step2_r6_filter` 返回值新增 `strong_suggest_codes: set[str]`（个股级强 suggest 抽到的 ts_code 集合）
- `meta_r6.strong_suggests_accepted[]` 新增字段：每条带 `ts_code / id / suggestion`，便于后续审计
- `build_pools_and_rules` 在 step4_watch_pool 之后，对 watch_pool 里命中 strong_suggest_codes 的票加：
  - `r6_strong_suggest: true`
  - `r6_suggestion: <原始建议文本>`
  - `r6_position_factor: 0.85`（下游渲染/执行按 × 0.85 降仓）
- render_markdown v1.6 渲染的 R6 段已经能展示 `r6_strong_suggest: true` 的票与原文

**验收**（10-16 实跑）:
- watch_pool 4 只
- 命中 R6 strong_suggest 个股：605058.SH 澳弘电子，factor=0.85，suggestion 文本完整保留
- meta_r6.strong_suggests_accepted: 1

**未自动降仓**: D1 v1 仍标 `mode=dry_run`，需用户 review 后手动 flip。算法逻辑就位但执行受 D1_ALGORITHM_V1_IMPLEMENTED=False 守门。

**version**: v1.8 (2026-10-16) · R6 全市场级降仓信号（M5/M1 叠加）

**根因**: v1.7 闭环了 R6.M3 个股级（抽 ts_code → 单票 × 0.85 降仓）。但 R6.M5（马尔科夫 top1 预测偏差）和 R6.M1（数据源冲突）是**全市场级**信号，不针对个股，v1.7 没接。这是更上游的"该不该重仓"问题——比个股级降仓重要。

**变更**:
- `build_pools_and_rules` 末尾新增全市场级降仓逻辑：
  - 规则：`market_wide_factor = 0.7`（M5+M1 命中）、`0.85`（M5 命中）、`1.0`（不命中）
  - 应用：exec_pool/watch_pool 每票的 `base_mobile_ratio = prev × ind_factor(R6.M3) × market_wide_factor(R6.M5/M1)`
  - 写 `meta_r6.market_wide_factor` + `meta_r6.market_wide_signals{M5_hit, M1_strong_hit, rule}` 供 render 展示
- 每票加 3 字段：`base_mobile_ratio`（最终值）、`r6_position_factor`（个股级 1.0 或 0.85）、`market_wide_factor`（全市场级 0.7/0.85/1.0）
- `render_markdown` 显示 D1 v1.8 实算的 `market_wide_factor` + 规则说明

**验收**（10-16 fallback 跑）:
- exec_pool 1 票 base=1.0 mwf=1.0（无 R6 强 suggest）
- watch_pool 4 票：3 票 base=1.0（无 R6 强 suggest），1 票 **605058.SH 澳弘电子 base=0.85 r6_strong=True**（R6.M3 个股级生效）
- meta_r6.market_wide_factor=1.0（10-16 R6.M5/M1 未命中，10-14/15 的 M5 命中样本是设计目标，等生产跑）

**说明**: D1_ALGORITHM_V1_IMPLEMENTED 仍 = False；D1 v1.8 算法本体就位，等用户 review 手动 flip `mode=live`。

**version**: v1.9 (2026-10-17) · R3/R4 结构化整合段（用户钦定"LLM 层结合程序概率 + 新闻做分析"）

**根因**: 用户 2026-10-17 钦定产品方向——程序层算概率（emotion_cycle/node_predict 81% 命中），LLM 层结合 R3 群聊 + R4 新闻做客观分析。但 D1 落盘 meta 没有结构化 R3/R4 段，LLM 拿到也是"自由心证整合"。

**变更**:
- `main_decision.py` 新增 `_r3_r4_integration(trade_date)` 函数：
  - R3: sentiment_score / next_day_signal（verdict+direction+score）/ kol_summary（5 条，清洗 XML）/ resonance_top_themes（5 主题）
  - R4: top_events（10 条含 polarity+strength，清洗 XML）/ first_board_candidates_high（5 条 quality=high）
  - 4 个 LLM 整合提示（verdict_check / policy_catalyst / kol_corroboration / first_board_quality）——程序不算，留给 LLM 端判断
- D1 落盘 meta 新增 `r3_r4_integration` 段（schema_version="r3_r4_integration_v1"）
- render_markdown 新增 "## R3 群聊情绪 + R4 消息面整合" 段
- 微信原始 XML/HTML 清洗（`_clean`：去 `<?xml`、去 `<tag>`、截断补删残 `<`）

**验收**（10-16 fallback 跑）:
- R3: sentiment_score=61, verdict="中性（无明确次日方向信号）", 5 主题（创新药/网络安全/先进封装/AI视频/固态电池）, 5 KOL
- R4: 10 事件（中性/high 主导）, 5 首板高质量（日出东方 hit=4 / 中盐化工 hit=4 / 大晟文化 / 凯撒文化 / 洪田股份）
- LLM 整合任务 4 个 prompt 渲染可见

**设计边界**: 本段**不替 LLM 做判断**，只结构化抽取 + 给 LLM 提示任务。LLM 端 D1 消费 `meta.r3_r4_integration` 做 verdict/policy/kol/first_board 四类整合判断。

可内联推理或参考 `skills/exit_rules_derivation_v1/SKILL.md` 格式，**不委派** exit_rules skill 为独立 Agent。

### Step 6 — 可选二次核验（`_shared/`，不重写逻辑）

仅在 execution_pool 定稿前，对候选票做 last-minute 校验（`docs/01-系统现状全景.md` §1.3）：

| Skill | 场景 |
|-------|------|
| `skills/_shared/hithink-market-query` | 竞价前现价、涨跌停距离、停牌状态 |
| `skills/_shared/iwencai-query` | 硬条件复核（ST、连板高度、板块排名） |
| `@金融监管知识库`（v1.3 · 2026-08-06 新增） | 涨跌停规则合规、停牌/退市风险、跨市场监管差异（A 股/港股/美股/加密） |
| `@缠论形态识别`（v1.3 新增） | 候选票 30 日 K 跑 czsc，输出 `chanlun_signal: BUY1/BUY2/BUY3/SELL1/SELL2/SELL3/NONE`；**只有 BUY3 才加分 +0.03**（最强做多形态，2026-08-05 实测 002460 触三买） |
| `@大宗商品分析`（v1.3 新增） | 候选板块对应大宗商品月度动量检查，输出 `commodity_linkage_score: [-0.05, +0.05]`；与 R5 的 `commodity_linkage` 字段必须一致才有效 |

核验结果仅用于**剔除/降级**，不得用新数据重写 R2/R5 结论。突发公告可用 `news-search` / `announcement-search`（可选）。

### Step 7 — 组装、校验、落盘

1. 组装完整 `watchlist_plan.json`（字段见 § Output Schema）
2. **默认** `mode: "dry_run"`，`autonomous_trading_enabled: false`，`requires_user_confirmation: true`
3. pydantic 校验（失败则**不写盘**，报告错误字段）：

```bash
source .venv/bin/activate
python3 - <<'PY'
import json, sys
from pathlib import Path
from trading.schema.watchlist_plan import WatchlistPlan

date = sys.argv[1] if len(sys.argv) > 1 else "YYYYMMDD"
p = Path(f"data/plans/{date}/watchlist_plan.json")
plan = json.loads(p.read_text(encoding="utf-8"))
WatchlistPlan.model_validate(plan)
print("pydantic OK")
PY
```

4. 渲染 md（两份同内容）：

```bash
source .venv/bin/activate
python3 - <<'PY'
import json
from pathlib import Path
from src.plan.render_markdown import render_watchlist_plan_md

date = "YYYYMMDD"  # 替换
plan = json.loads(Path(f"data/plans/{date}/watchlist_plan.json").read_text(encoding="utf-8"))
md = render_watchlist_plan_md(plan)
Path(f"data/plans/{date}/plan.md").write_text(md, encoding="utf-8")
Path(f"chzl_kg/投研交易/盘前预案/{date}.md").write_text(md, encoding="utf-8")
print("md written")
PY
```

---

## 事故：决策退化为「纯 Python 量价规则版」（2026-09-30 用户打脸 · 必读）

**用户原话**：「我的一个硬性要求应该是要用大模型来做决策呀，怎么能用纯的量价关系的
Python 程序决策呢？那肯定会被骗的呀。」

### 真实事故链（四环，缺一不可）

1. **08:00 D1 LLM cron 每天 404** — `b6a7a8c23050` 未 pin provider，{provider: null}
   飘到已下线的 `https://api.minimaxi.com/anthropic/chat/completions` → 404。
   **实测：2026-09-14 ~ 09-30 每一个交易日均 `max_retries_exhausted / 404`**。
   即大模型主路径**早已全月失效**，只是没人发现。
2. **08:30 安全网落规则兜底** — `ensure_watchlist_plan.py` 只做 python fallback，
   从不重试大模型。
3. **兜底版伪装成正常预案** — 它写 `mode=live` +
   `agent_name="D1-main-decision (main_decision_v1, rule v1)"`，**不暴露"非大模型决策"**。
   用户看到的只是"D1 今天没给票"。
4. **08:30 早于上游落地** — R5(08:33:51)/R6(08:52:36) 尚未落盘，规则版无档位数据
   → 执行池必然为空 → 空池预案一路流到 P1 与 execute。

### 已落地修复（四处）

| # | 位置 | 修复 |
|---|------|------|
| 1 | cron `b6a7a8c23050`/`75bf632522ce`/`757e83acebd7` | `--provider volcengine-agent-plan --model deepseek-v4-flash-ga-260731 --pin`（禁止 provider 漂移） |
| 2 | `ensure_watchlist_plan.py` | **先重试大模型**（hermes CLI fresh context，默认 600s 超时），成功即止；失败才落兜底 |
| 3 | `main_decision.py` | 兜底版强制 `mode="fallback"` + `decision_source="python_fallback"` + `agent_name` 含「PYTHON FALLBACK · 非大模型决策」；加断言 `assert not (fallback and mode=="live")` |
| 4 | `render_markdown.py` | 兜底版 md 顶部 🚨 横幅 + frontmatter `decision_source`，人读一眼可见 |

另加 `_upstream_ready()`：R5/R6 未落盘时**拒绝产预案**（空池规则版比没预案更坏）。

### 排查口诀

**"D1 今天没给票" → 先查是不是大模型根本没跑，而不是先怀疑选股逻辑。**

```bash
# 1. 看决策来源（llm / rule_v1_standalone / python_fallback）
python3 -c "import json;p=json.load(open('data/plans/YYYYMMDD/watchlist_plan.json'));print(p['decision_source'],p['mode'])"
# 2. 看 08:00 主路径是否报错
ls -t ~/.hermes/profiles/canghai-plan/sessions/request_dump_cron_b6a7a8c23050_* | head -3
# 3. 看 D1 日志
cat data/logs/research_shell/YYYYMMDD/D1.log        # 08:00 主路径
cat data/logs/research_shell/YYYYMMDD/D1_llm_retry.log  # 安全网重跑
```

### 铁律

- **大模型是唯一决策者**；`d1_algorithm.py` 只能兜底占位，且必须**显眼自曝**。
- **agent 型 cron 必须 pin provider+model**，否则 provider 漂移到死端点会静默失败
  （drift 不报错、不告警，只是每天 404）。
- 预案里的 `decision_source` 字段是「今天谁做的决策」的唯一真相源，下游与 E1 都应消费它。

## Output Schema 要点

顶级字段必须齐全（详见 `docs/11-契约-盘前预案.md`）：

```json
{
  "schema_version": "watchlist_plan_v1",
  "trade_date": "YYYYMMDD",
  "mode": "dry_run",
  "agent_name": "D1-main-decision (main_decision_v1)",
  "generated_at": "ISO8601+08:00",
  "trading_style": "mainline_right_side_with_trend_pullback",
  "autonomous_trading_enabled": false,
  "requires_user_confirmation": true,
  "data_sources": { "...": "research_summary + fetch_manifest 审计" },
  "market_context": { "structure": "一句话结论", "...": "..." },
  "risk_limits": {
    "target_total_position_pct": 0.75,
    "max_positions": 5,
    "block_prefixes": [],  // 2026-08-06 起 300/688/920 全解禁(用户确认 QMT 端已可交易)
    "block_st": true
  },
  "execution_pool": [ "StockEntry × ≤5" ],
  "watch_pool": [ "StockEntry × 15-25" ],
  "rejected": [],
  "meta": {
    "position_cap_pct": 0.75,
    "position_cap_source": "R1-style",
    "r6_devil_advocate": {
      "hard_rejects_applied": [],
      "strong_suggests_accepted": [],
      "strong_suggests_overridden": [{ "id": "", "reason": "" }],
      "soft_notes": []
    }
  }
}
```

**StockEntry 枚举**（错一字校验失败）：
- `role`: `leader` / `core_midcap` / `core_largecap` / `elastic_core` / `watch_elastic` / `watch`
- `plan_status`: `execution_pool_hold` / `execution_pool_hold_add_on_pullback` / `watch_pool_only` / …
- `entry_rules[].type`: `trend_pullback_buy` / `leader_breakout`
- `exit_rules[].type`: `stop_loss_break` / `take_profit_hit` / `intraday_break_exit` / …
- `ts_code` 必须带后缀 `.SZ` / `.SH`；仓位为小数（0.14 = 14%）
- **`t1_game_analysis`**（v1.7 · 2026-09-04 新增 · 每只 execution 票必填，pydantic `extra=allow` 兼容）：`消息解读` / `预期差判断` / `买点结论` / `短线结构标签`——见 Step 4.5。缺失则该票不得进 execution_pool。

---

## md 模板（`render_watchlist_plan_md` 输出）

```markdown
---
date: YYYY-MM-DD
agent: D1-main-decision
generated_at: ...
position_cap: 0.70
execution_count: N
watch_count: M
mode: dry_run
---

# YYYYMMDD 盘前预案

## 一句话结论
风格 + 仓位上限 + 执行/观察数量 + R6 反证摘要

## 执行池(N 只)
### 1. 名称 ts_code(题材)
- **plan_status**: `...`
- **理由**: ...
- **stop_loss** / **take_profit**
- **entry_rules** / **exit_rules** 条数

## 观察池(M 只)
- ts_code 名称 — 理由

## R6 反证采纳
- hard_rejects / strong_suggest 记录
```

---

## Rules & Constraints（红线）

| # | 规则 |
|---|------|
| 1 | **fresh context**：只读 artifact，禁止携带 R1–R7 中间推理 |
| 2 | **禁止 override** R6 `hard_reject` |
| 3 | `execution_pool` ≤ 5（`max_positions` 铁律） |
| 4 | 单票 `max_position_pct` ≤ 0.15；单板块 ≤ 0.40；总仓 ≤ position_cap |
| 5 | `watch_pool` 15–25 只（低于 15 观察对照失效） |
| 6 | 每只 execution 须有完整 `entry_rules` + `exit_rules`（至少 1 条 `stop_loss_break`） |
| 7 | R6 `strong_suggest` 覆盖须写 `meta.r6_devil_advocate.strong_suggests_overridden[].reason` |
| 8 | `mode` 默认 `dry_run`；用户显式 flip 后才改 `live` |
| 9 | pydantic 校验失败 → **不写新文件**，告警用户 |
| 10 | **禁止**以 `d1_algorithm.py` / `main_decision.py` 为主路径 |

---

## 降级路径

| 上游状态 | D1 应对 |
|---------|---------|
| R1 死/骨架 | 默认震荡分化，`position_cap=0.50` |
| R2 死 | **拒绝出 plan** |
| R3/R4 死 | 忽略情绪/消息维度 |
| R5 死 | alpha/risk 默认 B，保守筛选 |
| R6 死 | 无反证，按最严风控 |
| `fetch_global_severity=3` | `mode=dry_run`，`autonomous_trading_enabled=false` |
| research_summary 缺失/过期 | 中止，不写 plan |

---

## mode 切换（用户 flip）

当前 T1' 批次 **`mode` 恒为 `dry_run`**。用户 review `plan.md` 满意后，手动将 JSON 内：

```json
"mode": "live",
"autonomous_trading_enabled": true,
"requires_user_confirmation": false
```

或由用户在对话中明确指令「今日 plan 切 live」。LLM **不得**自行切 live。

---

## 对照路径（非主路径，仅供 diff / fallback）

```bash
# 规则版 fallback（显式 opt-in；Hermes 主路径 skill: main_decision_v1）
source .venv/bin/activate
python3 scripts/plan/run_main_decision.py --date YYYYMMDD --fallback
# 或: CHZL_HERMES_FALLBACK=1 python3 scripts/plan/run_main_decision.py --date YYYYMMDD
# 产出: data/plans/YYYYMMDD/watchlist_plan.json（mode 仍 dry_run）
```

---

## Data Sources

### 退潮次日不空仓等死 (2026-09-29)

当 T-1 判退潮、次日定为空仓/极轻仓时，D1 预案必须写明：次日是否翻多由 `retreat_reversal_detection_v1` 盘中右侧判定（核心二证：广度≥0.55+昨涨停红盘率≥0.6，命中率90%；10:00-11:40每20分钟自动跑），确认后仓位 30%→45%。近一年31个退潮日 61% 次日翻多，竞价时点无法预判，只能盘中确认。

无独立数据源。纯 pull + 综合裁决；可选 `_shared` 二次核验（§ Step 6）。

### 数据源审计铁律 (2026-09-29)

报告里的"源不可用"必须区分三态，不得把调用失败写成源故障：`call_failed`（会话内失败/超时→重试或探针，不定性）、`not_yet_landed`（并行兄弟节点当时未落盘，只记时点不写 unavailable）、`source_down`（探针实测 HTTP 错误/连接拒绝才可定性）。高频误用：两融明细 T-1 盘前常已发布（0929 实测 0928 可用却误报 0924）、hithink 问财 OpenAPI（实测可用）。流水线收尾走 `scripts/research/reconcile_pipeline_status.py --patch-md`。

---

## Version History

| 版本 | 日期 | 说明 |
|------|------|------|
| v1 | 2026-07-04 | 骨架建立，pull-based 消费 research_summary |
| v1 P0 | 2026-07-05 | T1' parallel track D：fresh context LLM 主路径 prompt 结构冻结；`plan.md` 双份 md；默认 dry_run；禁止 d1_algorithm 主路径 |

---

## chzl_kg 人读 md 落盘（必需 · @render_kg_md_v1）

**契约来源**: `skills/_shared/render_kg_md_v1/SKILL.md`

除机读 JSON 落盘之外，本 skill 必须**同时**渲染一份人读 md 到 chzl_kg 供用户当日审阅。

### 落盘路径

```
chzl_kg/投研交易/盘前预案/{trade_date}.md
```

（目录若不存在，`mkdir -p` 创建。）

### frontmatter（必填，UTF-8 · Unix 换行）

```yaml
---
date: {trade_date YYYY-MM-DD}
agent: D1-main-decision
skill_version: main_decision_v1@1.0
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
# {trade_date 中文日期} · **主决策 / D1 盘前预案**

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
- skill: main_decision_v1
- artifact: data/.../{...}.json
- 生成耗时: N 秒
- model: {model 名}
```

### 落盘规则

1. **atomic write**: 先写 `.tmp` → `mv` 到目标（避免 Obsidian 抓半写）
2. **overwrite**: 同日重跑覆盖；若目标已存在先备份为 `.md.bak`
3. **失败不阻塞**: md 渲染失败**不**回滚 JSON artifact 落盘；skill status 写 `partial` 并在汇报中标注

### 验收

盘后 `test -f chzl_kg/投研交易/盘前预案/{trade_date}.md` 必须为 true；前 30 行满足 frontmatter schema。

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
- v1.2 (2026-08-07): D1 LLM 增强 — 仓位上限推导 + T+1 三档候选 + 不交易条件

---

## v1.2 新增 · 盘前预案过薄修复（P1-2 修复）

**问题根因**: 2026-08-05/06 实盘跑中,D1 输出的 `plan.md` 仅列 execution_pool 5 只票 + 简单 stop_loss,**没有**:
1. 仓位上限是怎么从 R1 风格 + R7 资金推出来的(用户看不到推导链,只能信)
2. T+1 候选(开仓/加仓/止损三档) → 次日 / T+1 行为没有预判
3. 不交易条件 → 何时**完全不开仓**(虽 R1 给的是 0.6 cap,但 D1 仍可输出"全平"决定),无明确红线

**v1.2 D1 LLM 增强契约**(硬约束,新增到 §Step 7 之前):

### 1. 仓位上限推导链(`position_cap_derivation`)

`watchlist_plan.json` 顶层新增字段(替代直接写死的 `position_cap_pct`):

```json
{
  "position_cap_derivation": {
    "r1_style_signal": "震荡分化",
    "r1_raw_cap": 0.60,
    "r7_northbound_strength": "neutral",   // strong_inflow / neutral / strong_outflow
    "r7_cap_adjustment": 0.0,              // strong_inflow +0.05, strong_outflow -0.10
    "r1_sentiment_score": 75,              // 来自 R1
    "emotion_cycle_phase": "贪婪",          // 来自 Step 0.5
    "emotion_cap_override": 0.60,          // 情绪联动:贪婪 → 顶格 0.60
    "r2_main_lines_count": 2,
    "main_lines_cap_multiplier": 1.0,      // 1 main=0.8, 2 main=1.0, 3 main=1.1
    "final_position_cap_pct": 0.60,
    "derivation_formula": "min(r1_raw=0.60, r7_adj=0.60, emotion_override=0.60) × main_lines_mult=1.0 = 0.60",
    "derivation_confidence": 0.85
  }
}
```

**公式**:
```
raw_cap = R1 风格给出的 cap
r7_adj = raw_cap + r7_cap_adjustment
emotion_override = 0.60 if phase==贪婪/狂热 else 0.55 if phase==极恐 else raw_cap
main_mult = {1: 0.8, 2: 1.0, 3: 1.1}.get(main_lines_count, 0.7)
final = min(raw_cap, r7_adj, emotion_override) * main_mult
clamp(final, 0.20, 0.85)
```

### 2. T+1 候选三档(`t1_candidates`)

`watchlist_plan.json` 顶层新增字段,结构:

```json
{
  "t1_candidates": {
    "open_position": [                     // T+1 计划开仓
      {
        "ts_code": "002050.SZ",
        "name": "三花智控",
        "trigger": "板块高开 < 2% 且龙头未封板",
        "entry_zone": [38.5, 39.2],
        "stop_loss": 36.5,
        "position_pct": 0.12,
        "rationale": "R2 leaders 龙一, R3 L1+L2 共振, R4 催化持续; T+1 关注分歧低吸"
      }
    ],
    "add_on_pullback": [                   // T+1 已持仓的加仓窗口
      {
        "ts_code": "688981.SH",
        "name": "中芯国际",
        "pullback_trigger": "回踩 5 日线且缩量",
        "add_size_pct": 0.05,
        "max_add_position": 0.20,
        "rationale": "T+0 已建底仓 0.10, 板块共振强, T+1 分歧给加仓机会"
      }
    ],
    "stop_loss_only": [                    // T+1 仅观察,触发即止损
      {
        "ts_code": "300442.SZ",
        "name": "润泽科技",
        "stop_loss_trigger": "破 20 日线 OR 板块跌出 top10",
        "stop_loss_price": 28.0,
        "current_position": 0.08,
        "rationale": "R6 distribution_alert 弱化,持仓谨慎"
      }
    ]
  }
}
```

**约束**:
- `open_position` 总和 ≤ `final_position_cap_pct × 0.5`(留一半加仓空间)
- `add_on_pullback` 每只 `add_size_pct` ≤ 0.05
- `stop_loss_only` 至少 1 条,否则视为 D1 风控漏检 → `status: partial`

### 3. 不交易条件(`no_trade_conditions`)

`watchlist_plan.json` 顶层新增字段,**任何一条命中则不开仓**:

```json
{
  "no_trade_conditions": [
    {
      "code": "R1_FAIL",
      "description": "R1 风格判断 confidence < 0.4 → 不开仓(主路径信号失效)",
      "active": false
    },
    {
      "code": "R6_HARD_REJECT_OVERFLOW",
      "description": "R6 hard_reject 命中候选池 > 30% → 不开仓(系统性风险)",
      "active": false
    },
    {
      "code": "R7_STALE",
      "description": "R7 staleness_status = unavailable → 不开仓(资金维度失效)",
      "active": true                       // 命中时, plan.md 顶部必须显式标 "⚠️ R7 数据失效,今日 no_trade"
    },
    {
      "code": "GLOBAL_SEVERITY_3",
      "description": "fetch_global_severity >= 3 → 不开仓(数据基础设施异常)",
      "active": false
    },
    {
      "code": "EMOTION_EXTREME_GREED",
      "description": "emotion_cycle.phase = 贪婪/狂热 AND main_lines_count = 0 → 不开仓(无主线 + 情绪过热)",
      "active": false
    },
    {
      "code": "USER_HOLIDAY",
      "description": "用户标记 holiday/出行 → 不开仓(可人工 override)",
      "active": false
    }
  ]
}
```

**硬约束**:
- `no_trade_conditions` 必须存在(即使全部 `active: false`)
- 任一 `active: true` → D1 输出 `mode: "no_trade"`,`autonomous_trading_enabled: false`,`execution_pool: []`,`watch_pool: []`(全空)
- plan.md **必须**在顶部展示"不交易条件清单 + 当前 active 项"(便于用户 review)

**降级**:
- R1 缺 → `R1_FAIL` 自动 `active: true`
- R7 缺 → `R7_STALE` 自动 `active: true`
- 全部不交易条件自动激活,plan 报 `no_trade_mode` 状态

### Step 2.7 — 跷跷板强对冲减仓（2026-09-06 周末会议纪要落地）

> 用户原话: "银行保险等大金融板块的上涨会抽血科技股, 形成'二选一'的格局"

调用 `@detect_seesaw_pairs_v1`（R7 子能力, `skills/_archive/detect_seesaw_pairs_v1/`）：
- 20 日相关 < -0.6 + 5 日方向反转 → 跷跷板对
- 主线对冲强度 > 0.7 → `position_cap_derivation.seesaw_penalty` 启用, cap ×0.5
- 主线对冲强度 > 0.5 → cap ×0.75
- 主线对冲强度 ≤ 0.3 → 不减仓

**写盘位置**: `position_cap_derivation.seesaw_penalty` 字段:
```json
{
  "position_cap_derivation": {
    "base_cap": 0.65,
    "seesaw_penalty": {"ratio": 0.5, "counter_sector": "大金融", "correlation": -0.78, "applied": true}
  }
}
```

### Step 4.6 — 预期差维度(2026-09-06 周末会议纪要落地)

> 用户原话: "周末发酵热点集中在银行与大科技, 农业板块存在预期差, 若板块走强, 建议推仓位参与"

调用 `@expectation_diff_v1`（`src/research/expectation_diff.py::judge_expectation_diff`）：
- 输入: `weekend_hot_topics`(从 R4 周末消息)+ `current_mainlines`(从 R2)
- 输出 `expectation_diff.level` ∈ {vacuum, aligned, diverging, contrarian}
- `level=diverging`(预期差向上) → 主线优先级 +1, 仓位上浮 10%
- `level=aligned`(共识已 priced in) → 不加仓, 持仓待涨
- `level=vacuum`(发酵真空) → 不押注
- 写盘: `expectation_diff` 字段在 `meta` 下

### Step 4.7 — 一字板预判(2026-09-06 用户方法论 · 盘前 09:00 用)

> 用户原话: "我有快速交易通道, 一字板本身没风险(9:20 前大单撤单可撤)。只顶首板/二板一字。三板+不用系统讲, 风险太大。"

调用 `@yizi_predictor_v1`（`src/research/yizi_predictor.py::predict_yizi_candidates`）：
- 输入: R4 top_events + R2 main_lines
- 核心因子（按权重排序）:
  1. 事件强度 high/medium/low（权重最大）
  2. 事件源数（多源交叉验证）
  3. 板块主流强度（R2 score）
  4. 个股业务相关度（top_pick_logic.business_relevance）
  5. 板数加权（首板 > 二板）
- 输出: `chzl_kg/投研交易/一字板预判/YYYYMMDD.json` + 盘前预案"一字板预判"节

**硬约束**（防止过拟合到特定场景）:
- ❌ **不硬编码**任何具体标的/板块名
- ❌ **不预判三板+**（用户不顶，系统跳过）
- ❌ **不自动下单**（只生成提示，用户快速通道顶单）
- ✅ **写盘后用户人工 review**，可顶可不顶

**板数过滤逻辑**:
- `board_stage=首板` → 候选保留，rank=重点关注
- `board_stage=二板` → 候选保留，rank=建议关注
- `board_stage=三板+` → 系统跳过（用户自行判断）

**预期效果**:
- 09:25 集合竞价前盘前预案输出"一字板候选 Top 10"
- 用户可在 09:25 第一时间用快速通道顶单
- 09:20-09:25 之间大单撤单可跟撤（低风险）

**验收**:
- 盘后 `tests/check_d1_plan_completeness.py` 校验:三个新字段必须存在;`no_trade_conditions` 中 `active: true` 时 `execution_pool: []`;`position_cap_derivation.derivation_formula` 非空
- 缺任一字段 → orchestrator 标 D1 失败

---

## Version History

| 版本 | 日期 | 说明 |
|------|------|------|
| v1 | 2026-07-04 | 骨架建立 |
| v1.1 (T1' parallel track D) | 2026-07-05 | fresh context LLM 主路径 + default dry_run + 禁 d1_algorithm 主路径 |
| v1.3 (Step 0.5) | 2026-08-06 | 宏观+情绪+行为金融 周期定位 |
| v1.10 | 2026-10-21 | 硬价位完整性(执行/观察/B计划必须带数字买区) + 点位表版渲染(render_plan_tables.py) |
| v1.2 (P1-2 修复) | 2026-08-07 | position_cap_derivation + t1_candidates 三档 + no_trade_conditions 硬约束 |
