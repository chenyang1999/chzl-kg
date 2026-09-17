# Skill 全景目录 & 使用指南

**整理日期**: 2026-08-06  
**覆盖范围**: SkillHub 官方 26 个 + 社区 96 个 + 沧海巨浪自建 skills  
**目标**: 一份文档说清楚"每个 skill 是什么、装没装、能干什么"

---

## 一、Skill 生态全图

```
SkillHub (@ iwencai.com/skillhub)
├── ⭐ 官方出品（26个）— 同花顺官方维护，品质保障
│   ├── 行情/板块/选股类（问财选A股/港股/美股/ETF/可转债/基金/期权）
│   ├── 数据查询类（公告/研报/新闻/指数/行情/财务/资金流）
│   ├── 宏观/事件/公司经营类
│   └── 工具类（模拟炒股/基本资料）
│
├── 🌍 技能社区（96个）— ClawHub 等社区创作者
│   ├── 量化框架（技术指标/多因子/机器学习/统计）
│   ├── 技术分析（B超/缠论/K线形态/艾略特波浪/一目均衡）
│   ├── 事件驱动（并购/回购/预增/业绩/监管内幕）
│   ├── 行为金融 & 情绪（行为金融/情绪分析/舆情/聪明钱）
│   ├── 宏观/地缘/全球资产配置
│   ├── 固收/信用/债券/利率
│   ├── 期权/波动率
│   ├── 链上/加密/DeFi
│   ├── 组合/风控/归因
│   ├── 投研报告（财报/研报/尽调/估值）
│   └── 投资哲学（股票大作手/桥水/方舟/贝莱德/指数投资）
│
└── 🏠 沧海巨浪自建（21个）
    ├── R1-R7 研究 Agent Skills（主线/风格/情绪/消息/个股/反证/资金）
    ├── D1 决策 Agent + E1 复盘 Agent
    ├── 数据获取（fetch/morning/xtick/weflow/sise）
    ├── 知识库（行为金融/情绪/缠论/大宗商品/宏观/金融监管）
    └── 专项工具（打板/持仓诊断/浮盈追踪/观察池）
```

---

## 二、已安装 Skills 清单

### ✅ 已安装（可立即使用）

#### A. 问财官方数据类（iwencai API key 已就绪）

| Skill 名称 | 安装位置 | 用途 | 调用方式 |
|-----------|---------|------|---------|
| **announcement-search** | `~/.openclaw/workspace/skills/announcement-search/` | A股/港股/基金/ETF公告查询（分红/回购/重组/定期报告等） | `announcement-search` skill + CLI |
| **report-search** | `~/.openclaw/workspace/skills/report-search/` | 主流投研机构研报搜索 | skill 调用 |
| **news-search** | `~/.openclaw/workspace/skills/news-search/` | 财经资讯搜索（官媒/垂直媒体/上市公司官网） | skill 调用 |
| **hithink-astock-selector** | `~/.openclaw/workspace/skills/hithink-astock-selector/` | 问财自然语言 A 股筛选 | skill 调用 |
| **hithink-business-query** | `~/.openclaw/workspace/skills/hithink-business-query/` | 主营业务/客户/供应商/参控股/重大合同 | skill 调用 |
| **hithink-event-query** | `~/.openclaw/workspace/skills/hithink-event-query/` | 业绩预告/增发/质押/解禁/调研/监管函 | skill 调用 |
| **hithink-industry-query** | `~/.openclaw/workspace/skills/hithink-industry-query/` | 行业估值/财务/盈利/行情/排名 | skill 调用 |
| **hithink-insresearch-query** | `~/.openclaw/workspace/skills/hithink-insresearch-query/` | 研报评级/业绩预测/ESG/基金评级/券商金股 | skill 调用 |
| **hithink-management-query** | `~/.openclaw/workspace/skills/hithink-management-query/` | 股本结构/股东户数/前十大股东/实控人 | skill 调用 |
| **hithink-market-query** | `~/.openclaw/workspace/skills/hithink-market-query/` | 实时价格/ETF/指数/资金流向/技术指标 | skill 调用 |
| **hithink-sector-selector** | `~/.openclaw/workspace/skills/hithink-sector-selector/` | 行业估值+资金流向+涨跌幅多条件板块筛选 | skill 调用 |
| **hithink-zhishu-query** | `~/.openclaw/workspace/skills/hithink-zhishu-query/` | 上证/沪深300/创业板/恒生/纳斯达克指数行情 | skill 调用 |

#### B. 沧海巨浪自建研究 Skills（`skills/` 目录）

| Skill | 类型 | 用途 |
|-------|------|------|
| **analyze_style_v1** | R1 风格 Agent | 22风格板块聚类差值+位置分析，输出"市场性格" |
| **analyze_main_sectors_v1** | R2 主线 Agent | 全市场板块挑1-3条主线，每条3-5只候选龙头 |
| **analyze_sentiment_resonance_v1** | R3 情绪 Agent | Tushare/XTick热榜+wechat群聊+全市场情绪周期定位 |
| **analyze_news_impact_v1** | R4 消息面 Agent | 公众号+财联社+突发新闻→板块/个股催化映射 |
| **analyze_stock_profile_v1** | R5 个股画像 Agent | 龙头候选六维画像+业务档案+认知偏差风险提示 |
| **analyze_devil_advocate_v1** | R6 反证 Agent | 消费R1-R5全部产出，反向找漏洞 |
| **analyze_capital_flow_v1** | R7 资金面 Agent | 时序资金流+跷跷板配对+游资协同+昨日资金前十 |
| **main_decision_v1** | D1 决策 Agent | 汇总R1-R7输出，生成次日操盘计划和仓位管理 |
| **daily_review_v1** | E1 复盘 Agent | 读R1-R7+D1产出，输出每日复盘报告 |
| **observation_tracking_v1** | 观察池 Agent | 跟踪自选标的持仓/浮盈/止损/条件单状态 |
| **fetch_all_sources_v1** | 数据获取 | 抓取公众号/财联社/群聊/快讯/xtick/sise/weflow |
| **hotlist_rank_signal_v1** | 热标信号 | 每日打板/炸板/强势低吸信号汇总 |

#### C. 知识库 Skills（`skills/` 目录）

| Skill | 来源 | 用途 |
|-------|------|------|
| **行为金融分析** | ClawHub | 过度反应/反应不足/情绪周期/认知偏差/量化去偏 |
| **市场情绪分析** | ClawHub | 恐慌贪婪指数/Put-Call/融资融券/北向资金/舆情量化 |
| **缠论形态识别** | ClawHub | 分型/笔/中枢/一买一卖二三买/多周期分析 |
| **大宗商品分析** | ClawHub | 原油供需/黄金定价/铜先行指标/库存周期/期货结构 |
| **金融监管知识库** | ClawHub | A股涨跌停/ST退市新规/港股T+0/美股PDT/加密监管 |
| **全球宏观分析框架** | ClawHub | 央行政策/汇率预测/地缘政治/资本流动/跨资产配置 |
| **小盘成长股挖掘** | ClawHub | A股小市值高成长筛选/专精特新企业识别 |
| **事件驱动策略** | ClawHub | 新闻/公告/宏观事件情绪评分→交易信号 |
| **《股票大作手》交易哲学** | ClawHub | Livermore 择时/买卖点/金字塔加码/移动止损 |
| **市场情绪偏离分析** | ClawHub | 逆向投资/超跌反弹/市场错杀机会识别 |

#### D. 工具型 Skills（`~/.openclaw/workspace/skills/`）

| Skill | 用途 |
|-------|------|
| **chart-image** | K线/分时图渲染 |
| **coding-agent** | 代码编写/调试 |
| **debug-pro** | 代码调试 |
| **excalidraw-flowchart** | 手绘风格图表 |
| **git-essentials** | Git 操作 |
| **github** | GitHub PR/Issues/CI |
| **local-rag-search** | 本地知识库检索 |
| **memory-system-v2** | 记忆系统 |
| **qmd-search** | 投研文档搜索 |
| **safe-exec** | 安全代码执行 |
| **slack** | Slack 消息 |
| **smtp-send** | 邮件发送 |
| **webapp-testing** | Web 应用测试 |
| **playwright-cli** | 浏览器自动化 |
| **test-runner** | 测试运行 |
| **skill-vetter** | Skill 质量评估 |

---

## 三、未安装但值得关注的 Skills

### 推荐安装（按优先级）

#### 🔴 高优先级（研究/决策直接相关）

| Skill | 来源 | 理由 |
|-------|------|------|
| **研报搜索**（report-search同类） | 官方 | 中报季找研报评级/目标价/业绩预测 |
| **行业轮动监控** | ClawHub | 判断6-12个月行业轮动，补充R2 |
| **催化剂日历** | ClawHub | 财报日期/会议/政策节点，提前布局 |
| **产业链解读** | ClawHub | 拆解产业链结构，辅助R5个股画像 |
| **投资逻辑跟踪** | ClawHub | 维护持仓 thesis，持续跟踪催化剂 |
| **ETF 分析** | ClawHub | 指数化操作时用 |

#### 🟡 中优先级

| Skill | 来源 | 理由 |
|-------|------|------|
| **量化因子选股** | ClawHub | 多因子A股筛选，补充量化视角 |
| **K线形态识别** | ClawHub | 15种经典K线形态，补充技术面 |
| **公司事件驱动分析** | ClawHub | 并购/回购/定增/股权激励/A股ST预警 |
| **SEC 文件分析** | ClawHub | 美股持仓时用 |
| **舆情监控达人** | ClawHub | 社交媒体舆情量化 |

#### 🟢 低优先级（特定需求时用）

| Skill | 来源 | 理由 |
|-------|------|------|
| **期权策略框架** | ClawHub | 有期权交易需求时 |
| **波动率策略** | ClawHub | 期权/波动率相关 |
| **DeFi 收益分析** | ClawHub | 加密相关 |
| **固收/信用分析** | ClawHub | 有债券/可转债需求时 |
| **LBO 模型** | ClawHub | PE 相关 |

---

## 四、环境变量速查

```
# iwencai API（announcement-search / hithink 系列 / 问财选股）
IWENCAI_BASE_URL=https://openapi.iwencai.com
IWENCAI_API_KEY=sk-proj-...La_w          # 在 ~/.zshrc

# Vibe-Trading MCP（xtick / tushare / 资金流 / 龙虎榜）
VIBE_TRADING_IWENCAI_KEY=sk-proj-...La_w  # 在 Vibe-Trading/.env
VIBE_TRADING_OPENAPI_KEY=...              # 在 Vibe-Trading/.env

# xtick MCP
XTICK_URL=https://某一地址                   # 在 config.yaml

# SkillHub CLI
PATH+=~/.local/bin                          # iwencai-skillhub-cli 路径
```

---

## 五、Skill 调用指南（按场景）

### 场景1：开盘前准备（07:00-09:15）

```
1. fetch_all_sources_v1  → 抓取夜间数据（公众号/财联社/外盘）
2. hithink-zhishu-query  → 确认外围市场（纳指/标普/VIX）
3. analyze_style_v1       → 判断今日市场风格
4. analyze_main_sectors_v1 → 选出1-3条主线
5. hithink-sector-selector → 验证主线板块资金流向
6. main_decision_v1      → 生成盘前操盘计划
```

### 场景2：盘中监控（09:30-15:00）

```
1. hithink-market-query   → 实时价格/涨跌/成交量
2. analyze_sentiment_resonance_v1 → 情绪周期定位
3. hithink-market-query   → 主力资金流向
4. hotlist_rank_signal_v1 → 打板/炸板信号
5. observation_tracking_v1 → 持仓/浮盈/止损状态
```

### 场景3：午盘复盘（11:30-12:00）

```
1. analyze_news_impact_v1 → 盘中重大消息影响评估
2. analyze_capital_flow_v1 → 上午资金流向
3. auction_amendment_v1   → 竞价+盘中信号汇总
```

### 场景4：收盘复盘（16:00-17:00）

```
1. analyze_capital_flow_v1 → 全天资金面分析
2. analyze_sentiment_resonance_v1 → 情绪变化
3. analyze_main_sectors_v1 → 主线是否延续
4. analyze_devil_advocate_v1 → 持仓逻辑证伪
5. daily_review_v1        → 生成每日复盘报告
```

### 场景5：周末深度研究

```
1. hithink-industry-query  → 行业估值/盈利/行情
2. hithink-insresearch-query → 券商金股/研报评级
3. hithink-business-query  → 主营/客户/供应商调研
4. 行为金融分析           → 认知偏差评估
5. 缠论形态识别           → 技术面验证
6. 小盘成长股挖掘         → 扩池备选
```

### 场景6：公告/新闻紧急查询

```
1. announcement-search     → 查分红/回购/重组/定期报告
2. hithink-event-query    → 业绩预告/解禁/调研/监管函
3. news-search            → 突发新闻/政策
4. report-search          → 相关研报深度阅读
```

---

## 六、安装命令参考

```bash
# 查看已安装 skills
iwencai-skillhub-cli list

# 安装新 skill
iwencai-skillhub-cli install <skill-name>

# 强制重装（覆盖）
iwencai-skillhub-cli install <skill-name> --force

# 卸载
iwencai-skillhub-cli uninstall <skill-name>
```

### 推荐安装命令

```bash
# 官方数据类
iwencai-skillhub-cli install hithink-astock-selector    # 问财选A股
iwencai-skillhub-cli install hithink-sector-selector   # 板块筛选

# 研究辅助类
iwencai-skillhub-cli install 行业轮动监控              # 宏观驱动板块配置
iwencai-skillhub-cli install 催化剂日历                 # 财报/会议节点
iwencai-skillhub-cli install 产业链解读                 # 辅助个股画像
iwencai-skillhub-cli install 投资逻辑跟踪               # 持仓 thesis 追踪
iwencai-skillhub-cli install 量化因子选股               # 多因子筛选
iwencai-skillhub-cli install K线形态识别               # 技术面验证
iwencai-skillhub-cli install 公司事件驱动分析           # 并购/回购/定增
```

---

## 七、Skill 命名与路径规范

```
# SkillHub CLI 安装路径
~/.openclaw/workspace/skills/<skill-name>/

# 沧海巨浪自建 skills
/Users/chenyang/Downloads/demo/沧海巨浪/skills/<skill-name>/

# Skill 调用约定
- skill 名称用中文：<skill-name>（中文 skill 名直接用中文）
- MCP 工具调用：mcp__vibe_trading__<tool_name>（双下划线）
- hithink 系列：skill name 直接用 hithink-xxx
```

---

## 八、已知限制

| 限制 | 说明 | 替代方案 |
|------|------|---------|
| `mcp__vibe_trading__iwencai_search` | 返回 401（需要特定 source），key 有效但平台未激活该 API | 用 `announcement-search` skill 或 `hithink-astock-selector` |
| 美股/港股实时行情（vibe MCP） | `get_market_data` 对 yfinance 格式支持不完整 | 用 xtick 拉 A 股；港股用 `hithink-sector-selector` 港股通 |
| xtick MCP 时区 | 日期格式必须 YYYY-MM-DD（不能用 YYYYMMDD） | — |
| 非交易日数据 | xtick market_emotion 对非交易日返回上一交易日数据 | 需过滤交易日历 |

---

*本目录基于 https://www.iwencai.com/skillhub 页面结构整理  
*官方 26 + 社区 96 + 沧海巨浪自建 21 = 143 个 skills*  
*最后更新：2026-08-06*
