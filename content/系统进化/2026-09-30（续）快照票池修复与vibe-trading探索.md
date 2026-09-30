# 2026-09-30（续）· 快照票池修复 + cron 告警 + 生成器防冲突 + vibe-trading 探索

> 承接同日《配置瘦身与孤儿分析清理》。本篇记录用户批复 P0/P1 后的落地结果，
> 以及用户新提的问题：「vibe-trading 78 个工具全历史只用 4 个，你应该自己去探索
> 要额外用哪些工具进一步优化分析 —— 比如我要分析量价，直接调它现成的 MCP 是不是更简单？」

---

## 一、必须先纠正我自己上一条的判断 ❌

我在《配置瘦身》文档里推荐 **「票池改成从当日 R2 龙头动态读，只留 06:50 一档，删 15:50」**。
用户采纳了。但**动手前实测发现这个方案逻辑上不成立**，我更正如下：

### 事实：06:50 这个时点**拿不到当日 R2**

近 8 个交易日 R2 落盘时间：

| 日期 | R2 落盘 |
|---|---|
| 09-21 | 08:30 |
| 09-22 | 07:50 |
| 09-23 | 07:58 |
| 09-24 | 07:51 |
| 09-25 | 07:43 |
| 09-28 | 08:00 |
| 09-29 | 07:44 |
| 09-30 | 08:08 |

R2 最早 07:43 落盘。**06:50 跑时，磁盘上只有前一日（T-1）的 R2** —— 所以：

- 「06:50 从当日 R2 读票池」→ 实际读的是 T-1 的 R2，票池错位一天
- 且会把产物写成 `date=<今天>`，当日 08:15 的 R5 若读快照，拿到的是**昨天的票池**

### 更深的一层：06:50 那档**根本没在算今天**

实测 `data/raw/20260930/chart_vision_snapshot.json`：

```
generated_at = 2026-09-30T15:52:29     ← 15:50 档的产物
```

06:50 档的产物被 15:50 档**同路径覆写**了，连证据都不剩。结合两档都读 `DEFAULT_UNIVERSE`
的事实，06:50 档实际是**在 06:50 重算昨天 15:50 已经算过的同一批固定票** —— 纯白烧。

### 结论：唯一正确的位置是「R2 之后、R5 之前」，不是任何固定钟点

这跟 D1 那边已经得出的教训是同一条：**不要看钟表，看上游落盘**。

---

## 二、实际采用的方案

### 改动清单

| # | 改动 | 文件 |
|---|---|---|
| 1 | **删掉 `chart_vision_snapshot` cron**（`fd61c030d180`，`50 6,15 * * *`） | cron |
| 2 | 票池改为从 **R2 龙头动态推导**（新模块，唯一真源） | `src/research/candidate_pool.py`（新） |
| 3 | 预渲染移到 **R2 落盘后、R5 启动前**，6 路并发 | `scripts/research/run_research_shell.sh` |
| 4 | R5 **先读快照，未命中才调 MCP**；命中记 `source:"snapshot"` | `skills/analyze_stock_profile_v1/SKILL.md` |
| 5 | 快照脚本加**覆盖度跳闸**（当日已覆盖 ≥50% 则 exit 0，不调 vision）+ `--force` | `scripts/fetch/run_chart_vision_snapshot.py` |
| 6 | 快照脚本加**合并写**（补渲不再整份覆盖） | 同上 |
| 7 | R5 把未命中票写**补渲队列** | `src/research/r5_stock_profiles.py` |

### 票池口径统一（防再次分叉）

新模块 `candidate_pool.py` **复用 R5 自己的 `_collect_leaders()`**，不再另写一套解析：

```
derive(r2)  ← R5 与快照生成器都调这里 → 口径不可能分叉
  ① R2.main_lines[].leaders        （R2 自己的排序）
  ② R2.secondary_lines[].leaders_hint  （①为空即 leaders_degraded 时，正则解析自然语言兜底）
```

### 实测效果

| 指标 | 改前 | 改后 |
|---|---|---|
| 快照 vs R5 实际候选重合度 | **1/12（8%）** | **12/12（100%）** |
| 覆盖票数 | 12 票（全是错的） | 16 票（13 R2 龙头 + 3 补渲） |
| 每日 vision 调用 | 24 次（06:50+15:50 各 12） | **13~16 次，且全部命中真候选** |
| R5 需直调的票 | 12 次 × 42s ≈ 500s | **0 次**（全部走快照） |

产物样例（新华传媒 600825.SH，真候选）：

```json
{"bias": "偏多", "confidence": 0.8,
 "signals": [{"type": "突破", "period": "日K", "confidence": 0.85, "price_hint": 10.35}]}
```

---

## 三、cron 失败告警（用户点名的 P0）

### 新增 `scripts/health/check_cron_failures.py`

挂在已有的 `canghai-health · 每日产出健康检查 (20:30)` 里，每天随 20:30 巡检一起跑。

检查三项：
1. `failure_streak >= 3` → 🚨 报警
2. agent 型 cron 但 `provider` 未 pin → ⚠️ 报警（drift 前兆）
3. `last_status == error` 且 streak 较小 → 🟡 提示

### 一个重要的防误报设计

首次运行就报出 `canghai-review · 周度进化(E2)` 连续失败 5 次 —— 但**这是假警报**：
我上午已把它 pin 了，只是它**每周五才跑**（下次 10-02），`failure_streak` 还是旧值。

所以加了区分：

- provider **已 pin** 但失败发生在 pin 之前 → `🕓 已修·待验证`（带末次/下次运行时间）
- provider **未 pin** 且失败 → `❌`（真在挂）

不加这层，每天都会误报「还在挂」，告警就会被无视 —— 那就白做了。

### 实测输出

```
⚠️ cron 巡检异常（检查 28 个 job，阈值 failure_streak>=3）
   连续失败 1 · 未 pin 0 · 新挂 0

🚨 连续失败（静默挂了）
  🕓 已修·待验证 [canghai-review] 周度进化(E2) (87d4d030b72b)
     连续失败 5 次 · 末次 2026-09-25 15:30 · 下次 2026-10-02 15:30
     RuntimeError: HTTP 404: 404 page not found
```

**「未 pin 0」**说明上午那批 pin 修复是完整的。

---

## 四、消除 cron 双轨

审计 28 个 job（default 25 + profile 3），发现**一处真重复**：

| job | 时点 | skill | 状态 |
|---|---|---|---|
| `b4085b037f87` (default) | 11:35 | `midday_amendment_v1` | ✅ 已删 |
| `75bf632522ce` (canghai-plan) | 11:40 | `midday_amendment_v1` | 保留 |

**同一个 skill 跑两遍**。且 11:35 那序与自己的上游冲突：
`canghai-fetch · 午盘快照` 也是 11:35 —— P2 可能读不到当次快照。
今日实盘证据：快照 11:37 落盘、P2 11:47 落盘（11:40 那序是对的）。

**处置**：删 default 11:35 那份，保留 canghai-plan 11:40（时点正确 + 已 pin）。

> 其余同时点 job 都是**互补**的，不能合并：
> - 18:00 `E1 每日复盘` + `持仓生命周期滚动复盘` → 两个不同 skill
> - 11:35 `午盘快照(fetch)` → P2 的**上游数据**，不是重复

cron 总数：**32 → 28**（本轮净减 4，含 snapshot 1 + P2 重复 1 + 上午的 3 个死 job，新增 1）。

---

## 五、配置生成器与手改打架（用户点名的 P1）

### 根因确认

`scripts/setup_hermes_doubao.py::_merge_mcp()` 对所有 server 都是**直接赋值覆盖**：

```python
servers["tushareMcp"] = {"url": ..., "timeout": 180, "connect_timeout": 60}   # ← 覆盖
```

**后果最严重的一处**：`tushareMcp` 被覆盖后，手工加的 `tools.include` 白名单
（254 → 69 的瘦身成果）**整个丢失**，schema 基线从 18.6k 反弹回 36k。

### 修法（两道）

1. **`_merge_server()` 按名合并**：存在则只 `setdefault` 补缺失键，**已有键一律保留**
2. **新增 `mcp_servers_opt_out`**：config 里列出「故意不挂」的 server，生成器不会加回来

### 实测验证

| 项 | 改前 | 改后 |
|---|---|---|
| 重跑 setup 后 `tushareMcp.tools.include` | ❌ 变 0（全丢） | ✅ 仍 69 |
| 其余 6 个 server | 不变 | 不变 |

---

## 六、回填 `research_summary.json`

### 实际情况比预估严重得多

我原本说「12 天缺失（09-14～09-29）」，**实测是 41 天缺**（从 07-08 到 09-29 几乎全缺）。

**成功回填 35 天**（其余 6 天 R 文件不足 7 个，无法生成）：

| 结果 | 天数 | 日期 |
|---|---|---|
| `complete` | 21 天 | 08-04, 08-07, 09-04～09-29 等 |
| `partial` | 14 天 | 07-08, 07-17, 08-11～09-01 |
| 跳过 | 6 天 | R 文件 < 7（07-05 / 08-03 / 09-02 / 09-03 / 09-11 / 09-13） |

用 `build_research_summary.py`（只读脚本，**不跑 orchestrator**，不会用规则版覆盖 LLM 产物）。

**意义**：这 35 天的 D1 当时全部走 `_minimal_summary()` → `orchestrator_status=degraded`。
现在历史复盘可以用统一口径重跑了。

---

## 七、vibe-trading 探索（用户点名要我自己挖）

### 先纠正我上一条的一个错误判断

我说「78 个工具全历史只用 4 个，其余 74 个零调用，可以再收一轮」。
**这个建议基本是错的** —— 用 `HERMES_DUMP_REQUESTS=1` 实测请求体：

```
本次请求注册工具数: 21
  vibe-trading 实际注册进 schema 的工具数: 0
```

**vibe-trading 的工具根本不在 context 里** —— 它们走 Hermes 的**延迟工具目录**
（`tool_search`），只在 agent 真要调时才把 schema 拉进来。所以：

- 那 74 个「零调用」工具**不花任何常驻 token**（省下来的是 `tool_search` 那 10,418 字符，与 server 挂几个工具无关）
- 「再收一轮白名单」**没有收益** —— 它本来就不占基线
- 真要收，那是 `tool_search` 目录层面的问题，不是 MCP 白名单

> 我上一条把这份 schema（88,534 字符 ≈ 22k tok）当成了常驻成本。**不是。**
> 这个数只在「agent 去 `tool_search` 搜工具」时才付出。

### 你问的「分析量价直接调它现成的 MCP 是不是更简单」→ **是，而且快得多**

我把量价相关的工具在**真实 A 股**上全跑了一遍（今日 exec 池的引力传媒 603598.SH）：

| 工具 | 耗时 | 实际返回 | 参数（易错，注意） |
|---|---|---|---|
| `technical_indicators` | **0.4s** | RSI14/MACD/BOLL/SMA20,50,200/EMA20 + **量比 ratio_20** | `symbol`, `indicators`, `interval`, `lookback=200` |
| `get_market_data` | **5.4s / 12 票** | OHLCV，返回 `{ts_code: [...]}` | `codes`(复数!), `start_date`, `end_date`, `interval` |
| `get_fund_flow` | **2.1s** | 主力/超大/大/中/小 单资金流 | `codes`(复数!), `period` ∈ `daily\|min` |
| `get_dragon_tiger` | **1.9s** | 当日龙虎榜 71 条 + 净买额 | `date`(非 `trade_date`), `code` |
| `get_lockup_expiry` | **1.1s** | 解禁明细（含 `free_ratio`） | `code`, `horizon_days` |
| `get_sector_info` | 0.2s | 所属板块（**东财板块代码**） | `code`, `mode`, `limit` |

**关键对比 —— R5 现在最贵的一段**：

| | chart_vision_analyze | vibe-trading `technical_indicators` |
|---|---|---|
| 12 票耗时 | **500s**（12 × 42s，串行） | **0.4s × 12**（毫秒级，可批量） |
| 是否用 LLM | 是（每次一次 vision 调用，花钱） | **否**（纯计算） |
| 输出 | 自然语言形态描述 | 精确数值（RSI/MACD/量比/均线） |

### 数值正确性验证（不只看它「跑通了」）

我拿自主 `kb/research.db` 的 236 日日线**独立复算**，与 vibe-trading 返回值对比：

| 指标 | vibe-trading | 我独立复算 | 判定 |
|---|---|---|---|
| SMA-20 | 17.9875 | 17.9875 | ✅ **完全一致** |
| SMA-50 | 17.5198 | 17.5198 | ✅ **完全一致** |
| RSI-14 | 55.7943 | 55.7876 | ✅ 差 0.007（算法变体） |
| EMA-20 | 17.99963 | 17.99980 | ✅ 差 0.0002 |
| MACD line | 0.2463 | 0.2457 | ✅ 差 0.0006 |
| 最新收盘/成交量 | 18.78 / 307,756 手 | 18.78 / 307,755.5 手 | ✅ **一致** |

→ **可信，可以直接用于决策输入。**

### 建议（这次是真建议）

**1. R5 的「技术形态」维度应该双轨**

现在只有 chart_vision（LLM 看图，42s/票，只给定性描述）。建议加一路 `technical_indicators`：

- **定位差异**：chart_vision 给「形态/结构」的**定性**判断（涨停突破、下降通道）；`technical_indicators` 给**精确数值**（量比 1.40、RSI 55.8、在 MA20 上 4.4%）
- **互补**：形态识别负责「像不像」，指标负责「够不够」。R5 现在缺后者
- **成本**：接近零（0.4s/票，无 LLM）
- **落地**：R5 skill 的「技术形态」维加一句「同时调 `technical_indicators` 取数值佐证」；数值与 chart_vision 结论冲突时标 `tech_divergence=true` 进 R6 观察池

**2. `get_sector_info` 补上「板块归属」的自动化**

R2 现在靠 LLM 读文字判断个股属哪个板块。`get_sector_info` 返回**东财板块代码 + 涨跌幅**，
可以拿来做机器校验（避免「这只票真的属于 AI 应用吗」这种误判）。

**3. `get_dragon_tiger` 可作为 R7 的独立第二源**

R7 现在龙虎榜主源是 tushare `top_list`。vibe-trading 走的是**东财通道** —— 真正的独立源，
可以交叉核验「龙虎榜净买」口径（R7 skill 里已在做「诱多识别」，多一源更稳）。

**4. 不要动的部分**

- `technical_indicators` 是**纯计算**，不涉及 LLM —— 符合你「决策必须大模型做」的铁律
  （它是**数据**，不是决策；决策仍由 R5 的 LLM 下）
- chart_vision **保留**：它是六维里唯一的「视觉证据」，与数值指标不是替代关系

**5. 可删的（低优先级）**

`pattern_recognition` 的参数是 `run_dir`（要你先准备 vectorbt 的 config.json + CSV），
对 R5 场景太重，建议不用 —— 形态识别继续走 chart_vision。

---

## 八、变更文件清单

### 新增

| 文件 | 用途 |
|---|---|
| `src/research/candidate_pool.py` | 票池推导唯一真源（R5 与快照共用） |
| `scripts/health/check_cron_failures.py` | cron 失败/未 pin 巡检 |
| `data/runtime/chart_vision_misses_YYYYMMDD.json` | 快照未覆盖票的补渲队列 |
| `chzl_kg/系统进化/2026-09-30（续）快照票池修复与vibe-trading探索.md` | 本文档 |

### 修改

| 文件 | 改动 |
|---|---|
| `scripts/fetch/run_chart_vision_snapshot.py` | 票池动态推导 + 覆盖度跳闸 + `--force` + 合并写 |
| `scripts/research/run_research_shell.sh` | R2 之后插入并发预渲染 |
| `skills/analyze_stock_profile_v1/SKILL.md` | v1.4：先读快照，未命中才调 MCP |
| `src/research/r5_stock_profiles.py` | 覆盖度核对 + 补渲队列 |
| `scripts/setup_hermes_doubao.py` | `_merge_server` 按名合并 + `mcp_servers_opt_out` |
| `~/.hermes/scripts/canghai_chart_vision_snapshot.sh` | 单档兜底 + 跳闸不误报 |
| `~/.hermes/scripts/canghai_daily_health_check.sh` | 串入 cron 失败巡检 |

### cron 变更

| job | 动作 |
|---|---|
| `fd61c030d180` chart_vision_snapshot (06:50+15:50) | **删除**（时点拿不到当日 R2，纯白烧） |
| `b4085b037f87` 午盘briefing P2 (11:35) | **删除**（与 canghai-plan 11:40 重复） |

### 数据回填

- 35 个交易日的 `data/research/*/research_summary.json`
- `data/raw/20260930/chart_vision_snapshot.json` 重建（16 票，100% 命中）

### 验证

- 快照覆盖度：**1/12 → 12/12**
- `tushareMcp` 白名单在重跑 setup 后**保持 69**
- 覆盖度跳闸生效（重跑 → `⏭️ 跳过`；`--force` → 照常重算）
- 合并写生效（13 重算 + 3 保留 = 16）
- cron 巡检：未 pin = **0**

---

## 九、待办 / 需你拍板

1. **R5 是否加 `technical_indicators` 数值轨**（第七节建议 1）—— 我认为值得，成本近零
2. **`data/research/` 下 6 天因 R 文件不足无法回填**（07-05 / 08-03 / 09-02 / 09-03 / 09-11 / 09-13）—— 需要的话可从 cron output 恢复
3. **`hermes-visitors` profile 的旧版 R5 skill 是否清理**（它还会读旧快照，schema 已变）
4. **cron 是否继续按「一功能一 job」整并**（本轮只处理了确证的 1 处重复）
