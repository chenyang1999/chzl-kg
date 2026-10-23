---
name: trade_discipline_v1
description: 交易纪律自检（十条铁律+开仓资格+禁止清单+情绪切换表）— 供 D1 决策前强制自检、E1 复盘过错本；横切 skill
agent_owner: 横切能力
version: v1
status: production
category: trading/纪律
created: 2026-09-04
updated: 2026-09-08
spec: chzl_kg/投研交易/游资风格/新生代游资交易纪律.md
---

# trade_discipline_v1 · 交易纪律自检（横切）

**归属**: 横切 skill — D1 决策前强制自检、E1 复盘过错本、execute 执行前纪律校验
**目的**: 把《新生代游资交易纪律》的硬规则落成可勾选 checklist，违反即减额/拒开
**算法依赖**: `src/research/core_judge.py`（核心判定）+ `src/plan/risk_reward.py`（盈亏比/仓位）

## 用法

D1 生成 execution_pool 前，**必须**对候选逐票跑纪律自检（十条铁律 + 开仓资格）。E1 复盘时用同一 checklist 核对「是否违反」。

## 一、十条铁律（违反 → 当天额度清零）

| # | 铁律 | D1 落盘字段 | 违反动作 |
|---|---|---|---|
| 1 | 先认市场，再认个股 | `discipline.r1_recognize_market` | 无主线不开新仓 |
| 2 | 只做龙头或低位，躲开中位杂毛 | `discipline.r2_leader_or_low` | 中位票剔出 |
| 3 | 周期不对就减维 | `discipline.r3_cycle_reduce` | 退潮→空仓/极小试仓 |
| 4 | 模式外的钱永远不赚 | `discipline.r4_style_only` | 模式外拉黑 |
| 5 | 进出理由必须一致 | `discipline.r5_reason_consistency` | 逻辑死→切 |
| 6 | 盈亏比优先于胜率 | `discipline.r6_rr_first` | RR<1 拒开（risk_reward.py） |
| 7 | 合力来自全市场 | `discipline.r7_market_consensus` | 逆势抱团降级（core_judge） |
| 8 | 计划外不出手 | `discipline.r8_no_plan_outside` | 盘中新票须归三类 |
| 9 | 错了快切不讲故事 | `discipline.r9_cut_fast` | 超短隔日走人 |
| 10 | 系统大于新技巧 | `discipline.r10_system_over_trick` | 不研究新打法 |
| 11 | 利润垫博弈原则 | `discipline.r11_profit_padding` | 无利润垫不参与高风险博弈（监管博弈/穿越博弈） |

## 二、开仓资格 checklist（缺一条不准买）

对每只 execution 候选，逐项勾选写入 `discipline.open_qualifications[]`：

- [ ] 今日主线/风格已写在计划里（非盘中才「发现」）
- [ ] 标的是：当日人气总龙 / 主线补涨龙 / 低位前排（首板/二板）三者之一
- [ ] 个股有市场地位（core_judge: `is_core=true` 或 `core_grade ∈ {leader, core}`）
- [ ] 不在下降趋势，非"防御板冒充进攻"
- [ ] 买点属于计划内手法（打板/半路/低吸按纪律 5）
- [ ] 仓位 ≤ 当日额度与单票上限（risk_reward: `position_suggestion_pct`）
- [ ] 若亏钱周期：只许"舌头碰热水"试仓，不当主仓

## 三、禁止清单（D1 硬过滤）

命中任一 → 直接剔出 execution_pool（写入 `rejected`，reason_code 记编号）：

1. `mid_laggard` — 中位股/杂毛/没地位的弱转强
2. `non_mainstream` — 已有既定主流时去看非主流
3. `opposite_of_strongest` — 最强板块的对立面
4. `cold_heavy` — 非主流冷门当低风险重仓
5. `counter_emotion_turn` — 情绪差时抓小转折点
6. `buy_after_fade` — 确认退潮后还买
7. `cross_high_climax` — 博弈穿越高潮
8. `down_trend_break` — 下降趋势板、无板块效应秒拉板
9. `late_speculation` — 14:00-14:30 后投机点火板
10. `plan_outside_scan` — 计划外扫板/广撒网
11. `overnight_bad_streak` — 手风不顺还隔夜赌反转
12. `cover_with_t` — 用 T 或补仓掩盖看错
13. `all_in_learning` — 梭哈（学习期禁止）
14. `mixed_template` — 纯图形/庄票 与 总龙锁仓 同天混用
15. `cover_after_blast` — 炸板或买入失败后补仓（必须承认错误离场）
16. `regulatory_confrontation` — 监管信号明确（"给区间"/点名/停牌）后仍博弈相关方向

## 四、情绪周期强制切换表（每阶段允许/禁止）

| 阶段 | 允许 | 禁止 | 仓位档 |
|------|------|------|--------|
| `low_test` 低位试错 | 打首板/低位补涨/切新题材 | 猛干高位龙、重仓 | ≤3 成，轻仓试错 |
| `main_up` 主升 | 干龙头（打板/竞价/半路）、连板补涨/低位潜伏 | 支线/暗线/自己选的龙 | 6-8 成，分 2-4 只核心 |
| `high_chop` 高位震荡 | 落袋、轻仓；龙头未死挖主线低位 | 博弈穿越 | ≤4 成，只留最强主线 |
| `main_down` 主跌 | 空仓为主；连冰后尾盘试错；切新题材一日游 | 参与小反抽当主升 | ≤2 成或空仓 |

## 五、总龙开关（定温度，D1 meta 记录）

- 总龙首阴后反包 → 行情可能继续
- 总龙首阴后被按 → 准备调整，减到风控仓
- 总龙第一次被关 → 可看板块中位加速/补涨（仍躲没地位的）
- 总龙第二次被关 → 小心高位板做多情绪
- 无持续性主流 + 指数下跌/盘整 → **空仓**

## 六、D1 落盘契约

```json
{
  "discipline": {
    "open_qualifications": [{"item": "是主线", "pass": true}, {"item": "是龙头/低位", "pass": true}],
    "iron_rules_violated": [],
    "forbidden_hits": [],
    "emotion_phase_override": {"phase": "high_chop", "allowed_cap": 0.4},
    "dragon_switch": {"first_yin_after_rebound": null, "action": "观察"}
  }
}
```

## 七、入场门槛与买点判定（时序三要件）

设计条件单/候补单时按本节写；复盘「买点是不是错过了」时按本节判。

**入场三要件必须同分钟成立，缺一即不买**：

1. **价格在带内** — 买点带是价格的函数，不是「条件满足后按市价买入」的许可
2. **板块结构成立** — 预案写明的条数逐条数（涨停家数 / 龙头状态 / 板块效应）
3. **个股资金成立** — 个股 T 日主力净额 / 超大单转正（个股级证据）

任一要件在价格离开买点带**之后**才成立 → **该交易当日作废**，转次日预案并重走四源确认，不补票。

**板块相对排名只能是仓位乘数，不能是入场开关**。相对排名是零和的（别人弱你才靠前）、慢变量、且口径不唯一（东财/同花顺、二级/三级、净额/占比/5 分钟速度）。用它当开关，条件必然在价格离带后才成立 → 系统性追高。它回答「这波该重仓还是轻仓」，不回答「现在能不能买」；仓位大小用它，买不买用三要件。

**推翻预案机械条款要留痕**：全局撤单条件（如「板块再涨停少于 N 家」「广度不足」）命中后若仍要开仓，必须写清理由 + 当时数据；不得以「条件后来成立了」为由补票。

**「错过」的定义**：只有「规则内出现过、且当刻可执行」的机会才算错过。**没买 ≠ 错过 ≠ 亏损**；把没买记成错过是 FOMO 的燃料。复盘错题本只记「是否违规」，不记「少赚多少」。

### 复盘核对「买点出现过没有」的硬要求

- 用**分钟级分时**核对当日最低/最高与候选带，**不得用 N 分钟截面估算**：截面每 10 分钟一格，会把「4 分钟深坑」和「全天从未触及」混为一谈。取数命令见**跨 skill 引用**：`analyze-capital-flow-v1` → `references/intraday-sector-flow-and-band-check.md`（本 skill 目录下没有该文件）。
- 盘中不存在「收盘口径」资金（tushare 板块资金盘后 19:00-20:00 才更新）。**用当日收盘榜回推盘中条件是否成立 = 拿事后数据当事前信号**；判定前先用 `date` 与最新截面时间戳对齐市场时段。
- **板块涨幅榜 ≠ 板块资金榜**，跨源口径（东财/同花顺、层级、时间窗）先与预案对齐再判定，否则结论可能完全相反。
- 候补单里含「缩量企稳」「超大单转正」这类实时不可得的确认项、而价格只在带内停留数分钟时，**该单实际不可执行**，属设计缺陷：要么改成「企稳后追突破」（更高价、有确认），要么明确放弃，「低价」和「确认」不能都要。

## 消费方

| 谁调用 | 何时 | 用法 |
|--------|------|------|
| D1 | 08:00 | execution_pool 定稿前强制自检；违反铁律/命中禁止 → 剔出 |
| E1 | 18:00 | 复盘"昨天违反了哪条纪律" → 错题本可度量 |
| execute | 盘中 | 下单前核对纪律（禁止清单实时拦截） |
