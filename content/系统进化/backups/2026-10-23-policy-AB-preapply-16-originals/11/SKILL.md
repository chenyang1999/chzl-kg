---
name: filter_leader_v1
description: R2 龙头硬约束过滤器 — 落地 user_preferences.yaml leader_preference，同板块只留龙一龙二
agent_owner: R2
version: v1
status: draft
category: research/R2
created: 2026-07-04
updated: 2026-07-05
spec: docs/agents/R2-主线板块Agent.md §3.3
---

# filter_leader_v1 · R2 龙头硬过滤

**跑动时点**: `analyze_main_sectors_v1` **完成之后立即执行**（同一次 R2 delegation 内）  
**性质**: **规则过滤步骤**，不是自由裁量分析  
**产出**: **原地更新** `data/research/YYYYMMDD/R2_main_sectors.json` 的 `leaders` / `candidates` 字段

---

## 唯一职责

将 `analyze_main_sectors_v1` 产出的候选龙头，按用户「**同板块只留龙一龙二**」硬规则过滤，标注 `leader_rank` 与 `filter_reason`。  
**禁止**: 重新选板块、改主线 score、给买卖点。

---

## 输入

| 路径 | 说明 |
|------|------|
| `data/research/YYYYMMDD/R2_main_sectors.json` | `analyze_main_sectors_v1` 刚写入的版本 |
| `data/user_preferences.yaml` | `leader_preference`, `filter_out_rules`, `st_filter`, `execution_block_prefixes` |

可选交叉验证（不扩大候选池）：

- R3 `hotlist_signals.distribution_alert` → 龙一若霸榜出货，标注 `filter_reason` 供 R6/D1  
- `@hithink-market-query`：仅当需核对龙一/龙二资金排名是否与规则一致

---

## 硬约束（不可协商）

来源：`data/user_preferences.yaml` → `leader_preference`

### 龙一认定（满足**任一**）

- 板块内涨停家数 **top 1**  
- 主力资金 **5 日累计 top 1**（`@hithink-market-query` 或上游已带字段）  
- 连板高度 **top 1**

### 龙二认定

- 板块内综合评分 **top 2**（且不同于龙一）

### 龙三及以下

- `leader_rank: filtered_out`  
- **不进 execution_pool**（除非后续 R6 对龙一 `hard_reject` 需替补 — 本 skill **只标注** `backup_eligible: true`，**不**决定 D1 是否启用）

### 杂毛过滤 `filter_out_rules`

命中以下 **≥2 项** → `leader_rank: filtered_out`, `filter_reason: 杂毛`:

1. 板块内主力 5 日流入排名 top 3 **之外**  
2. 龙虎榜近 30 日无机构/游资席位  
3. 连板高度 < 板块龙头 − 2  
4. 换手率 < 板块内 median 50%

### 合规

- `st_filter: true` → ST/*ST/退市 **一律** `filtered_out`  
- `execution_block_prefixes`（300/688/920）→ 标注 `execution_blocked: true`（watch 可含，execution 不含）

---

## 执行步骤

### Step 1 · 逐条主线处理

对 `main_lines[].leaders`（或 `candidates`）中每只票：

1. 按上节规则计算 `leader_rank`: `1` | `2` | `filtered_out`  
2. 写入 `filter_reason`（中文，可审计）  
3. 保留龙一、龙二、最多 3 只候补（`role: 候补` 且 `leader_rank: filtered_out` 仍可在 JSON 中留痕供 R5 深挖，但须标 `execution_eligible: false`）

### Step 2 · 数据不足降级

板块内可用候选 **<2 只** → 该主线 `data_health: insufficient_candidates`；**不**伪造龙二。

### Step 3 · 写回 JSON

更新字段示例：

```json
"leaders": [
  {
    "role": "龙一",
    "ts_code": "002050.SZ",
    "name": "三花智控",
    "leader_rank": 1,
    "execution_eligible": true,
    "filter_reason": "涨停家数板块第1 + 连板高度第1"
  },
  {
    "role": "龙二",
    "ts_code": "600089.SH",
    "name": "特变电工",
    "leader_rank": 2,
    "execution_eligible": true,
    "filter_reason": "综合评分板块第2"
  },
  {
    "role": "候补",
    "ts_code": "300124.SZ",
    "name": "汇川技术",
    "leader_rank": "filtered_out",
    "execution_eligible": false,
    "filter_reason": "龙三及以下不进 execution_pool"
  }
]
```

在 artifact 根级追加：

```json
"leader_filter_applied": true,
"leader_filter_version": "filter_leader_v1",
"leader_filter_at": "2026-07-04T07:52:00+08:00"
```

保持 envelope 字段 `schema_version`, `agent`, `status`, `confidence` 不变（除非过滤导致 confidence 下调，须在 `notes` 说明）。

---

## 红线

1. ❌ 不得新增 analyze_main_sectors_v1 未出现的板块或个股  
2. ❌ 不得因「看好」把龙三升为龙二  
3. ❌ 不做 D1 替补启用决策  
4. ✅ 每条主线 execution_eligible 的票 **≤2**（龙一+龙二）

---

## 消费者

| 下游 | 用法 |
|------|------|
| R5 | 对 `leaders` 中龙一/龙二 + 未 filtered 候补做画像 |
| R6 | 对 execution_eligible 龙头做反证 / hard_reject |
| D1 | 只从 `leader_rank` 1/2 且 `execution_eligible: true` 进 execution_pool 候选 |
