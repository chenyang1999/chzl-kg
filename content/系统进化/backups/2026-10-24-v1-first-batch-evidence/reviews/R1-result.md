# R1 独立审查与旧合同裁决

**结论：有限范围审查通过，两个旧测试确为过期合同；已获授权迁移且保留、增强安全断言。未改任何生产源码。最终冻结闭包354个不同case全部通过，另65个subtests通过，无error/skip、审计守卫违规0。不是当前I1集成或生产放行。**

## 1. 独立核验结果

先读取S1/S2/S3报告作为证据定位，不将其自报当结论；另读S2 before/after实现、旧测试与新测试、原生XML，复制必要源码闭包至R1后真实重跑。修复前、未经迁移的旧断言失败均独立重现并保留。

| 独立运行 | case通过/总数 | 失败 | exit | subtests另列 |
|---|---:|---:|---:|---:|
| S2 before三旧组 | 156/156 | 0 | 0 | 65通过 |
| S2 before原D01/D02诊断 | 0/2 | 2 | 1 | 0 |
| S2 after、原旧测试未改 | 155/156 | 1（原:365） | 1 | 65通过 |
| S2 after原诊断 | 2/2 | 0 | 0 | 0 |
| S2 after原新增组 | 34/34 | 0 | 0 | 0 |
| S1 before真实daemon唯一分派用例 | 0/1 | 1（实际4，期望2） | 1 | 0 |
| S1冻结after原staging未改 | 56/57 | 1（原:424，实际0） | 1 | 0 |
| S1冻结after真实边界组 | 93/93 | 0 | 0 | 0 |
| 迁移后S2三旧组 | 156/156 | 0 | 0 | 65通过 |
| 迁移后S2原诊断＋原新增组 | 36/36 | 0 | 0 | 0 |
| R1独立新增组 | 12/12 | 0 | 0 | 0 |
| 迁移后S1旧staging | 57/57 | 0 | 0 | 0 |
| 迁移后S1冻结真实边界组 | 93/93 | 0 | 0 | 0 |

最终口径：paper侧204个不同case；S1侧150个不同case；合计354。修前/中间/重复运行不累加。JUnit中三旧组suite的tests=221含65个unittest子测试，但原生testcase节点只有156；逐case索引按156个原生身份列出，65子测试另列，未把221当221个独立方法。

## 2. 原因码裁决：合理语义修复，不是放宽保护

目标测试：`tests/test_canghai_paper_plan_driver_20261023.py::test_fractional_pending_retry_does_not_square_or_compound_percentage`。

- 旧实现请求基数10000、比例0.5，成交5000仍标partial；没有不可变目标，故以`fractional_partial_sell_retry_unsupported_requires_reassessment`保护性拒绝续单。
- 新实现冻结target_quantity=5000、累计5000即filled；余仓5000不等于该档未完成。下一次应返回`fractional_exit_stage_completed`。R1真实重跑证明原:364的code==2、无新成交、余仓5000通过，唯一原失败在:365的旧原因字符串。
- 修改前精确字符串消费者扫描覆盖当前源代码树trading/src/scripts/tests/web及docs等，只有driver发出新原因及该旧测试断言旧原因，无发现依赖旧码的生产判断分支。扫描结果见`reason-code-consumers.json`；未扫描凭据、真实账户/账本或数据产物，不声称认证这些外部内容。
- 按授权只迁移此方法：**原code==2/不重复卖/余仓5000断言原样保留**；新增原基数10000、冻结目标5000、累计5000、filled、无新intent，以及现金/本金/费用/批次/成交/订单/持仓不变验证。不是仅换字符串求绿。

审阅关键位置：`ledger.py:568-649`目标/生命周期恢复、`:851-870`冻结目标与T+1、`:906-908`完成状态；driver`:266-344`先保护退出后续单；与before对应函数原字节均留在闭包中。

## 3. S1 staging裁决：mock合同过期，不是生产漏分派

准确路径：`tests/pipeline/test_plan_staging_freshness.py::test_isolated_daemon_loop_refreshes_new_canonical_without_double_reload`，原:424。

- before源码daemon每轮loader先执行、watcher再执行；R1独立重跑真实daemon用例得到4!=2，确认双分派不是只据报告推断。
- 冻结after源码daemon显式`run_load_plan(..., dispatch=False)`，准备阶段不构造context、不读持仓/写positions/执行规则；watcher负责唯一dispatch。R1重跑真实边界组93通过，其中daemon两轮context=2、dispatch=2。
- 原旧用例fake_watcher只读取loaded然后return，完全不调用dispatcher；原断言统计loader dispatch必须为2，故新loader只准备时实际0。原loaded刷新、mode/reload断言均已通过，不支持“生产不执行”结论。
- 只改此方法内部fixture：wrapper仍记录原loaded读取、mode/reload，却继续调用**真实watcher和真实dispatcher**；替换外部context、账户配置、positions及扫描为合成对象。保留原first/second刷新、score70/99、总dispatch2、staged==second断言；增加准备阶段无context/dispatch、context恰2且dry_run、每次实际分派对应first/second、watch_started产物验证。sleep次数受限使错误不会无限重试。
- AST核验两个旧文件除这两个获授权方法外，其他顶层AST全部相同；方法名/数量不变，无删例、skip或xfail。见`test-change-verification.json`。

## 4. S2行为审阅及补充实证

| 要求 | 独立证据与判定 |
|---|---|
| 比例目标不重复乘 | 原新增34及R1独立12通过；原基数、整数目标、目标余量分别保存，不按余仓重乘比例 |
| 持仓生命周期 | fill历史从0到正识别cycle；跨观察/日期/计划hash/说明/priority/池和规则顺序变化不重置；R1实测加仓不重新授予已消耗档位；原新增组覆盖清仓重开及旧单不复活 |
| 旧订单证据 | R1让**冻结before ledger真实写出**completed-mislabeled-partial、深度受限partial、零成交pending三类旧订单，再用新ledger只读恢复/跨日续单；不是只删除新JSON字段模拟旧订单。目标5000恢复、只读全表不变、原order_id续单均通过 |
| 缺证据安全拒绝 | 对真实旧writer产出的合成成交移除rule证明后，比例重试无成交、余仓9000；独立合法stop仍卖出9000。未迁移真实或任意损坏账本 |
| 优先级保护退出 | 原D01独立重现修前5000余仓无法止损→修后退出；三类真实旧单都不能全票占用阻止高优先级stop；原新增验证partial接管superseded与不复活 |
| 重启/跨日 | 比例未完成沿原order/limit补到原目标，完成档位不随新日/新观察再次卖；原/new/R1组均实测 |
| 原子回滚 | R1注入合成SQLite填单中止，全表accounts/orders/fills/lots/liquidity/exit_plans严格相同，包含盘口消耗；去除触发器后stop完成且旧partial正确superseded |
| 低层默认kill | 原D02独立重现修前文件存在仍买100→修后拒绝；原新增测试覆盖ledger/CLI、伪false、默认/显式路径、null/别名/符号链接、上层快照后出现kill；内容不读 |
| 买卖分离 | R1实测显式active=true不被无文件降级；不受新买研究/零预算/kill路径门禁的合法存量退出可成交；未授权/缺研究/零预算新买仍拒绝 |

有限审查内未确认新增生产真bug，故没有越权生产修复或建议撤销保护。旧intent的原limit/index不默默重解释；任意损坏SQLite/JSON或没有可信fills的导入账户仍不在认证范围。

## 5. 文件、原件与证据

仓库仅修改：
1. `tests/test_canghai_paper_plan_driver_20261023.py`（只改获授权方法）。
2. `tests/pipeline/test_plan_staging_freshness.py`（只改获授权方法）。
3. 新增 `tests/test_v1_independent_contract_review_20261024.py`（12个参数化后case）。

改前原件/hash：`original-tests/`、`original-test-hashes.json`。两个原SHA256分别：
- driver：`98d0bffcf281a7acb10d787d982a3c81f060bd74efc0f52a2426b500330ebcdf`
- staging：`a42b7d17c090958a6d9cede0c862fa4c9374118f66eaa28a04072f34efb0813b`

完整交付位于 `/Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/R1`：
- `original-evidence/`：S1/S2原生XML/run/log复制件；原失败未覆盖。
- `paper/pre/`、`paper/post/`、`s1-frozen/`：R1独立重现的原失败及冻结源码闭包。
- `paper-migrated/post/`、`s1-migrated/after/`：最终原生JUnit、完整stdout/stderr与命令/exit/guard JSON。
- `native-case-index.json`、`original-native-case-index.json`：逐原生case身份/状态/失败详情/证据路径；`native-run-summary.json`：逐组结果。
- `closure-manifest.json`、`migrated-source-hashes.json`、`source-current-comparison.json`、`artifact-hashes.json`：原件/受测代码/当前对照/证据hash。
- `R1-test-only.diff`：仅本次三测试文件增量，不混入HEAD或其他组改动。
- `contract-adjudication-before-edits.md`：改前裁决；`skill-proposal.diff.md`：仅建议未应用。
- `rerun-commands.json`、`migrated-commands.json`、`s1-before-daemon-command.json`：真实命令（项目venv python、-B）。每组`*-run.json`同时保留精确pytest参数。

所有运行均从scratch复制闭包收集指定文件，关闭插件、--noconftest、no:cacheprovider；audit钩子禁止生产读写/凭据、网络、业务子进程，DB仅独立fixture目录。无生产任务、重载、推送、券商/行情、真实账户/账本访问或Git写操作。账本、本金、授权、行情及日历全为显式合成，zero_fee_assumption不计生产净收益。

## 6. 未尽边界与问题

1. **必须由主控完成I1最新源码联合验收。** 出报告时当前`trading/load_plan.py`、`trading/execution_authorization.py`、`trading/watcher/run_once.py`已与冻结S1/after不同（精确hash见JSON）；这不推翻旧合同裁决，但本354通过不能背书该新源码。S2受测非包shim源码与当前一致。
2. 初次prepare只读消费者扫描遇到第三方目录`web/node_modules/fraction.js`被误当文件，报IsADirectoryError；已改为只扫描文件并排除node_modules/dist/build后完成。未造成产品测试失败或外部副作用。
3. 首轮迁移后R1新增11通过，后补1条“真实旧writer缺rule证据”反例后最终12通过；首轮证据完整保留在`migrated-attempt1/`，未将重复运行累加。
4. 未做全仓审计/全仓pytest、真实行情真实性认证、常驻进程加载或生产交易认证；没有配置、路径、交易政策、模型或技能改动。
