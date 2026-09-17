# 沧海巨浪 · MCP 数据源全景

> 最后更新：2026-07-07(vibe-trading 从"通用 54 工具"重分类为"投研工作台 78 skill / 29 swarm / 54+ tool")
> 重构后状态：所有 API key 已统一为新 key，全部可用

## 总览

当前系统共接入 **8 个 MCP 服务**，覆盖**数据源 → 研究 → 分析 → 执行 → 复盘**全链路：

| 服务名 | 传输 | 工具数 | 提供者 | 用途 | 状态 |
|--------|------|--------|--------|------|------|
| **chenhailangju-research** | stdio | 25 | 本地项目 | 投研流水线+公众号+四色四量+图表+WeFlow封装 | ✅ 在线 |
| **tushareMcp** | HTTP | 258 | Tushare 官方 | 全市场金融基础数据 | ✅ 在线 |
| **weflow-analytics** | HTTP/SSE | 15 | WeFlow | 群聊热词/情绪/概念/股票分析 | ✅ 在线（刚修复 API key） |
| **agentqmt_qmt** | HTTP | 9 | QMT | miniQMT 实盘交易执行（下单/持仓/查询） | ✅ 在线 |
| **datapro** | HTTP | 1 | 火山引擎 | 专业数据检索（股票/企业/新闻/政策/百科） | ✅ 在线 |
| **xtick** | stdio | 43 | XTick | A股实时/历史分笔行情、龙虎榜等 | ✅ 在线 |
| **vibe-trading** | stdio | **78 skill / 29 swarm / 54+ tool** | Vibe-Trading | **投研工作台**:A股风控/缠论/艾略特/因子/财报/估值/事件驱动 + 4-6 agent 多空辩论 swarm | ✅ 在线(⭐核心) |
| **obsidian** | HTTP | 16 | Local REST API | Obsidian 笔记读写 | ✅ 在线 |

---

## 1. chenhailangju-research（本地 25 工具）

**本地主 MCP，封装了项目核心投研能力：**

### 四色四量
- `sise_intraday_scan` — 盘中四色四量转强扫描（三红→四红）+ MA30 向上
- `sise_trigger_prices` — 测算四色四量触发价（低吸/追高参考）
- `sise_daily_scan` — 近 N 日四色四量转强信号

### 回测与流水线
- `run_research_pipeline` — 运行赛道投研流水线
- `run_rule_backtest` — 规则阈值回测
- `get_track_status` — 赛道与四色四量系统状态
- `run_vectorbt_backtest` — vectorbt 信号收益回测
- `generate_ai_trader_signals` — AI-Trader 策略信号生成
- `list_trading_signals` — 查询统一交易信号库

### 公众号（mptext）
- `wechat_search_accounts` — 搜索微信公众号
- `wechat_list_articles` — 获取公众号文章列表
- `wechat_download_article` — 下载单篇微信文章内容
- `wechat_fetch_latest` — 拉取公众号最新文章
- `wechat_analyze_latest` — 拉取最新文章 + LLM 投研解读
- `wechat_analyze_trading_logic` — N 日文章 + Tushare 对照，提炼交易逻辑
- `wechat_sync_account` — 同步公众号全量文章到本地

### 交易策略
- `canghai_market_action_plan` — 沧海自流框架：三情景交易预案

### WeFlow 集成
- `weflow_save_snapshot` — 保存 WeFlow 快照到本地缓存
- `weflow_sise_morning_forecast` — WeFlow群聊情绪×四色四量：明日强势板块与核心标的预判
- `weflow_sentiment_events` — WeFlow情绪发酵 → 事件驱动选股

### 图表分析
- `chart_fast_render_kline` — 极速四周期 K 线拼图 PNG
- `chart_fast_render_intraday` — 极速分时图 PNG
- `chart_vision_analyze` — 服务端出图 + 多模态 LLM 技术面分析
- `chart_lwc_render_kline` — Lightweight Charts 无头出图：成交量+牛熊线+MACD

### 问财集成
- `iwencai_search` — 同花顺问财自然语言选股

---

## 2. tushareMcp（远程 258+ 工具）

Tushare Pro 官方 MCP 接口，覆盖 A 股几乎所有基础数据：

**核心常用：**
- `stock_basic` — 股票基础列表
- `trade_cal` — 交易日历
- `daily` — 日线行情
- `daily_basic` — 每日基本面指标
- `adj_factor` — 复权因子
- `hsgt_top10` / `north_money` — 北向资金
- `top10_holders` — 十大股东
- `income` / `balancesheet` / `cashflow` — 财务报表
- `forecast` / `express` — 业绩预告/快报

完整列表见 Tushare 官方文档。

---

## 3. weflow-analytics（远程 15 工具）

WeFlow 群聊分析 MCP，提供情绪/热点数据：

### 通用热词
- `export_analytics_snapshot` — 一次导出全量热点统计 JSON（terms、group_keywords、heatmap、river）
- `get_hot_terms` — 热词排行 + citations 原文摘录
- `get_group_keywords` — 按群汇总 Top 关键词
- `get_heatmap` — 群×词热力矩阵
- `get_river` — 热词时间序列（河流图数据）
- `get_analytics_meta` — 元信息（时间窗/消息数/群数）
- `list_local_chatrooms` — 列出时间窗内有消息的群及 message_count
- `get_group_messages` — 按 chatroom_id 查询群消息正文（时间倒序）

### 股票/概念维度
- `export_stock_snapshot` — 一次导出概念-股票图 JSON（stock_terms、concept_pie、concept_links）
- `get_stock_hot_terms` — A 股股票热词排行
- `get_concept_hot_terms` — 概念/题材热词排行
- `get_concept_linked_stocks` — 查询概念下共现股票及 edge_weight
- `get_stock_river` — 股票热词时间序列
- `get_stock_heatmap` — 群×股票热力矩阵
- `get_stock_backfill_status` — LLM 回补进度

---

## 4. agentqmt_qmt（远程 9 工具）

迅投 miniQMT MCP 服务，跑在 Windows 实盘主机上，提供实盘交易能力：

### 查询功能
- `qmt_status` — miniQMT 连接状态（账户、userdata 路径等）
- `qmt_get_holdings` — 账户资金、持仓、今日/昨日盈亏
- `qmt_get_quotes` — 获取一个或多个股票的最新快照
- `qmt_list_orders` — 列出未成交/近期委托单
- `qmt_export_orders` — 导出当日所有委托单（含已撤销/废单）
- `qmt_export_trades` — 导出当日成交记录（交割单）到 JSON/CSV
- `qmt_get_broker_history` — 查询历史委托/成交（按日期范围）

### 交易功能
- `qmt_place_limit_order` — 限价下单（实盘模式由 AGENTQMT_MCP_LIVE_TRADING 控制）
- `qmt_cancel_order` — 按 broker order_id 撤单

---

## 5. datapro（远程 1 工具）

火山引擎字节跳动 DataPro 专业数据检索 MCP：

- `datapro_search` — 统一检索入口，支持：
  - 股票金融数据
  - 企业工商/风险信息
  - 学术文献
  - 新闻资讯
  - 政策解读
  - 百科常识

---

## 6. xtick（本地 43 工具）

XTick 行情 MCP，提供高精度行情：

**核心能力：**
- `list_instruments` — 股票/指数/ETF 列表
- `trade_calendar` — A 股交易日历
- `financial_indicators` — 财报/每股指标
- `kline_daily` / `kline_week` / `kline_month` — 多周期 K 线
- `kline_1min` — 1分钟实时行情
- `auction` — 集合竞价实时
- `orderbook` — 五档盘口实时
- `dragon_tiger` — 龙虎榜

---

## 7. vibe-trading（本地 78 skill / 29 swarm / 54+ tool · ⭐ 核心投研工作台）

**2026-07-07 重分类**:此前标为"通用 54 工具",实测发现是**产品级投研工作台**,是 tushare/xtick 之外的独立数据+分析双通道。评估纪要见 `vibe_trading_skill_evaluation_20260707.md`。

### 数据工具(54+ · 部分子集)
- **市场行情**: `get_market_data`(yfinance/okx/tushare/akshare/ccxt 多源自动路由)
- **A 股专用**: `get_block_trades`(大宗交易+营业部席位) / `get_margin_trading`(两融日度) / `get_dragon_tiger`(龙虎榜) / `get_northbound_flow` / `get_lockup_expiry`(解禁) / `get_shareholder_count`
- **基本面**: `get_financial_statements`(三表) / `get_stock_profile`(US/HK) / `get_sec_filings`(US) / `get_research_reports`(A 股卖方) / `get_macro_series`(FRED)
- **板块归属**: `get_sector_info`(21 板块一次拿全) / `get_stock_news`(新闻头条) / `get_fund_flow`(主力/超大/大/中/小单)
- **通用**: `read_url` / `read_document` / `web_search` / `search_symbol` / `iwencai_search`(需 key)

### skill 层(78 个 · 主题清单)
- **A 股风控**: ⭐ `ashare-pre-st-filter`(20 页产品级双轴风险评分)
- **财报分析**: ⭐ `financial-statement`(三表勾稽 + 12 大红旗 + 杜邦分解)
- **估值**: ⭐ `valuation-model`(DCF/DDM/SOTP + 10 大估值陷阱)
- **技术面**: 缠论 / 艾略特波浪 / SMC / 市场微观结构(6 个 pattern skill)
- **因子**: `factor-research` + `alpha-zoo`(Kakushadze 101 / GTJA 191 / Qlib 158)
- **事件驱动**: `earnings-forecast` / `event-driven` / `pead-strategy`
- **策略**: `strategy-generate` / `risk-analysis` / `portfolio-construction`

### swarm 预设(29 个 · 代表)
- ⭐ `investment_committee`(4 agent:多空辩论 + 风控 + PM)
- ⭐ `technical_analysis_panel`(6 agent 并行 TA)
- `sector_rotation_team` / `earnings_research_desk` / `macro_strategy_room` / ...

### 研究目标 & 证据管理
- `start_research_goal` / `add_goal_evidence` / `update_research_goal_status`
- 支持有审计的长任务(goal → criteria → evidence → completion)

### 已知问题
- `run_swarm` 目前有 `'LLMResponse' object has no attribute 'content_filter_triggered'` bug,4-agent 投委会启动即失败(待社区修复)
- `iwencai_search` 需要额外 key(可用本地 iwencai-cli 替代)

### 分层使用建议(沧海嵌入方式)
| 沧海 R Agent | vibe-trading skill 挂载 |
|---|---|
| R2 主线板块 | `factor-research`(排序因子面) · `sector_rotation` swarm |
| R4 消息面 | `event-driven` / `pead-strategy` |
| R5 个股画像(六维) | `financial-statement`(财务) + `valuation-model`(估值) + 6 pattern skill(技术) + `get_block_trades`/`get_margin_trading`(筹码 · 已 patch) |
| R6 反证 | `ashare-pre-st-filter` + 12 大红旗 checklist |
| R7 资金面 | `get_block_trades` / `get_margin_trading` / `get_dragon_tiger`(已 patch) |
| D1 顶层聚合(未来) | `investment_committee` swarm 作为对照(待 bug 修复) |

---

## 8. obsidian（本地 16 工具）

Obsidian Local REST API，允许 Hermes 直接读写你的笔记：

### 文件操作
- `vault_list` — 列出 vault 目录下的文件和子目录
- `vault_read` — 读取文件内容和元数据
- `vault_write` — 创建或覆盖文件（自动创建父目录）
- `vault_append` — 追加内容到文件末尾
- `vault_patch` — 修补文件指定段落
- `vault_delete` — 删除文件
- `vault_move` — 移动/重命名文件
- `vault_get_document_map` — 获取文档结构映射

### 集成功能
- `active_file_get_path` — 获取当前在 Obsidian 中打开的文件路径
- `periodic_note_get_path` — 获取/创建周期笔记（每日/每周/每月）
- `search_query` — JsonLogic 高级搜索
- `search_simple` — Obsidian 内置简单搜索
- `tag_list` — 获取 vault 中所有标签及使用次数
- `command_list` — 列出所有已注册的 Obsidian 命令
- `command_execute` — 执行 Obsidian 命令
- `open_file` — 在 Obsidian UI 中打开文件

---

## 分层调用原则（沧海巨浪 v6）

| 层级 | 职责 | 主要 MCP |
|------|------|----------|
| **Alpha 选股** | 为什么关注 | weflow-analytics / wechat / datapro / tushareMcp |
| **Setup 形态** | 有没有可交易结构 | chenhailangju-research 四色四量 / xtick / chart |
| **Execution 执行** | 下单/持仓 | agentqmt_qmt |

---

## 配置说明

- API key：所有 6 个 Hermes 子profile 已统一使用新 key(见 `.env` `DATAPRO_AGENT_PLAN_KEY`,勿写入本文档明文——2026-07-04 git init 前已脱敏)
- Tushare token：见 `.env` `TUSHARE_TOKEN`(2026-07-04 git init 前已脱敏,勿写入本文档明文)
- weflow-analytics URL：https://swl888aaa.ngrok.app/mcp/sse
- agentqmt_qmt URL：http://192.168.3.17:8787/mcp?token=chzlqmt-mcp-change-me-to-long-random
