---
name: fetch_auction_snapshot_v1
description: 09:27 集合竞价快照抓取(execution_pool 溢价 + 全市场情绪),subprocess + LLM report,供 P1 消费。⚠️ 竞价数据 09:27 才到,勿早于 09:27 跑
agent_owner: canghai-fetch
version: v3
status: T3-skeleton
category: fetch
created: 2026-07-04
updated: 2026-10-17
tested_with: []
---

# fetch_auction_snapshot_v1

**归属**: `canghai-fetch` profile · **09:27** 触发（Hermes **agent + skill**，`--no-agent` 作废）；⚠️ 竞价数据 09:27 才到，勿早跑
**目的**: 在集合竞价结束前 1 分钟抓取 `execution_pool`（及 plan 内 `watch_pool`）竞价数据 + 全市场情绪，写盘供 P1 `auction_amendment_v1` 消费。  
**架构依据**: `docs/01-系统现状全景.md` §9.2 · `docs/agents/P1-竞价校准Agent.md`

| 谁做 | 做什么 |
|------|--------|
| **Python subprocess** | 读 plan 名单、XTick/QMT 竞价（或 stub）、写 `auction_snapshot.json` |
| **Hermes LLM (本 skill)** | 激活 venv → 跑 shell 入口 → 读 JSON → 结构化 report |

---

## Execution Prompt（Agent 加载本 skill 后按序执行）

### Step 0 · 确定 trade_date

- 默认 **今日** `YYYYMMDD`（上海时区）
- cron / 用户传入日期时优先使用

### Step 1 · Subprocess 抓取（唯一数据入口）

在项目根 `/Users/chenyang/Downloads/demo/沧海巨浪` 执行：

```bash
source .venv/bin/activate
bash scripts/fetch/run_auction_snapshot.sh [YYYYMMDD]
```

等价 Python 入口（仅当 shell 不可用时）:

```bash
source .venv/bin/activate
python3 scripts/fetch/run_auction_snapshot.py --date YYYYMMDD
```

**禁止**:
- ❌ 本 skill 内手写 MCP 批量预抓（数据源逻辑在 Python subprocess）
- ❌ 分析竞价含义（那是 P1 `auction_amendment_v1` 职责）
- ❌ 修改 D1 的 `watchlist_plan.json`

**脚本职责**（已实现，勿重复）:
- 读 `data/plans/YYYYMMDD/watchlist_plan.json` → 提取 `execution_pool` / `watch_pool` 的 `ts_code`
- 竞价主路径 `code=all` 单次请求全市场（~0.8s/5500+只 ZIP 147KB）本地过滤；分批50只仅作回退（2026-09-28 改：旧分批串行超09:29窗口致 timeout）
- pool_auction 的 `ts_code` 保留 `.SZ/.SH/.BJ` 完整后缀（P1 按完整代码匹配）；bare code 只在查 XTick 时用
- ⚠️ `/doc/hot/emotion` 返回实时值不可重放：盘后重跑快照会污染 market_sentiment，重跑后必须恢复原始09:27值
- 优先 XTick `/doc/bid/time`（需 `XTICK_TOKEN`）；失败或无 token → **stub**（`severity: 2`）
- `watchlist_plan.json` 缺失 → **skipped**（不阻塞，stdout 报告）
- 落盘 `data/raw/YYYYMMDD/auction_snapshot.json`（须在 **09:28:00** 前完成，P1 09:28 启动即读取）

### Step 2 · 读 snapshot 并汇报（LLM 唯一产出）

读取:

```
data/raw/YYYYMMDD/auction_snapshot.json
```

若 Step 1 为 `skipped`，仅 report 跳过原因，不要求 snapshot 文件存在。

**Report 模板**（回复用户 / cron deliver）:

```
【fetch_auction_snapshot_v1 · YYYYMMDD】
status: {ok|stub|skipped}
severity: {0-3}
source: {xtick|stub|none}
pool_count: {N}
captured_at: {ISO8601}

market_sentiment:
  limit_up_count: {n}
  limit_down_count: {n}
  up_down_ratio: {ratio}

落盘: data/raw/YYYYMMDD/auction_snapshot.json（或 skipped 无文件）
ref_plan: data/plans/YYYYMMDD/watchlist_plan.json

结论: {P1 可消费 | stub severity=2 P1 可能 timeout_no_amendment | plan 缺失已跳过}
```

**severity 解读**:
- `0` + `status=ok` → P1 正常读取
- `2` + `status=stub` → P1 可尝试 XTick MCP 补一次；仍失败则无 amendment
- plan 缺失 `skipped` → P1 仍运行但无 pool 名单（由 P1 降级）

### Step 3 · 结束

- **不写** `data/plans/`、`data/research/`
- subprocess 非零退出 → report stderr + snapshot（若已写）
- 纯 Python，**几乎无 LLM 推理**；report 即可

---

## Purpose

轻量级、高确定性的 **09:27** 数据抓取；不涉及分析判断。

## Inputs

| 输入 | 说明 |
|------|------|
| `data/plans/YYYYMMDD/watchlist_plan.json` | D1 08:00 产出；读 pool 名单 |
| `XTICK_TOKEN`（可选） | `.env` / 环境变量；无则 stub |
| `trade_date` | `YYYYMMDD`，默认今日 |

## Outputs

`data/raw/YYYYMMDD/auction_snapshot.json`:

```json
{
  "schema_version": "auction_snapshot_v1",
  "trade_date": "YYYYMMDD",
  "captured_at": "ISO8601+08:00",
  "market_sentiment": {"limit_up_count": 0, "limit_down_count": 0, "up_down_ratio": 0},
  "pool_auction": [
    {"ts_code": "", "auction_price": 0, "prev_close": 0, "premium_pct": 0, "auction_volume": 0, "auction_amount": 0}
  ],
  "severity": 0,
  "status": "ok",
  "source": "xtick"
}
```

## Rules & Constraints

- 必须在 **09:28:00** 前完成落盘（P1 09:28 启动即读取；竞价数据 09:27 才到，勿早跑）
- 纯 Python subprocess；Agent 只 report
- `watchlist_plan.json` 当日不存在 → skipped，不阻塞 cron

## Data Sources

XTick `/doc/bid/time`（优先）、QMT quote（T3 后续接线）；stub 为 T3 骨架默认路径。

## Fallback Behavior

XTick 超时/无 token → stub + `severity: 2`；P1 收到空/占位快照后不产出 amendment（或 `timeout_no_amendment`）。

## Version History

| 版本 | 日期 | 说明 |
|------|------|------|
| v1 | 2026-07-04 | 骨架建立 |
| v2 | 2026-07-05 | T3：subprocess + agent report 对齐 `fetch_all_sources_v1`；`run_auction_snapshot.py` |
| v3 | 2026-10-17 | **双源竞价 + 全谱情绪**：①竞价主源改 Tushare `stk_auction`（一次全市场 8000 行，含 turnover_rate/volume_ratio/float_share，交易所口径 pre_close 更权威），XTick `code=all` 作回退（用户反馈 XTick 竞价链路不稳定）；②`market_sentiment` 增强为全谱：max_ladder/promotion_rate/broken_rate/promotion_1t2~4t5/zb_rate_1t2~2t3（xtick /doc/hot/emotion 的 mhigh/jjl/zbl/jj1t2...）；③修复 `python scripts/fetch/...` 直接运行时 `No module named 'src'`（sys.path 显式加项目根） |

### v3 双源优先级（2026-10-17）

```
Tushare stk_auction (09:25-29 取当日, 历史可回刷 2025-01 起) → 成功: source=tushare_stk_auction
  → 失败回退 XTick code=all → 成功: source=xtick
  → 都失败 → stub severity=2
```

**Tushare stk_auction 优势**：
- 单次最多 8000 行 = 全市场一次拉（XTick code=all 是 ZIP 解压，偶发不稳）
- 含 `turnover_rate`（换手率）/ `volume_ratio`（量比）/ `float_share` — XTick 竞价行没有
- `pre_close` 是交易所口径（更权威；002343.SZ 案例：XTick 昨收 8.91 vs Tushare 8.1，溢价差 1.7pp）

**注意**：Tushare 无情绪数据 → `market_sentiment` 仍走 XTick `/doc/hot/emotion`（`_fetch_xtick_sentiment` 独立函数，含全谱晋级率）。
