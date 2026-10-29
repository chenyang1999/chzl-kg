# research_summary.json 标准 Schema 说明

> **契约 3** · research 主控 → D1（CANONICAL v1.2 §3.2）
> 路径：`data/research/YYYYMMDD/research_summary.json`
> D1 主决策 Agent **只读此 summary 作为入口**，再按需 pull 各 `R*.json`

---

## 1. 设计原则

- **artifact-first**：主控不写分析结论，只调度 R1-R7 并汇总 artifact 路径与元数据
- **模型无关**：字段名与枚举由本 schema 冻结，Hermes delegation / Python orchestrator 均须遵守
- **R6 硬否决**：保留 R6 模式六出货与模式七既有财务合规硬否决，D1 必须执行；不因高度或辅助缺口新增硬否决

---

## 2. 顶级字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `schema_version` | string | ✅ | 固定 `"research_summary_v1"` |
| `trade_date` | string | ✅ | 交易日 `YYYYMMDD`，如 `"20260704"` |
| `generated_at` | string | ✅ | ISO 8601，带时区，如 `"2026-07-04T08:00:00+08:00"` |
| `orchestrator_status` | string | ✅ | `complete` / `partial` / `failed` / `skeleton` |
| `fetch_manifest` | string | ✅ | 上游 fetch 产物路径，如 `data/raw/20260704/manifest.json` |
| `fetch_global_severity` | integer | ✅ | 启动 research 时 manifest 的 `global_severity`（0-3） |
| `artifacts` | object | ✅ | R1-R7 各单元 JSON 路径，见 §3 |
| `confidence` | object | ✅ | 每单元为有限数 0.0–1.0 或 null；null=本次未评价/未知，0.0=真实评价为零，不按状态自动互换 |
| `hard_rejects` | array | ✅ | R6 硬否决清单，可为空；元素见 §4 |
| `timeouts` | array | ✅ | 超时或未完成的单元 ID，如 `["R5"]` |
| `completed_by` | string | ✅ | 计划完成时点 `"08:00"`（盘前批次） |
| `units` | object | 可选 | 各单元运行元数据（status、started_at、notes） |

---

## 3. artifacts 结构

键名固定为 `R1` … `R7`，值为**相对项目根**的路径字符串。

| 键 | 默认文件名 | 产出 Agent |
|----|-----------|-----------|
| `R1` | `data/research/YYYYMMDD/R1_style.json` | R1 风格 |
| `R2` | `data/research/YYYYMMDD/R2_main_sectors.json` | R2 主线板块 |
| `R3` | `data/research/YYYYMMDD/R3_sentiment.json` | R3 情绪热度 |
| `R4` | `data/research/YYYYMMDD/R4_news.json` | R4 消息面 |
| `R5` | `data/research/YYYYMMDD/R5_stock_profiles.json` | R5 情报深挖 |
| `R6` | `data/research/YYYYMMDD/R6_devil_advocate.json` | R6 反证 |
| `R7` | `data/research/YYYYMMDD/R7_capital_flow.json` | R7 资金面 |

**校验规则**：

- 7 个键必须全部存在（即使某单元 failed，路径仍指向占位 JSON 或昨日 fallback）
- 路径所指文件必须存在且为合法 JSON，否则该单元不得写入 `artifacts`（改记 `timeouts`）

---

## 4. hard_rejects 元素结构

仅 R6 `severity: hard_reject` 条目进入此数组。D1 收到后须从 `execution_pool` 候选中剔除对应标的。

```json
{
  "ts_code": "600519.SH",
  "name": "贵州茅台",
  "reason": "霸榜出货：连续3日龙虎榜同一游资席位净卖出",
  "evidence": ["R6 mode-6", "tushare top_list 20260702-20260704"],
  "source_agent": "R6",
  "suggestion": "hard_reject — 禁止纳入 execution_pool"
}
```

| 字段 | 类型 | 必填 |
|------|------|------|
| `ts_code` | string | ✅ |
| `name` | string | ✅ |
| `reason` | string | ✅ |
| `evidence` | array[string] | ✅ |
| `source_agent` | string | ✅ 固定 `"R6"` |
| `suggestion` | string | ✅ |

---

## 5. confidence 结构

```json
"confidence": {
  "R1": 0.85,
  "R2": 0.80,
  "R3": 0.75,
  "R4": 0.70,
  "R5": 0.65,
  "R6": 0.90,
  "R7": 0.80
}
```

| 场景 | 取值 |
|------|------|
| 正常完成 | 0.5-1.0，由子 Agent 自评 |
| 降级（单源失联） | 0.3-0.5 |
| 本次未评价（含 skeleton / 超时 / 昨日历史参考） | null；另列状态、日期与缺口，不以 0 冒充评价 |
| 真实评价为零 | 0.0，原样保留 |

汇总只接受有限、非 bool、在 [0,1] 内的数值；缺失、非法、非有限值记 null 并保留原始质量说明。消费者先区分 null 与数值，禁止 `or 0` 或用 null 触发数值零的降级/默认仓位；null 不构成完成或通过证明。JSON/MD 交付、研究就绪和交易授权是独立事实。

---

## 6. units 结构（可选，主控写入）

```json
"units": {
  "R1": {
    "status": "complete",
    "started_at": "2026-07-04T07:30:00+08:00",
    "finished_at": "2026-07-04T07:38:00+08:00",
    "notes": ""
  },
  "R7": {
    "status": "skeleton",
    "started_at": "2026-07-04T07:30:00+08:00",
    "finished_at": "2026-07-04T07:30:05+08:00",
    "notes": "T1: Python orchestrator placeholder"
  }
}
```

`status` 枚举：`pending` / `running` / `complete` / `degraded` / `failed` / `timeout` / `skeleton`

---

## 7. 完整示例（T1 skeleton 批次）

```json
{
  "schema_version": "research_summary_v1",
  "trade_date": "20260704",
  "generated_at": "2026-07-04T08:00:00+08:00",
  "orchestrator_status": "skeleton",
  "fetch_manifest": "data/raw/20260704/manifest.json",
  "fetch_global_severity": 1,
  "artifacts": {
    "R1": "data/research/20260704/R1_style.json",
    "R2": "data/research/20260704/R2_main_sectors.json",
    "R3": "data/research/20260704/R3_sentiment.json",
    "R4": "data/research/20260704/R4_news.json",
    "R5": "data/research/20260704/R5_stock_profiles.json",
    "R6": "data/research/20260704/R6_devil_advocate.json",
    "R7": "data/research/20260704/R7_capital_flow.json"
  },
  "confidence": {
    "R1": null, "R2": null, "R3": null, "R4": null, "R5": null, "R6": null, "R7": null
  },
  "hard_rejects": [],
  "timeouts": [],
  "completed_by": "08:00",
  "units": {
    "R1": {"status": "skeleton", "notes": "await delegation v2"},
    "R2": {"status": "skeleton", "notes": "await delegation v2"},
    "R3": {"status": "skeleton", "notes": "await delegation v2"},
    "R4": {"status": "skeleton", "notes": "await delegation v2"},
    "R5": {"status": "skeleton", "notes": "await delegation v2"},
    "R6": {"status": "skeleton", "notes": "await delegation v2"},
    "R7": {"status": "skeleton", "notes": "await delegation v2"}
  }
}
```

---

## 8. 消费者

| 消费者 | 用法 |
|--------|------|
| D1 主决策 | pull `research_summary.json` → 按需读各 `R*.json` → 出 `watchlist_plan.json` |
| P2 午盘修订 | 读 R7 11:35 增量字段（同路径文件内 `midday_increment` 段） |
| E1 复盘 | 对比 R1 风格预判 vs 实际走势 |

---

## 8.1 单项研究修订：局部补审交付，不自动准入

- 只允许受审调用方绑定的同交易日R6局部补审；指定原研究/汇总版本、目标对象与缺项。本次只更新审核结果及其汇总绑定，不重跑其余六类研究、不重新选票、不补抓数据。
- 复用的每份主研究仍保留原生产run/attempt、原内容版本、交付回执与事实时点；本次接收/修订时刻另记，不给旧材料伪造新产出或倒填首次可用时间。接收程序核原可信回执和当前实际字节，不能靠模型自报摘要或仅凭文件存在通过。
- 不重启/修改已终结原批次。普通程序在现有研究脚本、日志/历史快照及health回执机制中接收单项修订，明确区分本次R6新交付与其他单元的已验版本复用；不新建服务、角色或并行数据目录。一次受信接收所用旧版本不得在校验和发布间漂移。
- R6必要覆盖按现行技能`patterns_status`各模式对象中的`mode_id/candidate_checks`核对；模式1/2/6/7逐票完成与真实硬否决分别记录，不用全局布尔或空否决推定逐票通过。原未涉及结论和全部有效风险保留，缺证继续未知/未完成，不新增默认通过。
- 接收与汇总发布必须同版绑定R6 JSON/MD及全部复用输入，失败不能留下“旧汇总配新R6”的可用交付；保留原可恢复字节及失败提案，不回滚他人变更或冒称跨文件任意崩溃原子性。现有正常整批路径及旧有效交付继续按原契约核验。
- 本节只授权研究单项修订交付。不会调用D1/事件/scanner晋级，不改变正式计划、原execution_pool/watch_pool、资格、买卖规则、零预算或执行身份。逐票重新准入及预算owner的合法重评另列，不从本次复审完成推导。

---

## 9. 版本历史

| 版本 | 日期 | 说明 |
|------|------|------|
| research_summary_v1 | 2026-07-04 | T0/T1 首版，对齐 CANONICAL v1.2 契约 3 |
