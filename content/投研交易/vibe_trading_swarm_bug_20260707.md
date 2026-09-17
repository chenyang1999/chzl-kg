---
date: 2026-07-07
category: MCP bug tracking
target: vibe-trading run_swarm
severity: P2(阻塞多空辩论 swarm,不阻塞其他工具)
status: reproducible
---

# vibe-trading `run_swarm` `content_filter_triggered` bug 追踪

## 复现

- 时间: 2026-07-07 05:03 UTC
- run_id: `swarm-20260707-050305-c923dbf5`
- 预设: `investment_committee`
- 变量: `target=688981.SH, market=china_a`
- 结果: `status=failed`,7.1 秒内两个上游 agent(bull_advocate/bear_advocate)同时失败

## 错误堆栈

```
task-bull/bull_advocate: 'LLMResponse' object has no attribute 'content_filter_triggered'
task-bear/bear_advocate: 'LLMResponse' object has no attribute 'content_filter_triggered'
task-risk: Blocked: upstream not completed (task-bull=failed, task-bear=failed)
task-decision: Blocked: upstream not completed (task-risk=blocked)
```

## 诊断

- 属于 vibe-trading swarm engine 与 LLM provider adapter 的**属性契约不匹配** bug
- `LLMResponse` 对象缺少 `content_filter_triggered` 属性,swarm 的 orchestrator 在检查内容过滤时抛 AttributeError
- 应该是 vibe-trading 更换 LLM adapter(或升级到新 provider)后未同步更新 swarm 检查逻辑
- **所有 29 个 swarm 预设可能都受影响**(需实测 `technical_analysis_panel` / `sector_rotation_team` 是否同 bug)

## 影响面

| 能力 | 是否可用 |
|------|---------|
| 单 skill 调用 (`load_skill`) | ✅ 正常 |
| 数据工具 (`get_block_trades` 等 54+) | ✅ 正常 |
| `run_swarm` 4-agent 投委会 | ❌ 失败 |
| `run_swarm` 6-agent 技术面板 | ⚠️ 未测,预期同样失败 |

## 沧海端处置

1. **不阻塞 R7/R5 集成** — 大宗+两融+龙虎榜工具全部可用,今日 patch 有效
2. **D1 顶层聚合不引入 swarm** — 暂不把 `investment_committee` 作为对照,直到 bug 修复
3. **P3 待办** — 起 GitHub issue 反馈给 https://github.com/HKUDS/Vibe-Trading

## 复测计划

- 每周一次实测 `run_swarm(investment_committee, 688981.SH, start_only=False)`
- 一旦返回 completed,复评估 swarm 是否作为 D1 对照实验入选

## 建议 issue 文案(草稿)

> Title: `run_swarm` fails immediately with `'LLMResponse' object has no attribute 'content_filter_triggered'` across all presets
>
> All 4 tasks in `investment_committee` preset fail within 7s of start. Both `bull_advocate` and `bear_advocate` raise `AttributeError: 'LLMResponse' object has no attribute 'content_filter_triggered'`. Downstream `risk_officer` + `portfolio_manager` blocked. Reproducible with `variables={"target": "688981.SH", "market": "china_a"}`. Likely a LLM adapter contract mismatch after a provider upgrade; swarm engine checks a field the new response object doesn't expose.
