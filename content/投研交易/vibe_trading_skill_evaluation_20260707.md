---
date: 2026-07-07
author: hermes-canghai
category: 投研工具评估
target: vibe-trading MCP · 78 skill / 29 swarm / 54+ tool
---

# vibe-trading MCP 深度评估纪要 · 2026-07-07

## 摘要一句话

**vibe-trading 不是"数据源",而是完整投研工作台。78 个产品级 skill 覆盖 A 股风控 / 缠论 / 艾略特 / 因子 / 财报 / 估值 / 事件驱动等,产品打磨程度远超我们自研的任何 skill。原先在 MCP 全景图中把它标为"通用 54 工具"是严重低估。**

---

## 一、`financial-statement` skill 评估

### 内容规模
- 篇幅约 **200 行 markdown**,覆盖三表勾稽 / 盈利质量 / 12 大红旗 / 杜邦分析
- 提供 **公式 + 阈值表 + 输出模板** 三层封装

### 硬核干货清单
| 模块 | 关键交付 | 我们自研有没有 |
|------|---------|--------------|
| 三表勾稽 | 3 条数学公式(净利→留存/收入→应收/BS→CF)+ Python 验证片段 | ❌ 没有 |
| 现金流质量矩阵 | CFO/CFI/CFF 六种组合状态分类 | ❌ 没有 |
| 盈利质量评分卡 | 5 项加权评分 + 阈值 | ❌ 没有 |
| **12 大红旗** | **存贷双高 / 应收暴增 / 商誉炸弹 / 资本化率 / 关联交易... 每项含检测方法 + 严重度** | ❌ 完全缺失 |
| 杜邦三级/五级分解 | 行业 ROE 对比表(白酒 25-30% / 银行 10-14%) | ❌ 没有 |

### 结论
- ✅ **建议直接引用**:在未来的 R5 六维"财务与估值"维度里,`@` 挂载 `mcp_vibe_trading_load_skill("financial-statement")` 作为深度分析入口
- ✅ **提升点**:12 大红旗可以直接作为 D1 execution_pool 的**hard_reject 规则**(比如商誉/净资产 > 30% + 存贷双高)
- ⚠️ **注意**: 该 skill 强调"银行/保险不适用",R5 遇到银行股要绕开
- 🎯 **落地路径**:P0 - 把 12 大红旗写进 R6 `analyze_devil_advocate_v1` 反证 skill 的 checklist

---

## 二、`valuation-model` skill 评估

### 内容规模
- 篇幅约 **250 行 markdown**,覆盖 DCF/DDM/SOTP 绝对估值 + PE-Band/PB-ROE/EV-EBITDA 相对估值 + 10 大估值陷阱
- 内容为英文(需要翻译衔接) · A 股参数已本地化(Rf=2.5%, ERP=5-7%)

### 硬核干货清单
| 模块 | 关键交付 | 我们自研有没有 |
|------|---------|--------------|
| DCF 4 步法 | FCFF 预测 + WACC 计算 + TV 双方法 + 敏感性矩阵 | ❌ 没有 |
| WACC 参考区间 | 5 大行业 WACC + β 对照表 | ⚠️ `@bayesian-intrinsic-growth-valuation` 有部分 |
| **10 大估值陷阱** | **周期股低 PE 陷阱 / 高 PEG 增长 / 商誉炸弹 / 应收陷阱 / 资本化 / 一次性收益...** | ❌ 完全缺失 |
| 估值方法决策树 | 按公司类型自动分派 DCF/DDM/SOTP/PS | ❌ 没有 |
| PB-ROE 四象限 | 明确"低 PB 高 ROE = 最佳买入" | ⚠️ `@gf-dma-health-index` 部分交叉 |

### 结论
- ✅ **建议引用**:R5 六维"估值安全"维度的**顶层框架**,取代当前松散的三个 `@` 估值 skill
- ⚠️ **本地化差**:全英文,A 股股民语境需要翻译层
- ⚠️ **冲突**:与自研 `@bayesian-intrinsic-growth-valuation` / `@tam-adj-peg` / `@gf-dma-health-index` 有职责重叠
- 🎯 **落地路径**:P1 - 用 vibe-trading valuation-model 作为**决策树入口**,自研 3 个估值 skill 作为**具体方法实现**

---

## 三、能力对齐总表(vibe-trading vs 沧海自研)

| 能力面 | vibe-trading | 沧海自研 | 处置建议 |
|--------|--------------|----------|----------|
| A 股 ST 风控 | ⭐ `ashare-pre-st-filter`(20 页产品级) | 无 | **直接引用** |
| 财报三表分析 | ⭐ `financial-statement` | 无 | **直接引用 · 12 红旗进 R6** |
| 估值方法学 | ⭐ `valuation-model`(DCF/DDM/SOTP) | 3 个专用 skill | vibe 做决策树,自研做实现 |
| 缠论/艾略特/SMC | ⭐ 6 个 pattern skill | 无 | 待 P2 评估 |
| 因子研究 | ⭐ `factor-research` + `alpha-zoo`(Kakushadze 101/GTJA 191/Qlib 158) | 无 | 待 P2 评估 |
| 事件驱动/PEAD | ⭐ `earnings-forecast` + swarm | R4 消息面 v1 | 融合 |
| **WeFlow 群聊** | 无 | ⭐ R3 200-300 群 | **沧海独有 alpha** |
| **公众号消息面** | 无 | ⭐ R4 hcallmedia | **沧海独有 alpha** |
| **四色四量转强** | 无 | ⭐ canghai_sise | **沧海独有 alpha** |
| 大宗交易/两融 | ⭐ `get_block_trades` + `get_margin_trading` | 无 | ✅ **已于今日 patch 进 R5/R7** |
| 多 Agent 委员会 | ⭐ 29 swarm 预设 | D1 顶层聚合 | 待 P2 复测 swarm bug |

---

## 四、行动清单(post-evaluation)

### P0 · 已完成(2026-07-07)
- [x] R7 `analyze_capital_flow_v1` 补 `get_block_trades` + `get_margin_trading` + `get_dragon_tiger` 硬调用
- [x] R5 `analyze_stock_profile_v1` 补大宗+两融+龙虎榜三源交叉核实
- [x] 本评估纪要落盘

### P1 · 待办(本周内)
- [ ] R6 `analyze_devil_advocate_v1` 加入 vibe-trading **12 大红旗** 作为 hard_reject checklist
- [ ] R5 财务与估值维度改造为"vibe-trading 决策树 + 自研估值 skill 实现"双层结构
- [ ] MCP 数据源全景图更新(P3)

### P2 · 待办(下周)
- [ ] 评估 `factor-research` + `alpha-zoo` 因子库能否作为 R2 板块排序的因子面
- [ ] 评估 6 个 pattern skill(缠论/艾略特/SMC)能否嵌入 R5 技术形态维度
- [ ] 复测 `run_swarm` 修复情况(投委会 4 agent + 6 agent 技术面板)

### P3 · 待办(下下周)
- [ ] `investment_committee` swarm 作为 D1 顶层聚合的对照实验(如 bug 修复)
- [ ] 起 issue 反馈 `content_filter_triggered` bug 给 vibe-trading 社区

---

## 五、关键洞察

1. **定位差异**: vibe-trading = 通用投研骨架(A 股 + 港股 + 美股 + 加密),我们 = A 股情绪 alpha + WeFlow 独占 · **互相嵌入而不是并行造轮子**
2. **知识产品化 gap**: vibe-trading skill 达到 SKILL.md 20+ 页 · 含公式 / 阈值 / 伪代码 / 输出模板 · 是**社区打磨的产物**;我们的 R1-R7 skill 还处于契约级抽象,产品化程度差 2 个身位
3. **可复制方向**: 学习 vibe-trading 的 skill 写法 — **每个技术概念都要落地到公式 + 阈值 + 检测方法 + 输出模板** 四件套
4. **不可复制方向**: WeFlow 群聊 / 公众号 / 四色四量 / QMT 实盘执行 → 沧海独有护城河,vibe-trading 完全没覆盖

---

## Version History

- v1.1 (2026-07-07 evening): 补充 `event-driven` + `factor-research` 评估;R6 未落地(仅存 memory 中);行动清单细化。
- v1 (2026-07-07): 首次评估 · 覆盖 financial-statement + valuation-model + 能力对齐总表

---

## 附录 A · `event-driven` skill 评估(2026-07-07)

### 定位
- vibe-trading 用于**回测框架**内的事件信号处理:CSV schema + 时间衰减 + 与技术信号加权
- 参数体系:`alpha=0.6`(tech 60% + event 40%)、`decay_lambda=0.1`(10 日衰减到 37%)、`event_lookback=30`、`min_score_threshold=0.2`
- 事件类型 6 类:earnings / macro / policy / sentiment / insider / technical_break;每类含**影响时长表**

### 与自研 R4 消息面对比
| 维度 | vibe-trading `event-driven` | 自研 R4 `analyze_news_impact_v1` |
|---|---|---|
| 输入源 | 通用 `read_url` + LLM 打分 | 公众号 + 财联社 + 突发新闻(hcallmedia)|
| 打分方式 | -1.0 ~ 1.0 标准化 prompt | 分类到板块/个股 + 硬事件催化清单 |
| 用途 | **回测**(信号引擎)| **盘前预案**(选股) |
| 时间衰减 | 指数衰减 `exp(-λ·days)` | 无(默认当日) |
| 冲突检测 | 无 | 有(多源交叉验证) |

### 结论
- ✅ **正交互补**:vibe-trading 服务**回测**,R4 服务**盘前预案**,不冲突
- ⚠️ **可借鉴**:R4 应引入**时间衰减**(3 日前的公众号消息按 exp(-0.15·days) 打折,7 日归零)
- 🎯 **落地路径**:P1 - R4 加入 event_type + score + decay 三字段;时间衰减 λ=0.15(比 vibe 快)

---

## 附录 B · `factor-research` skill 评估(2026-07-07)

### 定位
- **回测框架内**:IC/IR + 分位数回测 + 因子组合(等权/IC 加权/正交化)
- 依赖 vibe-trading `factor_analysis` 工具 + `alpha-zoo`(450+ 预置 alpha)
- **产品级严谨性**:AlphaMeta schema · 形状校验 · NaN/inf 过滤 · 前瞻偏差检测 · 行业中性化 · 幸存者偏差

### IC/IR 阈值表(直接可用)
| 指标 | 阈值 | 含义 |
|---|---|---|
| IC 均值 | > 0.03 | 基础预测力 |
| IC 均值 | > 0.05 | 强预测力 |
| IC 均值 | > 0.10 | 异常高 · 查前瞻偏差 |
| IR | > 0.5 | 稳定有效 |
| IC > 0 占比 | > 55% | 方向稳定 |

### 与自研 R2 主线板块的关系
- 当前 R2 用 tushare 板块涨跌 + 情绪聚类,**没有因子回测层**
- vibe-trading `factor-research` 可作为 R2 的**因子面板选票器**(哪个动量因子/成交量因子/换手因子在过去 60 日 IR 最高,就用它排序板块内个股)

### 结论
- ✅ **强烈建议引用**:P1 - R2 加入 `factor-research` 作为板块内个股排序的选票器
- ✅ **alpha-zoo 值得单独评估**:Kakushadze 101 / GTJA 191 / Qlib 158 = 450 个预置 alpha,可直接跑 IC 筛选出适合 A 股的
- ⚠️ **要求**:R2 需要提供 factor CSV + return CSV,前者可从 tushare `stock_factor` 拉取
- 🎯 **落地路径**:
  1. R2 orchestrator 每周日夜跑一次 `factor_analysis` 在 30 个板块 top 5 个股上,找出 top 5 IR 因子
  2. 次日 R2 用这 5 个因子排序板块内候选,取 top 3 送 R5 六维画像

---

## 附录 C · P1 落地待办(注入 sprint)

- [ ] **R6 反证 skill 落地**:创建 `skills/analyze_devil_advocate_v1/SKILL.md`,内含 vibe-trading 12 红旗 checklist + 10 大估值陷阱 + ST 双轴风险 · 作为 D1 hard_reject 前置层
- [ ] **R4 加时间衰减**:引入 `event_type` + `score(-1~1)` + `decay_lambda=0.15` 三字段,消息面 CSV 落 `data/research/YYYYMMDD/R4_events.csv`
- [ ] **R2 因子面板选票**:每周日夜跑 `factor_analysis` 在 A 股全池,产出 `data/factor_snapshot/YYYY-MM-DD/top_ir_factors.json`,R2 消费此文件排序个股
- [ ] **R5 估值层重构**:改造为"vibe-trading valuation-model 决策树 + 自研 3 个估值 skill 实现"双层
- [ ] **每票财报三表体检**:R5 六维"财务与估值"维度,新增 `financial-statement` 12 红旗检出结果字段

