# R6 局部补审交付 · 可验最小闭包 HANDOFF

## 结论 / 当前检查点

- **获批实现已应用，隔离专项在当前源码 87 passed / 0 failed / 0 error / 0 skipped，exit=0。** 分组：本项50、共同summary读取必要回归28、既有native usage必要回归9；身份列表来自原生JUnit，不与历史队列相加。
- 最终证据目录：`/Users/chenyang/.hermes/cache/scratch/r6-local-delivery-20261029-v3/`。`result.json`、`junit.xml`、`command.json`为短回执；`pytest.log`只是补充。最终测试结束：2026-10-29 14:29 CST。
- 39个Python进程已装收集前守卫；36个原生合成子进程全部有对应守卫回执，0未守卫、0本轮意外违规。另一次守卫自测的6个预期拒绝独立记录，**不混入0违规结论**。
- 原终态研究state的字节和mtime不改；六份复用主JSON及MD的字节/mtime、原生产run/attempt/回执与事实时点保持。仅新R6双件和新summary由普通程序发布；新summary被真实`consume_authorized_inputs`及`verify_saved_inputs`接受。
- 研究修订≠重新准入。未运行真实模型、行情、账户、业务DB或生产补跑；未调用D1/事件/scanner晋级；未动计划/原池/资格/entry/exit/零预算/执行确认。不能据本测试声称真实模型生产或自然采用。

## 改动清单 / 授权边界

仅修改以下生产源码：
1. `scripts/research/run_research_shell.sh`：全批顶层副作用前的`--r6-local-review`独立出口，不source全批shell。
2. `scripts/research/pipeline_state.py`：调用方指定版本/范围、冻结基线、单次原角色启动、受控暂存与接收、有限发布失败保护。
3. `scripts/research/pipeline_artifacts.py`：RFC6901引用与逐模式覆盖校验、局部合并。
4. `scripts/research/build_research_summary.py`：单项修订汇总、原回执复用与真实共同消费者接线；旧路径不放宽。
5. `scripts/research/native_usage.py`：同一个原生计量适配器增加revision接收位置，不修改旧终态业务state，不造第二计量模型。

新增测试：`tests/pipeline/test_r6_local_revision.py`。没有修改skill/docs/SOUL、其他角色/profile/model、价格引擎或D1源码，没有新生产module/service/数据库/平行data目录。两份获批契约的实际SHA仍等于expected，由主控单独应用。

## 交付链与信任边界

- 入口参数：`r6-local`需要`--date`、`--revision-id`、`--baseline-summary-sha256`、`--baseline-r6-sha256`、`--targets-json`；目标形如`{"000001.SZ":[1,2,6,7]}`。外层shell使用`--r6-local-review`后转交上述参数。默认仍是原`canghai-research`/`analyze_devil_advocate_v1`，没有`--model/--provider`覆盖。
- `--retry-delivery`只接已有同请求/同原文提案；不存在提案、提案/备份/源漂移、不同请求都拒绝，不能借retry发起模型。已完成项/空工作/越界对象在启动前拒绝。同revision成功重交付只读核验，无重复模型。
- 模型只输出局部JSON差分与本轮MD说明到stdout；不会被要求写正式文件或logs。普通程序在既有`data/logs/research_shell/{date}/r6-revision.{id}/`保存原件、原stdout/stderr、输入/argv、暂存双件、失败回执及接收state。
- 局部启动显式`-t file`保留file工具。**额外使用本机已有`/usr/bin/sandbox-exec`**，拒绝模型子进程写canonical research/plan/runtime/health/KG以及本次普通接收程序的基线/状态/暂存文件；父普通程序不在该子进程sandbox中。真实合成可执行子进程尝试写R6 JSON、MD、原health、本次state和原件，五次均被OS拒绝，随后正常stdout提案仍可交付。不是靠替身直接返回“保护成功”。没有该已测macOS启动器时失败关闭，不静默退成可写模式。
- 输入正文不塞进argv：只给原已绑定精确路径/版本、原R6版本与目标，由file读取。`launch.json`记录实际sandbox+Hermes argv及加载契约版本；合成可执行替身实际打开并核获批技能SHA及源SHA。真实Hermes技能解析/模型行为尚未运行，不能冒称已自然采用。
- 必要覆盖只读`mode_id + candidate_checks`：四模式都要逐票`completed`、非空实际引用、空missing；缺明细/未知不算完成。RFC6901路径须存在，null不认证完成，false/0按原类型保留。模型负责事实语义、对象关联、分支适用性和观察窗口；程序不按散文、空否决、全局布尔推逐票通过，不新增风险阈值。
- 合并只更新指定未完成单元，保留未涉及/已完成单元、原反面发现和全部硬拒绝；新发现仍附加。根级正式完成由整批四项覆盖计算。两票一完整一缺时false，全范围有据完整时true；两种合法正例都保持原计划与零预算不变。
- MD保持旧已交付全文字节前缀及尾部反面证据，仅附本轮说明与新JSON SHA；无第二模型重写全文，无计划renderer复用。先验证暂存双件，再由普通程序发布。
- 复用六份报告仍核原state中的`verify_binding`；只R6核新revision的原生交付回执。summary的生产run保留原基线run，修订marker另指向新revision，接受时点另记。原终态run不重启/不修改，未给旧六份盖新生产回执。旧summary配新R6立即拒收。
- 发布前/各步检查源及目标版本，共享health目录锁排除合作写者；普通I/O失败仅恢复仍匹配本次发布版本的原件和原mtime，保留提案。并发他人编辑不覆盖/不回滚，失败关闭。不是任意断电跨文件事务，也不承诺不合作写者在最后检查后的任意编辑不可发生。

## 红 → 当前验收证据

- 首轮原源码3红已保存`first-original-red.xml/.log`（入口不存在、无局部接收实现、全局标记不能替代逐票覆盖）。
- 又在批准包**精确原字节**隔离重放4红：`original-red-replay.xml/.log`；第四项实际调用原`_binding`证明旧六份不能直接换新run合法通过。此直接换标签在新实现中仍必须拒绝；新正例通过显式修订接收解决，不是放宽原verify_binding。
- 当前87项覆盖：跨终态基线仅R6新交付+六原版真实消费；全覆盖true和一完整一仍缺false；原拒绝/末尾负面/未涉及/已完成项/原计划零预算保留；坏版本/坏绑定/缺证/假完成/越界/源漂移拒绝；JSON、MD、summary、接收状态单项I/O失败保留；同提案免模型重交付；提案/备份漂移拒绝；发布后漂移拒绝；并发编辑不回滚；收尾读回失败撤销本次接收；旧普通start/stage/check/summary/消费者路径；原native计量必要兼容；实际shell argv及OS子进程禁写。
- `command.json`保存完整实际测试命令、白名单环境与cwd；`run_acceptance.py`为本次实际runner副本。最终环境去掉继承的认证变量，HOME/HERMES_HOME/XDG_CONFIG_HOME/TMPDIR均隔离，settings在收集前替换，网络/DB/正式读取写入均受审计守卫；子进程继承同一启动隔离。
- 没有重跑图像30、提示16、事件40、评分/模拟/价格工程；因共同读取增加修订分支，补了28项bound-input读取和9项native必要回归。**不把旧54或其他历史队列宣称成已全量同版重跑。**
- 早先85项、加入OS子进程禁写后的86项是历史检查点；发现“无原提案的delivery-only retry可能启动模型”后修复并加入反例，当前结项只按v3的87项及其SHA。

## Source / patch / 复验

- `implementation-source-before.json`：批准包绑定、实现前五份源码SHA；`implementation-before/`可恢复原字节。
- `source-before.json`：**最终测试前（已修复）**的完整依赖SHA；`source-after.json`：最终测试后同版，前后无漂移。包含五源码、三测试文件、两份获批契约。
- `repair-only.patch` SHA256：`1b1742aa422fe4b62d37d01919bbda02fe6afe0f34839ca84856c3d6e364471a`。只含本项五源码增量和新增测试，不是相对HEAD的整个脏树diff。
- `repair-replay.json`：在scratch的批准前字节副本上`git apply --check`及`git apply`均exit0，六个目标全部得到最终SHA；没有触碰真实索引。
- 索引前后均`ac7ff7479ac6a4bc2f9f0bdbb50b45e405e26164731dd8dfbe0a5f21ba950143`。没有stage/commit/reset/stash。
- 运行依赖：五个真实研究helper和新增测试；共同输入28项复用原测试夹具（只替代其无关orchestrator I/O，不stub summary/state/绑定消费者）；9项native计量保留真实adapter/state。外部Hermes调用全部替换为可执行合成进程。需要本机macOS sandbox-exec及项目Python/pytest；未测试Linux替代启动器。

## 明确保留的边界 / 继续条件

1. 本期只接受**未修订的已验终态基线的一次局部revision**及其同提案重交付。对已经修订的summary不会递归拼接第二条revision链；会明确拒绝，不造递归信任平台。后续如要连续多次不同范围修订，需沿当前显式来源扩展并另做有界验收，不能用新run标签覆盖六份旧来源。
2. 原资料不足保持incomplete；不补抓、不生成资金/财务事实，不认证真实模型研究质量。原native计量新接收在revision回执中，原终态day state不改；不声称该记录是全部连续任务/跨日期的权威总账。
3. 普通主研究阶段及旧有效消费者已测；没有补跑真实完整cron、真实D1或实际账户。父控需独立核当前SHA/归档，再决定自然任务采用；不能拿隔离绿测换取生产重跑或执行授权。
4. 首轮3红的纯脚本夹具没有安装通用审计器，也未显式固定pytest捕获TMPDIR；没有导入src/settings或业务客户端，但临时捕获目录不可据现有回执证明。随后首次带守卫运行实际阻止了一次系统临时目录写尝试，并曾阻止pytest写`/dev/null`；显式固定scratch TMPDIR、仅放行`/dev/null`后解决。这些历史阻止/首轮隔离缺口不能被最终0违规抹去；最终87项及合成shell链使用完整守卫与去认证环境。
5. 全部证据目前在scratch，不是已归档生产记录或clean Git checkpoint；主控应将当前v3证据按原批准backup归档。实现者不写skill/docs/SOUL，流程沉淀留给主控按既定所有权办理。
