# 12 模块 gap 诊断表 · 2026-07-06

session 高质量深度 vs profile cron 实际产出的差距诊断。目标：让 profile 一次调用直出 v7 级 md。

## 现状盘点（20260706 md 存在情况）

| # | 模块目录 | 20260706.md | 行数 | session 特征词 | 深度评级 | 缺什么 |
|:-:|--------|:-:|:-:|:-:|:-:|------|
| 1 | 风格研判 | ✅ | 364 | 30日+叉乘+推理+22表+18引用+47emoji | 🟢 v7 | — |
| 2 | 主线研判 | ✅ | 127 | 叉乘+推理+4表+0引用 | 🟡 v3 | 30日窗口/散文体/emoji 状态标注 |
| 3 | 消息面 | ✅ | 167 | 叉乘+推理+4表+3引用 | 🟡 v3 | 8 条硬事件 + 板块极性叉乘 |
| 4 | 群聊情绪 | ✅ | 152 | 叉乘+推理+10表+3引用 | 🟡 v3 | L1+L2 共振主题 + 群名匿名化规范 |
| 5 | 反证 | ✅ | 129 | 叉乘+推理+4表+3引用 | 🟡 v3 | 四象限负面识别 + 6 类反证模式落地 |
| 6 | 盘前预案 | ✅ | 225 | 叉乘+推理+33表+9引用+27emoji | 🟢 v6 | 数据源审计 9 行 + 散文体开场 |
| 7 | 资金面 | ❌ | — | — | 🔴 缺产出 | 昨日前十 5 日走势追踪 |
| 8 | 个股画像 | ❌ | — | — | 🔴 缺产出 | ≥30 日 K + 量价 + 中报 + 龙虎榜 |
| 9 | 复盘记录 | 部分（复盘_YYYYMMDD） | 58 | — | 🟡 E1 待跑 | 双重复盘 + missed_alpha |
| 10 | 周度进化 | ❌ | — | — | 🔴 缺产出 | E2 周五触发即可 |
| 11 | 午盘briefing | ❌ | — | — | 🔴 缺产出 | P2 11:35 触发 |
| 12 | 主线板块外 | 部分 | — | — | 🟡 R2 覆盖 | — |

## 根因

`src/research/orchestrator.py` L12-27 明确写：
> "cron 无 LLM 会话这个环境约束下，对 CANONICAL §4.3 delegation 机制做的最小必要替代"

= R1-R7 全部在跑 `src/research/r*.py` **确定性 Python 规则**，不是 LLM sub-agent。
= 硬编码 `confidence=0.55` / 无叉乘推理 / 无自然语言 md 输出。
= 2026-07-05 用户已否决"最小必要替代"路径，宪法级违规。

## 修复路径（本次一口气交付）

| 层 | 修复动作 | 交付物 |
|:-:|------|------|
| skill | 固化 6 R + 1 D + 1 池 方法论 | 8 个 SKILL.md 全量落盘 |
| 编排 | Python orchestrator → shell wait + hermes CLI | `scripts/research/run_research_shell.sh` |
| 数据源 | 补充 iwencai + tushare 板块 + 公众号反查 | stock-pool-mining-v1 skill |
| 深度约束 | R5 强制 ≥30 日 K + 量价 + 事件时间线 | analyze-stock-profile-v1 skill |
| 验收 | 手工 dry-run 12 md 生成 | 明日 07:30 cron 验证 |

## 深度对齐目标

每份 md 必须包含（对标风格研判 v7）：

1. YAML frontmatter（date/agent/skill_version/generated_at/confidence/degraded/data_sources/input_freshness）
2. 一句话结论（自然语言，不许 JSON dump）
3. 30 日窗口分析（禁 T-1 单日）
4. 叉乘章节（叙事×走势/资金×走势/基本面×技术）
5. 数据源审计表（≥5 行，含日期+来源+状态 emoji，禁时分秒）
6. 反证段（说明"如果错，什么信号会先出现"）
7. sub-agent 元数据（generated_at/degraded_flag/tokens_used）
