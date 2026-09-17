# 风格研判(R1 每日产出)

R1 风格 Agent 每天开盘前 07:30 写入这里。

**内容**:今日市场是什么风格,能不能做,做什么方向。

**Schema**:
```yaml
---
date: YYYY-MM-DD
agent: R1-style
style: 连板情绪型 / 主线扩散型 / 震荡分化型 / 防御观望型 / 崩溃退潮型
sentiment_score: 0-100
main_lines_count: 0-3+
position_cap_suggestion: 0-0.8
data_health_severity: 0/1/2/3
---
```

**规格**:见 `docs/agents/R1-风格Agent.md`

**不做**:❌ 不推板块 ❌ 不推个股 ❌ 不做技术分析 ❌ 不做估值
