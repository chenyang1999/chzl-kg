# 沧海巨浪规则/契约修复签核提案（2026-10-23）

> **状态：尚未应用。** 仅在 scratch 生成本文件及配套 `.patch`；没有写生产源码、SOUL、skill、配置、cron、数据库、账户或正式产物，没有补跑研究，没有 git 写操作。主 SOUL 只读，不在任一包内。
>
> 本提案基于当前真实文件逐字生成，不以审计时行号代替现文件；基线核验时点 2026-10-23 12:06 CST。A 为“已修实现的契约同步”；B 为“会改变研究资格/业务门禁语义的规则提案”。**A 不包含 B 的清观察解禁；B 不解除任何真实禁新仓。北向、窗口、RR 均没有代用户选择。**

## 1. 用户最少需要确认什么

### 本轮可签的两个包（签核文件修改，不等于交易授权）

1. **A：实现契约同步**——未就绪 LLM 版保留重评义务；交付/研究就绪/可交易分开；null 与真实零分开；合法 mode 与 no_trade 分开；竞价无价/partial/禁令优先展示；正式→runtime 单向权威。A 中的 R6 条款仅强调原 complete-only 和无对象非通过，不改依赖接受范围。
2. **B：研究连续性与现行用户原则落文**——禁止新仓不等于停止研究/清研究观察；真实候选画像继续、无对象允许空；研究观察不自动获得买点/开仓权限；阶段只定温度、通道动态选择；20/50 亿按用户已明确边界；不为候选数量绕否决。涉及两个子 profile SOUL，须逐文件签核并在批准应用后启动其新会话。**主 SOUL 不改。**

### 真正仍缺裁决的三类政策（未给可应用 diff）

- **北向缺失政策**：选择本文件 NB-1 / NB-2 / NB-3 或另定；确认北向是“研究完整性要求”还是“新仓必要条件”，并明确整体 confidence 与最终交易门禁的独立语义。未选前保留现禁令，不按“partial”字样自动放行。
- **生产窗口与刷新 owner**：06:10 是正式批还是提前研究？是否另有 07:30 复核？研究刷新由谁触发/验收、D1 谁重评、最迟交付何时？本轮不改 cron、不将承诺改成过去式来掩盖未刷新。
- **RR 唯一裁决**：1 / 1.8 / 2 分别是底线、仓位分档还是统一开仓门槛？对执行/观察/B计划适用范围如何？单票 RR_FAIL 是否应全局禁新？数值边界、取价、舍入口径需明确。**没有拟选任一数字。**

推荐签核顺序：先 A，再 B 中解除停研究/清观察的闭环；北向交易门禁、窗口和 RR 另裁决。A/B 都不保证产生可交易股票，也不保证今日可重评。

## 2. 不可突破的验收边界

- 有效零预算保持零，研究就绪不自动变 live，研究观察不构成开仓许可；现有全局禁令、R6 hard_reject、逐票资格、买点、账户授权仍独立生效。
- **R6 保持 `status == complete` 的输入可用性定义**；partial/degraded 研究可供观察，不等于正式反证完成。R2 无逐票对象仍不能硬凑，`candidates_evaluated=0` 和空 hard_rejects 不等于“全部通过”。不把已存在硬否决降级成建议，不为凑票递补。
- 不改模型/provider、并发、cron、输出布局、write whitelist、用户偏好或账户。本提案没有重新授权已有或新增交易。
- 未就绪 LLM 版的现有安全网仅接受全 R1–R7 与 summary 的更新批次；需要部分刷新+复用旧单元的血缘规则，必须另提签核，不能偷偷放宽。
- 本提案不裁定 R6 模式六“唯一硬否决”与模式七/九并列硬否决的遗留权限冲突；保留所有现有真实否决，绝不以澄清文案自动通过。

## 3. 真实基线、变更范围与会话生效

仓库根：`/Users/chenyang/Downloads/demo/沧海巨浪`。原 32 项暂存未写，全部 index records SHA256：`c24736dd938685a85db19301280d8b9fdafdf6fb2bab56a056068dc026df152b`。

相同目标出现在两包时，**B 的前置内容是 A 的拟议结果**。文件原 hash 永远指真实磁盘；B 另列前置 hash，不能直接拿 B 套原文件。配套 patch 用包标记分隔，只供审阅，不应整体直接 `git apply`，更不应用于包含绝对 profile 路径的无范围操作。任何实际应用前都须重新核对当前 hash、签核范围与依赖。

### A · `/Users/chenyang/Downloads/demo/沧海巨浪/docs/10-契约-研究汇总.md`

- 原文件 SHA256：`99d6d74d8c0abb7d04cd8d74e81035e4eee567588dc29c206509e1ab273cdefb`
- 本包精确前置 SHA256：`99d6d74d8c0abb7d04cd8d74e81035e4eee567588dc29c206509e1ab273cdefb`
- 拟议结果 SHA256：`14e57f6ed5e6292aed312973fbfe37cd2fa34efebdc0a914fbb4b9a4e58229e9`（**仅内存结果，不是磁盘已变更**）
- 变更范围：对齐真实summary nullable接口。；精确说明输入清洗与消费者语义，不发明置信阈值。；骨架示例改为未评价。
- 是否需新会话：文档无运行效力；下次读取采用，不能替代实现与产物重评。

### A · `/Users/chenyang/Downloads/demo/沧海巨浪/docs/11-契约-盘前预案.md`

- 原文件 SHA256：`c785655b63a9be5027bbf829f1023b3f3d7b8709819c133d47ea533c4de30652`
- 本包精确前置 SHA256：`c785655b63a9be5027bbf829f1023b3f3d7b8709819c133d47ea533c4de30652`
- 拟议结果 SHA256：`bee1b1fce3a336afac195c3b6a7362054a9ec01c7193781f2d3babfe02d7f9e2`（**仅内存结果，不是磁盘已变更**）
- 变更范围：同步单向权威读取，不扩大任何profile写目录。；执行环境与交易决定分字段。；补分层状态与观察非授权，不改资格。
- 是否需新会话：文档无运行效力；下次读取采用，不能替代实现与产物重评。

### A · `/Users/chenyang/Downloads/demo/沧海巨浪/skills/analyze_devil_advocate_v1/SKILL.md`

- 原文件 SHA256：`d9721b4145d3ef9c9832a55ad96f56ce83bc5b173c406d49e424d6714cdd1188`
- 本包精确前置 SHA256：`d9721b4145d3ef9c9832a55ad96f56ce83bc5b173c406d49e424d6714cdd1188`
- 拟议结果 SHA256：`8b863ebba7d026becb4538a08606296f4c4c3c854b63521661995fd63bae583b`（**仅内存结果，不是磁盘已变更**）
- 变更范围：保护R6完整性，不将修研究观察偷换自动通过。
- 是否需新会话：skill须fresh context重新加载；当前会话不追溯生效。

### A · `/Users/chenyang/Downloads/demo/沧海巨浪/skills/auction_amendment_v1/SKILL.md`

- 原文件 SHA256：`bbff34144e521172d78b38d28f4c4abf555906348d291ba6a4d2719a0114e878`
- 本包精确前置 SHA256：`bbff34144e521172d78b38d28f4c4abf555906348d291ba6a4d2719a0114e878`
- 拟议结果 SHA256：`d1a6ac6d276774946e4e450017cdcd526895dd626776c0a61809496242b20a6c`（**仅内存结果，不是磁盘已变更**）
- 变更范围：同步竞价禁令优先与partial展示，不改硬窗口或reload。；删除旧runtime反写修法。；移除人工补表/超时按档执行的旧规避建议。；超时历史陷阱不再教人补成执行建议。
- 是否需新会话：skill须fresh context重新加载；当前会话不追溯生效。

### A · `/Users/chenyang/Downloads/demo/沧海巨浪/skills/fetch_auction_snapshot_v1/SKILL.md`

- 原文件 SHA256：`dff225e2c70b77302ac64fe862ac0b3eb937ba7122376ad679494115a71bc478`
- 本包精确前置 SHA256：`dff225e2c70b77302ac64fe862ac0b3eb937ba7122376ad679494115a71bc478`
- 拟议结果 SHA256：`013e8c9d8eb351fdd8695119df5ff26fbe2f4dff52b5e8a8d8bf397802940965`（**仅内存结果，不是磁盘已变更**）
- 变更范围：真实partial枚举。；同步真实主备来源。；partial不等于全死，ok不等于授权。；仅空值示例，真实数值0保留。；同步C组缺失、量纲与统计契约。
- 是否需新会话：skill须fresh context重新加载；当前会话不追溯生效。

### A · `/Users/chenyang/Downloads/demo/沧海巨浪/skills/main_decision_v1/SKILL.md`

- 原文件 SHA256：`0f0af85c59761520b8616678a53b001c9851fd0737004a719f78ce240c2baf8d`
- 本包精确前置 SHA256：`0f0af85c59761520b8616678a53b001c9851fd0737004a719f78ce240c2baf8d`
- 拟议结果 SHA256：`8927d05eaea4ea5850af77af24d7228599e6ce9aff5cc5ccfd546b02be79d2d2`（**仅内存结果，不是磁盘已变更**）
- 变更范围：与A组已实现安全网重评边界同步，不扩大刷新权限。；仅修mode枚举，A包不暗改观察资格；B包单独解除清观察。；消除“不可发半成品”与合法安全临时版混淆；校验失败仍拒绝。；阶段表中的禁交易也使用独立no_trade字段，不新增mode枚举。
- 是否需新会话：skill须fresh context重新加载；当前会话不追溯生效。

### A · `/Users/chenyang/Downloads/demo/沧海巨浪/skills/research_orchestrator_v1/SKILL.md`

- 原文件 SHA256：`3171c4bc9b7515a30ec6d461799fb7c63eedf97b7e9ef68a9778216e4aed94e3`
- 本包精确前置 SHA256：`3171c4bc9b7515a30ec6d461799fb7c63eedf97b7e9ef68a9778216e4aed94e3`
- 拟议结果 SHA256：`bb6a99cf16c0d55d511e42e75659cf44684090d7d79441679e6b66e428bbe200`（**仅内存结果，不是磁盘已变更**）
- 变更范围：统一null与真实零，历史参考不冒充本次评价。；示例不再用0占位未评价。；移除第二处超时固定零。
- 是否需新会话：skill须fresh context重新加载；当前会话不追溯生效。

### A · `/Users/chenyang/Downloads/demo/沧海巨浪/tests/checks/check_md_namespace.py`

- 原文件 SHA256：`7cc99ec0423c303785bbcd0dcc02e7186d5b9f39a1e06fd22e3454ae367d8040`
- 本包精确前置 SHA256：`7cc99ec0423c303785bbcd0dcc02e7186d5b9f39a1e06fd22e3454ae367d8040`
- 拟议结果 SHA256：`ea1651ee12a058355071d6b943f38b65a6f0687c764942eb03dde5e5f1140634`（**仅内存结果，不是磁盘已变更**）
- 变更范围：null呈现契约兼容；仅为拟议代码，未应用。
- 是否需新会话：下次检查进程读取；无SOUL会话重启要求。

### B · `/Users/chenyang/.hermes/profiles/canghai-plan/SOUL.md`

- 原文件 SHA256：`5c6c6c28e72a7b1970a852b3d16f2b033b06d5c0bc10c955cc16bb51ae13e3a2`
- 本包精确前置 SHA256：`5c6c6c28e72a7b1970a852b3d16f2b033b06d5c0bc10c955cc16bb51ae13e3a2`
- 拟议结果 SHA256：`2a1497baba4db228927ac7376b32453044d0126c4378e149c7152fc8b64364b1`（**仅内存结果，不是磁盘已变更**）
- 变更范围：计划身份层取消固定阶段资格；不动RR条款或预算阈值。
- 是否需新会话：必须：批准应用后仅该profile新会话生效。

### B · `/Users/chenyang/.hermes/profiles/canghai-research/SOUL.md`

- 原文件 SHA256：`9dd5bf534052fa41b2762fa999899a87d3f58b65afe76234b10e4d3fa185fb31`
- 本包精确前置 SHA256：`9dd5bf534052fa41b2762fa999899a87d3f58b65afe76234b10e4d3fa185fb31`
- 拟议结果 SHA256：`f3b1d30e494f42ca6efd037a6d793a309c7202c957e043c6a0bafa6a59eb5d35`（**仅内存结果，不是磁盘已变更**）
- 变更范围：解除身份层停研究级联；不改主SOUL、不新增写权限。
- 是否需新会话：必须：批准应用后仅该profile新会话生效。

### B · `/Users/chenyang/Downloads/demo/沧海巨浪/skills/_archive/filter_leader_v1/SKILL.md`

- 原文件 SHA256：`794e312b5bec04787b93b3c6e262b1e6f0fd8dda2a56d2e534b2ea89c3744f03`
- 本包精确前置 SHA256：`794e312b5bec04787b93b3c6e262b1e6f0fd8dda2a56d2e534b2ea89c3744f03`
- 拟议结果 SHA256：`f14c371ab1727af7d1649c60c4da00b54ff6d1b2c60a0f6b125553cd145f845b`（**仅内存结果，不是磁盘已变更**）
- 变更范围：仍被加载的归档skill删除替补例外，其他过滤阈值原封不动。
- 是否需新会话：skill须fresh context重新加载；当前会话不追溯生效。

### B · `/Users/chenyang/Downloads/demo/沧海巨浪/skills/analyze_devil_advocate_v1/SKILL.md`

- 原文件 SHA256：`d9721b4145d3ef9c9832a55ad96f56ce83bc5b173c406d49e424d6714cdd1188`
- 本包精确前置 SHA256：`8b863ebba7d026becb4538a08606296f4c4c3c854b63521661995fd63bae583b`
- 拟议结果 SHA256：`aeee4559edbb1d095759202b03c33e50dd9fc3a5c6581a254d5d8124b67d0e0d`（**仅内存结果，不是磁盘已变更**）
- 变更范围：硬否决不再含“保留执行池”等买点歧义；不裁定模式七权限。
- 是否需新会话：skill须fresh context重新加载；当前会话不追溯生效。

### B · `/Users/chenyang/Downloads/demo/沧海巨浪/skills/analyze_main_sectors_v1/SKILL.md`

- 原文件 SHA256：`f8326ea438d7da792a072ee91aef9d4450c87b0b3789c91dba90278389b674c7`
- 本包精确前置 SHA256：`f8326ea438d7da792a072ee91aef9d4450c87b0b3789c91dba90278389b674c7`
- 拟议结果 SHA256：`e327944d4a9a51989b6a6582a1d25a5521e61261170adf14cd996a265dd8aea0`（**仅内存结果，不是磁盘已变更**）
- 变更范围：研究方向不被当日交易主线数一刀切。；同步用户20/50现行边界，明确这是资格语义变更，放B。；明确execution_eligible前置筛选不是最终权限。；删除生命周期直接进执行池。
- 是否需新会话：skill须fresh context重新加载；当前会话不追溯生效。

### B · `/Users/chenyang/Downloads/demo/沧海巨浪/skills/analyze_stock_profile_v1/SKILL.md`

- 原文件 SHA256：`a180541fe70ce174e48e181a9e4bc62ea99c63e87f05386b107a290af926d92a`
- 本包精确前置 SHA256：`a180541fe70ce174e48e181a9e4bc62ea99c63e87f05386b107a290af926d92a`
- 拟议结果 SHA256：`3a69092fc6950939f6c9e563031c1df4ca53088b0ffaf5d51240d8e5482da614`（**仅内存结果，不是磁盘已变更**）
- 变更范围：禁交易不再触发R5研究跳过。；删除至少5只assert；保留原扩池来源与上限目标，不授予新仓。；不再鼓励为数量绕风控；不冒称旧检查器存在。
- 是否需新会话：skill须fresh context重新加载；当前会话不追溯生效。

### B · `/Users/chenyang/Downloads/demo/沧海巨浪/skills/analyze_style_v1/SKILL.md`

- 原文件 SHA256：`6097bb83402d836101de3348446129d71e6d3ff337b20dc6b9304455e07c6311`
- 本包精确前置 SHA256：`6097bb83402d836101de3348446129d71e6d3ff337b20dc6b9304455e07c6311`
- 拟议结果 SHA256：`40ef3105c0495223b52c510302ee4fa452e5bf43b675830c373da44f326faff6`（**仅内存结果，不是磁盘已变更**）
- 变更范围：R1不再以action字段注入固定打法。
- 是否需新会话：skill须fresh context重新加载；当前会话不追溯生效。

### B · `/Users/chenyang/Downloads/demo/沧海巨浪/skills/main_decision_v1/SKILL.md`

- 原文件 SHA256：`0f0af85c59761520b8616678a53b001c9851fd0737004a719f78ce240c2baf8d`
- 本包精确前置 SHA256：`8927d05eaea4ea5850af77af24d7228599e6ce9aff5cc5ccfd546b02be79d2d2`
- 拟议结果 SHA256：`b3e8d6d49e42b84a80613e4e63f7f5a578b95a6c1ab009e606cc2eacc6627876`（**仅内存结果，不是磁盘已变更**）
- 变更范围：从A安全mode补丁再改观察资格；B依赖A，禁止P1绕禁。；观察数量不得反向驱动凑数。；移除第二个最低15硬配额，不另定数量。；消除被否后自动递补旧例外。；撤销固定阶段打法/主升任何位置；保留全部原cap常数和≤2约束。；不换规则引擎、不改通道代码，清楚标明后续实现依赖。；避免旧表继续呈现硬白名单。；删除按阶段最低3%强制参与，B显式改变业务参与下限而非暗放行。
- 是否需新会话：skill须fresh context重新加载；当前会话不追溯生效。

### B · `/Users/chenyang/Downloads/demo/沧海巨浪/skills/short_line_thinking_v1/SKILL.md`

- 原文件 SHA256：`dad7f28dad6779ee40b16ed1cfcdd39348435c5407f63968dfb711e306c49c54`
- 本包精确前置 SHA256：`dad7f28dad6779ee40b16ed1cfcdd39348435c5407f63968dfb711e306c49c54`
- 拟议结果 SHA256：`aab4dd21f870e1cc13c9920ca8d10731e9ec627966874f0c5cffc353a2a94994`（**仅内存结果，不是磁盘已变更**）
- 变更范围：移除所有低吸按阶段禁用，不解除真实禁令。
- 是否需新会话：skill须fresh context重新加载；当前会话不追溯生效。

### B · `/Users/chenyang/Downloads/demo/沧海巨浪/skills/trade_discipline_v1/SKILL.md`

- 原文件 SHA256：`076853d910830a033ed05f94830c63debbeb4dea2f972a34094113e4e35e6edf`
- 本包精确前置 SHA256：`076853d910830a033ed05f94830c63debbeb4dea2f972a34094113e4e35e6edf`
- 拟议结果 SHA256：`6ee0609a07e3fd93e11ba3162f47455906641ad4d5ce93238de27ab4fb9ba6e1`（**仅内存结果，不是磁盘已变更**）
- 变更范围：最小限定旧表效力，不顺手改仓位参数和禁止清单。
- 是否需新会话：skill须fresh context重新加载；当前会话不追溯生效。

## 4. A 包：实现契约同步的精确最小差异

下列上下文、删除与新增均为当前文件逐字差异（每个 hunk 保留三行上下文）。A 包对 no_trade 暂保留原清观察限制，防止“mode兼容修复”偷带业务资格变更；清观察只在 B 包改。

```diff
--- /Users/chenyang/Downloads/demo/沧海巨浪/docs/10-契约-研究汇总.md
+++ /Users/chenyang/Downloads/demo/沧海巨浪/docs/10-契约-研究汇总.md
@@ -25,7 +25,7 @@
 | `fetch_manifest` | string | ✅ | 上游 fetch 产物路径，如 `data/raw/20260704/manifest.json` |
 | `fetch_global_severity` | integer | ✅ | 启动 research 时 manifest 的 `global_severity`（0-3） |
 | `artifacts` | object | ✅ | R1-R7 各单元 JSON 路径，见 §3 |
-| `confidence` | object | ✅ | 各单元置信度 0.0-1.0，skeleton/降级时为 0 |
+| `confidence` | object | ✅ | 每单元为有限数 0.0–1.0 或 null；null=本次未评价/未知，0.0=真实评价为零，不按状态自动互换 |
 | `hard_rejects` | array | ✅ | R6 硬否决清单，可为空；元素见 §4 |
 | `timeouts` | array | ✅ | 超时或未完成的单元 ID，如 `["R5"]` |
 | `completed_by` | string | ✅ | 计划完成时点 `"08:00"`（盘前批次） |
@@ -98,7 +98,10 @@
 |------|------|
 | 正常完成 | 0.5-1.0，由子 Agent 自评 |
 | 降级（单源失联） | 0.3-0.5 |
-| skeleton / 昨日 fallback / 超时 | 0 |
+| 本次未评价（含 skeleton / 超时 / 昨日历史参考） | null；另列状态、日期与缺口，不以 0 冒充评价 |
+| 真实评价为零 | 0.0，原样保留 |
+
+汇总只接受有限、非 bool、在 [0,1] 内的数值；缺失、非法、非有限值记 null 并保留原始质量说明。消费者先区分 null 与数值，禁止 `or 0` 或用 null 触发数值零的降级/默认仓位；null 不构成完成或通过证明。JSON/MD 交付、研究就绪和交易授权是独立事实。
 
 ---
 
@@ -145,7 +148,7 @@
     "R7": "data/research/20260704/R7_capital_flow.json"
   },
   "confidence": {
-    "R1": 0, "R2": 0, "R3": 0, "R4": 0, "R5": 0, "R6": 0, "R7": 0
+    "R1": null, "R2": null, "R3": null, "R4": null, "R5": null, "R6": null, "R7": null
   },
   "hard_rejects": [],
   "timeouts": [],
--- /Users/chenyang/Downloads/demo/沧海巨浪/docs/11-契约-盘前预案.md
+++ /Users/chenyang/Downloads/demo/沧海巨浪/docs/11-契约-盘前预案.md
@@ -1,6 +1,6 @@
 # watchlist_plan.json 标准Schema说明
 
-> 路径：`data/runtime/watchlist_plan_YYYYMMDD.json`
+> 正式产物：`data/plans/YYYYMMDD/watchlist_plan.json`；执行运行副本：`data/runtime/watchlist_plan_YYYYMMDD.json`。由现有校验交接单向正式→runtime，不能用副本反写、补缺或替换正式源；本条不改变任何输出目录或 owner。
 > 交易Agent网页和执行Agent都依赖这份结构化数据，**必须严格遵守字段名和枚举值**
 
 ---
@@ -10,7 +10,7 @@
 | 字段 | 类型 | 必填 | 说明 |
 |------|------|------|------|
 | `trade_date` | string | ✅ | 交易日，格式 `YYYYMMDD` 如 `"20260629"` |
-| `mode` | string | ✅ | `"live"` 实盘 / `"dry_run"` 回测 |
+| `mode` | string | ✅ | 仅 `"live"` / `"dry_run"`；执行环境不是交易决定，禁新仓另写 `no_trade: true`，不得新增 mode 枚举或丢弃禁令 |
 | `agent_name` | string | ✅ 固定 | `"盘前预案 Agent / Stock Selection & Setup Agent / Alpha-Setup Agent"` |
 | `generated_at` | string | ✅ | ISO格式时间 `"2026-06-29T08:30:00+08:00"` |
 | `trading_style` | string | ✅ 固定 | `"mainline_right_side_with_trend_pullback"`（主线进攻+右侧低吸） |
@@ -25,6 +25,8 @@
 | `watch_pool` | array | ✅ | 观察池（备选，不在今日计划买入但跟踪），每个元素是 **StockEntry** |
 | `rejected` | array | ✅ | 否决标的（可以为空） |
 | `research_anchor_only` | array | ✅ | 仅研究不交易（可以为空） |
+
+`production_ready` / `research_completion_passed` / `reassessment_required` 显式显示研究是否仍待重评；安全发布和交付 completed 不代表研究完成。未就绪版保持 dry_run、关闭自动交易、要求用户确认；就绪 true 也不自动放行。观察池或研究锚不构成开仓权限，须独立通过当日全局禁令、R6、逐票资格、预算、买点与用户授权。缺失 confidence 保留 null，不填 0。
 
 ---
 
--- /Users/chenyang/Downloads/demo/沧海巨浪/skills/analyze_devil_advocate_v1/SKILL.md
+++ /Users/chenyang/Downloads/demo/沧海巨浪/skills/analyze_devil_advocate_v1/SKILL.md
@@ -152,6 +152,8 @@
 
 构建 `upstream_usable: {R1..R7: bool}`（`status == complete`）。  
 R2 不可用 → 直接产出降级 JSON（spec §6），`counter_arguments: []`。
+
+**不改变 complete-only**：研究观察有对象或上游 partial/degraded，不等于可直接通过正式反证；所需完整输入不足时继续标未完成及缺口。无逐票对象时如实 `candidates_evaluated: 0`，空 `hard_rejects` 只代表未形成否决，不代表全票审核通过；不凑对象、不用空反证解除禁新仓，也不把 skipped/degraded 自动改 complete。
 
 ### Step 2 · 逐模式扫描
 
--- /Users/chenyang/Downloads/demo/沧海巨浪/skills/auction_amendment_v1/SKILL.md
+++ /Users/chenyang/Downloads/demo/沧海巨浪/skills/auction_amendment_v1/SKILL.md
@@ -97,6 +97,8 @@
 4. 记录 `observe_only: true`（T3 首周默认）写入 `notes`
 
 ### Step 1 — 逐票检查 execution_pool（对照 auction_expectation 三档）
+
+先独立展示原预案禁新仓/零预算/未就绪与 P1 修订状态：任一禁令、权威预案校验失败、超时/未完成时，不凭快照、档位、briefing 或 promote 文本新增授权，表内动作只能作观察参考。partial 保留有效报价并逐项列缺口；无有效竞价价或昨收时不填0、不推断符合预期。空 items 只代表未列修订，不代表逐票通过；研究观察不自动升级开仓权限。
 
 对每只 `execution_pool` 票，读其 `entry_rules.auction_expectation`（2026-09-17 起每票必填），用 snapshot 竞价价机械对照：
 
@@ -215,14 +217,14 @@
 ## Pitfalls（2026-09-22 实战）
 
 1. **三档表真实位置是票顶层，不是 `entry_rules[0].auction_expectation`**：D1 主路径输出里每只 execution 票顶层就有 `auction_expectation`（base_close/expected_open_band/bands）。消费侧（P1 / render_auction_judgment）必须先读票顶层，entry_rules 内嵌只作回退。只查 entry_rules 会误判 `auction_expectation_missing`。
-2. **D1 主路径完整 json 常落在 `data/runtime/watchlist_plan_YYYYMMDD.json`，漏拷契约路径 `data/plans/YYYYMMDD/watchlist_plan.json`**；而 08:30 安全网 fallback 已在契约路径落了空池规则版（`meta.python_fallback: true` / agent_name 含 "rule v1"）。09:27 快照、09:28 P1、渲染器只认契约路径 → 全读到空池 → "无执行池"。修法：统一走 `src/plan/plan_resolver.resolve_authoritative_plan(date)`——契约路径是 fallback 且 runtime 有更新的非 fallback json 时自动同步；快照 `_read_plan` 已接入（09:27 是 P1 前的同步窗口）。
+2. **权威源与副本单向交接**：统一调用 `src/plan/plan_resolver.resolve_authoritative_plan(date)`，只读经交易日与现有 schema/安全旗标校验的正式 `data/plans/YYYYMMDD/watchlist_plan.json`。缺失/非法时如实拒绝；runtime 不反写、不补缺、不替换正式源，`sync` 参数只兼容、不恢复旧同步行为。
 3. **user_briefing 为 null 是常态**（只有大面积异常才填）；渲染器不得在 null 时吐“竞价与预案对照完毕，按三档执行”这种空话，要基于 execution_pool 生成有信息量的结论（无执行池＝明写“无买点，空仓”）。
 4. **pitfall #2 仍会复发（2026-09-23 实测）**：09:27 快照仍读了契约路径 fallback 版（pool_auction 只有 fallback 的 9 只 watch 票，不含 runtime 主路径 execution_pool 4 票）。P1 不能假设快照覆盖执行池——逐票对照前先比对 snapshot.pool_auction 的 ts_code 集合与权威 plan execution_pool；缺口票直接用 XTick `xtick_auction_detail(code, tradeDate)` 取 09:25 结算竞价补齐（单票一次调用，4 票可并行）。
-5b. **渲染脚本也读契约路径 → 空池误导（2026-09-24 实测）**：pitfall#2 复发时 render_auction_judgment.py 同样读契约路径 fallback，md 显示"（无执行池）"，即使权威 plan 有执行池。P1 落盘后必须检查渲染出的 md：执行池段为空而权威 plan 非空 → 用 patch 补入逐票判定表（竞价价/昨收/溢价/档位/动作），否则用户开盘看到空话。渲染器长期修法=接入 plan_resolver.resolve_authoritative_plan。
-5d. **renderer 在 timeout 修订下逐票写"无修订（符合预期或未触发）"=误导（2026-09-28 实测）**：amendment items=[] 时 render_auction_judgment.py 对每只执行池票默认写"P1 判定: 无修订（符合预期或未触发）"，读者会误以为竞价落在预期档。实际是竞价价缺失、P1 超时。timeout 落盘后必须 patch 掉这 3 行（改"⚠️ P1 超时未产出，竞价价缺失，开盘后按真实开盘价对照三档表执行"），否则用户开盘看到假判定。
+5b. **人读与机读使用同一权威预案**：渲染器也走只读 resolver；拒绝后不得裸读或从 runtime 恢复。实际缺交付记缺交付，不手工拼造与正式源不一致的执行表。
+5d. **超时/缺价不得假判通过**：顶部与逐票显示无有效修订、报价缺失和无新仓授权；已有三档仅供观察，不写“符合预期/按档执行”。空 items 不作通过证明，不事后补写有效修订。
 7. **后缀不匹配=拿着答案误判未覆盖（2026-09-28 timeout 真根因）**：快照 pool_auction 实际含执行池3票且竞价价齐全，但快照 ts_code 无后缀（000592）、plan 带 .SZ 后缀（000592.SZ），P1 字符串比对失败误判"未覆盖"，逐票 XTick 补数拖到09:29:22超硬窗口。P1 覆盖率比对必须统一 bare code（去后缀）再比较集合；fetch 已改为保留后缀输出、code=all 单次抓全（0.8s），正常情况下无需补数。
 5c. **cron 环境 execute_code 被禁（2026-09-24 实测）**：`execute_code` 在 cron 模式直接 BLOCKED（"Cron jobs run without a user present to approve it"），浪费窗口内一轮调用。P1 全流程禁用 execute_code，JSON 提取一律用 terminal 单行 `python3 -c` + read_file。今天因此超时 12s → timeout_no_amendment。
-5e. **cron 安全扫描器连嵌套 `python3 -c` 也拦（2026-10-13 实测，整窗报废）**：cron 模式不仅禁 execute_code，`terminal` 里带引号嵌套的 `python3 -c "import json; ..."` 也被 Tirith 安全扫描 BLOCKED（"Nested executable body could not be resolved"），连续两次拦截直接烧掉 09:28-09:29 硬窗口 → timeout_no_amendment。P1 在 cron 下**唯一安全姿势=先 write_file 写脚本再 terminal 执行**（普通 `python3 xxx.py` 不拦）；所有 JSON 提取/落盘都走脚本文件，禁止任何内联 python。若已过 09:29：立即落 timeout_no_amendment（含 notes 记录已核事实），渲染 md 后人工补事实判定行（如"竞价 2.78 落符合预期档→按预案回踩 2.72"），勿再等数据。
+5e. **cron 安全扫描器连嵌套 `python3 -c` 也拦（2026-10-13 实测，整窗报废）**：cron 模式不仅禁 execute_code，`terminal` 里带引号嵌套的 `python3 -c "import json; ..."` 也被 Tirith 安全扫描 BLOCKED（"Nested executable body could not be resolved"），连续两次拦截直接烧掉 09:28-09:29 硬窗口 → timeout_no_amendment。P1 在 cron 下**唯一安全姿势=先 write_file 写脚本再 terminal 执行**（普通 `python3 xxx.py` 不拦）；所有 JSON 提取/落盘都走脚本文件，禁止任何内联 python。若已过 09:29：立即落 timeout_no_amendment（含 notes 记录已核事实），渲染 md 仅补已核实竞价事实与缺口，并标“超时、无有效修订、仅供观察”；不得事后补成有效落档或买入动作，勿再等数据。
 5f. **read_file 读大 JSON 也烧窗口（2026-10-15 实测）**：plan(753行)+snapshot(1481行)+昨日schema+渲染脚本轮番 read_file 共 4-5 轮，把 09:28-09:29 窗口烧到 09:30 才落盘 → timeout。P1 的提取必须一个脚本搞定：write_file 写 `extract_p1.py`（只打印所需字段：执行池 ts_code/name/top层 auction_expectation base_close/expected_open_band/bands action、snapshot 对票竞价价/premium/base_close 一致性、orchestrator_status），一次 terminal 执行打印全部，再根据输出决定判定。禁止用 read_file 顺序读多个大 JSON。需要参照 schema 时读历史 amendment 用 read_file（小文件可）。
 5g. **date+发现性 ls 必须并入提取脚本，写 status 前先看钟（2026-10-16 实测，超窗 2.5min）**：cron 09:28:55 启动，首轮 ls/find 发现 + 提取脚本 + 先写 complete 再核钟改 timeout 双写，落盘 09:31:32。教训：①提取脚本第一步就打印 `date` 与各输入文件存在性，禁止先 ls 再写脚本；②`head -n` 截断会砍掉脚本尾部关键字段（orchestrator_status 被 head -120 截掉→被迫多一轮 read_file）——关键字段放输出最前面，或干脆不 head；③落盘前先看 date，已过 09:29 直接写 timeout_no_amendment，别先写 complete 再重写（每次 write_file 都是 ~2s+ 排队）。
 6. **plan base_close 可能过期（2026-09-23 实测）**：D1 规则版对 300324（base 17.24→实际昨收 4.14）、601811（14.14→16.82）用了过期参考价，整张 auction_expectation 三档表失效。P1 逐票先拿 XTick detail 的 `close` 字段与 plan `auction_expectation.base_close` 比对，不一致时以 XTick/Tushare 为准重判档位，并在 notes 标注 `base_close_stale`（E1 计 D1 参考价合规率）。渲染器会把过期 base_close 写进 md 表头——P1 判定行必须自带真实价纠正。
--- /Users/chenyang/Downloads/demo/沧海巨浪/skills/fetch_auction_snapshot_v1/SKILL.md
+++ /Users/chenyang/Downloads/demo/沧海巨浪/skills/fetch_auction_snapshot_v1/SKILL.md
@@ -74,9 +74,9 @@
 
 ```
 【fetch_auction_snapshot_v1 · YYYYMMDD】
-status: {ok|stub|skipped}
+status: {ok|partial|stub|skipped}
 severity: {0-3}
-source: {xtick|stub|none}
+source: {tushare_stk_auction|xtick|stub|none}
 pool_count: {N}
 captured_at: {ISO8601}
 
@@ -92,7 +92,8 @@
 ```
 
 **severity 解读**:
-- `0` + `status=ok` → P1 正常读取
+- `0` + `status=ok` → 可读取；只证明快照质量，不证明逐票可交易
+- `1` + `status=partial` → 保留有效行/字段，逐项展示质量缺口；不是全源不可用。报价及情绪均缺失才按现有实现 stub/severity=2；不得以缺失填0洗成ok。
 - `2` + `status=stub` → P1 可尝试 XTick MCP 补一次；仍失败则无 amendment
 - plan 缺失 `skipped` → P1 仍运行但无 pool 名单（由 P1 降级）
 
@@ -125,9 +126,9 @@
   "schema_version": "auction_snapshot_v1",
   "trade_date": "YYYYMMDD",
   "captured_at": "ISO8601+08:00",
-  "market_sentiment": {"limit_up_count": 0, "limit_down_count": 0, "up_down_ratio": 0},
+  "market_sentiment": {"limit_up_count": null, "limit_down_count": null, "up_down_ratio": null},
   "pool_auction": [
-    {"ts_code": "", "auction_price": 0, "prev_close": 0, "premium_pct": 0, "auction_volume": 0, "auction_amount": 0}
+    {"ts_code": "", "auction_price": null, "prev_close": null, "premium_pct": null, "auction_volume": null, "auction_amount": null}
   ],
   "severity": 0,
   "status": "ok",
@@ -136,6 +137,10 @@
 ```
 
 ## Rules & Constraints
+
+- 无价/无昨收/非有限数 → 对应字段 null 并记缺失原因，不用0占位；有效正报价与昨收才算溢价，真实0收益有效。严格 JSON 禁 NaN/Infinity。
+- 篮子按唯一标的分别展示 `requested_count` / `valid_count` / `missing_count` / `coverage_ratio`，均溢价仅用有效样本；兼容字段 `n` 表示有效数，不拿请求数冒充有效数。
+- XTick `jjl` 仅作成功率，不当成交亿元；独立情绪成交额字段及单位未确认时 `auction_volume_yi=null`。XTick 原始 `jje` 保留但不猜单位；Tushare 已确认 amount 以元标 CNY。
 
 - 必须在 **09:28:00** 前完成落盘（P1 09:28 启动即读取；竞价数据 09:27 才到，勿早跑）
 - 纯 Python subprocess；Agent 只 report
--- /Users/chenyang/Downloads/demo/沧海巨浪/skills/main_decision_v1/SKILL.md
+++ /Users/chenyang/Downloads/demo/沧海巨浪/skills/main_decision_v1/SKILL.md
@@ -30,7 +30,7 @@
 |------|---------|
 | 08:00（盘前批次） | 同日 `data/research/YYYYMMDD/research_summary.json` 已存在且 `orchestrator_status` ≠ `failed` |
 
-若 research 主控未完成，**拒绝出 plan**，告警用户，不写半成品 JSON。
+若 research 主控未完成，告警并保留未完成事实；缺少必需输入/校验失败仍拒绝写 plan，不拼造半成品。若现有安全校验允许发布未就绪 LLM 临时版，必须完整符合安全发布字段与重评契约（见 Step 3.5.8），只能 dry_run/禁新仓，不视为研究完成或最终裁决。
 
 ---
 
@@ -129,7 +129,7 @@
 |------|---------|----------------|------|
 | `main_up` 主升 | 猛干龙头，任何位置进都对 | 龙头/龙二满配 | 按 R1 cap 上限执行 |
 | `high_chop` 高位震荡 | 落袋为安，控仓；只做龙头分歧低吸或低位补涨 | 减半，只留最强主线 | cap × 0.75 |
-| `main_down` 主跌 | 空仓/切换新题材一日游；连跌2天尾盘试错 | **≤2 只**或空 | cap × 0.4，或 mode=no_trade |
+| `main_down` 主跌 | 空仓/切换新题材一日游；连跌2天尾盘试错 | **≤2 只**或空 | cap × 0.4，或 mode=dry_run 且 no_trade=true |
 | `low_test` 低位试错 | 打首板/低位补涨，轻仓试错 | 小仓试错 | cap × 0.5 |
 
    - **优先级**: 本四阶段 > Step 0.5 的 7 阶段（7 阶段偏描述性，四阶段直接给操作）。两者冲突时以四阶段为准
@@ -332,7 +332,9 @@
 09:20 再跑也不重建 → 全链一整天读陈旧空池。
 
 **规则**：安全网判幂等时，除"文件存在"外还必须校验**兜底 plan 是否早于
-关键上游（R5/R6）落盘**；若是则用完整上游重建。LLM 主路径产物一律不覆盖。
+关键上游（R5/R6）落盘**；若是则用完整上游重建。完整、已评估的合法 LLM 决策（含 no_trade/空执行池）不得被兜底覆盖，`--force` 也不例外。
+
+**交付完成 ≠ 研究就绪 ≠ 可交易**：未就绪 LLM 版可按现有校验安全发布，但须显式 `production_ready: false`、`research_completion_passed: false`、`reassessment_required: true`，保持 `mode: dry_run`、`autonomous_trading_enabled: false`、`requires_user_confirmation: true`；不能因文件存在、LLM 来源、交付 completed 或执行池为空而免除重评。研究刷新归研究 owner，D1 重评归计划 owner；安全网不代跑 R1–R7、不切模型、不抬有效零预算。现有重评实现只在 R1–R7 与 summary 均晚于未就绪预案、日期/路径/已有 run_id 一致且显式未就绪标记已解除后重试 D1；缺新批次或重评仍未完成时保留未完成状态并非零返回，不以 Python 规则覆盖。`production_ready=true` 也不构成 live/开仓授权。生产窗口和刷新触发待用户另签。
 
 ### Step 3.6 — 战术层短线信号(2026-09-04 新增 · 硬闸门 · v1.7)
 
@@ -1206,7 +1208,7 @@
 
 **硬约束**:
 - `no_trade_conditions` 必须存在(即使全部 `active: false`)
-- 任一 `active: true` → D1 输出 `mode: "no_trade"`,`autonomous_trading_enabled: false`,`execution_pool: []`,`watch_pool: []`(全空)
+- 任一 `active: true` → D1 输出 `mode: "dry_run"`、独立 `no_trade: true`、`autonomous_trading_enabled: false`、`requires_user_confirmation: true`、`execution_pool: []`、`watch_pool: []`（本行暂保留原清观察限制；是否保留研究观察由 B 包单独签核）。`mode` 只表示执行环境，不新增 `no_trade` 枚举；不得删除禁令来通过 schema。
 - plan.md **必须**在顶部展示"不交易条件清单 + 当前 active 项"(便于用户 review)
 
 **降级**:
--- /Users/chenyang/Downloads/demo/沧海巨浪/skills/research_orchestrator_v1/SKILL.md
+++ /Users/chenyang/Downloads/demo/沧海巨浪/skills/research_orchestrator_v1/SKILL.md
@@ -148,7 +148,7 @@
 
 **R6 特殊**: 从 `R6_devil_advocate.json` 提取 `severity: hard_reject` 条目 → 填入 `hard_rejects[]`（schema 见 `docs/10-契约-研究汇总.md` §4）。
 
-**Fallback（T1' 软降级）**: 某 R* 失败时可读 **昨日** 同路径 artifact 作替代，`confidence=0`，`timeouts` 标注 — **不**调用 Python `src/research/r*.py`。
+**Fallback（T1' 软降级）**: 昨日 artifact 仅可显式作为历史参考，不冒充本次研究完成；本次未评价的 `confidence=null`，真实评价为零时保留 `0.0`，并标注原日期、缺口与 `timeouts` — **不**调用 Python `src/research/r*.py`。交付 completed 与研究就绪分别核验；未就绪版保留研究 owner 的刷新义务，不能由安全网自行代跑研究。
 
 ### Step 5 · 写 research_summary.json
 
@@ -173,7 +173,7 @@
     "R6": "data/research/YYYYMMDD/R6_devil_advocate.json",
     "R7": "data/research/YYYYMMDD/R7_capital_flow.json"
   },
-  "confidence": {"R1": 0.0, "R2": 0.0, "R3": 0.0, "R4": 0.0, "R5": 0.0, "R6": 0.0, "R7": 0.0},
+  "confidence": {"R1": null, "R2": null, "R3": null, "R4": null, "R5": null, "R6": null, "R7": null},
   "hard_rejects": [],
   "timeouts": [],
   "completed_by": "08:00"
@@ -281,7 +281,7 @@
 | 场景 | 行为 |
 |------|------|
 | manifest 缺失 | `orchestrator_status=failed`，不写 summary，告警 |
-| 单 R* 超时 | 昨日 artifact + `confidence=0` + `timeouts` |
+| 单 R* 超时 | 昨日 artifact 仅标历史参考；本次未评价 `confidence=null`，保留 `timeouts` 与原日期；不冒充本次完成 |
 | R6 超时 | D1 视为「无反证」保守处理；**不可**自行放宽 R6 约束 |
 | Hermes delegation 全失败 | 告警 + 空池；**不**跑 Python orchestrator（T1' 冻结） |
 | **LLM quota 超限** | 保留已验证研究并明确失败单元、实际错误与可恢复状态；D1 交由计划端及已授权安全网处理，研究端不写计划/触发价，不自动切换模型 |
--- /Users/chenyang/Downloads/demo/沧海巨浪/tests/checks/check_md_namespace.py
+++ /Users/chenyang/Downloads/demo/沧海巨浪/tests/checks/check_md_namespace.py
@@ -96,6 +96,9 @@
         if not m:
             return []  # 没有 confidence 字段也不报错（不是所有 md 都有）
         conf_str = m.group(1)
+
+    if isinstance(conf_str, str) and conf_str.strip().lower() in {"null", "~"}:
+        return []  # 未评价，不按数值零校验；不代表研究或交易门禁通过
 
     try:
         confidence = float(conf_str)
```

## 5. B 包：需单独签核的研究资格/业务门禁语义差异

这不是“保证给票”：允许真空池、允许保持 no_trade；只是避免禁交易变成无法继续研究和重评。保留原仓位常数，不新增固定打法映射。取消“阶段自动给至少3%参与”的保底额度是显式的业务语义收紧，非暗调仓位阈值。R2 20/50 亿按当前用户原则提案，不把旧50亿硬门槛藏在实现同步包。

```diff
--- /Users/chenyang/.hermes/profiles/canghai-plan/SOUL.md
+++ /Users/chenyang/.hermes/profiles/canghai-plan/SOUL.md
@@ -32,8 +32,8 @@
 D1 出盘前预案是整套系统的**决断点**。心法不是参考,是**思考顺序**。
 
 ### D1 必走的 5 步决策(纪律 §9 强制)
-1. **情绪阶段 → 仓位上限**:调 `@emotion_cycle_v1` 取 phase→position_cap(主升满配 / 震荡压半 / 主跌仅试仓)
-2. **主线候选 → 总龙 → 补涨**:调 `@mainline_lifecycle_v1` 取 stage→可选 stage(启动/主升早中/高潮/退潮),不在主升段的不进 execution
+1. **阶段只定温度**:读 `@emotion_cycle_v1` 与已批准仓位上限，不预设“阶段→打法/通道”；阶段不自动授权或停止研究，既有禁新仓与有效零预算优先。
+2. **主线研究候选 → 核心身位 → 资金确认**:读 `@mainline_lifecycle_v1` 作为风险背景，按当日赚钱效应动态选择通道；研究就绪不等于可交易，非主升阶段不自动清研究观察池。主跌转修复只研究新题材首板/二板、不接高位老龙，所有开仓仍须独立通过原门禁。
 3. **每只 execution 票 → Step 3.6 四闸门**(2026-09-04 新):
    - 关1 核心判定(`@core_judge_v1`) → 共振/逆势抱团 → leader/core/laggard/watch 四档
    - 关2 盈亏比(`@risk_reward_v1`) → RR<1 拒绝,1-2 试仓,2-3 正常,≥3 主仓
--- /Users/chenyang/.hermes/profiles/canghai-research/SOUL.md
+++ /Users/chenyang/.hermes/profiles/canghai-research/SOUL.md
@@ -51,8 +51,8 @@
 4. **今天计划做什么、不做什么？** 计划外不出手。
 
 ### 思考顺序铁律（每次 R* 输出前必走一遍，违反即重写）
-1. **先认市场，再认个股** — 没有主线 / 风格 / 赚钱效应，不准进 R2/R5 选股环节。
-2. **段位决定能做什么** — 主跌期降维（只输出观察，不输出候选），高位震荡压仓（中位股剔除）。
+1. **先认市场，再认个股** — 没有已确认可交易主线 / 风格 / 赚钱效应时，不授予开仓资格；R2/R4 仍须按已有证据筛选研究观察对象，R5 对真实研究候选画像，不因禁新仓停止研究。无合格对象允许为空，必须列覆盖、剔除与缺口，不为数量造票。
+2. **阶段只定温度，不预设固定打法** — 按当日赚钱效应与资金确认动态选择通道，主跌转修复聚焦新题材首板/二板、不接高位老龙；低吸是强势票相对涨停价仍低，不是抄底。研究候选与可交易候选分层记录；研究观察不构成开仓权限，现有预算、否决与逐票门禁仍独立生效。
 3. **只有龙头或低位，躲中位和杂毛** — R2 输出必须显式标 `rank ∈ {龙头, 龙二, 龙三}` + `rank=杂毛` 的剔除理由。
 4. **盈亏比优先于胜率** — 候选票如果止损距 < 5% 或 RR < 2，必须降级 watch，不能进 execution。
 5. **计划外不出手** — R4/R5 输出的"机会"必须回答：它是今日核心 / 主线补涨 / 计划内试错 中的哪一种。都不是，剔除。
--- /Users/chenyang/Downloads/demo/沧海巨浪/skills/_archive/filter_leader_v1/SKILL.md
+++ /Users/chenyang/Downloads/demo/沧海巨浪/skills/_archive/filter_leader_v1/SKILL.md
@@ -56,7 +56,7 @@
 ### 龙三及以下
 
 - `leader_rank: filtered_out`  
-- **不进 execution_pool**（除非后续 R6 对龙一 `hard_reject` 需替补 — 本 skill **只标注** `backup_eligible: true`，**不**决定 D1 是否启用）
+- **不进 execution_pool**；后续 R6 对龙一 `hard_reject` 也不自动产生替补资格，不为候选数量把龙三/杂毛升位。可保留研究观察及否决理由，不能以 `backup_eligible` 绕过原否决
 
 ### 杂毛过滤 `filter_out_rules`
 
--- /Users/chenyang/Downloads/demo/沧海巨浪/skills/analyze_devil_advocate_v1/SKILL.md
+++ /Users/chenyang/Downloads/demo/沧海巨浪/skills/analyze_devil_advocate_v1/SKILL.md
@@ -107,7 +107,7 @@
 仅命中 (1) 未确认 (2) → 降级为 **`strong_suggest`**（D1 须显式处理，可覆盖）。
 
 **否决后的出口(v1.2 · 2026-10-19 用户钦定, 取代"红线3保护")**:
-- 龙一被 hard/strong 否决后,合法出口只有两个: ①execution_pool 为空(附理由) ②保留龙一并标注"等分歧买点"
+- 龙一被 hard_reject 后只能从 execution_pool 剔除，可留研究观察并记录禁令/空池理由；不得以“等分歧买点”保留执行资格。strong_suggest 仍按原有显式处理/覆盖契约，不自动视为通过；不为数量递补杂毛
 - ❌ **禁止用龙二/弹性核心/低位补涨票降级替补**——杂毛失去板块β时风险>龙头,补涨票不得因龙头被否而升位
 - 已删除旧规则"候选<3只时hard_reject自动降级为strong_suggest"——该规则逼系统凑数,是辨识度问题的制度根源
 - 否决"高位/一致"龙一必须同时给出具体证据(霸榜出货/资金净流出/身位崩塌),不得只因位置高就否决
--- /Users/chenyang/Downloads/demo/沧海巨浪/skills/analyze_main_sectors_v1/SKILL.md
+++ /Users/chenyang/Downloads/demo/沧海巨浪/skills/analyze_main_sectors_v1/SKILL.md
@@ -107,7 +107,7 @@
 
 ### Step 1 · 读上游 + 定主线数量上限
 
-- 读 R1：`main_lines_count` 与 `style` 约束今日主线条数（防御/退潮风格 → 倾向 0–1 条或只做最强一条）
+- 读 R1：`main_lines_count` 与 `style` 作为市场温度和交易约束输入；不能据此停止研究或预先清空研究观察对象。分别记录已确认可交易主线与待资金确认的研究方向；真实无合格对象允许空，不用研究方向冒充已确认主线。
 - 读 R3：`resonance_top_themes` 中 `L1+L2+L3` / `L1+L2` 主题优先
 - 读 R4：`sectors_catalyzed` 中 `strength=high` 板块加权
 - 读 R7：资金净流入前十板块
@@ -163,14 +163,14 @@
 2. `@hithink-market-query` / Tushare moneyflow：主力资金流入 top5  
 3. 近 5 日龙虎榜频次（`top_list`）  
 4. 连板高度（`limit_step`）  
-5. 流通市值 ≥ 50 亿；排除 ST/退市/风险警示  
-6. `@iwencai-query` 可选验证：「{板块名} 涨停 连板高度 市值大于50亿」  
+5. 流通市值 <20 亿不看；20–50 亿警惕但不刻意回避，逐票注明风险与依据；排除 ST/退市/风险警示，缺市值不伪造合格  
+6. `@iwencai-query` 可选验证：「{板块名} 涨停 连板高度 流通市值不低于20亿」；返回字段及单位须核验  
 
 **板块前缀规则（2026-08-16 更新）**：300（创业板）/ 688（科创板）与主板**同权参与**龙一/龙二/中军竞争，**不得**因前缀自动降级为候补或加"需过滤"标注。仅 920（北交所）因流动性问题不进执行池推荐。20cm 票可按弹性角色（如"弹性龙二"）标注，但前缀本身不构成扣分项。
 
 输出 `leaders[]`：`role` = 龙一/龙二/候补，`ts_code`, `name`, `pct_chg`, `limit_times`, `selection_basis`。
 
-**本步产出的是候选池**；最终 execution 资格由 `filter_leader_v1` 裁定。
+**本步产出的是研究候选池**；`filter_leader_v1` 仅标龙头层级与执行前置资格，不是最终交易许可。禁新仓/零预算时保留有证据的研究观察对象并标仅研究；R5 仍可画像，R6 完整性门槛不变。最终开仓须由 D1 与执行侧逐票通过既有门禁及授权，无对象不凑数。
 
 ### Step 4.4 · 主线生命周期判定（2026-09-04 新增 · `@mainline_lifecycle_v1`）
 
@@ -188,7 +188,7 @@
 写入每条主线的 `stage` / `stage_name` / `stage_action` 字段（`formation`/`early_up`/`mid_up`/`climax`/`fade`）。
 
 **联动规则（治"一日游"）**：
-- `early_up`（主升早期）→ 最高优先级主线，龙头/龙二进 execution_pool
+- `early_up`（主升早期）→ 优先研究龙头/龙二；进入 execution_pool 仍须 D1 独立核验全部交易门禁，阶段不能自动授权
 - `mid_up` → 可做，龙头分歧低吸或后排补涨，控仓
 - `climax`（高潮分歧）→ **只做龙头或空仓等分歧**，禁追高缩量一字
 - `fade`（退潮反抽）→ **降级次线**，不进主线主推；除非情绪周期=主升（超跌反弹博反抽）
--- /Users/chenyang/Downloads/demo/沧海巨浪/skills/analyze_stock_profile_v1/SKILL.md
+++ /Users/chenyang/Downloads/demo/沧海巨浪/skills/analyze_stock_profile_v1/SKILL.md
@@ -229,7 +229,7 @@
 
 ## 降级
 
-- R2 无候选 → `status: skipped`, `profiles: []`  
+- R2 经核验确无研究候选 → `status: skipped`, `profiles: []`，说明覆盖与空池原因；禁新仓/零预算本身不是“无研究候选”。存在真实研究观察对象时继续画像，但不因此取得 execution 资格  
 - 单票 MCP 失败 → 该票 `partial: true`, 不阻塞其余票
 - 档位确实无法判定 → 显式写 `"B"` 并在 `flags` 标注 `grade_defaulted`，
   **不得留空**（留空会触发 D1 侧降级路径，掩盖真实风险）
@@ -364,11 +364,12 @@
     seen = {c["ts_code"] for c in candidates}
     supplement = [s for s in supplement if s["ts_code"] not in seen]
     supplement.sort(key=lambda x: x["r2_score"], reverse=True)
-    need = 5 - len(candidates)  # 至少保证 candidates >= 5
+    # 仅补有研究价值且未命中硬否决的真实对象；5只是扩池目标，不是最低配额
+    need = max(0, 5 - len(candidates))
     candidates.extend(supplement[:need])
 
-# 终态:candidates >= 5(若仍不够,记录 r2_expand_shortfall 到 JSON,告警)
-assert len(candidates) >= 5, f"R5 candidate pool short: {len(candidates)} < 5"
+# 不足目标如实记录覆盖/剔除/缺口；真实空池允许 skipped，不绕否决、不凑数
+# 研究扩池不产生开仓权限；后续R6完整性和D1逐票门禁保持不变
 ```
 
 **消费契约**:
@@ -380,7 +381,7 @@
 - `R2_main_sectors.json` 缺失 `all_scored_boards_top10` 字段 → 视为 R2 schema 降级,本次跳过扩池,记录 `r2_schema_missing_top10=true` 到 R5 JSON 顶层,供 E1 复盘统计
 
 **验收**:
-- 盘后脚本 `tests/check_r5_candidate_pool.py` 必须通过(本 skill 在 §Rules 增加红线 11: R5 候选池 < 5 → `status: partial`)
+- 验收按实际研究候选覆盖与缺口，不将未凑够5只本身判画像失败；真实空池须有 R2 证据，非空候选仍核数量/降级标记。不得为通过数量检查解除否决；对应检查器需先确认是否存在及与当前 contract_checks 一致，未验不得自报通过
 
 ---
 
--- /Users/chenyang/Downloads/demo/沧海巨浪/skills/analyze_style_v1/SKILL.md
+++ /Users/chenyang/Downloads/demo/沧海巨浪/skills/analyze_style_v1/SKILL.md
@@ -99,7 +99,7 @@
    - 若 `data/research/YYYYMMDD/emotion_cycle.json` 已存在（由 `compute_cycle_metrics.py` 预计算），直接消费
 2. 把阶段写入 R1 产出新字段：
    - `emotion_cycle_phase`: `low_test` / `main_up` / `high_chop` / `main_down`
-   - `emotion_cycle_action`: 该阶段该做什么（主升猛干龙头 / 震荡控仓做补涨 / 主跌空仓）
+   - `emotion_cycle_action`: 仅说明市场温度、原仓位约束与待验证风险；不得写固定“阶段→打法/通道”或要求停止研究。通道由 D1 按当日赚钱效应与资金确认动态选择，禁新仓不等于清研究观察
 3. **联动规则**（与 3.1 风格分类互相校验）：
    - 风格=崩溃退潮型 且 阶段=主跌 → 双确认，仓位下限压到最低
    - 风格=连板情绪型 但 阶段=高位震荡（炸板率>25% 未反映在风格表里）→ **以情绪周期阶段为准**，下调仓位上限（风格表只看涨停/高度，会漏掉炸板率>40%的分歧）
--- /Users/chenyang/Downloads/demo/沧海巨浪/skills/main_decision_v1/SKILL.md
+++ /Users/chenyang/Downloads/demo/沧海巨浪/skills/main_decision_v1/SKILL.md
@@ -123,16 +123,16 @@
 2.5. **情绪周期四阶段定位（硬接入 · v1.7 · 2026-09-04 新增 · `@emotion_cycle_v1`）**：
    - 读 `data/research/YYYYMMDD/emotion_cycle.json`（由 `compute_cycle_metrics.py` 预计算）或调 `@emotion_cycle_v1` 现场算
    - 四阶段：`low_test` 低位试错 / `main_up` 主升 / `high_chop` 高位震荡 / `main_down` 主跌
-   - **阶段 → 该做什么（硬规则，写入 plan）**：
-
-| 阶段 | 该做什么 | execution_pool | 仓位 |
-|------|---------|----------------|------|
-| `main_up` 主升 | 猛干龙头，任何位置进都对 | 龙头/龙二满配 | 按 R1 cap 上限执行 |
-| `high_chop` 高位震荡 | 落袋为安，控仓；只做龙头分歧低吸或低位补涨 | 减半，只留最强主线 | cap × 0.75 |
-| `main_down` 主跌 | 空仓/切换新题材一日游；连跌2天尾盘试错 | **≤2 只**或空 | cap × 0.4，或 mode=dry_run 且 no_trade=true |
-| `low_test` 低位试错 | 打首板/低位补涨，轻仓试错 | 小仓试错 | cap × 0.5 |
-
-   - **优先级**: 本四阶段 > Step 0.5 的 7 阶段（7 阶段偏描述性，四阶段直接给操作）。两者冲突时以四阶段为准
+   - **阶段只定温度，不预设打法**：按真实赚钱效应、龙头身位与资金确认动态选择通道；不因阶段自动停止研究或自动授权交易。以下保留原仓位约束数字，仅列温度，不构成开仓许可：
+
+| 阶段 | 温度 / 研究要求 | execution_pool | 原仓位约束（不因本提案上调） |
+|------|------------------|----------------|---------------------------|
+| `main_up` 主升 | 研究当前最强核心，不能认为任何位置都可买 | 逐票通过门禁才可入 | 按 R1 cap 上限 |
+| `high_chop` 高位震荡 | 核对分歧与承接，不静态锁定打法 | 保留原减量约束 | cap × 0.75 |
+| `main_down` 主跌 | 继续研究新题材首板/二板，不能接高位老龙或抄底 | 原 ≤2 只或空；禁新时空 | cap × 0.4；禁新决定另写 no_trade |
+| `low_test` 低位试错 | 准备右侧确认剧本，不凭阶段给代码授权 | 小仓仍须独立资格 | cap × 0.5 |
+
+   - **优先级**：阶段用于温度与已有仓位约束，不覆盖全局禁令、R6、逐票资格或用户授权；不把描述性的阶段标签当通道白名单。
    - 写入 `meta.emotion_cycle_phase` + `meta.emotion_cycle_action`
 
 3. **跨资产→板块映射**（`@大宗商品分析` commodity→sector）：
@@ -252,7 +252,7 @@
    - 「基本面亏损 / 资金面弱 / 估值高」→ 只压仓位（如 ≤3%），**禁止**直接把主线龙头降为「只观察不参与」
    - 唯一硬例外：R6 `hard_reject`（模式六霸榜出货等）仍不可覆盖
 2. **主线龙一/龙二必须至少进 execution_pool（轻仓）或 watch_pool 最高观察级**：
-   - 主线 `stage=early` 且涨停潮启动 → 龙一给最小仓位（≥3%）参与，龙二观察
+   - 主线 `stage=early` 且涨停潮启动 → 优先完成龙一研究；仅在当日允许新仓且逐票通过全部门禁后由 D1 定仓，无保底参与额度；否则只观察并保留禁令
    - 龙一一字锁仓买不进 → 顺势切龙二/候补的参与机会，**而不是放弃整条线**
 3. 本原则写入 `meta.mainline_participation_applied`，供 E1 复盘核对是否被执行
 
@@ -271,7 +271,7 @@
    - 每板块仅龙一、龙二可进 execution_pool
    - 龙一：板块涨停家数 top1 **或** 主力 5 日累计 top1 **或** 连板高度 top1
    - 龙二：板块综合评分 top2
-   - 龙三及以下 → watch_pool（除非龙一被 R6 hard_reject，龙二递补）
+   - 龙三及以下 → watch_pool；龙一被 R6 hard_reject 后不得为数量或低位偏好启用龙二/杂毛递补，保留真实否决与空池理由
    - **杂毛过滤**（满足 ≥2 项即剔除 execution）：主力排名 top3 外、龙虎榜 30 日无机构席位、连板高度 < 龙头-2、换手率 < 板块 median 50%
 5. **风险等级**（R5 `alpha_grade` / `risk_grade` × position_cap）：
    - `position_cap ≤ 0.4`：仅 `alpha_grade=A` 且 `risk_grade≤B`
@@ -293,9 +293,9 @@
 这与用户三通道体系（打板/强势低吸/跟单）直接冲突：打板是其数据中 64% 胜率的正 α 通道，
 却在前瞻层被结构性排除。
 
-**规则**：入口通道由 R1 风格 regime 决定（`d1_algorithm.step_regime_channels`）：
-
-| R1 style | 可用通道 | ignition |
+**规则**：入口通道由当日赚钱效应、龙头结构和资金确认动态选择，不由 R1 阶段或风格机械开关。下表仅保留历史规则实现映射供核对，不再作为 LLM 主路径资格白名单；规则版 `d1_algorithm.step_regime_channels` 尚未在本提案改动，不能据此宣称实现已统一。所有通道仍受当日禁令、预算、买点与授权约束：
+
+| R1 style（历史映射，非许可） | 历史通道示例 | 历史 ignition |
 |---|---|---|
 | 连板情绪型 / 主升 | `trend_pullback_buy` + `leader_breakout` | ✅ |
 | 主线扩散型 | `trend_pullback_buy` + `leader_breakout` | ❌ |
@@ -411,7 +411,7 @@
 4. 昨日 `observation_tracking` 中未成交观察票 + 长期主线未启动票（`sector_off_line`）
 
 每只须含合法 `role`（`watch` / `watch_elastic`）与 `plan_status`（`watch_pool_only` / `watch_pool_wait_for_entry`）。
-**观察池宁多勿漏**：上限 40 只，用于盘中扫描与次日回看，不进 execution、不参与自动交易。
+**观察池宁多勿漏但不凑数**：原数量范围是覆盖目标，不是硬配额；上限 40 只不变。用于盘中扫描与次日回看，不进 execution、不参与自动交易；有效对象不足时列覆盖、淘汰与数据缺口，允许为空。禁交易时观察及重评义务仍保留。
 
 ### Step 4.5 — 买点推演 + T+1 博弈（2026-09-04 用户方法论 · 硬要求）
 
@@ -898,7 +898,7 @@
 | 2 | **禁止 override** R6 `hard_reject` |
 | 3 | `execution_pool` ≤ 5（`max_positions` 铁律） |
 | 4 | 单票 `max_position_pct` ≤ 0.15；单板块 ≤ 0.40；总仓 ≤ position_cap |
-| 5 | `watch_pool` 15–25 只（低于 15 观察对照失效） |
+| 5 | 观察数量按 Step 4 的真实覆盖记录，原范围是目标不是最低资格；不足或空池必须有覆盖/淘汰/缺口证据，不为凑数绕否决 |
 | 6 | 每只 execution 须有完整 `entry_rules` + `exit_rules`（至少 1 条 `stop_loss_break`） |
 | 7 | R6 `strong_suggest` 覆盖须写 `meta.r6_devil_advocate.strong_suggests_overridden[].reason` |
 | 8 | `mode` 默认 `dry_run`；用户显式 flip 后才改 `live` |
@@ -1208,7 +1208,7 @@
 
 **硬约束**:
 - `no_trade_conditions` 必须存在(即使全部 `active: false`)
-- 任一 `active: true` → D1 输出 `mode: "dry_run"`、独立 `no_trade: true`、`autonomous_trading_enabled: false`、`requires_user_confirmation: true`、`execution_pool: []`、`watch_pool: []`（本行暂保留原清观察限制；是否保留研究观察由 B 包单独签核）。`mode` 只表示执行环境，不新增 `no_trade` 枚举；不得删除禁令来通过 schema。
+- 任一 `active: true` → D1 输出 `mode: "dry_run"`、独立 `no_trade: true`、`autonomous_trading_enabled: false`、`requires_user_confirmation: true`、`execution_pool: []`；不再因禁交易清空研究观察。有真实证据的对象留 `watch_pool`/`research_anchor_only`，逐票标仅研究、`auto_trade_enabled: false`、`entry_rules: []`，同时列全局禁令与待验证条件；无对象仍可空。`mode` 只表示执行环境，不新增 `no_trade` 枚举；不得删除禁令来通过 schema。P1/P2 不得凭观察身份或 promote 自动解禁，须由有权限 owner 独立重评全部原门禁。
 - plan.md **必须**在顶部展示"不交易条件清单 + 当前 active 项"(便于用户 review)
 
 **降级**:
--- /Users/chenyang/Downloads/demo/沧海巨浪/skills/short_line_thinking_v1/SKILL.md
+++ /Users/chenyang/Downloads/demo/沧海巨浪/skills/short_line_thinking_v1/SKILL.md
@@ -203,7 +203,7 @@
 agent 输出任何"低吸/埋伏/捡便宜/跌出机会"类建议前,必须过 3 问,任一不满足 = 不许给代码,改归类为"抄底"并按负 α 处理:
 
 1. 这只票今天/明天有没有涨停预期?它是不是主线总龙/补涨龙/低位前排?
-2. 当前情绪周期允许开仓吗?(退潮/主跌期:禁止一切低吸,空仓)
+2. 当前温度、当日禁令与逐票资格允许开仓吗？不按退潮/主跌标签静态禁用强势低吸；低吸≠抄底，须有强势延续、资金确认与涨停预期。禁新仓/零预算仍禁止开仓，只保留研究观察。
 3. 我推荐它的理由是"强势延续"还是"跌多了该反弹"?后者 = 均值回归幻觉,直接否。
 
 **特别警惕时点**:尾盘 14:00 后问"埋伏进去等明天有没有收益"——这是禁止清单 #9 `late_speculation` + #11 `overnight_bad_streak` 的组合形态,默认回答是"不买",除非次日有已核实的硬事件催化 + 竞价确认路径已写明。--- /Users/chenyang/Downloads/demo/沧海巨浪/skills/trade_discipline_v1/SKILL.md
+++ /Users/chenyang/Downloads/demo/沧海巨浪/skills/trade_discipline_v1/SKILL.md
@@ -69,7 +69,9 @@
 15. `cover_after_blast` — 炸板或买入失败后补仓（必须承认错误离场）
 16. `regulatory_confrontation` — 监管信号明确（"给区间"/点名/停牌）后仍博弈相关方向
 
-## 四、情绪周期强制切换表（每阶段允许/禁止）
+## 四、情绪周期温度参考（不作为固定打法/通道许可）
+
+阶段只定温度；下表打法为历史示例，不作为静态允许/禁止清单。实际通道由当日赚钱效应、身位与资金确认动态选择；本提案不改表内既有仓位数字或禁止清单，任何全局禁新仓、R6、逐票资格和授权仍优先，研究观察不因此停止。
 
 | 阶段 | 允许 | 禁止 | 仓位档 |
 |------|------|------|--------|
```

## 6. 北向一维缺失：准确原句与可选政策（没有选择、没有放行 diff）

### 6.1 本日事实与矛盾

当前 `data/research/20261023/R7_capital_flow.json` 生成于 `2026-10-23T06:29:07+08:00`，`status=partial`，`staleness_status=unavailable`，`confidence=0.0`；breakdown 保留 `raw_formula_confidence=0.2625`，但 `override="northbound_unavailable_requires_zero"`。`northbound.status=unavailable`、`net_flow_today=null`，理由是无可信净额语义，不是把净额测成0。主力、龙虎榜/游资、ETF 仍有内容（审计 RULE03/C01），不能称“四源全死”。不将 龙虎榜股通席位代理/持股快照/成交额 偷换成全市场净流入。

当前正式计划 `2026-10-23T06:51:36+08:00` 将 `R7_STALE` 激活，原描述：`R7 staleness_status=unavailable，可靠北向净额缺失，整体资金资格未通过`。另外 MAIN_DOWN、RESEARCH_NOT_PRODUCTION_READY、NO_ELIGIBLE_CANDIDATES 也 active；**即使将来只改北向政策，也不能据此解除其他禁令。**

### `/Users/chenyang/Downloads/demo/沧海巨浪/skills/analyze_capital_flow_v1/SKILL.md` · L223–L273

原 SHA256：`e82f07cc276651cacaac808faa786ac37a76dc7394b0c94f3b530c378e76ec77`。本节只读引用，未拟改。

```text
223|
224|## v1.2 新增 · R7 stale 数据贴今天标签问题修复（P0-2 修复）
225|
226|**问题根因**: 2026-08-06 复盘发现 `R7_capital_flow.json` 的 `generated_at = "2026-08-06T07:30:00+08:00"` 但内部 `resolved_trade_date = "20260805"`(T-1 实际交易日),文件名也是 `R7_capital_flow.json`(不带日期)被重生成覆盖。三处时间字段不一致,导致下游 D1/R6 误以为 R7 是 T+0 fresh 数据,实际是 stale 24h 旧数据。
227|
228|**v1.2 staleness 契约**(硬约束,新增到 §输出契约 之前):
229|
230|```yaml
231|# R7 落盘前必填的三时间字段
232|generated_at: "ISO8601+08:00"        # 本次落盘时刻(机器时)
233|resolved_trade_date: "YYYYMMDD"      # 实际数据归属交易日(可能 = T-1)
234|staleness_status: ok | partial | stale | unavailable
235|stale_threshold_hours: 24             # 硬阈值
236|unavailable_reason: ""                # 当 status=unavailable 时必填
237|```
238|
239|**staleness 计算与状态机**(由 R7 LLM 在写盘前自动算):
240|
241|```
242|# 主口径: 交易日缺口(trading_gap)—— 小时数会误伤周一/长假(64h 的周五数据其实是最新 T-1)
243|trading_gap = trade_date 与 resolved_trade_date 之间的「交易日」间隔
244|             (0 = T-1 或当日 → 数据就是最新可得; 1 = T-2 缺一档; 2 = T-3 缺两档; ...)
245|# 用 tushare trade_cal(或 manifest 可见的最早交易日)数交易日, 不算自然日/周末
246|
247|if trading_gap <= 0:     status = "ok"        # 周一盘前用上周五数据 = 正常, 绝非 stale
248|elif trading_gap == 1:   status = "partial"   # T-2, 真降级一档
249|elif trading_gap == 2:   status = "stale"     # T-3, 衰减 0.7
250|else:                    status = "unavailable"
251|  → unavailable_reason = "northbound_data_lag_{gap}days"
252|  → 整体 confidence = 0 (消费者应走降级)
253|
254|# 副口径(仅写 note, 不进状态机): hours_since_data = (generated_at - resolved_trade_date 当日 15:00) 小时
255|# 周一盘前它天然是 ~64h(周末), 不代表数据旧 —— 不要用小时数直接定 status
256|```
257|
258|**硬约束(新增强制项)**:
259|1. 当 `generated_at.date < trade_date + 06:00` 视为**严重错位**,直接 `status=unavailable`,写 `unavailable_reason="generated_at_before_trade_date_06am"`,**不得**让下游(D1/R6)按 ok 消费
260|2. 文件名必须带 trade_date 后缀:`R7_capital_flow_{trade_date}.json`(老路径 `R7_capital_flow.json` 保留作 soft link 指向当日)
261|3. `resolved_trade_date ∈ {trade_date, T-1}` 为**正常**(尤其周一 T-1=上周五);仅当 resolved 早于 T-1 才写 `cross_date_mismatch=true`。**禁止**把正常的 T-1 误判为 mismatch
262|4. `staleness_status` 字段**不得为 null**,**不得省略**
263|
264|**消费契约**(供 D1 / R6 消费):
265|- D1 在 §Step 0 读 R7 时,先看 `staleness_status`:
266|  - `ok` → 正常消费
267|  - `partial` → 消费但 `risk_limits.position_cap_pct` 衰减 ×0.95
268|  - `stale` → 消费但 `position_cap_pct` 衰减 ×0.85,且在 `meta.position_cap_source` 追加 `r7_stale_override`
269|  - `unavailable` → 跳过 R7 资金维度,`risk_limits.target_total_position_pct` 走 R1 默认 0.50
270|
271|**降级**:
272|- 北向数据完全拉空(Tushare `moneyflow_hsgt` 错)→ `staleness_status=unavailable`,但仍写盘(填空数组),让 E1 复盘能感知
273|- 硬约束 1 触发时,`degraded=true` 必须写入 JSON 顶层
```

### `/Users/chenyang/Downloads/demo/沧海巨浪/skills/main_decision_v1/SKILL.md` · L1183–L1187

原 SHA256：`0f0af85c59761520b8616678a53b001c9851fd0737004a719f78ce240c2baf8d`。本节只读引用，未拟改。

```text
1183|    {
1184|      "code": "R7_STALE",
1185|      "description": "R7 staleness_status = unavailable → 不开仓(资金维度失效)",
1186|      "active": true                       // 命中时, plan.md 顶部必须显式标 "⚠️ R7 数据失效,今日 no_trade"
1187|    },
```

### `/Users/chenyang/Downloads/demo/沧海巨浪/skills/main_decision_v1/SKILL.md` · L1207–L1215

原 SHA256：`0f0af85c59761520b8616678a53b001c9851fd0737004a719f78ce240c2baf8d`。本节只读引用，未拟改。

```text
1207|**硬约束**:
1208|- `no_trade_conditions` 必须存在(即使全部 `active: false`)
1209|- 任一 `active: true` → D1 输出 `mode: "no_trade"`,`autonomous_trading_enabled: false`,`execution_pool: []`,`watch_pool: []`(全空)
1210|- plan.md **必须**在顶部展示"不交易条件清单 + 当前 active 项"(便于用户 review)
1211|
1212|**降级**:
1213|- R1 缺 → `R1_FAIL` 自动 `active: true`
1214|- R7 缺 → `R7_STALE` 自动 `active: true`
1215|- 全部不交易条件自动激活,plan 报 `no_trade_mode` 状态
```

### `/Users/chenyang/Downloads/demo/沧海巨浪/docs/agents/R7-资金面Agent.md` · L129–L147

原 SHA256：`438bcb7e15ca1d12373b19d81a161d801347635ad3276f1c861c939c9cf6b63f`。本节只读引用，未拟改。

```text
129|## 6. 降级路径
130|
131|| 数据源死了 | 应对 |
132||-----------|------|
133|| DataPro 死 | 降级为 Tushare + XTick，`data_health: degraded` |
134|| XTick 死 | 07:30 仍可用 Tushare+DataPro；11:35 增量整批跳过 |
135|| Tushare 死 | 仅 DataPro 口径，标注 severity |
136|| 07:30 全失败 | 出 skeleton JSON，`confidence: 0`，不阻塞 R2（R2 自有 MCP） |
137|| 11:35 增量失败 | 跳过增量，P2 走无 amendment 保守路径 |
138|
139|---
140|
141|## 7. 红线
142|
143|1. ❌ 不输出买卖时点（D1 / execute 处理）
144|2. ❌ 不硬否决个股（交给 R6 模式六）
145|3. ❌ 11:35 批次不重算 07:30 全量历史（避免 P2 超时）
146|4. ✅ 每条 sector/stock 资金结论须标注数据源与时间窗口
147|5. ✅ `confidence` 与 manifest severity 联动：global_severity≥2 时 confidence 上限 0.5
```

### `/Users/chenyang/Downloads/demo/沧海巨浪/src/research/contract_checks.py` · L122–L158

原 SHA256：`2c64dbc88c07506e28bc4e8f6be798d311a29ae38fa680b9685c9e68136e99f7`。本节只读引用，未拟改。

```text
122|def check_r7_staleness(r7_data: dict[str, Any], trade_date: str) -> list[str]:
123|    """P0-2: staleness 状态机 + resolved_trade_date + unavailable_reason。"""
124|    errors: list[str] = []
125|
126|    status = r7_data.get("staleness_status")
127|    valid = {"ok", "partial", "stale", "unavailable"}
128|
129|    if status is None:
130|        errors.append("staleness_status 字段缺失")
131|    elif status not in valid:
132|        errors.append(f"staleness_status 非法值: {status}")
133|
134|    resolved = r7_data.get("resolved_trade_date")
135|    if not resolved:
136|        errors.append("resolved_trade_date 字段缺失")
137|
138|    gen_at_str = r7_data.get("generated_at", "")
139|    if gen_at_str and status is not None:
140|        gen_at = _parse_gen_at(gen_at_str)
141|        if gen_at:
142|            try:
143|                td = datetime.strptime(trade_date, "%Y%m%d")
144|                td_06am = td.replace(hour=6, minute=0)
145|                if gen_at < td_06am and status != "unavailable":
146|                    errors.append(
147|                        f"generated_at({gen_at_str}) < trade_date 06:00 "
148|                        f"但 staleness_status={status}(应为 unavailable)"
149|                    )
150|            except ValueError:
151|                pass
152|
153|    if status == "unavailable":
154|        reason = r7_data.get("unavailable_reason", "")
155|        if not reason:
156|            errors.append("status=unavailable 但 unavailable_reason 为空")
157|
158|    return errors
```

### `/Users/chenyang/Downloads/demo/沧海巨浪/tests/checks/check_r7_staleness.py` · L67–L108

原 SHA256：`327b622c6b668658b01b969cbd0053e54cef1fd8b06b722e99c9744403f1621b`。本节只读引用，未拟改。

```text
67|        failures.append(f"staleness_status 非法值: {status}")
68|        print(f"  ❌ staleness_status: {status} (不在 {VALID_STATUSES})")
69|    else:
70|        print(f"  ✅ staleness_status: {status}")
71|
72|    # 规则 4: resolved_trade_date 存在
73|    resolved = data.get("resolved_trade_date")
74|    if resolved:
75|        print(f"  ✅ resolved_trade_date: {resolved}")
76|    else:
77|        failures.append("resolved_trade_date 字段缺失")
78|        print(f"  ❌ resolved_trade_date: 缺失")
79|
80|    # 规则 1: generated_at 检查
81|    gen_at_str = data.get("generated_at", "")
82|    if not gen_at_str:
83|        failures.append("generated_at 字段缺失")
84|        print(f"  ❌ generated_at: 缺失")
85|    else:
86|        try:
87|            gen_at = parse_gen_at(gen_at_str)
88|            # trade_date 当日 06:00
89|            td_date = datetime.strptime(trade_date, "%Y%m%d")
90|            td_06am = td_date.replace(hour=6, minute=0)
91|            if gen_at < td_06am:
92|                # 严重错位 → status 应为 unavailable
93|                if status != "unavailable":
94|                    failures.append(
95|                        f"generated_at({gen_at_str}) < trade_date 06:00 "
96|                        f"但 staleness_status={status}(应为 unavailable)"
97|                    )
98|                    print(f"  ❌ 生成时间早于 06:00 但 status 不是 unavailable")
99|                else:
100|                    print(f"  ⚠️  generated_at < 06:00, status=unavailable (合规降级)")
101|            else:
102|                print(f"  ✅ generated_at: {gen_at_str} (>= 06:00)")
103|        except ValueError as e:
104|            failures.append(f"generated_at 解析失败: {e}")
105|            print(f"  ❌ generated_at 解析失败: {e}")
106|
107|    # 规则 3: unavailable 时必须有 reason
108|    if status == "unavailable":
```

### 6.2 三种可选政策与准确影响范围

| 选项 | 研究事实/整体状态 | 最终新仓门禁 | 需要用户定义 | 准确涉及源文件/原句 |
|---|---|---|---|---|
| NB-1 严格四维必要条件 | 保留缺一维整体 unavailable；北向原值仍 null。若整体置信度因门禁覆盖成0，必须标“政策覆盖为零”，不能写全部测量无效 | 北向缺可信净额继续禁新，不停止研究 | 是否确认北向就是不可替代必要条件；何种同口径、日期与单位证据能恢复；不得用代理冒充 | R7 skill L247–252/L272 保留严格含义；**必须改其 L269 “走R1默认0.50”与 D1 禁新冲突的消费者句**；D1 skill L1184–1186/L1214 保留禁新；R7 spec §6需说清单维缺失不等于全源死；contract_checks/check_r7_staleness对应状态理由验证须同步 |
| NB-2 分维事实 + 独立保守资格 | 北向单维 unavailable；其余维度各保留时间、覆盖、信心，整体研究可 partial；整体置信度另定、未评估为null，不再一律被北向清0 | **仍要求北向齐全才允许新仓**，显式独立“不满足必要资金条件”的禁令；不能因整体partial而解除 | confidence汇总公式/分母、研究状态与交易资格分字段，以及原R7_STALE如何指向明确必要条件 | **替换** R7 skill L250–252/L272 的单维→整体升级与零覆盖，L265–269消费整段；**同步改** D1 L1184–1186/L1214避免只测整体 unavailable；R7 spec §6、contract_checks/check_r7_staleness新增维度与资格校验。原D1模式和清观察句只走A/B，不借本选项放行 |
| NB-3 分维降级 + 有条件交易评估 | 同 NB-2，缺北向不自动归整体失效；不假造缺失维分数 | 仅在用户确认的必要剩余维、逐票资金/价格确认及完整R6满足后，D1才可重新评估；不是自动开放 | 哪些维是必要、哪些可选，冲突如何处理，覆盖/时效门槛、置信汇总、预算是否/如何收紧。所有数值与例外均待签 | 同NB-2全部文件；D1 L1184–1186/L1214须明确何时激活禁令，R7 L267–269的0.95/0.85/默认0.50不能机械沿用或默认上抬；schema/校验/执行消费者若新增字段须完整落地测试，未完成前保留原限制 |

本节是政策菜单，不是补丁。北向 skill 没有出现在 A/B 拟改文件中；不能把 NB-2/NB-3 的名字当已选政策，也不默认采用原 R7 “0.50 回退”。`contract_checks.py` 目前只检查顶层状态枚举、日期与 unavailable_reason，**没有实现“北向缺失自动整体0置信”的代码公式**；关键升级来自 LLM skill/本日产物，不能只改校验器就声称解决门禁。

## 7. 06:10 / 07:30：只列决定，不改 cron

- 当前真实 job：`/Users/chenyang/.hermes/cron/jobs.json` 中 `24f4119fab82`，name=`canghai-research · 每日 R1-R7+D1 全量流水线 (06:10)`，`enabled=true`，schedule=`10 6 * * 1-5`，script=`canghai_research_daily.sh`。
- 桥接 `/Users/chenyang/.hermes/scripts/canghai_research_daily.sh` L3/L6 → 仓库 `scripts/research/run_research_shell_cron_wrapper.sh` → research shell；不是凭文件名猜入口。
- 当前业务状态 `data/health/research_pipeline_20261023.json.started_at=2026-10-23T06:10:47.340363+08:00`、`status=completed`；这是交付，不是承诺的生产窗口复核已完成。
- 原研究 SOUL L5：`盘前 07:30-07:55 完成 R1-R7 分析`；L74：`07:55 前所有 R* 必须完成`。R1 skill L15 仍写 `07:30（与 R3、R4、R7 并行）`；R7 skill L15 仍写 `07:30 全量`。shell L13–18仍保留旧时刻注释，与实际依赖批次也有差别。
- 必须由用户选择：①06:10起跑即承担正式生产就绪，还是②06:10为提前研究、07:30另有正式刷新，还是③另定可实现窗口。**此处不选任何方案，不建议仅改时间文字。**
- 无论选哪项都需点名：研究批次刷新 owner/触发器、依赖等待与完成截止；计划端 D1 重评 owner；安全网仅消费新批次、不代跑研究。未签 trigger 前，“保留重评义务”不等于已有定时重评任务，不能宣称明天会自动恢复。

### `/Users/chenyang/Downloads/demo/沧海巨浪/scripts/research/run_research_shell.sh` · L13–L18

原 SHA256：`dcab3c1d0cc3291c361cbcfca9ac6d2dc9e0da9563b47bfe2aadaee2cb9ac4e6`。本节只读引用，未拟改。

```text
13|# 时序：
14|#   07:15 fetch (前置，独立 skill)
15|#   07:30 R1 / R3 / R4 / R7 并行（& + wait）
16|#   07:45 R2 / R5 并行
17|#   07:55 R6（依赖 R1-R5/R7）
18|#   08:00 D1（依赖 R1-R7）
```

### `/Users/chenyang/.hermes/profiles/canghai-research/SOUL.md` · L3–L5

原 SHA256：`9dd5bf534052fa41b2762fa999899a87d3f58b65afe76234b10e4d3fa185fb31`。本节只读引用，未拟改。

```text
3|## Purpose
4|
5|盘前 07:30-07:55 完成 R1-R7 分析,输出 `research_summary.json` 供 D1(canghai-plan)消费。主控本身不做分析,只做 delegation 调度 + artifact 路径收集(见 `research_orchestrator_v1`)。11:35 R7 额外做一次盘中增量。
```

### `/Users/chenyang/.hermes/profiles/canghai-research/SOUL.md` · L69–L75

原 SHA256：`9dd5bf534052fa41b2762fa999899a87d3f58b65afe76234b10e4d3fa185fb31`。本节只读引用，未拟改。

```text
69|## Constraints
70|
71|- **主控禁止直接调用 MCP**（必须通过 delegation），避免主控 context 被数据污染
72|- **主控禁止修改 `data/user_preferences.yaml` / `data/human_thesis/`**（只读，传递给 sub-agent 作为 context）
73|- research 输出必须 pydantic schema 校验通过才写盘
74|- 07:55 前所有 R* 必须完成，超时的 R* 走 fallback（基于昨日 artifact）
75|- R6 反证是唯一硬否决权来源，主控不得干预或过滤 R6 的 `hard_reject` 结论
```

### `/Users/chenyang/Downloads/demo/沧海巨浪/skills/analyze_style_v1/SKILL.md` · L13–L17

原 SHA256：`6097bb83402d836101de3348446129d71e6d3ff337b20dc6b9304455e07c6311`。本节只读引用，未拟改。

```text
13|# analyze_style_v1 · R1 风格 Agent
14|
15|**跑动时点**: 07:30（与 R3、R4、R7 并行）  
16|**权威规格**: `docs/agents/R1-风格Agent.md`  
17|**产出路径**: `data/research/YYYYMMDD/R1_style.json`
```

### `/Users/chenyang/Downloads/demo/沧海巨浪/skills/analyze_capital_flow_v1/SKILL.md` · L13–L17

原 SHA256：`e82f07cc276651cacaac808faa786ac37a76dc7394b0c94f3b530c378e76ec77`。本节只读引用，未拟改。

```text
13|# analyze_capital_flow_v1 · R7 资金面 Agent
14|
15|**跑动时点**: 07:30 全量（与 R1/R3/R4 并行）· 11:35 盘中增量（P2 阶段）  
16|**权威规格**: `docs/agents/R7-资金面Agent.md`  
17|**产出路径**: `data/research/YYYYMMDD/R7_capital_flow.json` · 可选 `chzl_kg/投研交易/资金面/YYYYMMDD.md`
```

## 8. RR=1 / 1.8 / 2：当前完整决策链出处，数值不拟改

本节“完整”限定为本次盘前研究→D1→价位引擎的现行规则/实现链，不把全历史报告中的示例数字当政策，也不声称已穷尽仓库每个历史归档。三套口径确有不同角色：1是 risk_reward 试仓分支最低线；2既是 research身份的资格底线又是仓位分档；1.8是价位引擎默认门槛。另有止盈目标2R，**它不是门槛2的同一概念**。

### `/Users/chenyang/Downloads/demo/沧海巨浪/skills/main_decision_v1/SKILL.md` · L384–L388

原 SHA256：`0f0af85c59761520b8616678a53b001c9851fd0737004a719f78ce240c2baf8d`。本节只读引用，未拟改。

```text
384|**关2 · 盈亏比判断**（`@risk_reward` · `src/plan/risk_reward.py`）：
385|- 输入：买点（`buy_price`）+ 止盈（`take_price`）+ 止损（`stop_price`）+ 情绪阶段 + 是否核心
386|- 输出 `risk_reward_ratio` + `position_suggestion_pct` + `grade_check`
387|- **硬规则**：`risk_reward_ratio < 1` → 拒绝开仓（纪律铁律6: 盈亏比优先于胜率）
388|- 仓位按 `position_suggestion_pct` 写（主升核心可 15%，主跌只试仓）
```

### `/Users/chenyang/Downloads/demo/沧海巨浪/skills/trade_discipline_v1/SKILL.md` · L29–L33

原 SHA256：`076853d910830a033ed05f94830c63debbeb4dea2f972a34094113e4e35e6edf`。本节只读引用，未拟改。

```text
29|| 3 | 周期不对就减维 | `discipline.r3_cycle_reduce` | 退潮→空仓/极小试仓 |
30|| 4 | 模式外的钱永远不赚 | `discipline.r4_style_only` | 模式外拉黑 |
31|| 5 | 进出理由必须一致 | `discipline.r5_reason_consistency` | 逻辑死→切 |
32|| 6 | 盈亏比优先于胜率 | `discipline.r6_rr_first` | RR<1 拒开（risk_reward.py） |
33|| 7 | 合力来自全市场 | `discipline.r7_market_consensus` | 逆势抱团降级（core_judge） |
```

### `/Users/chenyang/.hermes/profiles/canghai-plan/SOUL.md` · L37–L42

原 SHA256：`5c6c6c28e72a7b1970a852b3d16f2b033b06d5c0bc10c955cc16bb51ae13e3a2`。本节只读引用，未拟改。

```text
37|3. **每只 execution 票 → Step 3.6 四闸门**(2026-09-04 新):
38|   - 关1 核心判定(`@core_judge_v1`) → 共振/逆势抱团 → leader/core/laggard/watch 四档
39|   - 关2 盈亏比(`@risk_reward_v1`) → RR<1 拒绝,1-2 试仓,2-3 正常,≥3 主仓
40|   - 关3 纪律自检(`@trade_discipline_v1`) → 十条铁律 + 7 项开仓资格 + 14 项禁止
41|   - 关4 战术信号(`@tactical_signal_v1`) → 板型/弱转强/总龙开关/禁止清单
42|4. **每只票 entry_rules 必须含**:买点类型(打板/半路/低吸)+ 触发价 + 止损(距买入价-5~-10%)+ 止盈 + 失败标准
```

### `/Users/chenyang/Downloads/demo/沧海巨浪/src/plan/risk_reward.py` · L41–L48

原 SHA256：`0534c00839c6f4a1b600062e71c2825a2f46850cd4b9fefd0f8aa5db69696612`。本节只读引用，未拟改。

```text
41|# 盈亏比与仓位映射（按纪律文档: 盈亏比优先于胜率）
42|# RR >= 3  核心主仓(主升期可 20-33%)
43|# RR 2-3  正常仓(10-20%)
44|# RR 1-2  试错仓(5-10%)
45|# RR < 1  不做
46|MIN_RR_MAIN = 3.0
47|MIN_RR_NORMAL = 2.0
48|MIN_RR_TRIAL = 1.0
```

### `/Users/chenyang/Downloads/demo/沧海巨浪/src/plan/risk_reward.py` · L88–L116

原 SHA256：`0534c00839c6f4a1b600062e71c2825a2f46850cd4b9fefd0f8aa5db69696612`。本节只读引用，未拟改。

```text
88|    profit_pct = (take_price / buy_price - 1.0) * 100
89|    loss_pct = (1.0 - stop_price / buy_price) * 100
90|    rr = (take_price - buy_price) / (buy_price - stop_price)
91|    evidence.append(f"盈亏比 = ({take_price}-{buy_price})/({buy_price}-{stop_price}) = {rr:.2f}")
92|
93|    # ── 仓位判定 ──
94|    # 阶段系数
95|    phase_mult = {"main_up": 1.0, "high_chop": 0.75, "low_test": 0.5, "main_down": 0.3}.get(emotion_phase, 0.5)
96|    core_bonus = 1.0 if is_core else 0.5
97|
98|    if rr >= MIN_RR_MAIN:
99|        base = 0.15
100|        tier = "core_main"
101|        evidence.append(f"盈亏比 {rr:.2f} ≥ 3 → 核心主仓")
102|    elif rr >= MIN_RR_NORMAL:
103|        base = 0.10
104|        tier = "core"
105|        evidence.append(f"盈亏比 {rr:.2f} ≥ 2 → 正常仓")
106|    elif rr >= MIN_RR_TRIAL:
107|        base = 0.05
108|        tier = "trial"
109|        evidence.append(f"盈亏比 {rr:.2f} ≥ 1 → 仅试错仓")
110|    else:
111|        return RiskRewardResult(
112|            trade_date, ts_code, name, buy_price, take_price, stop_price,
113|            round(rr, 2), round(profit_pct, 1), round(loss_pct, 1),
114|            0.0, "none", "拒绝",
115|            [f"盈亏比 {rr:.2f} < 1 → 风险大于收益，拒绝开仓"],
116|            datetime.now().astimezone().isoformat(timespec="seconds"),
```

### `/Users/chenyang/.hermes/profiles/canghai-research/SOUL.md` · L53–L58

原 SHA256：`9dd5bf534052fa41b2762fa999899a87d3f58b65afe76234b10e4d3fa185fb31`。本节只读引用，未拟改。

```text
53|### 思考顺序铁律（每次 R* 输出前必走一遍，违反即重写）
54|1. **先认市场，再认个股** — 没有主线 / 风格 / 赚钱效应，不准进 R2/R5 选股环节。
55|2. **段位决定能做什么** — 主跌期降维（只输出观察，不输出候选），高位震荡压仓（中位股剔除）。
56|3. **只有龙头或低位，躲中位和杂毛** — R2 输出必须显式标 `rank ∈ {龙头, 龙二, 龙三}` + `rank=杂毛` 的剔除理由。
57|4. **盈亏比优先于胜率** — 候选票如果止损距 < 5% 或 RR < 2，必须降级 watch，不能进 execution。
58|5. **计划外不出手** — R4/R5 输出的"机会"必须回答：它是今日核心 / 主线补涨 / 计划内试错 中的哪一种。都不是，剔除。
```

### `/Users/chenyang/Downloads/demo/沧海巨浪/skills/main_decision_v1/SKILL.md` · L487–L510

原 SHA256：`0f0af85c59761520b8616678a53b001c9851fd0737004a719f78ce240c2baf8d`。本节只读引用，未拟改。

```text
487|```bash
488|.venv/bin/python scripts/plan/apply_price_levels.py --date YYYYMMDD --write-json
489|```
490|
491|引擎口径（可复算）:
492|- **买区**: ①均线回踩 `[min(MA50,牛线)×0.99, MA50×1.01]`,区间>7%收窄至基准±1.5% ②分歧回踩(强势票,现价距MA10>8%) `[昨收×0.92, 昨收×0.97]` ③突破/打板 `pivot=max(昨收,20日高)`,买区 `[pivot×0.995, pivot×(1+1.5~3%)]`
493|- **止损**: 以**买入价(买区上沿)**为基准, `买价×(1-5%主板/8%20cm)` 与 `熊线×0.99`、`MA10×0.99` 取最高,且必须低于买区下沿
494|- **止盈**: 2R = 买价 + 2×(买价−止损);若20日高点在 2R 之下且高于买价5% → 取前高
495|- **RR** < 1.8 → `RR_FAIL`,不参与
496|
497|**LLM 的义务**: 在引擎值上做事件/情绪/身位微调,但:
498|- 偏离引擎买区 >10% 必须在 `derivation_reason` 写明依据(如事件未落地后移买点)
499|- 不得无依据地凭空写数——引擎算不出的情况(一字板/无价格数据)必须显式说明
500|
501|**每只票(execution_pool/watch_pool/seesaw_plan 候选)必须带数字价位,禁止只写条件**:
502|- buy_zone(可买区间两个数字)、trigger_price、stop_loss、take_profit
503|- "高开≤3%+竞价放量+板块≥3家涨停"只能作为确认条件,不能替代买区——用户无法据此判断具体多少钱买
504|- 纯观察票若确无买区(如温度计/禁买锚),必须显式标注原因,不能留空字段让人误以为漏了
505|- 昨收缺失的票从 kb/research.db market_daily_bars 补,但买区必须在本步骤写好,不靠渲染阶段反推
506|
507|**价位推导交付物**: `chzl_kg/投研交易/盘前预案/YYYYMMDD_价位推导.md`——每票一行价位表 + 逐票公式(止损/买区/止盈/RR/技术位),用户要看到"为什么是这个价"。
508|
509|**引擎会自动做的事**(不用 LLM 手工处理):
510|- `RR<1.8` 的票自动写入 `no_trade_conditions.RR_FAIL` 并标记 active → 当日不可开仓
```

### `/Users/chenyang/Downloads/demo/沧海巨浪/src/plan/price_levels.py` · L86–L96

原 SHA256：`db4e876468c7e4805d0af020115cd4f860a5426eeb5f50eebc31058229156d27`。本节只读引用，未拟改。

```text
86|    trade_date: str,
87|    *,
88|    name: str = "",
89|    ref_close: float | None = None,
90|    channel: str = "trend_pullback_buy",
91|    ignition: bool = False,
92|    one_word: bool = False,
93|    rr_min: float = 1.8,
94|) -> dict[str, Any]:
95|    """返回一只票的完整价位推导 + 公式明细（每条都写清怎么算的）。"""
96|    tech = load_tech(ts_code, trade_date)
```

### `/Users/chenyang/Downloads/demo/沧海巨浪/src/plan/price_levels.py` · L175–L189

原 SHA256：`db4e876468c7e4805d0af020115cd4f860a5426eeb5f50eebc31058229156d27`。本节只读引用，未拟改。

```text
175|    stop_label, stop_loss = max(cands, key=lambda x: x[1])
176|    if stop_loss >= low_edge:  # 兜底: 止损必须低于买区下沿
177|        stop_label, stop_loss = cands[0]
178|    stop_loss = round(stop_loss, 2)
179|
180|    # ── 3) 止盈 & RR ──
181|    risk = round(buy_ref - stop_loss, 2)
182|    take_2r = round(buy_ref + 2 * risk, 2)
183|    take = take_2r
184|    take_formula = f"2R目标 = 买{buy_ref:.2f} + 2×(买入价-止损{risk:.2f}) = {take_2r:.2f}"
185|    if hi20 and buy_ref * 1.05 < float(hi20) < take_2r:
186|        take = round(float(hi20), 2)
187|        take_formula = (f"20日高点{float(hi20):.2f} 低于2R目标{take_2r:.2f} 且高于买价5%以上 "
188|                        f"→ 取前高作第一压力位")
189|    rr = round((take - buy_ref) / risk, 2) if risk > 0 else None
```

### `/Users/chenyang/Downloads/demo/沧海巨浪/src/plan/price_levels.py` · L213–L217

原 SHA256：`db4e876468c7e4805d0af020115cd4f860a5426eeb5f50eebc31058229156d27`。本节只读引用，未拟改。

```text
213|        "max_acceptable_ask": max_ask,
214|        "stop_loss": stop_loss,
215|        "take_profit": take,
216|        "risk_reward_ratio": rr,
217|        "rr_grade": ("pass" if rr and rr >= rr_min else "RR_FAIL"),
```

### `/Users/chenyang/Downloads/demo/沧海巨浪/scripts/plan/apply_price_levels.py` · L129–L142

原 SHA256：`c7420b7b609b306885351cc6353737599b893da90064538c6b679986e19d8170`。本节只读引用，未拟改。

```text
129|    # ── RR_FAIL 处置: 不参与开仓, 写进 no_trade_conditions ──
130|    rr_fail = [r for r in rows if r.get("ok") and r["rr_grade"] == "RR_FAIL"]
131|    if rr_fail:
132|        names = "、".join(f"{r['name']}(RR{r['risk_reward_ratio']})" for r in rr_fail)
133|        plan.setdefault("no_trade_conditions", [])
134|        code = "RR_FAIL"
135|        if not any(c.get("code") == code for c in plan["no_trade_conditions"]):
136|            plan["no_trade_conditions"].append({
137|                "code": code,
138|                "description": (f"引擎 RR<1.8 的票不参与开仓（盈亏比不达标）：{names}。"
139|                                f"要么等更好的买区（回撤更深）使 RR 回到 1.8 以上，要么放弃。"),
140|                "active": True,
141|                "source": "price_levels_engine",
142|            })
```

### RR 必须回答的待决问题

1. 最终开仓底线是哪一个？是否区分 trial 与正常仓，是否区分通道/持有周期？三个值不默取 min、max 或最新日期，也不凭“用户钦定”历史文字推定本轮裁决。
2. research身份“RR<2或止损距<5%降观察”是在研究层剔除还是只禁止交易？研究观察是否仍应保留？止损距条件与主板/20cm止损引擎如何一致？
3. 以实际触发价、买区上沿还是引擎参考价计算 RR？先四舍五入再比还是原始数值比？边界等于门槛时如何处理？不在本提案拟数。
4. `apply_price_levels.py` 把 rows 中 RR_FAIL 汇总成**顶层 active no_trade_conditions**，D1 skill又规定任一 active 禁新。是只禁止对应个股，还是任何观察/B计划票 RR_FAIL 都禁整池？须明确作用域与执行消费者；不能借“RR同步”偷偷把全局门禁改成局部。
5. 缺价/一字无有效买点是“无法评价”而非“RR=0”，应等待/不交易并披露原因，不能为了算出RR编价；选定政策后须让上述全部出处、引擎、渲染和校验测试一次一致。

本轮 A/B 的所有数字差异中没有 RR 阈值替换；对应 code/SOUL 只读原句保留。R6 hard_reject 权限范围也未在这里代裁决。

## 9. 与四组实现验收的对应与未纳入项

- A组：完整读取 `scratch/canghai_repair_A_result_20261023.md`。本提案同步其 BUG01/02/03/11 的交付-就绪-授权、有效零、null、单向交接建议；重评不补跑研究、不放宽“全R1–R7新批次”边界。A组指出的 Markdown null检查器，本提案给出最小候选guard并做纯函数合成验证，尚未应用。
- B组：读取 `scratch/canghai_repair_B_20261023/manifest.json`，并核对本提案相关的当前源码；当前 scratch 未找到该组独立 Markdown建议报告，不能声称全文读过不存在的报告。其翻多参考仓位不构成授权，研究观察回路属于本B包；广度/价格制度的实现授权不授权另改阈值。
- C组：完整读取 `scratch/canghai_repair_C_20261023/REPORT.md`。同步无价、真实0、partial、单位未核实留null、禁令优先、resolver拒绝不裸读。海外freshness/collection分层、KOSPI/FX unverified、ETF真实覆盖缺口仍如实保留；不扩provider、不给接口猜单位。
- D组：读取 `scratch/canghai_D_repair_acceptance_20261023.json`，其中为验收证据而非独立规则建议报告。本轮不追写公告或台账策略；“未调用/可选缺失/停用/不适用/真实失败”继续分开，不能因文案统一把真错误洗绿。
- 范围外未闭环：规则版 `src/research/r2_main_sectors.py` L42/L122 仍是50亿硬过滤；其主路径非LLM规则对照，**本提案没改该代码，不宣称全系统市值实现已统一**。归档filter skill L71 的300/688/920旧前缀与R2现行同权口径仍待单独确权；本B包仅删除替补例外，不用这次研究连续性签核夹带解禁。其他情绪/主线横切skill及旧记忆存在历史映射，按现行用户指令优先，若要全量清理须另列精确范围；主SOUL不改。
- R4 当前skill并没有“主跌停止消息研究”的原句；该行为来自身份层与当天产物，不编造不存在的R4删除行。B包研究身份层要求R2/R4研究继续，R5/R6按真实对象与完整性履责。

## 10. 本提案实际验证与应用后仍需验证

**已做（仅离线内存/只读）**：

- 每个拟改目标全文读取并核字节 SHA256；全部 hunk 用三行上下文从真实文本生成，内存逐行重放 A、再重放 B，拟议内容完全一致。
- 唯一拟议 Python 片段 `check_md_namespace.py` 经 AST解析，只执行两个纯函数定义与合成 FakeFile；`null`、`~`、`0.0`、`0.75`接受，`nonsense`、`false`仍拒绝。未导入生产模块、未跑全仓测试、未访问真实报告/数据库/网络/账户。
- 保留 R6 `_is_usable` 原 complete-only，不给它任何代码 hunk；北向文件、cron/配置和所有RR数值没有patch。
- 最终只读核对：源文件 hash 无漂移、主 SOUL hash 不变、原32暂存 index hash不变；两份交付由 write_file 写入scratch并确认。此处是提案完整性验证，不冒称生产规则已验收或已生效。

**签核并实际应用后另验（未执行）**：

1. 新研究/计划profile会话实际加载已签版本；禁止新仓场景仍输出真实研究观察，R5不因交易空池跳过；无对象依然skipped且不凑数。
2. R6输入partial仍不自动complete，零对象不变成“全票通过”；真实hard_reject留存、不凑票绕否决。
3. 未就绪安全版保留no_trade与重评责任；只有新研究批次满足当前血缘边界时由计划owner重评，完整合法LLM no_trade即使force也不覆盖。
4. 观察票不能被P1/P2或执行侧仅凭存在、报价或promote升级；null不能被统计成0或当通过；竞价partial保留有效事实、禁令先展示。
5. 北向/窗口/RR未签即原门禁继续；若用户另选政策，先生成新增精确diff再测，不在此次patch中补默认选项。

**尚未应用。没有生产补跑，也没有修写今天的报告来伪装已按时研究完成。**


## 11. 主控补充：报价年龄政策仍未设定

第二轮实现复核已消除隐含零秒门槛。仅校验同业务日、有效常规时段、非未来及采集过程元数据，另保存实际quote_age、`source_age_limit_seconds=null`、`freshness_status=age_limit_not_configured`。这不等于已验证满足某个新鲜度SLA，也不授予交易权限。若需设最大报价年龄或跨源跨度，必须另给精确阈值差异并签核；不能默设0秒、数秒或数分钟。本补充没有修改原两包补丁。
