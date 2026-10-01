---
name: analyze-stock-profile-v1
description: R5 个股画像 Agent skill — 对 R2 圈定的龙头候选（6-15 只），逐只出六维画像。核心方法：≥30 日日 K + 量价 + 中报预告叉乘 + 龙虎榜 + 事件时间线。禁止单日推断，禁止只看当日涨跌。禁止出买卖点（那是 D1 的活）。
---

# R5 个股画像 skill · 六维 + 30 日窗口

## 适用场景

R5 每日 07:45 产出每只候选票的 `chzl_kg/个股/{代码}/YYYYMMDD_画像.md` + 汇总 `chzl_kg/投研交易/个股画像/YYYYMMDD.md`。D1 消费 R5 六维评级组 execution_pool。

## 核心元原则

**至少 30 日日 K + 量价**（用户 2026-07-06 硬要求）。禁止只看当日涨跌就推断个股。单日涨跌是形态尾巴，30 日窗口才能判断"主升 vs 洗盘 vs 破位"。

**R5 不出买卖点**。只出 `alpha_grade`（A/B/C）+ `risk_grade`（低/中/高）+ 六维证据。D1 决定是否进 execution_pool + 具体买卖价。

## 数据源

| 层 | 数据源 | 用途 |
|:-:|------|------|
| 主 | tushare `daily`（30 日 K 线） | 量价基础 |
| 主 | tushare `daily_basic`（PE/PB/换手率） | 估值分位 |
| 主 | tushare `moneyflow_dc`（主力资金） | 筹码结构 |
| 主 | tushare `top_list`（个股龙虎榜） | 席位追踪 |
| 主 | tushare `stk_holdernumber`（股东户数） | 筹码变化 |
| 主 | 东财中报预告 API `RPT_PUBLIC_OP_NEWPREDICT` | 业绩验证 |
| 主 | tushare `anns_d`（公告） | 事件时间线 |
| **主** | **`iwencai-query` NL 复合查询** | **筹码/事件/技术面交叉验证（硬调用，非可选）** |
| **主** | **`data/cache/chart_vision_latest.json` (chart_vision cron 快照)** | **多周期视觉技术判定 (每票必读,非可选)** |
| 备 | hithink-market-query（均线/资金流） | 高效获取技术指标 |
| 备 | xtick `/doc/kline/market`（K 线备源） | tushare 挂时降级 |

### iwencai NL 查询协议（硬要求）

对 **每只 R2 候选票**，必须用 `iwencai-query` 做 NL 复合查询，至少覆盖以下三组之一：

| 场景 | 查询语句 (中文) | 期望返回字段 |
|------|----------------|------------|
| 业绩预增 | `<ts_code> 中报预增 原因` | 预告类型, 净利均值, 变动原因 |
| 板块龙头 | `<ts_code> 所属概念 龙头 资金流向` | 概念板块, 主力净额, 排名 |
| 筹码集中 | `<ts_code> 股东户数 变化` | 股东数环比, 集中度 |
| 事件线索 | `<ts_code> 最近利好 最近利空` | 近 30 日公告, 事件时间 |

**调用时机**：拉完 tushare 主数据后、写 md 前调用。每只票至少 1 次 iwencai 查询（NL 交叉验证），禁止完全跳过。iwencai 返回为空时写 `iwencai=none` 到六维画像 footer，不阻塞分析。

### chart_vision 协议(硬要求 · 从 MCP 直调改为 cache 消费 · 2026-07-08)

**背景**: MCP `chart_vision_analyze` 是同步串行调用 · 单次 30-45s · sub-agent 串跑 12 只必 600s 超时。
改为 cron 批量脚本 `scripts/fetch/run_chart_vision_snapshot.py` 定时并发跑,agent 消费缓存。

**消费入口(sub-agent 侧)**:

```python
import json, pathlib
cv = json.loads(pathlib.Path("data/cache/chart_vision_latest.json").read_text(encoding="utf-8"))
# cv["generated_at"] · cv["ok"] / cv["n"] · cv["results"][ts_code] = {bias, confidence, summary, signals, action, ...}
```

**新鲜度红线**:
- ≤4h → 视为 fresh · 直接消费 · degraded=false
- 4-24h → 仍可消费 · 但 markdown 里标"技术判定 T-1 快照" · degraded 不改
- >24h → 视为 stale · 标 partial · 让 orchestrator 手动重跑 `scripts/fetch/run_chart_vision_snapshot.py`

**票池覆盖不到时的降级**: 缓存里没有该 ts_code → skill_report 里写 `chart_vision_universe_gap=[ts_code,...]` 让 orchestrator 补票池 · 本次 sub-agent 用 120 日 K 手工指标顶上(位置分位/量能/均线) · 不阻塞。

**cron 调度**: `chart_vision_snapshot_2x_daily` (job_id `fd61c030d180`) · 07:30 / 15:30 两档 · workdir 沧海巨浪根。手工触发 `bash ~/.hermes/scripts/canghai_chart_vision_snapshot.sh`(约 90s)。

**vision 判定字段写入"技术面"子段**:
- `bias`(偏多/偏空/震荡) + `confidence`
- `summary`(2-4 句综合判断)
- `signals[*]`(type/period/price_hint/reason)
- `action`(一句话操作建议)
- 补 30/60/120 日手工指标(均线/位置分位/量能变化)双验

## 六维画像

### 维度 1：催化背景（继承 R4）

- 该股在 R4 硬事件表中的位置
- 事件极性 + 强度
- valid_period 到期倒计时
- 如果 R4 未覆盖 → 标 `catalyst_grade=none`

### 维度 2：筹码结构

- **30 日主力资金流**（tushare moneyflow_dc buy_lg + buy_elg 累加）
- **股东户数环比**（stk_holdernumber，季度数据，看筹码集中度）
- **龙虎榜历史**（近 30 日上榜次数 + 席位类型：机构/游资/散户）
- 输出 `chip_grade=A/B/C`

### 维度 3：板块联动

- 该股所属主要板块（≤ 2 个）
- 板块 30 日累计涨幅 vs 该股 30 日累计涨幅
- 板块内排名（涨幅 / 成交额）
- 与 ETF 同步度（如属主线，ETF 30 日走势）
- 输出 `board_grade=A/B/C`

### 维度 4：财务与估值

- **中报预告数据**（东财 API）：PREDICT_TYPE + PREDICT_HBMEAN + CHANGE_REASON_EXPLAIN
- **PE-TTM 分位**（daily_basic pe_ttm 在近 3 年百分位）
- **PB 分位**
- **主营构成**（hithink-business-query，可选）
- 输出 `fundamental_grade=A/B/C`

### 维度 5：技术形态（30 日窗口 · 关键升级）

**必须拉 ≥ 30 日日 K + 量价**（硬要求）。从 30 日数据算：

1. **30 日累计涨幅**
2. **位置分位**（当前价在 30 日高低区间的 %）
3. **均线状态**（MA5/10/20/30 排列）
4. **量价配合**（涨幅 top 3 日成交额 vs 30 日均量 = 放量倍数）
5. **形态判定**：↗ 持续上 / ↘ 持续下 / → 横盘 / V 反弹 / M 见顶回 / 波动

**四色四量交叉**（可选，如 xTick 在线）：
- 3 红 → 4 红转强
- 紫转红
- 四量全红

输出 `tech_grade=A/B/C` + 形态描述（散文体 1 段）。

### 维度 6：研报与机构关注

- 近 30 日券商研报数量
- 目标价中位数 vs 现价（校准器：说 -30% 大概率真 -30%，说 +50% 打折看）
- 机构调研次数（tushare `stk_surv`）
- 卖方盲区标记（0 研报 = **潜在 alpha**，如 002396 星网锐捷 2026-07-03 4 连板案例）
- 输出 `research_grade=A/B/C`

## 事件时间线（关键升级 · 2026-07-06）

对每只票，输出**近 60 日事件时间线**：

| 日期 | 事件类型 | 事件描述 | 对应 K 线动作 |
|:-:|:-:|------|------|
| 2026-05-15 | 中报预告 | 净利 +200% | 次日 +5% |
| 2026-06-10 | 龙虎榜 | 章盟主 +8000 万 | 3 日累计 +12% |
| 2026-07-03 | 涨停 | 4 连板 | 板块内龙头 |

时间线让 D1 能"看到"该股的事件驱动路径。

## md 输出结构（每只票一份）

必须包含（顺序）：

1. YAML frontmatter（date, agent=R5, skill_version=v1, ts_code, name, generated_at, confidence, degraded, data_sources, input_freshness）
2. 一句话结论（≤ 100 字，例："600418 江淮汽车：华为汽车 R5 车型催化，六维评级 A/A/A/B/A/B，alpha_grade=A，risk_grade=中"）
3. **六维画像表**（催化/筹码/板块/估值/技术/研报 × A/B/C）
4. **30 日日 K 分析**（累计/位置/均线/量价/形态，散文体 1 段）
5. **事件时间线**（近 60 日）
6. **中报预告叉乘**（如有 API 数据）
7. **龙虎榜历史 + 席位分布**
8. **风险点清单**（≤ 3 条，标出可能证伪的信号）
9. 数据源审计表（≥ 5 行）
10. Sub-Agent 元数据

## md 汇总（个股画像目录一份）

`chzl_kg/投研交易/个股画像/YYYYMMDD.md` 汇总所有票的一句话结论 + 六维评级，方便 D1 快速消费。

## 🚨 C 档踏空风险标注（2026-07-08 复盘新增）

### 问题：C 档"勉强"标签导致踏空成本高

**2026-07-08 实战教训**：300017 网宿科技(+19.97% 涨停)被标为 C 档"勉强" → 主体逻辑是对的故事(CDN+AI 推理需求)但 R2 主线相关度弱 → D1 未入池 → 踏空 20cm。

**C 档不是"不买"的同义词，是"需要更多条件"的简写**。

### 规则变更

| 旧理解 | 新理解 |
|---|---|
| C = 不值 | C = 入池价值低但保留观察 |
| C 档票不写买入理由 | C 档票必须写"如果...则值得..."的条件句 |
| C 档不进 md 的思维链 → 被下一轮完全遗忘 | C 档票必须保留思维链（买入理由/风险/假设） |

### C 档三态区分

| 判定 | 标签 | 处置 |
|---|---|---|
| 逻辑弱 + 走势弱 | `C·弱` | 观察池不推荐 |
| 逻辑弱但走势强 → 可能我漏了 | `C·踏空观察` | **必须写条件句**，进 watchlist |
| R6 硬否决 | `C·否决` | 严格排除（同现） |

**条件句格式**：`如果 {触发条件}，则 {方向} 可能成立，因为 {逻辑}。观察价 {price}，确认信号 {signal}。`

## 红线

- ❌ 不出 entry/exit price（那是 D1 的活）
- ❌ 不出仓位建议
- ❌ 不覆盖 R2 未圈定的票
- ❌ 只看当日推断（硬要求 ≥ 30 日窗口）
- ❌ 卖方研报"目标价"当买入信号（研报是下限校准器）

## Pitfalls

1. **30 日窗口下限**（用户硬要求）：`--lookback 45` 拉 45 自然日保证 ≥ 30 交易日。禁止 10 日窗口。
2. **卖方盲区 = alpha 信号**：0 研报 + 中报预告爆表 + 深主板可 auto = 高 alpha（2026-07-03 星网锐捷案例）。这种要单独档次。
3. **中报预告 API 去重**：同一公司有 3 条记录（归母/扣非/EPS），用 SECUCODE 去重。
4. **龙虎榜诱多**：机构单日大买必须 T+1 早盘验证。R5 只列历史席位，验证在 R7。
5. **hithink-market-query 优先于 tushare 拉均线**：hithink 直接给 MA5/10/20/50/100/200，tushare 要自己算，效率差。

## 参考

- `core-alpha-trading-framework`（六维筛选原则）
- `analyze-capital-flow-v1`（R7，筹码结构上游）
- `canghai-pre-open-plan`（D1 消费 R5 alpha_grade 路径）
