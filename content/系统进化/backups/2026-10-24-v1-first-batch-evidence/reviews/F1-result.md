# F1 最终联合验收：阻断，不是全绿或生产放行

**同一份当前生产源码闭包真实重跑：711 个不同 case，698 通过、13 断言失败，error/skip 为 0；另 65 个 unittest subtests 全通过，不计新增 case。**

核心指定组 559 case：549 通过、10 失败。旧 RR 两文件共 141 case：138 通过、3 失败；F1 补充 11 通过，**不抵扣或替代 S3 原失败**。不能报告“S3 原129全部通过”。

## 最终原生结果

| 组 | case | pass | failure | error | skip |
|---|---:|---:|---:|---:|---:|
| s1 | 93 | 93 | 0 | 0 | 0 |
| i1 | 71 | 71 | 0 | 0 | 0 |
| paper | 156 | 156 | 0 | 0 | 0 |
| s2diagnostic | 2 | 2 | 0 | 0 | 0 |
| s2new | 34 | 34 | 0 | 0 | 0 |
| r1 | 12 | 12 | 0 | 0 | 0 |
| staging | 57 | 57 | 0 | 0 | 0 |
| s3 | 129 | 119 | 10 | 0 | 0 |
| s3diagnostic | 5 | 5 | 0 | 0 | 0 |
| rrparent | 32 | 32 | 0 | 0 | 0 |
| rrscope | 109 | 106 | 3 | 0 | 0 |
| f1 | 11 | 11 | 0 | 0 | 0 |

四个原 AST 诊断加 C05 缺扫描共5项，均实际读取当前冻结源码；S2原诊断只指定原 D01/D02 两项。所有指定数量、逐case身份、65 subtests均程序核对，coverage_errors 为空。每组独立进程，但生产算法副本逐字节来自同一个 frozen 目录，不复用旧组“after”实现。

## 阻断项（原断言完整保留）

### 1. S3 10 项：授权优先后的原因合同冲突

唯一方法 `test_final_context_refuses_missing_or_invalid_executable_book` 的买/卖×五种坏盘口。原方法直接传 `rule_type="synthetic_only"`，不属于当前授权计划中的已知规则。I1最终门禁先拒绝：买 `buy_rule_not_uniquely_authorized`、卖 `sell_rule_not_authorized`。原 `status==rejected` **10项均成立**，但它们还要求旧 `reason==missing_or_invalid_executable_quote`，故失败。原生 failure receipts 保存实际返回字典。

没有把未知买规则伪装成已知策略、没有包装 place_order 改 rule_type/返回值，也没有 monkeypatch `_authorization_reason`。仅补计划/账户不能让不受支持的 `synthetic_only` 买规则变成有效已知规则；即使补同名授权，真实买触发重验仍优先于旧盘口原因。要完成原129全绿，需要主控单独裁决旧方法的规则输入/原因断言迁移；**本授权禁止动断言或生产门禁，所以保留失败并退出。** 这13项失败不是证实下单穿透；本轮未确认新增生产安全绕过。

另新增10项以真实授权 `leader_breakout`/`stop_loss_break` 调用最终边界、保留None/0/True/NaN/Inf盘口，全部安全拒绝、真实JSONL复读一致且客户端0调用。买侧真实理由为 `buy_trigger_not_met`，卖侧为 `missing_or_invalid_executable_quote`。这些是补充证据，不冒充原10项通过。

### 2. 旧 RR 3 项：原合成资产买不起一手

已先读两个实际 RR 文件并原样运行。RR parent 32全通过；RR scope 原样106通过/3失败。scratch内仅补原context缺失的cash=100000、holdings={}和按原stock生成的buy_pullback/明确SISE扫描；**原源码、报价100、total_asset100000、position_pct .05和所有期待不改**。

补fixture后3项仍失败，真实 receipts 都显示 `zero_buy_qty`：100000×.05=5000元，拟限价100只能买50股，小于100股整手；正确向下取整为0。未增大资产、放宽比例、恢复旧强买100股或修改期待求绿。坏RR票仍为`stock_buy_eligibility`；合法卖出200股及观察池启动在对应混合用例中仍发生，失败点是“好票必须买”的旧期待。

## S3 获准 fixture 适配及断言保护

- 先以原S3测试原字节运行：129个真实setup errors（旧fixture闭包缺新 `trading.execution_authorization` 依赖）；原生XML/log全部保留，未用旧生产源码“先跑绿”。
- 只改S3 fixture依赖/辅助函数：复制当前授权帮助模块和纯models；显式计划/账户自主、无需确认、既有合成预算；绑定真实授权；各executor按测试原stock规则绑定，dispatcher fixture提供明确五类原规则及退出；只补缺失持仓估值，不改异常quote/cash/available/scan/触发值。
- `assertion-preservation.json`证明原29个test函数含参数装饰器的AST完全一致；没有删例、改断言、skip/xfail。原129 case身份与最终129完全相同。
- 两旧迁移测试、S1/S2/I1/R1测试与两个旧RR文件自本轮首次冻结以来hash一致，未再修改。

## 正向链不是“只拒绝”

I1原71全部通过，实际schema序列化→正式交接/loader→watcher→真实dispatcher/registry/executor→真实最终QMTContext→**合成末端transport**→真实scratch JSONL复读。合法买100股与零预算/缺扫描合法卖均有正例。

F1新增联合正例同样实际贯通上述链，先记录合成buy100，再显式注入独立合成可卖持仓，零买入预算/缺扫描下记录sell300，复读顺序buy/sell与两轮两次dispatch一致。300为现有base/mobile持仓分层下可卖移动仓，**不是1000股清仓、不是券商委托/成交**。新增正例首跑误期待1000的失败留在历史目录，后来仅纠正本轮新写测试的现有移动仓合同；没有改旧安全断言。paper各组持久化合成fills由原组原断言核验，不计生产业绩或真实净收益。

## 冻结、隔离与证据路径

最终证据：`accepted-evidence-20261024T143327Z-8b22d705/`。

- `source-manifest.json`：59份当前源码/测试，含47份生产源码。最终冻结/各组副本/当前工作树hash一致；这47份生产源码与第一次原样运行冻结也全一致，未写任何生产实现。
- 各组 `junit.xml`（原生未转换）、`pytest.log`、`run.json`（精确命令/pytest argv/exit/审计）、`failure-receipts.json`；`paper/subtest-index.json`。
- `native-case-index.json/csv`逐case去重；`native-subtest-index.json`另列65项；重复run不累计。
- `audit_worker.py`：网络、子进程、凭据/生产IO、sandbox外写守卫；SQLite仅本组fixtures，macOS dir_fd相对清理路径解析。12组审计违例均0。
- 原D01/D02与四AST诊断文件从历史证据取**测试源码**，真实旧writer只作R1兼容fixture输入，均在support/harness manifest标明；绝不当作受测当前实现。
- `originals/`、`original-hashes.json`、`S3-fixture-only.diff`；历史raw/fixture-check/final/parent目录原件不覆盖。
- `F1-result.json`列每项失败、全部命令和原生证据路径；`real-commands.json`便于主控复跑。

## 主控可直接运行

先读 `run_parent_verification.py` 与 `audit_worker.py`，然后：

```sh
'/Users/chenyang/Downloads/demo/沧海巨浪/.venv/bin/python' -B '/Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/FINAL/run_parent_verification.py'
```

脚本每次从**当前**白名单源码重新冻结，生成独立`parent-UTC-随机后缀/`，不复用现有冻结结果，不执行生产入口；固定上述指定组、禁插件/--noconftest/no:cacheprovider/scratch basetemp。默认仅给旧RR补缺失cash/holdings/scan；`--no-rr-adapt`保留完全原样RR fixture。当前状态应真实退出1并保留13项失败，不伪装exit0。已实际执行过不带参数的直接主控命令。

## 写集合与边界

仓库只修改 `tests/test_v1_s3_trigger_quote_safety_20261024.py` 的fixture设置，新增 `tests/test_v1_final_joint_acceptance_20261024.py`。其他新增全部位于FINAL。

未做Git写/提交/clean/reset/stash/push，未读.env/credential/真实账户/持仓/账本，不连QMT/IB/行情/业务网络，不执行生产任务/重载/推送，不改生产源码、两旧迁移测试、配置、skill、SOUL、cron或数据路径，不选择交易新参数。不是全仓审计/全仓pytest/并发订单对账或生产认证。按本批范围，**带真实联合阻断退出，等待主控对旧合同作独立裁决**。
