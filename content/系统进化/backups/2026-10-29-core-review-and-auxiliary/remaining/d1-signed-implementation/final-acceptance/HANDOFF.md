# D1 盘前差分重评交接（本子任务已收口，待主控必要联合）

## 边界/文件
仅修改生产 `scripts/plan/ensure_watchlist_plan.py`；仅新增 `tests/pipeline/test_d1_selective_reassessment.py`。本子任务释放写权。未改研究五源码、其他测试、技能、价格文件、风险/预算阈值；不提交Git。父级价格施工不作为本项漂移，不重验价格/研究57项。

- baseline ensure: `08688d64512fbda8db711195298cba5ff659fa4cce32402f91fa8208f504b5a1`，原字节 `ensure.before.py`
- final ensure: `c0885a6519266c21f273b5864a5043fbe229c5fea36d3178bd4e84aa4cf831ca`
- final new test: `7f2edd7dbbf714b7067c2efd63e24d834a15863bce9d730df3ebb76b760a0c68`
- `only.diff`: `ec39c0aa613775c8a0b632cf8a9a5c758e8c774e59f70a8fedb1b67d878a4903`
- final snapshot `tested-source/`，结论与SHA `final-result.json`。Git index、研究五源、现行签核D1技能均未被本项改写；最后核对成功。

## 实现结果
1. 原生 `verify_saved_inputs` / `consume_authorized_inputs` / `_accepted_r6_revision` 核当前owner及逐项JSON/MD run/attempt/receipt/hash。去掉“全部报告晚于旧预案、全部解除未就绪”的门槛；未变报告按完全相同身份复用，须有真实primary内容差分才启动D1。
2. 沿既有retry日志目录保存由实现者接收的输入/输出回执，绑定实际旧预案与MD；summary/plan marker不自签，错owner、错批、无旧身份、mtime-only、终态伪重发及重复输入拒绝。初始正常retry仍走原入口/发布链，新完整/no_trade幂等与force/no-llm不变。
3. 已合法发布但未就绪的LLM采用同一D1 owner的stdout-only候选运输（bot_room无写工具），私有临时目录先走真实schema、报告组装、输入复核，再走既有canonical→runtime发布。Python只验证，不生成决策。失败、错误输出、中途漂移保留最后有效JSON/MD/runtime，发布I/O失败仅回滚本次准确字节。
4. 必要审核仍缺时必须保留显式未就绪、no_trade、禁自主、人工确认；成功发布安全版仍返回非零。原池/entry/exit/预算权限不变，用户/账户/未知禁令不能撤销；正常卖出保留。来源明确的日内市场condition仅能改自身active，R6/审核缺口仍阻断解禁。
5. 原盘中事件函数与main分派逐函数AST等价，不作事件实现变更。

## 原生验收
`affected-aux/command.json` 是完整argv/env/cwd，原生 `junit.xml` / `pytest.log` / `result.json` / `source-before.json` / `source-after.json` / `sitecustomize.py` / `guards/` 全在同目录。

- 新专项41 + 原辅助28/9/17 = **95 passed**，未跳过/过滤/删断言。
- 真实R6 fixture→run_r6_revision→终态state/receipt/summary受信消费者→ensure_plan→真实发布链。原六报告mtime早于旧预案且原版本/身份保留；未整体mock研究/R6消费者。
- 51守卫进程、50合成原生子进程，全部继承收集前守卫，最终队列0违规、0未守卫子进程，受测源码前后稳定。
- 自测 `guard-selftest/command.json` / `probe-result.json`：scratch写/rename/symlink/dir_fd合法操作通过；.env/正式data/私有配置/网络/DB/越界symlink/dir_fd/无关子进程8类均被拒绝。自测的预期拒绝单列，不混入验收零违规。
- 真红 `red-real/`：在原ensure源码运行当时新增29项，14 failed/15 passed；正例实际因原fresh-batch门槛零运输而红。随后扩充新专项至41，保留原业务断言。

主控可复用完整启动隔离执行（不要只复制audit函数）：
```
.venv/bin/python -B /Users/chenyang/.hermes/cache/scratch/d1-selective-20261029/run_acceptance.py <新的唯一label> tests/pipeline/test_d1_selective_reassessment.py tests/pipeline/test_bound_auxiliary_inputs.py tests/pipeline/test_d1_auxiliary_caller_wiring.py tests/pipeline/test_signed_input_review_contract.py
```
实际pytest均 `--noconftest -p no:cacheprovider`，禁自动插件、字节码、缓存，独立scratch basetemp；runner读取此前R6完整父/子守卫并复制启动替身。无真实模型/网络/账户/DB/生产任务。

## 如实保留的红项/迭代
- `legacy-baseline/` 与 `legacy-current/` 各完整跑两个直接旧调用测试文件，共74项，均45 passed/29 failed，逐nodeid全部结果相同；旧源码复制到fixture后的SHA已实核。`legacy-comparison.json` 保留全部失败身份。原因是这些旧fixture早于已签辅助绑定，缺bound_auxiliary_inputs，本来就到不了模型运输。未改任何旧测试、未删原assert、未过滤求绿。仅显式scratch路径常量重定位，详见各自 `legacy_paths.py` / `fixture-path-relocation.json`。
- 初次 `legacy-direct/` 遇urllib3导入IPv6 bind探测，被守卫阻断（没有成功联网），留红；后续基线/当前对照只禁该import-only has_ipv6探测，不放开网络，两个对照队列均0守卫违规。
- `red/` 是早期fixture包/dispatch接线错误，不能当业务红；仅修新增fixture。`green-new/` 是私有MD目录漏建，已修。
- `green-new-2/` 暴露真实兼容点：native safety_net observation会改变终态研究state字节，破坏已接受R6基线。没有mock/放宽受信消费者，也没改native共享源；改在D1既有retry目录记录实际PID/argv/原生usage。后续真实受信消费通过。

## 未验边界（不得写成生产完成）
- 未做真实角色补证、模型恢复/付费调用、生产窗口、交易或自然采用。
- **历史shell/legacy临时预案无先前受信D1输入/输出回执时仍拒绝**；不得现场回填绑定。本次正链从真实初始retry建立回执后验证后继修订。
- 跨run缺继承证据仍拒绝。终态基线只消费已接受的R6局部owner，不重开旧terminal run或伪发旧run新回执。
- 差分D1原生用量保留本地PID/argv绑定观察，不写原研究终态resource_observation，不宣称覆盖全provider账单。预算/权限不靠此用量放行。
- 本项95绿不抹去上述旧74项的29个既存红项，也不替代主控最终必要联合。没有重跑研究57项/既有120项或价格163项。
