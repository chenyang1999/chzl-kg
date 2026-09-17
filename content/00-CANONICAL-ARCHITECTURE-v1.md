# 沧海巨浪 · 权威架构文档 v1

**版本**:v1.2(2026-07-04 深夜)
**作者**:用户 × Hermes 6 小时对话沉淀
**状态**:骨架 + 正文一体化,首个可施工版本
**替代关系**:本文档定稿后成为 `docs/` 目录的**唯一权威**架构描述。现有
`00-研究端总览.md` / `03-核心设计原则.md` / `10-研究端Agent骨架-v1.md` /
`refactor_plan.md` 等文档降级为**参考文献**(不删,但不作权威)。

**v1.2 相对 v1.1 的宪法级修订**:
- §1.1 原则一改为"Agent 的比较优势是无情绪,不是无客观"(偏见追溯性降为配套机制)
- §1.4 明确"用户经验是组件不是主体"、"E2 有权对用户经验提修订建议"
- §5.2 验证 4.5 新增:E2 审 user_preferences.yaml,提修订建议,用户 sign-off 生效
- §5.1 判断节点从 4 个写死改为"由 T3 实盘数据决定"

**阅读顺序**:0 诊断 → 1 宪法 → 2 骨架 → 3 数据流 → 4 skill → 5 机制 → 6 交互 → 7 路线 → 附录

<!-- SECTION_END_0 -->

---

## 第 0 章 · 为什么有这份文档

### §0.1 当前问题的诊断

到 2026-07-04 为止,沧海巨浪系统有以下**症状**:

1. **持仓实盘代价已经出现**:600522 -14.29% / 603019 -13.79% / 000063 大浮亏,裸奔至 07-06 周一开盘。这不是坏运气,是**契约模糊**的结果 —— cursor 与 Hermes 并行改同一份 `watchlist_plan.json` 导致 exit_rules 覆盖冲突,浮亏票没有及时执行 stop_loss。
2. **技术栈臃肿**:项目内 `skills/` 目录 16 个 skill,`~/.hermes/skills/` 领域 skill 数十个,多套 profile(canghai-research / trading / intel / risk / orchestrator)并行,cron 拓扑重复(daily-spine 与 daily-sync 同时 19:35 跑),多套 `data/` 路径(runtime / research / plans / reports / cache 各自演化)。
3. **agent 边界模糊**:R1-R7 的分工在 `docs/10-研究端Agent骨架-v1.md` 里写了 3 个版本,每次讨论都在漂移;funds_validator 和 R2 有重叠,event_analyzer 和 R4 有重叠,pattern_recognizer 和 R1 有重叠。
4. **盘中 cron 全崩**:07-03 起 `trading_jobs.sh intraday-once` 全部失败,原因初步定位为 event schema 版本漂移(v3 迁 v4 未完成),但根因未找到,cron 现处**暂停**状态。
5. **Hermes cron 也有历史脏数据**:job `11cee3888842` 暂停,macOS crontab 12 行,多个 job 引用的 skill 已被改名或删除。

**诊断结论**:**架构层面契约不明,是所有症状的共同根因**。修 event schema、修 cron、加 exit_rule 都是**症状级动作**,不解决根因。**根因是**:
- 没有唯一的 plan writer(cursor 和 Hermes 都在写)
- 没有唯一的架构文档(3 个版本的 agent 骨架都在流通)
- 没有 profile 之间的物理隔离(data 目录混用)
- 没有 skill 归属表(改一个 skill 不知道谁在依赖它)

### §0.2 上一版重构的失败教训

**2026-07-03 的 9-Agent 重构半途而废**。经过:
- 早上定 9-Agent 骨架(R1-R7 + D1 + E1),文档 `10-研究端Agent骨架-v1.md` 落盘
- 中午开始建 skill 骨架(`analyze_style_v1` / `analyze_sentiment_resonance_v1` / `analyze_devil_advocate_v1` / `hotlist_rank_signal_v1` / `observation_tracking_v1` / `fetch_all_sources_v1`)
- 下午发现 event schema v3→v4 迁移未完成 → 盘中 cron 全崩
- 傍晚放弃 9-Agent 施工,回退到修 cron
- 晚上到现在:cron 未修,9-Agent 停滞

**失败原因**:**没有先立宪法就开始改代码**。9-Agent 骨架写了,但**没有写清楚**:
- 为什么是 9 不是 8
- Agent 之间怎么协作(delegation 还是独立 profile)
- data 目录归属
- 与现有 skill 的兼容策略
- 换基座怎么办

**结果**:施工时每一步都要临场决定,决定错了就回滚,一天下来只完成 skill 骨架,核心逻辑没落地。

**本次重构的第一原则**:**先立宪法,再动代码**。本文档就是宪法。**只有本文档定稿,施工才开始**。

### §0.3 本次重构的边界

**不推翻**:
- 现存 16 个 canghai skill 的核心分析逻辑(它们里面的 tushare/xtick 调用、评分权重、六维画像等是资产)
- MCP 接入(tushare / xtick / datapro / weflow / wechat-cli / QMT / hithink 等)
- Obsidian `chzl_kg/` 知识库目录结构
- watchlist_plan.json 主 schema(schema 是可演化的资产)

**推翻**:
- Profile 编排(旧 canghai-intel / canghai-risk / canghai-orchestrator 删除,新建 canghai-fetch / canghai-plan)
- Cron 拓扑(旧 crontab 保留过渡期,新 cron 独立时段并行验证)
- `data/` 目录组织(重建 6 大子目录,每个 profile 只写自己那份)
- Agent 分工(R1-R7 + D1 + P1 + P2 + E1 + E2 共 12 个执行单元,归 5 个 profile)
- 老 canghai_* 系列 sub-agent 的调度模型(canghai_main_agent_v2 作为唯一 orchestrator 的模型作废)

### §0.4 本文档的地位

- 本文档是**施工前**的宪法。**施工完成后**,根据实盘运行结果,本文档需要修订 → v2。
- 本文档中每一个"必须"/"禁止"都是**硬约束**。想违反 → 修文档,再改代码;不能反向。
- 本文档与其他 docs 冲突时,**以本文档为准**,其他文档标注 "已被 v1 覆盖"。
- 本文档由用户 sign-off 生效。E2 自进化机制**可以对本文档提修订建议**,但**不能自动改本文档**。

<!-- SECTION_END_1 -->

---

## 第 1 章 · 宪法(3 条硬原则 + 用户三重角色)

**本章 4 条内容是 2026-07-04 凌晨用户自己挖出来的判断,不是 Hermes 推销的观点。凡与之冲突的架构决策,冲突方让位。**

### §1.1 原则一:Agent 的比较优势是无情绪,不是无客观

**核心断言**:**"客观 agent"是伪目标。Agent 相对人的核心优势是**没有情绪干扰**,不是**更客观**。架构的所有设计以放大无情绪优势为准,承认偏见永远存在。**

**为什么"客观"是伪目标**:
- 系统里流通的每一份 artifact 都携带偏见来源:数据源采样偏见(20 个公众号是"中文财经短线圈"的采样)、意识形态偏见(WeFlow 群体本身参与协调游戏)、时代偏见(训练数据凝固在某个时点的因果框架)、规则偏见(用户"单票 ≤15%"是极强的仓位偏好)。
- **"无偏见的 agent 无法做决策"**:A 股是叙事驱动市场,不是有效市场,要在其中赚钱必须**站在某个叙事上押注**;绝对客观的 agent 只会等权分散 → 市场平均收益(甚至更差)。

**Agent 相对人的真正优势(无情绪)**:
- **不套牢**:亏损票不会因为"套住了"而拒绝换仓
- **不贪心**:盈利票不会因为"还想涨"而拒绝止盈
- **不硬撑**:市场结构不好不会因为"手痒"而硬开仓
- **不迟疑**:signal 到了就执行,不因心情推迟

**这四条是**用户 2026-07-04 深夜原话**,写进宪法**:
> "Agent 相对来说比较理性,没有很多情绪上的干扰。这恰恰是它比较大的优势:它不会因为一个票亏了很多钱就有一种'套牢'的感觉,或者因为一个票赚了很多钱就一直在那贪心,也不会在市场大盘表现不好时还要硬着头皮去做,没有太多非理性的判断。"

**架构对"无情绪优势"的放大**:
- **execute 层全 Python + 硬风控**:确保执行不受任何情绪影响(见 §5.1 L1)
- **review 层 fresh context 强制**:E1/E2 每次开新 context,不携带昨天的 confidence bias(见 §5.1 L2/L3)
- **判断节点严格边界**:即使有 LLM 参与 execute 层(判断节点),也**只输出枚举结果**、超时保守默认(见 §5.1 层 3)

**偏见追溯性(配套机制)**:
- 因为偏见永远存在,系统必须**能追溯每份 artifact 的偏见来源**、可审计、可撤销
- 具体机制:5 层偏见承载位置(§1.4)+ 5 层对抗性验证(§5.2)
- **但偏见追溯性不是主目标,是保证"无情绪优势不被偏见污染"的辅助机制**

### §1.2 原则二:LLM 时间衰减必须由架构对冲

**核心断言**:**LLM 的因果框架会随时间滞后,不是数据补齐能解决的;架构必须允许基座换代(3-6 个月一次),同时资产完全保留**。

**衰减的 3 层机制**:

**层 1 · 事实缺失(表面层)**:
- LLM 不知道训练截止之后的事件
- 通过 fetch 塞给它原始数据 → 能读、能引用、能分析
- **这层最好补**

**层 2 · 因果关系失效(中间层)**:
- 市场里"因果关系"随时代变化(2020-2021 "美联储降息→A 股涨" 有效,2023 起失效)
- LLM 脑子里"因果模型"是训练时凝固的
- 看到新数据会**用旧因果框架解释**,得出**看起来合理但实际错的结论**
- **这层难补** —— 就算 fetch 给最新数据,LLM 也在用滞后的框架

**层 3 · 分布外泛化崩溃(深层)**:
- 训练时没见过的市场状态,LLM 会 **confidently 输出错误分析**
- 不会说"我不知道",而是**生成看似自洽但实际是训练时不相关知识拼凑的伪分析**
- **这层无法通过喂数据解决**,必须模型本身更新

**对冲的 3 条路径**:

**路径 A · 定期换基座**:
- 每 3-6 个月切换到最新基座(ark → Claude 5 → GPT-5.5 → 未来模型)
- 架构不能绑定任何单一 provider
- **Hermes 天然支持 provider 切换**,施工时 profile 层不 hardcode 模型名

**路径 B · human_thesis 显式化因果框架**:
- 用户通过 `data/human_thesis/` 提交 top-down 判断(如"科技化债")
- 这些 thesis 等于**在替代 LLM 脑子里滞后的因果框架**
- Thesis 有生命周期(有效期 + 破位信号)
- E2 每周评估 thesis 解释力(见 §5.2 验证 4)

**路径 C · Python 收口交易端**:
- Execute 层用 Python 规则引擎,不受 LLM 时间衰减影响
- LLM 判断节点严格受限(3 秒响应 / 枚举输出 / 超时保守 fallback)
- 即使 LLM 完全失灵,execute 也能靠 Python 规则维持运行

**基座换代频率现实校准**:
- 2026-07 现状:GPT-5.5 / Claude 5 已在市场,ark-code-latest 明显滞后
- 意味着基座实际更新速率是 **3-4 个月一次**,不是原估的 6-12 个月
- **架构必须承受**"一年内换 2 次基座",harness 可迁移性是**生存能力**,不是锦上添花

### §1.3 原则三:Harness 是资产,基座是商品

**核心断言**:**基座 LLM 是可替换商品,skills / profile SOUL / human_thesis / user_preferences / schema / rules / 历史数据是不可替换资产;架构的所有取舍以"最大化资产保留、最小化基座绑定"为准**。

**资产 vs 商品对照表**:

| 组件 | 性质 | 换基座后是否保留 |
|:-|:-|:-|
| 基座 LLM(ark / Claude 5 / GPT-5.5) | 商品 | 换掉 |
| 所有 skills | **资产** | 保留(prompt 层可能需微调) |
| Profile SOUL.md | **资产** | 保留 |
| human_thesis/*.md | **资产** | 保留 |
| user_preferences.yaml | **资产** | 保留 |
| watchlist_plan schema | **资产** | 保留 |
| observation_tracking 历史 | **资产** | 保留 |
| 错题本 corrections/ | **资产** | 保留 |
| E2 skill 修改建议历史 | **资产** | 保留 |

**Skill 双层结构**(保证跨基座迁移):
- **skill_logic.md**:模型无关的逻辑描述(输入 / 输出 / 约束 / 数据源)
- **skill_prompt_<model>.md**:针对当前基座的 prompt 实现
- 换基座只重写 prompt,logic 不动

**Schema-first, prompt-second 原则**:
- 所有 skill 输出**先定 pydantic schema**,再写 prompt
- Schema 是模型无关的契约
- Prompt 只负责"引导 LLM 填这个 schema"
- 换基座只影响引导方式,不影响契约

**跨基座测试标注**:
- 每个 skill 头部 YAML frontmatter 加 `tested_with:` 字段
- 记录该 skill 在哪些基座上测过、吻合度如何、最后调优日期
- 换基座前批量 review 该字段,决定哪些 skill 需要 retest

**多基座策略**(施工到 T4 后可实施):
- **canghai-plan (D1 / P1 / P2)**:配 Claude 5 或最新最强模型(需推理深度)
- **canghai-review (E1 / E2)**:配 Claude 5(需诚实复盘 + 打破 confidence bias)
- **canghai-research (R1-R7)**:可配便宜快模型(广域信息处理)
- **canghai-execute 判断节点**:配最便宜快模型(3 秒响应硬要求)
- **canghai-fetch**:几乎无 LLM,可配最便宜

**跨市场可迁移性(意外收益)**:
- Skills / thesis / rules / observation_tracking 长期看**可跨市场复用**
- 换到港股:核心 skill 保留,数据源改(WeFlow → 港股社群)
- 换到 crypto:核心 skill 保留,数据源改(Tushare → CoinGecko)
- **用户当前不做跨市场,但架构不排除未来可能**

### §1.4 用户在系统里的三重角色(宪法级)

**核心断言**:**用户的输入是**组件**,不是**决策主体**。用户的经验通过 3 条通道贡献,不进入 R1-R7/D1/execute 的判断逻辑;E2 自进化机制有权对用户经验提修订建议**。

**用户的三重角色**:

**角色 1 · 基础设施提供者**:
- 加数据源、加 MCP、造更好的 fetch skill
- 修 profile 配置、修 cron、修 schema
- **这是用户的核心贡献**,不可替代

**角色 2 · 视野守门员**:
- 通过扩展数据源清单减少系统采样偏见
- 维护 source_diversity_matrix(数据源多样性矩阵)
- 每加一个数据源必须回答"在方法论 / 意识形态 / 时间尺度 / 地域 4 维中,和现有源不同的是哪一维"

**角色 3 · 进化审阅员**:
- Review E2 skill 修改建议,sign-off 或拒绝
- Review E2 preferences 修订建议,sign-off 或拒绝
- Review E2 thesis 撤销建议,sign-off 或拒绝
- **用户是唯一 skill/preferences/thesis 变更触发者**

**两条可选补充通道**(用户经验的承载位置):

**通道 α · user_preferences.yaml**(永久硬先验):
- 用户在 `data/user_preferences.yaml` 声明永久偏好
- 举例:"龙头优先"、"单票 ≤15%"、"板块 ≤40%"、"prefer_pullback_over_breakout"
- **永久生效**,无破位条件,但 E2 可以提修订建议

**通道 β · human_thesis/**(临时视角):
- 用户在 `data/human_thesis/*.md` 提交 top-down 判断
- 举例:"科技化债 = 政策工具 → 板块选择"
- **临时视角**,有效期 + 破位信号 + 影响范围,可撤销即删
- **不进 skill,零永久污染**

**用户经验**不进入**的地方**:
- 不进 R1-R7 判断规则的具体代码
- 不进 D1 最终 plan 的直接决定(只能通过 preferences/thesis 间接影响)
- 不进 execute 硬风控(除通过 preferences 的 position_hard_rules 间接影响)

**"用户不是首席策略师"**:
- 用户的经验是**输入组件**,不是**最终判断者**
- 系统的最终判断由 R1-R7 + D1 + E2 迭代产生
- 用户的特权是**被承载**(preferences + thesis)、**被审阅**(E2 建议提给用户 sign-off),**不是被服从**

**E2 对用户经验的修订权**:
- **E2 有权对 preferences 提修订建议**(阈值调整、加规则、删规则)
- **E2 有权对 thesis 提撤销/修订建议**(基于兑现率数据)
- **E2 不能自动改**,必须用户 sign-off
- **这一条是**用户 2026-07-04 深夜原话**,写进宪法**:
> "人的经验可以作为一部分的输入或者组件注入到整个系统中,但是自进化的机制仍然会去对其进行修订、更改和反思。"

---

## 第 2 章 · 系统骨架(5 profile + 12 执行单元)

### §2.1 5 profile 中性命名

| Profile | 类脑对应(仅记忆) | 职责 | 载体 | LLM 会话数/日 |
|:-|:-|:-|:-|:-|
| `canghai-fetch` | 丘脑 | 数据抓取 + MCP 健康检查 + 竞价快照 + 午盘快照 + market_scanner | Python 为主 + 少量 LLM 调用 | 0-1 |
| `canghai-research` | 皮层 | R1-R7 分析,主控 + 7 sub-agent(delegation) | 主控 LLM + delegation | 1 主控 + 7 delegation |
| `canghai-plan` | 前额叶 | D1 主决策 + P1 竞价校准 + P2 午盘修订 | LLM,每次 fresh context | 3 |
| `canghai-execute` | 纹状体+杏仁核+小脑 | 有状态市场感知服务:秒级 tick + 分钟级全市场 + 硬风控 + T 管理 + 判断节点 | Python 主导 + 受控 LLM 判断节点 | 视触发次数 |
| `canghai-review` | 海马 | E1 日复盘 + E2 周进化 | LLM,fresh context | 1-2 |

**共 5 profile,分别对应 5 种能力**:
- fetch = **感知**(数据流入 + 健康)
- research = **分析**(信息 → 结论)
- plan = **取舍**(结论 → 决策)
- execute = **执行 + 反应**(决策 → 下单 + 盘中判断)
- review = **反思**(结果 → 修订)

### §2.2 每个 profile 的"消灭测试"

**"如果消灭这个 profile 会怎样"** —— 这是我们判断 profile 是否**必要**的方法。

**消灭 canghai-fetch**:
- 数据抓取分散到每个 agent → 每个 agent 都要处理 MCP 健康检查、fallback、限流、缓存
- 数据版本漂移:R1 拉的和 R2 拉的可能不是同一时刻的快照
- 降级逻辑散落:20 号公众号挂了 R4 走 fallback,但 R7 不知道数据源已降级
- **结论:必须独立**

**消灭 canghai-research(把 R1-R7 拆成 7 个 profile)**:
- 7 倍配置成本(每个 profile 的 SOUL.md / cron / 环境变量)
- 7 倍冷启动时间(每个 profile 的 hermes 初始化)
- 跨 profile artifact 读取(R6 反证要读 R1-R5+R7 全部产出,7 profile 之间同步靠磁盘)
- 但**如果不拆**:一个 LLM 会话内做完 7 次分析,注意力被稀释
- **结论:合并为 1 profile + delegation**。delegation 隔离 sub-agent context,主控只看每个 sub-agent 的最终输出,不受中间 tool call 污染
- 每天 7 次 delegation call ≈ 7 个独立 LLM 会话,但共享 1 份 profile 配置

**消灭 canghai-plan(把 D1 塞回 canghai-research)**:
- D1 在同一 context 里跟做 R1-R7 的主控 → 做完 7 次分析后 confidence 已经很高
- **接着做取舍时会试图**"平衡所有 warning" → 持仓 >5、单票 <10%、板块过散
- **07-03 -14% / -13% 的直接机制就是这个**:D1 在 research context 内被 R2/R5 的多个 "opportunity" 感染 → 分散持仓 → 分散风控失效
- **结论:D1 必须 fresh context**,只看 R1-R7 的最终 artifact,不看中间推理过程

**消灭 canghai-execute(交易也用 LLM)**:
- LLM 处理"时间敏感+高频重复+确定性要求高"的任务不适合:
  - **成本**:秒级 tick 一天 4 万次调用,LLM 成本失控
  - **确定性**:同样输入 LLM 可能输出略微不同,交易系统不能容忍
  - **延迟**:秒级 tick 要求 100ms 级响应,LLM 200-2000ms
  - **Instruction-following 反噬**:LLM 在长 context 下会"发挥",不按 rule 执行
- **但完全无 LLM 也不对**:某些判断节点(如"板块效应是否成立")用 LLM 比硬编码好
- **结论:Python 主导 + LLM 判断节点(受控,3 秒内,枚举输出,超时保守 fallback)**

**消灭 canghai-review(复盘塞回 canghai-plan)**:
- LLM 在同一 context 里**不会背叛自己刚才的判断**
- 让 D1 复盘自己昨晚的 plan → confidence bias / sunk cost → 无诚实复盘
- **结论:review 必须 fresh context**,重新读 artifact,像第三方分析师那样评估

### §2.3 sub-agent 通过 delegation 实现,不通过 profile 拆分

- `canghai-research` 内 1 个主控 + 7 sub-agent(R1/R2/R3/R4/R5/R6/R7)
- 通过 `delegate_task(goal, context, toolsets)` API 委派
- 中间 tool call 不进主控 context,只回传最终 artifact 路径
- 主控串起时序:R1/R3/R4/R7 并行 → R2/R5 串行 → R6 消费所有 → 主控收集全部 artifact 路径 → 输出 research_summary.json

**Sub-agent 的 tool harness** 通过 `toolsets` 参数落地:
- R1 风格:`[file, tushare, xtick]`
- R2 主线板块:`[file, tushare, datapro, hithink]`
- R3 情绪:`[file, weflow, hotlist]`
- R4 消息面:`[file, wechat, tushare]`
- R5 个股画像:`[file, tushare, serenity-alpha, valuation]`
- R6 反证:`[file]` **禁 MCP**(反证必须从已有 artifact 找漏洞,不能自己去找新证据)
- R7 资金面:`[file, tushare, xtick, datapro]`

**这样即使 R7 想用 iwencai,不允许**(不在 toolsets 白名单内),SOUL.md 拦截。

**5 profile ≠ 5 hermes 会话**:sub-agent 是同一 profile 内 delegation,不是独立 profile。

### §2.4 12 执行单元的具体分工

| 单元 | 归属 profile | 时点 | 唯一职责 | 详细 spec |
|:-|:-|:-|:-|:-|
| **R1 风格** | research | 07:30 | 5 种市场模式识别 + 情绪浓度 + 仓位上限建议 | `docs/agents/R1-风格Agent.md` |
| **R2 主线板块** | research | 07:45 | 1-3 条主线 + 每条 3-5 只**龙头**(遵守 preferences) | `docs/agents/R2-主线板块Agent.md` |
| **R3 情绪与热度** | research | 07:30 | 三源共振主题(WeFlow + KOL + 热榜) | `docs/agents/R3-情绪与热度Agent.md` |
| **R4 消息面** | research | 07:30 | 事件抽取 + 板块/个股映射 | `docs/agents/R4-消息面Agent.md` |
| **R5 情报深挖** | research | 07:45 | R2 龙头逐票**六维画像 + serenity 基本面链** | `docs/agents/R5-情报深挖Agent.md` |
| **R6 反证** | research | 07:55 | 消费 R1-R5+R7,找漏洞,硬否决权 | `docs/agents/R6-反证Agent.md` |
| **R7 资金面** | research | 07:30 + 11:35 增量 | 时序资金流 + 跷跷板配对 + 游资协同 | 待写 `docs/agents/R7-资金面Agent.md` |
| **D1 主决策** | plan | 08:00 | 出 watchlist_plan.json + 盘前预案 md | `docs/agents/D1-主决策Agent.md` |
| **P1 竞价校准** | plan | 09:25-09:29 | 竞价异常 → auction_amendment.json | 待写 `docs/agents/P1-竞价校准Agent.md` |
| **P2 午盘修订** | plan | 11:35-12:05 | 上午打脸检测 → midday_amendment.json + 用户 briefing | 待写 `docs/agents/P2-午盘修订Agent.md` |
| **E1 每日复盘** | review | 15:10 | 双重复盘 + 观察池追踪 + missed_alpha + 错题本 | `docs/agents/E1-每日复盘Agent.md` |
| **E2 周度进化** | review | 周五 15:30 | 消费 5 天复盘 → skill/preferences/thesis 修订建议 | `docs/agents/E2-周度进化Agent.md` |

**归属汇总**:
- research 内 7 单元(R1-R7)
- plan 内 3 单元(D1 / P1 / P2)
- review 内 2 单元(E1 / E2)
- fetch 内 0 LLM 单元(纯 Python 数据流,但内含 market_scanner)
- execute 内 0 独立单元(判断节点算规则引擎的一部分,不算独立 agent)

### §2.5 现存 profile 的处置

| 旧 profile | 处置 | 说明 |
|:-|:-|:-|
| `canghai-research` | **改造沿用** | 重定义边界为 R1-R7 主控 + delegation |
| `canghai-review` | **改造沿用** | 重定义边界为 E1/E2 |
| `canghai-trading` | **改名 + 重写** → `canghai-execute` | Python 主导,原 LLM 交易逻辑迁 P1/P2 |
| `canghai-intel` | **删除** | 职责入 R3(情绪)/ R4(消息)/ R7(资金) |
| `canghai-risk` | **删除** | 硬规则入 `execute/amygdala.py`,软规则入 R6 反证 |
| `canghai-orchestrator` | **删除** | refactor_plan 已判死刑,delegation 取代 |
| **新建** `canghai-fetch` | 新建 | 数据抓取 + market_scanner |
| **新建** `canghai-plan` | 新建 | D1 + P1 + P2 |

### §2.6 profile 与 agent 的物理隔离

**每个 profile 独立**:
- `~/.hermes/profiles/canghai-<name>/config.toml`
- `~/.hermes/profiles/canghai-<name>/skills/`
- `~/.hermes/profiles/canghai-<name>/SOUL.md`
- `~/.hermes/profiles/canghai-<name>/cron/`

**数据目录归属**(项目 root `/Users/chenyang/Downloads/demo/沧海巨浪/`):
- fetch 只写 `data/raw/`
- research 只写 `chzl_kg/` + `data/research/`
- plan 只写 `data/plans/`
- execute 只写 `data/execution/`
- review 只写 `data/reports/` + `data/corrections/`
- E2 只写 `data/evolution/`

**违反物理隔离即 bug**。SOUL.md 里明确写出各 profile 的 write 白名单,越权时施工侧应报错。

<!-- SECTION_END_2 -->

---

## 第 3 章 · 数据流

### §3.1 目录树(硬约束)

```
/Users/chenyang/Downloads/demo/沧海巨浪/
├── docs/                              # 权威文档(本文档 + agent spec + schema)
│   ├── 00-CANONICAL-ARCHITECTURE-v1.md    ← 本文档
│   ├── agents/                            # 12 个执行单元的 spec
│   │   ├── R1-风格Agent.md ... R7-资金面Agent.md
│   │   ├── D1-主决策Agent.md
│   │   ├── P1-竞价校准Agent.md            ← 新增(v1.2)
│   │   ├── P2-午盘修订Agent.md            ← 新增(v1.2)
│   │   ├── E1-每日复盘Agent.md
│   │   └── E2-周度进化Agent.md
│   ├── watchlist_plan_schema.md
│   └── amendment_schema.md                ← 新增(P1/P2 契约)
│
├── data/                              # 运行时数据(profile 分区写)
│   ├── raw/                               # ← 只有 fetch 写
│   │   ├── YYYYMMDD/
│   │   │   ├── wechat_official_20.jsonl
│   │   │   ├── weflow_snapshot.json
│   │   │   ├── wechat_cli_5groups.jsonl
│   │   │   ├── auction_snapshot.json        # 09:24 抓
│   │   │   ├── midday_snapshot.json          # 11:35 抓
│   │   │   └── mcp_health.json
│   │   └── manifest.json                    # 数据源健康状态 + fallback 记录
│   │
│   ├── research/                          # ← 只有 research 写
│   │   ├── YYYYMMDD/
│   │   │   ├── R1_style.json
│   │   │   ├── R2_main_sectors.json
│   │   │   ├── R3_sentiment.json
│   │   │   ├── R4_news.json
│   │   │   ├── R5_stock_profiles.json
│   │   │   ├── R6_devil_advocate.json      # 含 hard_reject/strong_suggest
│   │   │   ├── R7_capital_flow.json         # 新增
│   │   │   └── research_summary.json        # 主控串接产物
│   │
│   ├── plans/                             # ← 只有 plan 写
│   │   ├── YYYYMMDD/
│   │   │   ├── watchlist_plan.json          # D1 出
│   │   │   ├── auction_amendment.json       # P1 出(增量)
│   │   │   ├── midday_amendment.json         # P2 出(增量)
│   │   │   └── watchlist_plan.loaded.json   # execute 加载后的合并版
│   │
│   ├── execution/                         # ← 只有 execute 写
│   │   ├── YYYYMMDD/
│   │   │   ├── events.jsonl                # 全部信号事件
│   │   │   ├── decisions.jsonl              # 规则决策 + judgment node 记录
│   │   │   ├── orders.jsonl                # 下单流水
│   │   │   ├── positions_state.json         # 实时持仓快照
│   │   │   └── market_snapshot.parquet     # 分钟级全市场(可选归档)
│   │
│   ├── reports/                           # ← 只有 review 写
│   │   ├── YYYYMMDD/
│   │   │   ├── E1_daily_review.md          # 双重复盘 markdown
│   │   │   ├── E1_data.json                # 复盘数据 artifact
│   │   │   └── observation_tracking.json   # T+1/T+5 追踪
│   │
│   ├── corrections/                       # ← 只有 review 写(错题本)
│   │   └── YYYY-Www/
│   │       └── error_case_XXX.md
│   │
│   ├── evolution/                         # ← 只有 E2 写(修订建议 backlog)
│   │   └── YYYY-Www/
│   │       ├── skill_patches.md            # skill 修改建议
│   │       ├── preferences_patches.md      # preferences 修订建议 (新)
│   │       ├── thesis_reviews.md           # thesis 兑现率评估 (新)
│   │       └── sign_off_log.md             # 用户 sign-off 历史
│   │
│   ├── human_thesis/                      # ← 用户写 + E2 只读评估
│   │   ├── active/
│   │   │   └── tech_debt_relief.md         # 举例
│   │   ├── archived/
│   │   └── schema.md
│   │
│   ├── user_preferences.yaml              # ← 用户写 + E2 只读建议
│   └── source_diversity_matrix.md         # ← 用户维护
│
├── chzl_kg/                           # Obsidian 知识库(research + review 写)
│   ├── 投研交易/
│   │   ├── 盘前预案/YYYYMMDD.md          # D1 出
│   │   ├── 午盘briefing/YYYYMMDD.md      # P2 出 (新)
│   │   ├── 复盘记录/YYYYMMDD.md          # E1 出
│   │   ├── 资金面/YYYYMMDD.md            # R7 出 (新)
│   │   └── 错题本/YYYY-Www/xxx.md        # E1/E2 出
│   └── 系统进化/
│       └── YYYY-Www.md                    # E2 出
│
├── skills/                            # 项目本地 skill(见 §4)
│   └── [16 个现存 canghai skill,按 §4.3 迁移]
│
└── scripts/                           # execute Python 脚本
    ├── watcher.py                          # 主循环
    ├── amygdala.py                         # 硬风控 (新)
    ├── market_snapshot.py                  # 分钟级全市场 (新)
    ├── sector_stats.py                     # 板块横截面 (新)
    ├── market_scanner.py                   # 全市场异动扫描 (新,归 fetch profile)
    ├── executors/                          # 现有 executor 模块
    └── judgment_nodes/                     # LLM 判断节点 (新)
        └── [具体节点由 T3 实盘决定]
```

**目录树是硬约束**。任何 profile 越权写非自己那份 → SOUL.md 拦截 → 施工报错。

### §3.2 契约:JSON schema 是模型无关的资产

**核心契约 3 份**:

**契约 1 · watchlist_plan.json**(D1 → execute):
- 位置:`docs/watchlist_plan_schema.md`
- 版本字段:`schema_version` 硬约束
- 核心字段:mode / total_position_cap / execution_pool / watch_pool / exit_rules / entry_rules
- 详见现有 `docs/watchlist_plan_schema.md`(v1 沿用,不改)

**契约 2 · amendment.json**(P1/P2 → execute)【新增】:
- 位置:`docs/amendment_schema.md`(施工时新建)
- 类型 3 种:`skip` / `defer` / `promote` / `tighten_exit` / `flag_for_user`
- 每个 amendment 引用 `watchlist_plan.schema_version`,不兼容即拒
- 详见 §3.5

**契约 3 · research_summary.json**(research 主控 → D1):
- 位置:`docs/research_summary_schema.md`(施工时新建)
- 汇总 R1-R7 产出的 artifact 路径 + 各自 confidence + R6 hard_reject 清单
- D1 pull 此 summary,再按需 pull 具体 R*.json

### §3.3 每日数据流时间轴(v1.2)

```
──────────────────────── 盘前(07:15 - 08:59)────────────────────────
07:15  fetch                  抓取 20 号公众号 + WeFlow snapshot + wechat-cli 5 群
                              MCP 健康检查,写 manifest.json
07:30  R1 / R3 / R4 / R7      并行 delegation(风格 / 情绪 / 消息 / 资金)
07:45  R2 / R5                串行 delegation(主线 / 个股画像,依赖 R1/R3/R4/R7)
07:55  R6                     反证 delegation(消费 R1-R5+R7)
08:00  D1                     fresh context,出 watchlist_plan.json + 盘前预案 md
                              → 推 iLink 摘要给用户(可 08:30 后阅读)

──────────────────────── 集合竞价(09:15 - 09:30)────────────────────
09:15  execute service        启动 watcher 服务,warm-up market_snapshot(历史 K)
                              加载 watchlist_plan.json → watchlist_plan.loaded.json
09:24  fetch (轻量)            抓 auction_snapshot.json(集合竞价快照)
09:25  P1                     fresh context,竞价校准 → auction_amendment.json
                              4 分钟内必须出结果,超时 fallback = 无 amendment
09:29  execute                reload amendment 合并进 loaded.json

──────────────────────── 盘中上半场(09:30 - 11:30)──────────────────
execute service 持续运行,内部 4 层频率:
  · 秒级 tick(1-5s):QMT quote 拉 execution_pool + candidate 深度
                     → entry/exit rule 检查
                     → judgment node 触发(如 buy_confirm)
                     → 硬风控 → 下单
  · 分钟级(1min):XTick 全市场 1 分钟 K + 板块横截面统计
                    → 更新 sector_stats / 龙头动态 / 跷跷板确认
  · 5 分钟级(5min):market_scanner 全市场异动扫描
                     → iLink 推送用户,不自动买
                     → 归 fetch profile
  · 10 分钟级(10min):cron 保活 watcher,读磁盘状态同步

──────────────────────── 中场(11:30 - 13:00)────────────────────────
11:30  execute                上半场结束,冻结 positions_state.json 快照
11:35  fetch (轻量)            抓 midday_snapshot.json
11:35  R7 (research 增量)      北向盘中变盘 + 主力上午净流 + 板块资金上午值
11:40  P2                     fresh context,午盘修订 → midday_amendment.json
                              + `chzl_kg/投研交易/午盘briefing/YYYYMMDD.md`(≤500 字)
                              30 分钟内出结果,12:05 前给用户
12:05-13:00  用户              读 briefing / iLink 关键 flag(20 分钟)

──────────────────────── 盘中下半场(13:00 - 15:00)──────────────────
13:00  execute                reload midday_amendment
13:00-14:55  execute           同上半场 4 层频率
14:55-15:00  execute EOD       尾盘强制处理:
                                - rebound_reduce_2(反弹减仓 2)
                                - eod_forced_exit(尾盘强制平仓)

──────────────────────── 盘后(15:00 - 22:00)────────────────────────
15:10  E1                     fresh context,日度复盘
                              → chzl_kg/投研交易/复盘记录/YYYYMMDD.md
                              → data/reports/YYYYMMDD/
                              包含:双重复盘 + 观察池追踪 + missed_alpha + 错题本触发
(周五)15:30  E2              fresh context,周度进化
                              → data/evolution/YYYY-Www/
                              包含:skill_patches / preferences_patches / thesis_reviews
                              → 推 iLink 给用户 sign-off
```

**时点分配的三个原则**:
1. **盘前所有 research + D1 必须 08:00 前完成**:留出 08:00-09:15 给用户读预案 + 手动干预窗口
2. **P1 4 分钟 / P2 30 分钟不同**:P1 时间死限,超时保守;P2 可以慢一点,因为午盘 1.5 小时,LLM 有余裕
3. **E1 15:10 触发**:不在 15:00 是因为要等 EOD 数据落磁盘,15:05 给 execute 收尾 5 分钟

### §3.4 artifact-first, pull-based 通信

**核心原则**:sub-agent 之间**不通过 memory / session 通信**,只通过磁盘 artifact 通信。

**具体机制**:
- 上游 agent 写 `data/research/YYYYMMDD/R*.json`
- 下游 agent 通过 `read_file` 或 `search_files` pull
- 主控只需要知道**artifact 路径**,不需要看 artifact 内容(除非要合成)

**收益**:
- **R6 可以随时重跑**:R6 反证只依赖 R1-R5+R7 的 artifact 文件,任何时候重跑都得到相同输入
- **debugging 友好**:所有中间产物都在磁盘,可以事后追溯
- **换基座友好**:artifact 是模型无关的 JSON,换基座后 artifact 可以直接被新基座消费
- **P1/P2 可以只读 amendment.json,不用重跑 D1**:P1/P2 只需要 D1 的 artifact,不需要 D1 的 context

**代价**:
- 磁盘 IO 有一定开销(可以接受,每份 artifact <100KB)
- 需要严格的目录规范(见 §3.1)

### §3.5 human_thesis 目录(临时视角承载)

**目录**:`data/human_thesis/`
- `active/`:当前生效的 thesis
- `archived/`:已失效的 thesis(保留复盘用)
- `schema.md`:thesis 格式规范

**Thesis 结构(pydantic schema)**:
```yaml
---
thesis_id: tech-debt-relief-2026
title: 科技化债作为政策工具
author: user
created: 2026-07-04
status: active   # active / archived
expires: 2026-09-30
impact_scope:
  sectors: [半导体, 军工, 商业航天]
  duration: 3个月
breaking_signals:
  - 大盘破 3050 且科技板块领跌
  - 政策转向刺激内需消费
  - 半导体设备板块 5 日累计资金净流出 > 30 亿
consumers: [R2, R6, R7]  # 哪些 agent 应读
---

# Thesis 正文
(用户手写因果框架描述,LLM 消费时作为 extra context)
```

**Thesis 生命周期**:
1. 用户创建 → `active/*.md`
2. R2/R6/R7 每天启动时 pull 所有 `status=active` 的 thesis 作为 extra context
3. E2 每周评估兑现率(见 §5.2 验证 4)
4. **E2 可提修订建议**:撤销 / 修订破位信号 / 延长有效期
5. 用户 sign-off → 修改 thesis(或移到 archived)
6. Thesis 触发破位信号 → E2 强制标记 archived,推 iLink 告警

**Thesis 不进 skill**:zero permanent pollution。撤销即从 active/ 移到 archived/,下次 pull 就不再被消费。

### §3.6 user_preferences.yaml(永久硬先验)【新增】

**位置**:`data/user_preferences.yaml`
**性质**:永久硬先验,与 thesis(临时)、amygdala(不可撤销)三层并列
**首版内容**:

```yaml
schema_version: v1
last_updated: 2026-07-04
last_signed_by: user

# ═══════════════════════════════════════════════════════════
# 龙头优先规则(用户 2026-07-04 深夜明确)
# ═══════════════════════════════════════════════════════════
leader_preference:
  enabled: true
  rule: "same_sector_only_top_2"
  detail:
    - 龙一必须满足以下任一:板块内涨停家数 top 1 或 主力资金 5 日累计 top 1 或 连板高度 top 1
    - 龙二可以是板块内综合评分 top 2
    - 龙三及以下不进 execution_pool(除非龙一 R6 hard_reject)
  filter_out_rules:  # 杂毛过滤:满足 2 项即为杂毛,D1 强制剔除
    - 板块内主力资金 5 日累计流入排名 top 3 之外
    - 龙虎榜近 30 日无机构/游资席位
    - 连板高度 < 板块龙头 -2
    - 换手率 < 板块内 median 50%

# ═══════════════════════════════════════════════════════════
# 硬风控(与 amygdala.py 同源,给 LLM 读)
# ═══════════════════════════════════════════════════════════
position_hard_rules:
  max_single_stock_pct: 0.15       # 单票 ≤15%
  max_single_sector_pct: 0.40      # 板块 ≤40%
  max_total_position_pct: 0.80     # 总仓 ≤80%
  max_positions: 5                  # 持仓 ≤5
  drop_loss_threshold: -0.05        # 非主线浮亏 >5% 换仓

# ═══════════════════════════════════════════════════════════
# 板块黑白名单
# ═══════════════════════════════════════════════════════════
sector_blacklist: []  # 用户明确不做的板块(当前空)
sector_whitelist_priority: []  # 用户长期看好的板块,R2 得分权重 +20%(当前空)

# ═══════════════════════════════════════════════════════════
# 合规过滤(execution_pool 自动买入的硬门槛)
# ═══════════════════════════════════════════════════════════
execution_block_prefixes:  # 自动买入禁用,watch 可含
  - "300"  # 创业板
  - "688"  # 科创板
  - "920"  # 北交所
st_filter: true   # ST / *ST / 风险警示全部阻断

# ═══════════════════════════════════════════════════════════
# 交易时机偏好
# ═══════════════════════════════════════════════════════════
trading_time_preference:
  no_open_buy: false  # 允许开盘直接买入
  prefer_pullback_over_breakout: true  # 优先低吸,追高需 R6 明确无诱多
  eod_close_position_gt_pct: 0.03  # 尾盘涨停未封,盈利 >3% 强制减仓一半

# ═══════════════════════════════════════════════════════════
# 观察池策略(watchlist 侧)
# ═══════════════════════════════════════════════════════════
watchlist_policy:
  min_watch_pool_size: 15
  max_watch_pool_size: 25
  allow_300_688_in_watch: true  # watch 可含,execution 不含
  execution_pool_size_range: [5, 8]
```

**谁读谁改**:
- **R2 / R5 / D1 / P1 / P2 pull 此文件作为强约束**(每次 fresh context 启动时读)
- **E2 只读**,可提修订建议但不能自动改
- **用户手工编辑 或 通过 hermes 对话触发 patch**

**与 human_thesis 的关键区别**:
| 维度 | user_preferences.yaml | human_thesis/*.md |
|:-|:-|:-|
| 生命周期 | 永久 | 临时(有 expires) |
| 破位条件 | 无 | 必须写 breaking_signals |
| E2 可否修订建议 | 是 | 是 |
| 是否可自动撤销 | 否(只能用户改) | 是(触发 breaking_signals 时) |
| 承载什么 | 规则偏好(阈值、黑白名单) | 因果视角(叙事、时代判断) |

---

## 第 4 章 · Skills 与 Harness(资产层)

### §4.1 Skill 的双层结构

**核心断言**:**换基座时**,skill 的 logic 层完全保留,只调整 prompt 层**。

**目录形态**:
```
skills/analyze_style_v1/
├── SKILL.md               # 传统 skill 入口(YAML frontmatter + prompt)
├── skill_logic.md         # 【新增】模型无关的逻辑描述
├── skill_prompt_ark.md    # ark 基座的 prompt 实现(当前默认)
├── skill_prompt_claude5.md # (未来)Claude 5 的 prompt 实现
├── skill_prompt_gpt55.md  # (未来)GPT 5.5 的 prompt 实现
├── references/            # 参考数据、样例
├── templates/             # 输出模板
└── scripts/               # 辅助脚本
```

**skill_logic.md 的必写内容**:
1. **Purpose**:一句话说明这个 skill 是干嘛的
2. **Inputs**:输入 schema(数据源、字段、格式)
3. **Outputs**:输出 schema(pydantic 结构,模型无关)
4. **Rules & Constraints**:必须遵守的硬约束(如"不允许 300/688 进 execution")
5. **Data Sources**:允许调用的 MCP / API
6. **Fallback Behavior**:数据源缺失时的降级策略
7. **Version History**:版本变更记录

**skill_prompt_<model>.md 的必写内容**:
1. 针对基座的**语言风格调优**(如 Claude 偏好 XML tag,ark 偏好 markdown)
2. 具体的 few-shot 例子
3. 输出格式的具体约束(如"输出必须是纯 JSON,禁止解释性文字")
4. **tested_with**:测过的基座 + 通过率 + 最后测试日期

**换基座工作流**:
1. 选定新基座(如 Claude 5)
2. `cp skill_prompt_ark.md skill_prompt_claude5.md` 作为起点
3. Review 每个 skill 的 logic 层不变
4. 微调 prompt(风格、few-shot、约束表述)
5. Run 回归测试(用 T0 阶段积累的 artifact 作为 fixture)
6. 更新 `tested_with` 字段
7. 切换 profile 配置的模型名

### §4.2 Skill 的归属(每个 profile 拥有的完整 skill 清单)

#### canghai-fetch/skills/

| Skill | 来源 | 状态 | 说明 |
|:-|:-|:-|:-|
| `fetch_all_sources_v1` | 现存 | 保留,补 v2 | 07:15 抓公众号 + WeFlow + wechat-cli |
| `fetch_auction_snapshot_v1` | **新增** | 待建 | 09:24 竞价快照(execute pool 溢价 + 全市场情绪) |
| `fetch_midday_snapshot_v1` | **新增** | 待建 | 11:35 午盘快照(全市场涨跌 + 板块资金上午值) |
| `market_scanner_v1` | **新增** | 待建 | 5 分钟异动扫描 + iLink 推送 |
| `mcp_health_check_v1` | 现存(在 fetch_all_sources 内) | 独立出来 | 独立 skill 便于复用 |

#### canghai-research/skills/(主控 + 7 sub-agent 各自的分析 skill)

**主控层(delegation 调度)**:
| Skill | 来源 | 状态 |
|:-|:-|:-|
| `research_orchestrator_v1` | **新增** | 待建。串起 R1-R7 并行/串行 + 收集 artifact 路径 |

**R1 风格 Agent**:
| Skill | 来源 | 状态 |
|:-|:-|:-|
| `analyze_style_v1` | 现存 skeleton | **合并 pattern_recognizer 的 5 模式识别** |
| `~~pattern_recognizer~~` | 现存 | **归档**(内容合并进 analyze_style_v1) |

**R2 主线板块 Agent**:
| Skill | 来源 | 状态 |
|:-|:-|:-|
| `analyze_main_sectors_v1` | **新增** | 待建。1-3 主线 + 每条 3-5 龙头 |
| `filter_leader_v1` | **新增**(用户"龙头优先"落地) | 待建。硬约束 |
| `~~funds_validator~~` | 现存 | **三分**:板块资金入 R2,个股资金入 R5,游资全景入 R7 |

**R3 情绪与热度 Agent**:
| Skill | 来源 | 状态 |
|:-|:-|:-|
| `analyze_sentiment_resonance_v1` | 现存 skeleton | 保留 |

**R4 消息面 Agent**:
| Skill | 来源 | 状态 |
|:-|:-|:-|
| `analyze_news_impact_v1` | **改名自 event_analyzer** | 内容对齐 R4 spec |
| **补 data source**:wechat-cli 5 群 + 财联社 | | |

**R5 情报深挖 Agent(六维画像 + serenity 基本面链)**:
| Skill | 来源 | 状态 |
|:-|:-|:-|
| `analyze_stock_profile_v1` | **新增** | 待建。六维画像统合 |
| `serenity_analyst`(canghai_serenity_analyst_v2) | 现存 | **保留,承担 §3.4 财务估值维度** |
| `bayesian-intrinsic-growth-valuation` | 现存(全局 skill) | 横切,serenity 调用 |
| `tam-adj-peg` | 现存(全局 skill) | 横切,serenity 调用 |
| `gf-dma-health-index` | 现存(全局 skill) | 横切,serenity 调用 |
| `buy-side-equity-research-memo` | 现存(全局 skill) | 横切,重点票深挖时调用 |

**R6 反证 Agent**:
| Skill | 来源 | 状态 |
|:-|:-|:-|
| `analyze_devil_advocate_v1` | 现存 skeleton | 保留 |
| `~~risk_manager~~` | 现存 | **拆分**:软规则并入 R6,硬规则迁 amygdala.py |

**R7 资金面 Agent(新增)**:
| Skill | 来源 | 状态 |
|:-|:-|:-|
| `analyze_capital_flow_v1` | **新增** | 待建。四维统合(北向/主力/游资/ETF+期货) + 时序 5日/10日/20日 |
| `detect_seesaw_pairs_v1` | **新增** | 待建。板块间跷跷板配对(相关系数 <-0.6 + 5 日方向反转) |
| `hot_money_synergy_v1` | **新增** | 待建。游资协同信号(同一游资 3 日内多次上榜同一票) |

**Research 横切(R3/R7 共用)**:
| Skill | 来源 | 状态 |
|:-|:-|:-|
| `hotlist_rank_signal_v1` | 现存 skeleton | 保留 |

#### canghai-plan/skills/

| Skill | 来源 | 状态 |
|:-|:-|:-|
| `main_decision_v1`(D1 核心) | **新增**,继承 canghai_main_agent_v2 决策逻辑 | 待建 |
| `exit_rules_derivation_v1` | **新增** | 待建。exit_rule 生成(由 R6 + preferences + 个股情况推导) |
| `auction_amendment_v1`(P1) | **新增** | 待建。竞价校准 → skip/defer/promote |
| `midday_amendment_v1`(P2) | **新增** | 待建。午盘修订 → tighten_exit/promote/flag_for_user |
| `main_agent`(canghai_main_agent_v2) | 现存 | **骨架保留,内容重写为 D1 spec** |

#### canghai-execute/scripts/(纯 Python,不是 skill)

| 模块 | 来源 | 状态 |
|:-|:-|:-|
| `watcher.py` | 现存 `scripts/trading_agent_intraday_watcher.py` | 沿用,大幅重构 |
| `amygdala.py` | **新增** | 硬风控二次校验(与 preferences.position_hard_rules 同源) |
| `market_snapshot.py` | **新增** | 分钟级全市场维护(内存 + 可选磁盘 parquet) |
| `sector_stats.py` | **新增** | 板块横截面统计 + 龙头动态排位 + 跷跷板实时确认 |
| `executors/` | 现存 `trading/executors/` | 沿用 |
| `judgment_nodes/` | **新增** | LLM 判断节点(具体节点由 T3 决定) |
| `~~holding_optimizer~~`(canghai_holding_optimizer_v2) | 现存 skill | **迁出 research,归 execute Python 实现** |

#### canghai-review/skills/

| Skill | 来源 | 状态 |
|:-|:-|:-|
| `daily_review_v1`(E1) | 继承 daily_reviewer,大幅扩展 | 补观察池追踪 + missed_alpha + preferences 兑现率 |
| `weekly_evolution_v1`(E2) | 继承 weekly_evolution,大幅扩展 | 补 skill_patches + preferences_patches + thesis_reviews |
| `observation_tracking_v1` | 现存 skeleton | 保留(E1 核心 skill) |
| `daily_reviewer`(canghai_daily_reviewer_v2) | 现存 | **骨架保留,内容重写** |
| `weekly_evolution` | 现存 | **骨架保留,内容重写** |

#### 共享横切 skill(不归任何单一 profile)

**数据源类**:
- `iwencai-query`:同花顺问财 NL 选股(R2/R5 用)
- `hithink-*`:同花顺问询系列(R2/R4/R5 用)
- `tushare-*`:Tushare API 系列(全 profile 用)
- `xtick-*`:XTick 盘中信号(R7/execute 用)
- `weflow-*`:WeFlow 情绪(R3/R7 用)
- `wechat-cli`:5 群消息拉取(R4 用)
- `announcement-search` / `report-search` / `news-search`:研报/公告/新闻(R2/R4/R5 用)

**图表类**:
- `fast-chart-mcp` / `chart_lwc_render_kline`:K 线渲染(D1 生成盘前预案 md 用)

**交易类**:
- `qmt-trade-execution`:QMT 下单(execute Python 调用)

**研究方法类**:
- `serenity-alpha`:事件驱动 Alpha 框架
- `bayesian-intrinsic-growth-valuation`
- `tam-adj-peg`
- `gf-dma-health-index`
- `buy-side-equity-research-memo`

### §4.3 现存 16 个 canghai skill 迁移映射

**继承并扩展 `skills/README.md`**,本表为唯一权威。

| 旧 skill | 新架构位置 | 处理方式 | 迁移动作 |
|:-|:-|:-|:-|
| `main_agent`(canghai_main_agent_v2) | D1 主决策(plan) | 骨架保留 + 内容重写 | 保留目录,重写为 D1 orchestrator |
| `event_analyzer`(canghai_event_analyzer_v2) | R4 消息面(research) | 改名 + 内容对齐 | 重命名为 `analyze_news_impact_v1`,补 wechat-cli 5 群 |
| `serenity_analyst`(canghai_serenity_analyst_v2) | R5 §3.4 财务估值维度(research) | 保留,不改 | 只更新 frontmatter 说明其定位 |
| `funds_validator`(canghai_funds_validator_v2) | R2 + R5 + R7 三分 | **三分,原目录归档** | 板块资金入 R2,个股资金入 R5,游资全景入 R7 |
| `pattern_recognizer`(canghai_pattern_recognizer_v1) | R1 风格 | **合并进 analyze_style_v1** | 归档,内容合入 R1 skill |
| `holding_optimizer`(canghai_holding_optimizer_v2) | execute Python 实现 | **迁出 research** | 从 skill 变 Python module |
| `daily_reviewer`(canghai_daily_reviewer_v2) | E1(review) | 骨架保留 + 扩展 | 补观察池追踪 + missed_alpha |
| `risk_manager`(canghai_risk_manager) | R6 + amygdala.py | **拆分** | 软规则入 R6,硬规则入 execute Python |
| `weekly_evolution` | E2(review) | 骨架保留 + 扩展 | 补 preferences/thesis 修订建议 |
| `analyze_style_v1` | R1 | 保留 + 合并 pattern | 补 5 模式识别 |
| `analyze_sentiment_resonance_v1` | R3 | 保留 | 无重大改动 |
| `analyze_devil_advocate_v1` | R6 | 保留 + 合并 risk 软规则 | 补 hard_reject 判定 |
| `hotlist_rank_signal_v1` | R3/R7 共用 | 保留 | 无改动 |
| `observation_tracking_v1` | E1 | 保留 | 无改动,施工时填充实现 |
| `fetch_all_sources_v1` | fetch | 保留 + v2 | 补 auction/midday snapshot |
| `README.md` | 归档 | 本表继承 | 保留原文件作为迁移历史 |

**新增 skill 汇总**(共 15 个):
- Research 内:`analyze_main_sectors_v1` / `filter_leader_v1` / `analyze_stock_profile_v1` / `analyze_capital_flow_v1` / `detect_seesaw_pairs_v1` / `hot_money_synergy_v1` / `research_orchestrator_v1`
- Plan 内:`main_decision_v1` / `exit_rules_derivation_v1` / `auction_amendment_v1` / `midday_amendment_v1`
- Fetch 内:`fetch_auction_snapshot_v1` / `fetch_midday_snapshot_v1` / `market_scanner_v1` / `mcp_health_check_v1`

### §4.4 跨基座测试标注

**Frontmatter 规范**:
```yaml
---
name: analyze_style_v1
description: R1 风格 Agent 核心 skill(5 模式识别 + 情绪浓度 + 仓位建议)
version: v1
status: skeleton  # skeleton / draft / production
agent_owner: R1
category: research/R1

tested_with:
  - model: ark-code-latest
    provider: custom
    last_tested: 2026-07-05
    pass_rate: 0.85  # 用 T0 阶段 fixture 回归测试
    notes: 基线,已 skeleton 通过
  # 未来加入:
  # - model: claude-sonnet-5
  #   provider: anthropic
  #   last_tested: null
  #   pass_rate: null
  #   notes: 待测

updated: 2026-07-05
---
```

**换基座前 review**:
1. `grep -r "tested_with" skills/` 找出所有 skill 的测试记录
2. 挑选测过 fixture 数最多的 skill 作为回归 baseline
3. 新基座跑一遍 baseline,记录 pass_rate 差异
4. 差异 <5% → 直接切换;差异 >5% → 逐 skill 微调 prompt

<!-- SECTION_END_4 -->

---

## 第 5 章 · 机制(3 层 loop + 5 层对抗性验证)

### §5.1 3 层 loop

#### L1 · 日内 loop(三层混合架构,不是纯 Python)

**这是 v1.2 相对 v1.0 的重大澄清**。**execute profile 不是"简单 Python",是**Python 主导 + 结构化规则 + LLM 判断节点**三层混合**。

**层 1 · 硬约束(纯 Python,不可协商)**:
- `amygdala.py`:硬风控二次校验
  - 单票 ≤15%
  - 板块 ≤40%
  - 总仓 ≤ preferences.total_position_cap
  - 持仓数 ≤ 5
  - execution_block_prefixes 拒绝
  - ST/*ST 拒绝
- 状态机:
  - T+1 硬约束(available_qty 校验)
  - kill_switch 文件机制
  - QMT quote 校验(限价单价格来源)
- 下单流程:
  - 限价单价格(买 ask / 卖 bid)
  - 委托去重
  - 撤单机制

**层 1 对 LLM 完全无话语权。违反即拒**。

**层 2 · 结构化规则(纯 Python,通过 preferences.yaml 调参)**:
- Entry rule:
  - trigger_price / max_premium_pct / buy_zone
  - filter_leader_v1 具体阈值
  - 板块效应检测(板块内涨跌家数 / 平均涨跌 / 龙头动态)
- Exit rule:
  - stop_loss / take_profit
  - rebound_reduce_1 / rebound_reduce_2
  - eod_forced_exit
  - trailing_stop(可选)
- 做 T 状态机(如启用):
  - 底仓 base_qty 永久保护
  - 机动仓 mobile_qty 日内闭环
  - 上升趋势正 T / 箱体正反 T / 下跌禁 T

**层 2 可量化的经验都进这里**。**用户说的"大单少了敢买"的可量化部分进这里**。

**层 3 · 判断节点(受控 LLM,3 秒响应,边界严格)**:
- **触发时机**:entry/exit rule **即将触发**时(比如价格触及 trigger_price ±0.5%)
- **LLM 任务**:回答一个**是/否/延迟**判断,不做数值决策
- **上下文**:该票 5 分钟分时 + 板块横截面 + 龙头动态 + 今天 R1-R7 摘要
- **限制**:
  - 单次响应 <3 秒(用便宜快模型)
  - 只输出枚举结果:`confirm` / `reject` / `defer_60s`
  - 不能改仓位、不能改 trigger_price、不能改 exit_rule
  - 超时 → **默认 reject**(保守)
- **具体判断节点举例**(T3 阶段实盘决定最终选哪几个):
  - `buy_confirm`:trigger 触及时,板块效应是否成立?
  - `sell_confirm`:take_profit 触及时,是真突破还是诱多?
  - `leader_switch`:昨晚龙一今天被龙二反超,是否切换目标?
  - `anomaly_pause`:market_scanner 发现异常,是否暂停 entry 序列?

**层 3 的哲学定位**:
- Python 是**主控**,LLM 是**顾问**
- LLM 的每次调用有明确输入 / 明确输出 / 明确超时 / 明确边界
- LLM hallucinate 或时间衰减 → 最坏结果是拒绝机会(defer/reject),不会造成非法下单
- Python 硬风控在 LLM 之后二次校验
- LLM 挂了 / 慢了 → Python 走 fallback(无 LLM 判断 = 按规则执行 或 保守跳过)

**这就是**"Agent 做研究,交易讲纪律"**的完整落地**:
- **纪律 = Python 主控 + 硬风控二次校验 + 明确边界**
- **判断能力 = LLM 在受控节点提供上下文分析**
- 不违反用户师傅那句"交易讲纪律",**也不浪费**用户脑子里那套操盘手直觉

**四层频率**(在三层混合基础上):
| 频率 | 覆盖范围 | 数据源 | 主要任务 |
|:-|:-|:-|:-|
| **秒级(1-5s)** | execution_pool + candidate 深度 | QMT quote | trigger/exit 检查 + judgment node 触发 |
| **分钟级(1min)** | 全市场 5000+ 票 K + 板块统计 | XTick 全市场 1min | 板块横截面 + 龙头动态 + 跷跷板 |
| **5 分钟级(5min)** | 全市场异动 | XTick 涨停/龙虎榜/情绪 | market_scanner 推 iLink |
| **10 分钟级(10min)** | watcher 保活 | 磁盘状态 | reload plan/amendment/state |

**执行同时消费秒级 + 分钟级**:规则决策不是只看该票深度,是看该票深度 **+ 该票所在板块的横截面**。

#### L2 · 日度复盘 loop(每日 15:10,LLM,fresh context)

- 触发:cron @ 15:10
- 载体:canghai-review profile
- Skill:daily_review_v1
- 输入:
  - `data/execution/YYYYMMDD/` 全部(events / decisions / orders / positions_state)
  - `data/plans/YYYYMMDD/` 全部(watchlist_plan / auction_amendment / midday_amendment)
  - `data/research/YYYYMMDD/research_summary.json`
  - 昨日 `data/reports/YYYY-MM-DD/observation_tracking.json`
  - **preferences.yaml + human_thesis/active/*.md**(理解当日 context)
- 输出:
  - `chzl_kg/投研交易/复盘记录/YYYYMMDD.md`(用户看的双重复盘)
  - `data/reports/YYYYMMDD/E1_daily_review.md`
  - `data/reports/YYYYMMDD/E1_data.json`
  - `data/reports/YYYYMMDD/observation_tracking.json`(watch_pool T+1/T+5 追踪)
  - 触发时:`data/corrections/YYYY-Www/error_case_XXX.md`(错题本)
- 关键计算:
  - **missed_alpha** = 观察池等权收益 - 执行池实际收益
  - **watch_pool 兑现率** = 触发 trigger 的 / 总数
  - **R6 反证兑现率** = hard_reject 后未启动 / 总 hard_reject
  - **preferences 兑现率** = 每条规则的触发次数 + 触发后收益差
  - **judgment node 准确率**(如已启用):confirm 后收益 vs reject 后错过收益

#### L3 · 周度进化 loop(每周五 15:30,LLM,fresh context)

- 触发:cron 周五 @ 15:30
- 载体:canghai-review profile
- Skill:weekly_evolution_v1
- 输入:
  - 5 天 `data/reports/*/E1_data.json`
  - 5 天 `data/corrections/YYYY-Www/*.md`
  - 5 天 `data/reports/*/observation_tracking.json`
  - `preferences.yaml + human_thesis/active/*.md`
- 输出:
  - `data/evolution/YYYY-Www/skill_patches.md`:skill 修改建议(patch 格式,含 old_string/new_string)
  - `data/evolution/YYYY-Www/preferences_patches.md`:preferences 修订建议
  - `data/evolution/YYYY-Www/thesis_reviews.md`:thesis 兑现率评估 + 撤销/延长建议
  - `chzl_kg/系统进化/YYYY-Www.md`:用户看的周报
  - `data/evolution/YYYY-Www/sign_off_log.md`:等待用户 sign-off 的清单
- **用户是唯一 sign-off 触发者**:
  - 通过 hermes 对话触发 sign-off 或修改
  - E2 不能自动 patch 任何东西
  - Sign-off 后由 hermes 施工 patch(git commit + 更新 tested_with)

### §5.2 5 层对抗性验证

**验证 1 · 硬风控**(不接受 override):
- 位置:`scripts/amygdala.py`(execute profile)
- 与 preferences.yaml.position_hard_rules 同源
- 单票 ≤15% / 板块 ≤40% / 总仓 ≤ position_cap / 持仓 ≤5
- kill_switch 文件机制:`data/execution/KILL_SWITCH` 存在时全部拒单
- **这一层 LLM 无话语权,用户手工修改也需明确改 preferences.yaml + amygdala.py 双侧**

**验证 2 · R6 反证**(消费 R1-R5+R7,产出 hard_reject):
- distribution_alert 是**唯一硬否决权**(D1 不能覆盖)
- strong_suggest 需 D1 显式覆盖并写理由
- weak_suggest 是提示,D1 自由决定
- 详见 `docs/14-反证机制spec.md`(现有,沿用)

**验证 3 · observation_tracking**(watch_pool 兑现率):
- 每日 E1 追踪 watch_pool 30-50 只
- T+1 / T+5 / T+20 追踪
- 按 `watch_reason_code` 分组统计兑现率
- **兑现率**用于评估:
  - watch 逻辑本身的准确度(比如"业绩预增板块 watch" 兑现率如何)
  - R6 反证的准确度
  - preferences 规则的兑现率
- 详见 `docs/13-观察票追踪spec.md`(现有,沿用)

**验证 4 · human_thesis 破位信号 + E2 修订建议**:
- 每份 thesis 必须写 `breaking_signals`
- E2 每周评估 thesis 解释力(该 thesis 影响的 sectors 表现 vs 大盘)
- **E2 可提建议**:撤销 / 修订 breaking_signals / 延长有效期
- **不能自动改**,必须用户 sign-off
- 触发 breaking_signal 时,E2 强制标记 archived + 推 iLink 告警(不需 sign-off)

**验证 4.5 · user_preferences E2 审阅**【新增,v1.2】:
- E2 每周评估 preferences 各条规则的兑现率
- **E2 可提修订建议**:
  - 阈值调整(如"龙头 top 1 → top 2")
  - 加新规则
  - 删旧规则
- **不能自动改**,必须用户 sign-off
- E2 输出 `data/evolution/YYYY-Www/preferences_patches.md`,含 old_value / new_value / 数据依据

**验证 5 · source_diversity_matrix**(数据源采样偏见):
- 位置:`data/source_diversity_matrix.md`
- 每加一个数据源必须回答"在方法论 / 意识形态 / 时间尺度 / 地域 4 维中,和现有源不同的是哪一维"
- 系统维护矩阵(手工 + E2 辅助)
- 过度聚集时警报(比如 "20 个源里 18 个都是 A 股短线圈中文自媒体")
- E2 每周检查是否需要用户加新维度

### §5.3 Harness(每个 profile 的执行边界)

**核心断言**:**每个 profile 的 SOUL.md 明确写出"允许什么 / 禁止什么";delegate_task 通过 toolsets 参数落地 sub-agent 的 tool 白名单**。

**SOUL.md 必写内容**:
1. **Purpose**:该 profile 做什么
2. **Ownership**:允许写的目录白名单(硬约束)
3. **Toolsets**:允许调用的 MCP/tool 白名单
4. **Consumers**:该 profile 的输出被谁消费
5. **Constraints**:硬约束(如"D1 fresh context,禁止携带 R1-R7 中间推理")
6. **Sub-agent Harness**(仅 research):delegation 的 toolsets 白名单

**举例 · canghai-research SOUL.md 骨架**:
```markdown
# canghai-research SOUL

## Purpose
盘前 07:30-07:55 完成 R1-R7 分析,输出 research_summary.json 供 D1 消费。

## Ownership (write whitelist)
- data/research/YYYYMMDD/*.json
- chzl_kg/投研交易/资金面/YYYYMMDD.md  (R7)

## Toolsets (主控)
[file, delegation]

## Sub-agent toolsets
- R1: [file, tushare, xtick]
- R2: [file, tushare, datapro, hithink]
- R3: [file, weflow, hotlist]
- R4: [file, wechat, tushare]
- R5: [file, tushare, serenity-alpha, valuation-suite]
- R6: [file]  # 反证禁 MCP
- R7: [file, tushare, xtick, datapro]

## Consumers
- D1 (canghai-plan)
- E1 (canghai-review)

## Constraints
- 主控禁止直接调用 MCP(必须通过 delegation)
- 主控禁止修改 preferences.yaml / human_thesis/
- research 输出必须 pydantic schema 校验通过才写盘
- 07:55 前所有 R* 必须完成,超时的 R* 走 fallback(基于昨日 artifact)
```

**Harness 是**Agent 边界的物理落地**。SOUL.md 里禁止的东西,施工时 hermes 内核应报错(或至少警告)**。

---

## 第 6 章 · 交互(3 层用户接触面)

**核心断言**:**用户不应每天与系统对话超过 30 分钟。系统输出**静态可读物**为主,**iLink 告警**为辅,**对话**只在明确必要时**。

### §6.1 静态看板(默认接触面,零对话)

**载体**:Obsidian `chzl_kg/`

**每日固定产出**(用户想看时读,不想看不读):

| 文件 | 内容 | 出品时点 | 阅读时长 |
|:-|:-|:-|:-|
| `投研交易/盘前预案/YYYYMMDD.md` | D1 出,含 execution_pool / watch_pool / entry-exit 规则 / R6 反证 / 主线逻辑 | 08:00 | 10-15 min |
| `投研交易/资金面/YYYYMMDD.md` | R7 出,含北向/主力/游资/ETF 四维 + 跷跷板 | 08:00 | 3-5 min |
| `投研交易/午盘briefing/YYYYMMDD.md` | P2 出,含上午打脸检测 + 增量修订 | 12:05 | 3-5 min |
| `投研交易/复盘记录/YYYYMMDD.md` | E1 出,含双重复盘 + 观察池追踪 + missed_alpha | 15:15 | 5-10 min |
| `投研交易/错题本/YYYY-Www/*.md` | E1/E2 触发时出 | 事件驱动 | 2-3 min/条 |
| `系统进化/YYYY-Www.md` | E2 出,每周五 | 周五 15:30 | 15-20 min |

**每日总阅读时长**:15-30 分钟(周内)、45-60 分钟(周五含 E2)。

**静态看板的哲学**:
- **信息不主动打扰用户**,用户主动读
- 用户可在**任何时段**读,不需要开会
- 所有决策的 rationale 都在磁盘,可事后追溯
- **不依赖对话** —— 用户不问也能知道系统在做什么

### §6.2 iLink 告警(异常接触面,只在必要时打扰)

**载体**:iLink(hermes 集成的移动推送)

**推送场景 · 只有以下 6 种,不做其他推送**:

| 场景 | 推送时点 | 内容 | 用户预期动作 |
|:-|:-|:-|:-|
| **D1 完成** | 08:00-08:05 | 盘前预案摘要 3 行 + Obsidian 链接 | 08:30 后打开看 |
| **P1 完成** | 09:29 | 竞价校准结果(有 amendment 才推;无 amendment 不推) | 09:30 前扫一眼 |
| **P2 完成** | 12:05 | 午盘 briefing 摘要 3 行 + Obsidian 链接 | 12:30 前扫一眼 |
| **market_scanner 严重异动** | 盘中 | 某只不在 pool 的票涨停/异动 + 建议是否 watch | 用户自行判断,不自动买 |
| **thesis breaking_signal 触发** | 事件驱动 | 某 thesis 破位,自动 archived,建议 review | 当天有空时 review |
| **kill_switch 触发** | 事件驱动 | 硬风控拒单/系统异常/execute 服务挂 | 立刻处理 |

**不推送的情况**:
- 每笔正常下单(在 Obsidian 复盘看即可)
- 每次 rule 触发(events.jsonl 里查即可)
- E1 完成(用户 15:20 主动打开 Obsidian 即可)
- E2 完成(推 iLink,但用户可以周六看)

**iLink 疲劳**是系统交互的头号大敌。**推得多**→ 用户屏蔽通知 → 关键异动被忽略 → 系统失效。

### §6.3 对话(按需接触面,只在必要时开)

**载体**:hermes 对话(TUI / iLink 反射)

**对话场景 · 只有以下 4 种**:

**场景 A · E2 sign-off**(每周五晚 或 周末):
- E2 出周报后,用户对话:"给我看看这周的进化建议"
- Hermes 读 `data/evolution/YYYY-Www/*.md`,展示 skill_patches / preferences_patches / thesis_reviews
- 用户逐条 sign-off:"这个 patch 通过 / 那个不要 / 这个改一下措辞"
- Hermes 施工 patch(git commit + 更新 tested_with)
- **时长预算:15-20 分钟/周**

**场景 B · 手动调整**(用户主动):
- 用户观察到系统某个行为偏差,主动开对话
- "今天为什么 D1 没把中际旭创进 execution_pool?"
- Hermes 读当日 artifact,追溯原因
- 用户可能触发:调 preferences / 新增 thesis / 修某个 skill
- **时长预算:不固定,尽量 <15 分钟/次,<3 次/周**

**场景 C · 系统故障**(异常):
- kill_switch 触发或 iLink 报错时
- 用户开对话:"execute 挂了,查一下"
- Hermes 查日志 → 定位问题 → 修
- **时长预算:视故障严重性,目标 <30 分钟/次**

**场景 D · 深度架构讨论**(不定期,类似今晚):
- 用户对系统某个核心机制有新想法或质疑
- 用户和 hermes 深度对话
- 结论沉淀进本文档(v2 修订)或 skill
- **时长预算:1-3 小时/月**

**日常对话时长**:0 分钟/天。**周日常**:E2 sign-off ~ 15 分钟 + 偶发讨论 ~ 30 分钟 = 45 分钟。**月常**:深度讨论 1-3 小时。

### §6.4 3 层接触面的边界

**关键原则**:**尽量把决策推向静态看板 + iLink,减少对话**。

**判断准则**:
- 用户能在 Obsidian 读到的信息 → 不推 iLink
- 用户能在 iLink 摘要看到的信息 → 不需要对话
- 用户能通过 sign-off 触发的动作 → 不需要主动对话

**反例**(该做但没做):
- 系统盘中每 10 分钟主动汇报"现在持仓 -0.3% / 无异动" → **绝对不做**(推 iLink 疲劳)
- 系统每日给用户发心灵鸡汤或"今天大盘怎么看" → **绝对不做**(无信息量)
- 系统每次 skill 修改都问用户"要不要 patch" → **改为周批 sign-off**(用户负担降低)

**用户的合理接触面预算**:
- **每天**:15-30 min 读 Obsidian(通勤时 / 早餐时 / 午餐时都行)
- **每周**:+ 15-20 min sign-off + 偶发对话
- **总量**:< 3 小时/周

**如果超过**:说明某处设计不合理,回本文档 review。

<!-- SECTION_END_6 -->

---

## 第 7 章 · 施工路线图(T0-T5)

**核心原则**:**契约先立,骨架先建,再逐步替换**。不做"关掉全部再重建",系统始终 alive。

### §7.1 T0 · 契约冻结 & 骨架落地(本文档 sign-off ~ +2 天)

**目标**:本文档定稿 → 关键契约文件落盘 → 施工侧有明确目标

**具体动作**:
1. 用户 sign-off 本文档(v1.2 → v1.3 若有修订)
2. 施工侧建立目录树骨架(空目录 + 占位 README):
   - `data/raw/` `data/research/` `data/plans/` `data/execution/` `data/reports/` `data/corrections/` `data/evolution/` `data/human_thesis/`
   - `docs/agents/` 补 P1 / P2 / R7 三份 spec
   - `docs/amendment_schema.md` 起草
   - `docs/research_summary_schema.md` 起草
3. **`data/user_preferences.yaml` 首版落盘**(内容按 §3.6 写死,用户 sign-off)
4. `data/source_diversity_matrix.md` 首版落盘
5. 现存 profile 打 tag `v0-legacy`(锁快照,不删)
6. 现存 cron 保留运行不动

**验收**:
- 本文档 sign-off
- 目录树骨架落盘
- preferences.yaml v1 sign-off
- 现有系统仍运行(不影响盘中/复盘 cron)

**时间预算**:1-2 天

### §7.2 T1 · Profile 新建 + 数据流验证(+3-5 天)

**目标**:5 个新 profile 建成 + 数据流打通 + **原有 profile 并行**

**具体动作**:
1. 创建 5 个新 profile:
   - `canghai-fetch`(SOUL.md + skills/ 骨架 + cron 拓扑)
   - `canghai-research`(SOUL.md + skills/ 骨架 + sub-agent toolsets)
   - `canghai-plan`(SOUL.md + skills/ 骨架)
   - `canghai-execute`(SOUL.md + scripts/ 骨架)
   - `canghai-review`(SOUL.md + skills/ 骨架)
2. 现存 16 个 canghai skill 按 §4.3 迁移映射逐个移动/复制/归档
3. **fetch 先跑通**:每天 07:15 抓数据 → 写 `data/raw/YYYYMMDD/`
4. Manifest / MCP 健康检查上线
5. **research 主控 pull fetch 产物,delegation 调 R1-R7**(可先用**旧 skill 内容**跑通链路,skill 内部逻辑暂不改)
6. **D1 pull research summary** 出 watchlist_plan.json,与旧 canghai-research 产出的 plan **并行**(不合并)
7. 旧 profile 的 plan 继续供 execute 消费(不切换)

**验收**:
- 新 5 profile 全部创建,SOUL.md sign-off
- fetch → research → plan 数据流跑通 1 次
- **新 D1 出的 plan 与旧 D1 出的 plan 可对比**(diff 记录进 corrections)
- 旧系统仍在跑,盘中/复盘不受影响

**时间预算**:3-5 天

### §7.3 T2 · Execute 层重构(+5-7 天)

**目标**:execute Python 服务上线 → 秒级+分钟级架构落地 → 硬风控 + 状态机稳固

**分阶段落地(选项 B · 最小可用 → 迭代加强)**:

**T2.1 最小可用**(3 天):
- `amygdala.py` 硬风控上线
- `watcher.py` 秒级 tick + entry/exit rule + 现有 executor
- kill_switch 文件机制
- **暂不含**分钟级全市场 / 板块横截面 / 判断节点
- **上线策略**:午盘小仓位试跑,和现有 intraday-once cron **并行**
- 每日盘后 diff:新 execute 决策 vs 旧 execute 决策

**T2.2 分钟级全市场**(2 天):
- `market_snapshot.py` 分钟级全市场 K 内存维护
- `sector_stats.py` 板块横截面 + 龙头动态
- 规则引擎消费 sector_stats(板块效应检测 / 龙头切换检测)

**T2.3 5 分钟 market_scanner**(2 天):
- `market_scanner.py`(归 fetch profile)全市场异动 → iLink 推送
- 与用户约定异动阈值(避免 iLink 疲劳)

**T2.x 判断节点**(推迟到 T3):
- T2 不加 LLM 判断节点,先跑纯 Python
- T3 开始根据 T2 数据决定加哪几个判断节点

**验收**:
- T2 全部结束后,新 execute 服务与旧 intraday-once cron 并行 5 个交易日
- 5 天 diff 显示新 execute 无重大偏差
- 硬风控 5 天内零违规
- 用户 sign-off 切换 → 旧 intraday-once cron 停

**时间预算**:5-7 天

### §7.4 T3 · Plan 层 P1/P2 + Review 层 E1/E2 补强(+5-7 天)

**目标**:P1/P2 上线 → E1 双重复盘 + missed_alpha + preferences 兑现率 → E2 修订建议

**具体动作**:
1. **P1 竞价校准**上线:
   - `fetch_auction_snapshot_v1` 09:24 抓
   - `auction_amendment_v1` skill 起草
   - `canghai-plan` cron @ 09:25
   - 首周只出 amendment,execute 不 reload(observe-only)
   - 首周 diff:P1 amendment 逻辑 vs 现实(人为判断准确率)
   - 用户 sign-off 后开启 execute reload
2. **P2 午盘修订**同上模式(11:35-12:05)
3. **E1 daily_review_v1 完整实现**:
   - 双重复盘 markdown
   - 观察池 T+1/T+5 追踪
   - missed_alpha 计算
   - **preferences 各条规则的兑现率统计**
   - 错题本触发
4. **E2 weekly_evolution_v1 完整实现**:
   - skill_patches
   - preferences_patches
   - thesis_reviews
   - 用户周五晚 sign-off 流程
5. **判断节点决策**:根据 T2 5 天数据 + 用户对话,决定加哪几个 LLM 判断节点
6. 判断节点小范围试点(如只加 buy_confirm)

**验收**:
- P1/P2 各跑通 5 个交易日
- E1 每日出品,用户可读
- E2 出 1 次,用户完成 1 次 sign-off
- 用户对判断节点 sign-off,T4 时全量上线

**时间预算**:5-7 天

### §7.5 T4 · 全量切换 + 旧系统下线(+3-5 天)

**目标**:新系统跑主战场 → 旧 profile / cron 归档

**具体动作**:
1. 用户 sign-off 全量切换
2. 旧 cron 停(intraday-once / daily-spine / daily-sync 全部)
3. 旧 profile 归档(不删,tag v0-legacy)
4. 旧 skill 归档(不删,tag v0-legacy)
5. 新 cron 拓扑上线(见 §7.7 cron 一览)
6. 判断节点全量上线
7. R7 完整上线(不再仅 skeleton)
8. 首周日常运行,每日盘后诊断 + iLink 无异常告警

**验收**:
- 新系统跑 5 个交易日无重大 bug
- 硬风控零违规
- 用户 sign-off "切换完成"
- 旧系统归档

**时间预算**:3-5 天

### §7.6 T5 · 稳定期 + E2 首次修订生效(+2 周持续观察)

**目标**:E2 首次生效 → 数据驱动进化 → 系统真正 alive

**具体动作**:
1. E2 每周五出报告
2. 用户每周五晚 或 周末 sign-off
3. Skill / preferences / thesis 首次真实修订
4. Corrections 错题本累积
5. Judgment node 准确率数据积累
6. **2 周后**:review 本文档,若需要 → 出 v2

**验收**:
- E2 至少 2 次 sign-off 完成
- 系统运行 2 周无重大 bug
- 首次 skill patch 生效
- **用户 sign-off 系统正式生产化**

**时间预算**:2 周持续观察

### §7.7 Cron 拓扑一览(新系统)

**新 cron 时间表**(替换旧 crontab 12 行 + Hermes cron):

| Cron | 时点 | Profile | Job | 备注 |
|:-|:-|:-|:-|:-|
| pre-fetch | 07:15 * * 1-5 | canghai-fetch | fetch_all_sources_v1 | 20 号公众号 + WeFlow + wechat-cli |
| research | 07:30 * * 1-5 | canghai-research | research_orchestrator_v1(全流程) | 内部 delegation R1-R7 |
| plan | 08:00 * * 1-5 | canghai-plan | main_decision_v1 | fresh context |
| auction-fetch | 09:24 * * 1-5 | canghai-fetch | fetch_auction_snapshot_v1 | 竞价快照 |
| auction-plan(P1) | 09:25 * * 1-5 | canghai-plan | auction_amendment_v1 | 4 min 硬窗口 |
| execute-service | 09:15-15:05 * * 1-5 | canghai-execute | watcher.py(daemon) | 服务持续运行 |
| execute-keepalive | */10 09:30-15:00 * * 1-5 | canghai-execute | keepalive.sh | 10 min 保活 |
| midday-fetch | 11:35 * * 1-5 | canghai-fetch | fetch_midday_snapshot_v1 | 午盘快照 |
| midday-research-r7 | 11:35 * * 1-5 | canghai-research | R7 增量 delegation | 只跑 R7 增量 |
| midday-plan(P2) | 11:40 * * 1-5 | canghai-plan | midday_amendment_v1 | 30 min 窗口 |
| daily-review | 15:10 * * 1-5 | canghai-review | daily_review_v1 | E1 |
| weekly-evolution | 15:30 * * 5 | canghai-review | weekly_evolution_v1 | E2 周五 |
| health-monitor | */30 * * * * | canghai-fetch | mcp_health_check_v1 | 30 min 巡检 |

**共 13 个 cron**,替换掉旧 macOS crontab 12 行 + Hermes cron 若干。

**Cron 归属原则**:
- 每个 cron 归**唯一** profile
- 不允许 cross-profile 一 cron 跑多 profile
- Cron 命名 = `<profile>-<job>` 前缀,便于诊断

### §7.8 兜底与回滚

**回滚触发条件**:
- T2 execute 首日出现硬风控违规 → 立即停用新 execute,回滚 intraday-once cron
- T3 P1/P2 首周准确率 <60% → 关闭 auto-reload,只 observe
- T4 全量切换首日出现 kill_switch 触发 3 次以上 → 部分回滚(只保留 fetch / research,execute 回旧)
- T5 稳定期 E2 首次 sign-off 后系统性下滑 3 日 → 回滚 preferences 修改

**回滚工具**:
- Git tag 每个 T 阶段完成打 tag
- 旧 profile / skill 保留(tag v0-legacy)
- 用户 sign-off 记录进 `data/evolution/YYYY-Www/sign_off_log.md`
- 回滚 = `git checkout <tag>` + 重启 profile

**兜底原则**:
- **任何时候用户都可以手工下单**(通过 QMT 客户端,不依赖任何 profile)
- **任何时候都可以停系统**(kill_switch 文件放进 `data/execution/`)
- **任何时候都可以 review 决策**(所有 artifact 在磁盘)

<!-- SECTION_END_7 -->

---

## 附录 A · 术语表

| 术语 | 定义 |
|:-|:-|
| **Profile** | Hermes 会话配置单元,一个 profile 一份 config.toml / SOUL.md / skills / cron |
| **Sub-agent** | 同一 profile 内通过 delegate_task 派发的独立 LLM 会话 |
| **Skill** | 可复用的分析/执行逻辑单元(YAML frontmatter + prompt/logic) |
| **Harness** | Agent 的执行边界(允许什么 / 禁止什么) |
| **SOUL.md** | Profile 的执行规约(purpose / ownership / toolsets / constraints) |
| **Artifact** | 磁盘上的中间产物(JSON / markdown),模型无关 |
| **watchlist_plan** | D1 出的当日 plan,含 execution_pool / watch_pool / entry-exit rules |
| **amendment** | P1/P2 出的增量修订,不重写 plan 只补丁 |
| **research_summary** | Research 主控出的汇总 artifact,D1 消费入口 |
| **execution_pool** | 当日自动下单候选(5-8 只) |
| **watch_pool** | 当日观察候选(15-25 只),含 300/688(仅 watch 不买) |
| **candidate_pool** | 盘中动态维护的秒级监控池(execution + watch + 分钟级新入围) |
| **execution_block_prefixes** | 自动买入禁用代码前缀(300/688/920) |
| **龙头 (leader)** | 板块内涨停家数 / 主力资金 / 连板高度综合排名 top |
| **杂毛** | 板块内非龙头且满足 filter_out_rules 的票,D1 强制剔除 |
| **跷跷板** | 板块间资金流负相关(相关系数 <-0.6)且 5 日方向反转 |
| **主线** | R2 出的 1-3 条当日核心板块,execution_pool 优先从中选 |
| **thesis (human_thesis)** | 用户手写的因果框架,临时视角,有 breaking_signals |
| **preferences (user_preferences.yaml)** | 用户永久硬先验(阈值 / 黑白名单 / 交易偏好) |
| **amygdala** | 硬风控二次校验的比喻名(纯 Python,不可协商) |
| **judgment node** | Execute 内的 LLM 判断节点(3 秒响应,枚举输出,超时保守) |
| **hard_reject** | R6 反证的硬否决权(D1 不能覆盖) |
| **strong_suggest** | R6 反证的强建议(D1 需显式覆盖 + 写理由) |
| **weak_suggest** | R6 反证的弱建议(D1 自由决定) |
| **missed_alpha** | 观察池等权收益 - 执行池实际收益(评估选股 vs 选执行) |
| **observation_tracking** | Watch_pool T+1/T+5/T+20 追踪(评估 watch 逻辑准确度) |
| **corrections** | 错题本,E1/E2 触发时出,固化系统性偏差 |
| **fresh context** | LLM 会话每次开新 context,禁止携带昨日 confidence |
| **T+1 硬约束** | A 股 T+1 交割,available_qty 校验(当日买入不可当日卖出) |
| **kill_switch** | `data/execution/KILL_SWITCH` 文件存在时全部拒单 |
| **市场感知服务** | Execute profile 的完整定位,不仅仅是 watcher |
| **协调游戏** | A 股主力群体协同游戏(用户提出的市场理论,§1 宪法背景) |
| **无情绪优势** | Agent 相对人的核心优势(不套牢/不贪心/不硬撑/不迟疑) |

## 附录 B · 关键决策记录(与用户对话沉淀)

| 决策 # | 决策内容 | 来源(用户对话) | 落地位置 |
|:-|:-|:-|:-|
| **决策 1** | 5 profile 中性命名(fetch/research/plan/execute/review) | 用户 06-30 批"命名太脑洞" | §2.1 |
| **决策 2** | Sub-agent 用 delegation 不用 profile 拆分 | 用户"7 profile 太重" | §2.3 |
| **决策 3** | Execute 归 Python 主导 | 用户师傅"交易讲纪律" | §5.1 |
| **决策 4** | R1-R7 = 7 agent,不合并不再拆 | 07-03 深挖后定 | §2.4 |
| **决策 5** | R6 反证禁 MCP(只读 artifact 找漏洞) | 07-03 讨论"反证不能自己找证据" | §2.3 |
| **决策 6** | D1 fresh context,不携带 R1-R7 中间推理 | 07-03 定位 07-03 亏损根因 | §2.2 消灭 canghai-plan |
| **决策 7** | R6 hard_reject 硬否决权,strong_suggest 需 D1 覆盖 | 07-03 定 | §5.2 验证 2 |
| **决策 8** | Skill 双层结构(logic + prompt_<model>) | 07-04 深夜"换基座" | §4.1 |
| **决策 9** | Schema-first, prompt-second | 07-04 "换基座后 schema 保留" | §4.1 |
| **决策 10** | 定期换基座(3-6 月一次),harness 迁移能力是生存能力 | 07-04 "GPT-5.5 已出" | §1.2 / §1.3 |
| **决策 11** | P1 竞价校准 + P2 午盘修订 归 canghai-plan | 07-04 深夜"盘中漏 9:25 / 11:30" | §2.4 / §3.3 |
| **决策 12** | R7 资金面 Agent 独立(4 维时序) | 07-04 深夜"没有资金面 agent" | §2.4 / §4.2 |
| **决策 13** | user_preferences.yaml 承载永久硬先验 | 07-04 深夜"龙头偏好不是 thesis" | §3.6 |
| **决策 14** | 龙头偏好硬约束(same_sector_only_top_2) + 4 条杂毛过滤 | 07-04 深夜 | §3.6 / §4.2 |
| **决策 15** | R5 必须完整落地 serenity 基本面链 | 07-04 深夜"基本面在哪" | §4.2 |
| **决策 16** | 跷跷板配对由 detect_seesaw_pairs_v1 输出 | 07-04 深夜"跷跷板不能只看快照" | §4.2 |
| **决策 17** | Execute 内 4 层频率(秒/分钟/5 分钟/10 分钟 cron) | 07-04 深夜"10 分钟太粗" | §5.1 |
| **决策 18** | Execute 全市场 1 分钟扫描是必要的(板块横截面) | 07-04 深夜"板块共振判断需要" | §5.1 |
| **决策 19** | market_scanner 归 fetch profile,不归 execute | 07-04 深夜"感知不是执行" | §2.1 / §7.7 |
| **决策 20** | Execute 是"Python 主导 + LLM 判断节点"混合架构 | 07-04 深夜"经验能不能程序化" | §5.1 |
| **决策 21** | 判断节点严格受限(3 秒 / 枚举 / 超时保守) | 07-04 深夜"LLM 不能改仓位" | §5.1 层 3 |
| **决策 22** | 具体判断节点由 T3 实盘数据决定,不写死 | 用户 07-04 未答 4 节点问题 | §5.1 层 3 |
| **决策 23** | 宪法原则一改为"Agent 无情绪优势",客观是伪目标 | 07-04 深夜"Agent 优势是无情绪" | §1.1 |
| **决策 24** | 用户经验是组件不是主体 | 07-04 深夜"人的经验是输入" | §1.4 |
| **决策 25** | E2 有权对 preferences / thesis 提修订建议(不能自动改) | 07-04 深夜"自进化会修订经验" | §5.2 验证 4.5 |
| **决策 26** | 静态看板 + iLink + 对话三层接触面,总量 <3 小时/周 | 07-04 深夜(隐含用户不想 30 min/天对话) | §6 |
| **决策 27** | 契约冻结 + 逐 profile 替换,不做"关闭全部再重建" | 用户 07-04 "反对大重写" | §7 T0-T5 |
| **决策 28** | 系统始终 alive,旧系统 tag v0-legacy 不删 | 07-04 "系统不能停" | §7.5 / §7.8 |

## 附录 C · 与现有文档的对应关系

| 现有文档 | v1 位置 | 处置 |
|:-|:-|:-|
| `00-研究端总览.md` | §2.1 / §2.4 | 参考,内容已被 v1 §2 覆盖 |
| `03-核心设计原则.md` | §1 | 参考,内容已被 v1 §1 覆盖 + 扩展 |
| `10-研究端Agent骨架-v1.md` | §2.4 | 参考,R1-R7 分工已被 v1 §2.4 覆盖 + 补 R7 |
| `13-观察票追踪spec.md` | §5.2 验证 3 | **保留权威**(v1 只引用不重写) |
| `14-反证机制spec.md` | §5.2 验证 2 | **保留权威**(v1 只引用不重写) |
| `agents/R1-风格Agent.md` ... `agents/R6-反证Agent.md` | §2.4 引用 | **保留权威**(具体 spec 在这) |
| `agents/D1-主决策Agent.md` | §2.4 引用 | **保留权威** |
| `agents/E1-每日复盘Agent.md` | §2.4 引用 | **保留权威** |
| `agents/E2-周度进化Agent.md` | §2.4 引用 | **保留权威** |
| `agents/R7-资金面Agent.md` | §2.4 引用 | **待建**(T1 施工时创建) |
| `agents/P1-竞价校准Agent.md` | §2.4 引用 | **待建**(T3 施工时创建) |
| `agents/P2-午盘修订Agent.md` | §2.4 引用 | **待建**(T3 施工时创建) |
| `watchlist_plan_schema.md` | §3.2 契约 1 | **保留权威** |
| `amendment_schema.md` | §3.2 契约 2 | **待建**(T0/T3 时创建) |
| `research_summary_schema.md` | §3.2 契约 3 | **待建**(T0/T1 时创建) |
| `HERMES-交易端对接说明.md` | §5.1 / §3.3 | 参考,盘中 10 分钟频率描述已被 v1 §5.1 覆盖 |
| `trading_agent_datasources.md` | §5.1 层 1-2 | 参考,tick 1-5 秒描述已并入 v1 §5.1 |
| `trading_agent_runtime_runbook.md` | §7.7 | 参考,cron 拓扑已被 v1 §7.7 覆盖 |
| `refactor_plan.md` | §7 | 覆盖,v1 §7 是新的施工路线 |

## 附录 D · 未解决问题

以下问题**未在本文档解决**,施工时按 T 阶段决定:

1. **判断节点具体清单**:T3 阶段根据实盘数据决定(§5.1 层 3)
2. **市值管理配合减持的识别方法**:已知问题(WeFlow 群消息暗示),但技术实现暂无(可能进 R4)
3. **龙虎榜数据源**:目前依赖同花顺,是否需要冗余源?(T4 后评估)
4. **做 T 策略是否启用**:preferences.yaml 未开,T5 后评估(需先看无 T 情况下的收益)
5. **判断节点用哪个基座**:Claude 5 haiku 或 GPT-5 mini?(T3 阶段实测选)
6. **E2 周报的 sign-off UI**:hermes 对话 or Obsidian markdown 打勾?(T3 施工时定)
7. **kill_switch 触发后的恢复流程**:目前只定义触发条件,恢复流程待补(T4 时补 runbook)
8. **多市场扩展**:港股 / crypto 用同套 harness?(v2 议题,当前不考虑)
9. **Skill fixture 回归测试基础设施**:目前无,T3 后建
10. **数据源冗余矩阵**(source_diversity_matrix)的定期 review 机制:E2 每周?或每月一次?(T3 时定)

## 附录 E · 用户三重角色 checklist

**每周用户应完成的任务**:

**每日**(15-30 分钟):
- [ ] 早读 Obsidian 盘前预案(08:30 后)
- [ ] 中午扫 Obsidian 午盘 briefing(12:05-12:30)
- [ ] 傍晚读 Obsidian 复盘记录(15:15 后)
- [ ] 处理 iLink 异动告警(如有)

**每周**(15-20 分钟 + 偶发):
- [ ] 周五晚 或 周末 E2 sign-off
- [ ] 手工 review preferences.yaml 是否需要调整
- [ ] 手工 review human_thesis/active/ 是否需要补 / 撤

**每月**(可选,1-3 小时):
- [ ] 深度架构 review(是否需要修订本文档 v2)
- [ ] 数据源 review(source_diversity_matrix 是否需要补维度)
- [ ] Skill 大改动(如果 E2 累积了大量小修订)

**每季度**(评估,不定时):
- [ ] 换基座评估(现有基座是否明显落后于市场新基座)
- [ ] 系统实盘绩效 review(过去 3 月收益 / 最大回撤 / 换手 / missed_alpha)

---

## 文档结束

**本文档 v1.2 定稿于 2026-07-04 深夜**。

**用户 sign-off 后进入 T0 施工阶段**。

**下次修订** = v2,触发条件:
- T5 稳定期结束后的**首次系统性 review**
- 或用户提出重大架构分歧(如"要不要做港股"、"要不要用 RL fine-tune")
- 或换基座后的**首次 review**(基座换代可能带来能力边界变化)

**修订权**:
- 用户 sign-off 生效
- Hermes 可提修订建议
- E2 可提关键机制建议(如"§5.1 层 3 判断节点数量应扩至 6 个")
- **本文档一旦冲突,以用户 sign-off 版本为准**



