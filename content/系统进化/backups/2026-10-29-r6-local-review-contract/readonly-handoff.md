# 逐票补审与重新准入：最小施工交接（只读源码核查）

范围：`/Users/chenyang/Downloads/demo/沧海巨浪`。先加载仓库现行 `analyze_devil_advocate_v1`（实际路径 `skills/analyze_devil_advocate_v1/SKILL.md`），再核生产与消费。未运行模型、测试、行情、生产脚本；未读生产研究/计划、账户、持仓成交、业务DB或认证；未修改源码、技能、配置、Git索引。只写本scratch交接。本文是静态源码结论，不是自然任务采用或交易许可证明。没有复验已结项40/54项。

## 结论：先做“定向R6补审结果交付”，不做“补审即晋级”

- 有可复用的R6**阶段执行及交付校验**，没有查到现行生产链中可直接调用的“按票/缺项补审并保留其他票结论”入口。不能把整个shell脚本当作单阶段函数库来source：它有顶层启动和全批编排。
- 已有“观察候补经认证owner确认后修订计划”的纯消费者，不能说系统完全没有晋级能力；但它不生产R6审核、不补研究缺项，也不接受任意研究观察票。
- 最小缺边先补：**绑定既有材料与指定票/缺项 → 原R6角色局部核验 → 原字段结果及必要覆盖明细 → 可信交付回执与summary重新绑定**。这一期到研究结果交付为止，原池、逐票资格、预算与执行身份不变；不要同时重做事件、scanner或执行全链。
- 真正重新进入执行池是第二项独立业务授权；不能因为R6完成或事件翻多，清除原禁买、补出entry_rules、抬零预算或推定已通过其他门禁。

## 1. 当前必要审核结构与真实生产者

### 正式范围（以现行技能和当前R6规格为准）

必要项是模式1资金/消息交叉、模式2风格一致性、模式6出货风险、模式7财务合规；逐对象、证据版本及观察窗口完成。辅助估值/历史/昨日兑现/扩展缺口可局部降级，但不能删除已发现风险。来源：`docs/agents/R6-反证Agent.md:30-44`；现行技能“反证模式与正式审核范围”“Step 1”两节。

现有正式结果容器：
- 根级 `status`、`formal_review_completed`、`review_passed`、`research_objects_inspected`、`candidates_evaluated`；示例位于 `skills/analyze_devil_advocate_v1/SKILL.md:220-237`。
- `patterns_status` 按模式承载已核对象/证据定位、未完成项、owner；`counter_arguments` 承载实际反面发现；`hard_rejects` 仅汇总真实硬否决。技能Step 1要求这些明细，但**没有冻结“每票×四必要项”的机器可解析键集合与枚举**，不能自行发明逐票通过字段。
- `formal_review_completed` 是本批必要范围全部完成的摘要，不是每票通过；`review_passed` 或空 `hard_rejects` 同样不是买入许可。
- `hard_rejects` 元素现有字段：`ts_code/name/reason/evidence/source_agent/suggestion`，见 `docs/10-契约-研究汇总.md:57-79`。该文档第13行仍写“仅模式六”，与当前R6规格模式6/7边界不齐；施工不得照旧句丢掉财务合规硬拒绝，也不在本任务改文档。

### 谁生产/写入真实R6

生产路径是 `scripts/research/run_research_shell.sh:81-94` 的 `run_agent()`，默认研究profile `canghai-research`；原生计量wrapper调用在 `133-140`，R6具体调用在 `283-289`。实际R6角色按现行技能写：
- `data/research/{date}/R6_devil_advocate.json`
- `chzl_kg/投研交易/反证/{date}.md`

调用prompt已要求反证对象的 `sector_id/round_id/event_at/valid_from/valid_until` 有据保留、缺证null（shell:287）；这不是允许猜轮次或向所有对象填示例值。

可信接收由普通程序完成，不由R6自报成功：shell `163-184`；`pipeline_state.check():220-262`，核同一run/attempt启动后的JSON和MD、版本与回执。`pipeline_artifacts.verified_delivery():301-318` 再核日期、attempt、hash/bytes/mtime及payload显式身份。角色写文件≠接收成功≠研究完成。

`src/research/r6_devil_advocate.py` 虽有旧规则实现，不应拿来生产本次补审；shell `291-301` 已明确不要调用规则orchestrator覆盖LLM产物。`scripts/research/run_missing_only.sh:54-78` 是R2/R5/R6/D1连跑、旧式弱交付检查，不是可直接复用的逐票入口。

### 必须绑定的输入与输出

建议绑定于已有可信接收/summary，不新增服务或角色：
1. 交易日、原研究run/attempt/交付回执和原R6内容版本；明确本次目标票及缺失必要项，保留原对象/主张/角色，不凭R5画像推定execution_eligible。
2. 现行R6允许的R1/R2/R3/R4/R5/R7已存主产物及实际证据路径/窗口：R2对象与主张；R1同窗口风格；R4消息/R7适用资金；R3显式alert；R5必要的近5日资金确认及财务合规检查范围、时点。未有材料交原owner，不抓新数、不重跑七研究，不假设 `R5.review_status` 存在。
3. 原有硬拒绝、未涉及对象/模式及其限制必须保留；仅替换本次获授权票/缺项的核验结果。不能把局部补审结果冒充“全批R6全新完整产物”，也不能悄悄删除原风险。
4. 输出继续沿用上述现有字段/JSON及MD路径；局部证据、缺项、owner写入现有审计容器。**具体机器明细结构和局部合并规则须先列差异确认，当前并无已冻结的逐票四项状态协议。** 根级完成标记按整批真实覆盖重算，不因一票补齐设true。

## 2. 三种逐票状态在现有消费者的实际表现

| 状态 | 当前实际消费 | 不能推导的权限 |
|---|---|---|
| 必要四项已审、未形成真实硬拒绝，且strong_suggest有明确处置 | 当前没有通用“逐票四项全部通过”的解析器。事件分支仅从 `mode6_condition_audit` 中抽 `formal_evaluated=true` 的票，再要求 `permission_layers.formal_review_completed is True` 才允许stock adjudication写superseded（`ensure_watchlist_plan.py:728-738`） | mode6已评不是四项已完成；根级/permission全局完成不是该票通过；superseded只是一条重评记录，不改票对象 |
| 真实硬拒绝 | summary合并R6根级hard_rejects与counter_arguments中的hard_reject，partial/degraded也保留（`build_research_summary.py:463-469`）；事件清除全局no_trade时任何此类否决阻塞（`ensure_watchlist_plan.py:762-770`） | 不能因市场翻多覆盖硬拒绝；事件分支也不会自动从旧execution_pool移出票，因为池字段不可变 |
| 必要审核未完成/无法追溯 | 当前技能要求保留partial/degraded及缺项；事件没有该票formal_evaluated或全局嵌套完成true时，不接受stock superseded；可retained/unresolved，原资格原池不动 | 空hard_rejects不是通过；retained不是新审核完成；未完成不能伪造为已审安全 |

**关键契约错位须先处理，不能默认补metadata：**
- 技能示例完成标记在R6根级（技能:229-230），事件消费者却读 `permission_layers.formal_review_completed`，并依赖 `mode6_condition_audit[].formal_evaluated`。在本次检索的 `src/`、`scripts/` 生产源码中，后两者只查到事件读取，未查到负责保证它们生成的当前生产实现；LLM可能产出不等于有正式生产契约。
- 事件的clearing检查只对嵌套三个字段**显式False**阻塞，缺键不等于False（`ensure_watchlist_plan.py:765-770`）。因此“未知审核缺口一定在代码被识别”不能作保证；本次不改已关闭的事件工程，但下一项若让它消费补审，必须先对齐正式逐票证据与缺键语义，不能用全局True补洞。
- 规则兜底 `d1_algorithm.step2_r6_filter():102-146` 主要按hard_rejects筛code和处理strong/soft；不检查逐票四项完成。其调用位于同文件:779；入口 `main_decision.build_watchlist_plan():258-272`。这是兜底消费能力，不是生产R6补审入口。
- `buy_eligibility.evaluate_stock_buy_eligibility():64-211` 是价格/RR及既有显式限制的纯资格校验；外部资格、review_required、no_trade_conditions见:96-112。它没有读取或完成R6四项审核的能力，不可拿RR_PASS当R6通过。

## 3. 从真实事件入口到计划消费者：缺哪条边

已存在链：`scripts/plan/run_retreat_reversal.py --reassess`（:102-110、135-140）→ `ensure_watchlist_plan.reassess_event()`（:562）→ `event_inputs()`（:479-496）→ `verify_saved_inputs()`（`build_research_summary.py:526-547`）→ `consume_authorized_inputs()`（同文件:347-390）。

事件绑定原计划JSON、人读MD、summary、所有授权primary版本和run_id；只投影完整R1/R2、原池选中的R5及完整R6（`ensure_watchlist_plan.py:630-645`）。允许更新的顶层字段仅 `market_context/no_trade/decision_status/no_trade_conditions`（:715-717）；condition只能在封闭R1/R2来源映射下改active，其余身份/次序保留（:739-755）。原execution_pool/watch_pool、票资格、entry/exit、预算、执行身份和确认要求都不变（:562-567、650-656、790-794）。

**缺边不是“再跑一遍D1”**：先缺“新鲜绑定的局部必要审核结果 → 受信R6交付及summary更新”，再缺“被允许的逐票资格/池身份修订”。当前市场重评即使可解除有来源市场条件，也无法把原watch/research-only恢复成可执行对象；这正是两段工作不能合并宣称完成的原因。

还要避免时序陷阱：改R6字节后原summary绑定立即失效（`consume_authorized_inputs():378-385`）；更新R6必须经新交付回执和summary重新绑定，不能只覆盖JSON再喂旧summary。

## 4. 最小可施工一条：只补“局部审查交付边”

建议在**既有** `scripts/research/run_research_shell.sh` 启动逻辑增加明确单R6/指定对象缺项的受限调用分支，而非新模块/新服务/新角色；复用 `run_agent()`、native_usage、`pipeline_state.check()`、原R6输出及summary组装。现在不能直接source整脚本；无单阶段CLI也不能伪称已有命令。

最小新增差异，仅建议、未实施：
1. 进入全批顶层副作用前识别局部调用范围，输入绑定明确限定目标票/缺项、原R6及已交付上游版本；冻结未涉及内容。
2. 原R6只完成指定缺项并提交可核覆盖，不重新选票、抓数或替其他owner编证据；保留所有原有效拒绝/限制。
3. 接收侧检查局部变化边界、证据绑定、整批完成摘要和JSON/MD实际交付，再更新summary与其可信绑定；失败保留最后有效研究交付，不碰计划。
4. 只交付审查，不调用D1/事件/scanner晋级，不变更计划字段或交易预算。

**当前必须先决的两点：**
- `pipeline_state.start():133-154` 对新run清旧stages/receipts，terminal run不能重启；`update():161-166` 禁改terminal state；summary消费又要求每份主研究当前run回执。不能新起补审run后给未重跑R1-R5/R7补新回执，也不能偷偷改已终结run。须由研究owner明确局部修订的可信接收方式（如何引用旧已核输入、接收新R6并绑定新summary），再给最小实现差异。复用校验函数不代表这条跨批接线已存在。
- 先冻结现有 `patterns_status` 中逐票必要四项覆盖的具体表示/合并语义，并对齐事件已有嵌套旧读法。没有该契约，最多能交付人读局部结论，不能安全自动认定逐票完成；本报告不虚构新字段名。

## 5. 已有重新进入执行池入口：能复用但不能冒充补审

`src/plan/candidate_revision.py::consume_candidate_confirmation():36-39` 接受已有 `plan/review/owner_review/confirmation/trusted_owner_id/as_of`，认证身份必须来自调用者的可信owner通道，不能来自模型/计划自称（:8-10、47-69）。源码调用引用位于 `trading/entry_selector.py:382`、`src/plan/amendment_consumer.py:170`；本次仅核到这两处导入/接线位置，未逐行核其全部调用上下文，不宣称线上已有可用认证producer。

现有确认字段：`schema_version=candidate_confirmation_v1`、`decision=confirmed`、`owner_id/confirmation_id/confirmed_at/plan_sha256/review_sha256/owner_review_sha256/action`；action仅 `promote_candidate/replace_candidate`，严格限定watch_index/entry_rule_index/ts_code及替换时的execution索引（:47-78）。

它只接原 `plan_status=watch_pool_wait_for_entry` 的唯一观察候补及已有entry情景（:79-95）；全局买门禁、显式完整预算、真实拒绝/研究锚、研究就绪都须过（:104-114）。owner_review现有checks为 `sector_conditions/market_freshness/account_dynamic/other_d1/entry_conditions`（:24、116-130），含证据引用、观察/可用/有效时点；同分钟板块/价格/入场确认、实际ask、原区间、RR、原票/情景正预算、原退出与T+1仍须满足（:131-153）。不能凭R6补审结果填一组eligible通过。

当前可见输出变化是对原plan深拷贝，将指定watch对象取出，保留选中原entry情景，强制该票 `auto_trade_enabled=false`、`requires_user_confirmation=true`（:155-159）；函数定位说明它返回修订计划交原owner既有通道发布，不自己下单/发布（:1-6）。这不是给research-only且entry_rules为空的票重建买点的入口。函数后半段及caller全部发布细节未在本次调用额度内继续展开；后续若选此条，只需补核这一小段，不重开全链。

## 6. 真要“重新准入”，最少新增业务问题（不是模型/平台问题）

1. **本期范围是否只交付补审？** 推荐是；请明确上述局部输入/结果合并和跨批可信接收差异。若要求准入，明确仅原合法条件候补，还是包括research-only且无entry_rules的对象；后者需要另定谁能重新产出买点/退出/资格，不能借候补入口自动恢复。
2. **准入允许改哪些现有字段，由哪个认证owner确认？** 最小候补复用只涉及选定watch→execution及原情景；不动entry价格/exit/总预算/执行身份。若要解除 `buy_eligibility`、review_required、逐票no_trade_conditions或重建entry_rules，须逐项给允许差异、原阻塞owner及有效证据。真实hard_reject不得按市场事件覆盖；strong_suggest另按既有显式采纳/覆盖规则处理。
3. **若原有效预算为0，零值来自哪里、谁有权重评？** 需提供原字段、明确来源owner、约束类型、版本/时点及获准变更范围；无法核来源就保持0。本次未读生产计划或政策/账户，因此不判断任何实际零预算属于R1市场cap、D1计划cap、用户还是账户，也不补预算数值。R6无权决定这些。

预算代码依据：`buy_eligibility.evaluate_plan_buy_gate():214-251` 检查no_trade、逐票/全局限制以及 `risk_limits.target_total_position_pct`、`meta.position_cap_pct`、`position_cap_derivation.final_position_cap_pct` 的显式零/非法值；`execution_authorization.py:15-19、22-48、80-83` 只认现有RiskLimits字段并对缺失/零买入cap失败关闭，:51-77取计划/账户显式交集。`effective_new_position_budget_pct` 并非此RiskLimits允许字段，不能自行加进去当预算来源；metadata也不是自行抬预算的授权。canonical→runtime仍经 `load_plan.stage_plan():152-183`，禁止自动扩大live权限；研究交付或候补修订不改变它。

## 交付状态

完成：现行R6范围、生产/可信交付、summary绑定、事件不可变边界、逐票状态错位、已有候补确认入口及预算边界的静态核查；给出只补交付边的最小建议。
未做：源码/技能/配置变更、任何测试/模型/生产运行、正式研究或计划写入、新字段定义、新买权、预算owner事实确认。没有把未知契约、未知来源零预算或未展开caller细节写成已解决。
