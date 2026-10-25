# S2 修复结果：独立模拟退出保护与低层默认 kill

**实现已完成，D01/D02 原诊断均由失败转为通过；但不能宣称全回归通过。** 三组既有 paper 测试完整执行后仍有 **1 条历史原因码断言失败**，原断言未修改。新增 **34 条通过**，主控尚未独立验收。本报告不是生产交易放行。

## 授权与变更边界

- 用户授权范围仅 D01/D02、指定源码及新增测试。未动 Git/index、schema、其他组源码、配置/.env、模型、cron、SOUL、技能或保留期限。
- 改前原件与 SHA256 已保存在 `before/`、`before-hashes.json`；本次增量见 `repair-only.patch`，不是对 HEAD 的混合 diff。
- 只在 S2 scratch 内使用合成独立 SQLite 账本、权限、行情、日历与本金。**未打开、初始化、迁移或重设任何生产/生产模拟账户**；无 QMT/IB、HTTP/行情服务、推送或业务子进程调用。
- 验收对象是冻结的工作树源码闭包复制件，不是干净 Git checkpoint。`post/tested-source-hashes.json` 共记录 16 份源码/测试；与当前可对应工作树文件逐一比较，漂移为 0。既有三份 paper 测试与修前复制件 hash 相同。

## 已修复

### D01：比例目标、订单状态与余仓分离

- 比例单首次确定整数股 `target_quantity`，仅剩目标量参与续单撮合；不再对余仓重复乘 `quantity_pct`。原请求基数保持在 `intent_json`，订单是否完成按目标量判断，剩余持仓不被当作未完成量。
- 比例档位以真实 fill 推导的持仓生命周期及数值规则身份识别，不随新观察、正式计划哈希、日期、池归属或规则说明文字重置。平仓再开仓才是新生命周期。
- driver 不再用旧 pending/partial 全票保留集阻断评估；每轮先按优先级评估保护退出。比例已完成或旧止盈未触发，不妨碍高优先级止损。
- 保护成交接管低优先级未完成退出时，只原子写 `superseded` 和来源关联；现金、批次、成交、盘口消耗与接管失败时一并回滚。没有凭空补成交或改本金。
- 新池缺票、零预算、禁新买、缺研究仍可消费账本保存的合法退出来源；原有买入资格门禁仍拒绝未授权/缺研究/零预算新买。

### D02：低层重新核验既有默认 kill

- 新增惰性纯帮助模块 `trading/paper/safety.py`，共用既有 `data/runtime/KILL_SWITCH` 默认及批准 token；只检查存在性，不读取内容。
- `PaperLedger.execute` 买入边界在事务内自行复查，`run_paper_trading` CLI 因此同样受保护，不把计划或上层填的 `kill_switch_active=false` 当作文件不存在的证据。
- 未批准路径、null、别名、符号链接及未知状态拒绝新买。显式 active=true 不会被不存在的文件降级；高层既有默认保护保留。合法卖出仍独立于买入 kill/研究/预算门禁。
- 附加反例证明：上层观察到 false 后才出现 kill 文件，低层仍拒绝买入。

## 原生验证结果

| 运行 | case | 通过 | 失败 | error | skip | 子测试另列 | exit | 守卫违规 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| pre/paper | 156 | 156 | 0 | 0 | 0 | 65 | 0 | 0 |
| pre/diagnostic | 2 | 0 | 2 | 0 | 0 | 0 | 1 | 0 |
| post/paper | 156 | 155 | 1 | 0 | 0 | 65 | 1 | 0 |
| post/diagnostic | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| post/new | 34 | 34 | 0 | 0 | 0 | 0 | 0 | 0 |

最终运行按原生 JUnit case 身份去重：**192 case＝191 通过＋1 失败，error/skip 均 0；另 65 个子测试通过。** 修前或中间重跑不累加为新通过数。JUnit suite 中 tests=221 包含既有 156 case＋65 子测试，不把 221 当独立 case。

三组既有 paper 的修后分项：execution **30/30**，parent-review **89/89**，plan-driver **36/37**。原生 XML、完整 stdout/stderr 与命令分别在 `pre/`、`post/` 的 `*-junit.xml`、`*.log`、`*-run.json`，逐 case 索引在 `native-test-cases.json`。

### 唯一既有断言失败：完整保留，不伪造兼容错误码

`tests/test_canghai_paper_plan_driver_20261023.py::test_fractional_pending_retry_does_not_square_or_compound_percentage`：

- 第 364 行的安全结果仍通过：拒绝再次卖同档、没有新 fill、保留 5000 股。
- 第 365 行期待旧原因 `fractional_partial_sell_retry_unsupported`；修复后这个档位已经完成，实际原因是 `fractional_exit_stage_completed`。
- 未改原测试期待、未 xfail/skip、未为全绿冒充“未支持”。这是需主控审阅的历史契约迁移，**不因此宣称全部测试通过**。

### 旧诊断修前/修后

- 原 D01：修前止盈 5000 后仍余 5000，硬止损没有成交；修后剩余仓位合法退出，原诊断通过。
- 原 D02：修前默认 kill 已存在仍低层买入 100；修后低层拒绝，原诊断通过。
- 两条原诊断源码未变，原有 6 项诊断中其他 4 项属于别组，不在 S2 重跑/修复范围。D/H 原始失败证据未覆盖。

### 新增覆盖

同观察重放、重启、深度受限比例续单及跨日续单、已完成档位跨观察/跨日不再卖、部分止盈到硬止损、事务接管回滚、旧 partial/零成交 pending 兼容、旧证据缺失的安全拒绝与独立止损、新生命周期与旧订单防复活、低层 CLI/default/伪 false/路径拒绝/符号链接/上层快照后文件变化，以及未授权/缺研究/零预算拒绝。

### 隔离器首次失败：透明保留

最初的修前三组回归退出 **98**，不是产品安全回归结论：macOS `shutil.rmtree` 以 `dir_fd` 相对路径 unlink，首版审计守卫误按 cwd 解析文件名，产生 119 条 scratch 清理误报。已按 `F_GETPATH` 还原父目录，**未放宽应用路径与数据库夹具分离**。首轮日志/JUnit/run JSON 均保留为 `pre/harness-attempt1-*`；更正后修前 156＋65 全通过且守卫违规 0。

中间迭代的源码、hash、JUnit 和日志分别留在 `post/attempt1/`、`attempt2/`、`attempt3/`，最终证据在 `post/` 根下，不覆盖历史失败。

## 旧订单兼容与明确边界

1. New fractional orders persist target_quantity/exit_stage_key/exit_rule in result_json; no SQL schema changes. A target is frozen once, matching keyed integer-share fills and surviving restart/next-day plan changes.
2. Stage identity uses immutable fill-derived position lifecycle plus numeric rule type/trigger/pct/time-window, not daily plan hash, rule index, description or priority. Fully closed/reopened positions get a distinct lifecycle; adding shares while holding does not reset a consumed tranche.
3. Legacy filled/partial sells without target metadata resolve read-only from original fill rule evidence and T+1 sellable inventory reconstructed from immutable prior fills. Zero-fill legacy pending orders use saved exit source and creation-time eligible inventory. Complete legacy partial rows are not rewritten just to relabel them.
4. Only a real retry of an incomplete legacy order persists new target metadata; higher-priority filled protection can mark lower pending/partial orders superseded transactionally. No fabricated cash, lots or fills; an aborted fill rolls back supersession and liquidity too.
5. Missing legacy rule/history evidence or impossible prior quantities fail closed for that ratio retry. Independently valid full hard-stop exits still work. Arbitrarily corrupted JSON/SQLite or ledger imports without trustworthy fills are not certified/migrated.
6. Existing pending intent rule index and original limit are not silently reinterpreted/repriced. A changed pending numerical rule or lifecycle requires reassessment; a new explicit rule setup is separate authorization evidence, not inferred policy.
7. 100% exit requests retain their existing explicit requested-quantity/T+1 partial semantics; fractional quantity_pct bases alone become capped immutable tranche targets.
8. No production or paper production ledger was opened, reinitialized, migrated, or capital-reset. All fills shown are synthetic and zero-fee assumptions are explicitly fixture-only, not brokerage/net return claims.

## 真实执行命令

下列命令由各次 `*-run.json` 读取；runner 固定 `-B`、插件关闭、`--noconftest`、`no:cacheprovider`、scratch basetemp/JUnit，并安装导入、网络/子进程、生产读写和 SQLite 路径守卫。所有测试收集均在已审阅并复制的闭包下，没有原目录裸跑 pytest。

```sh
TMPDIR=/Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/S2/pre/fixtures /Users/chenyang/Downloads/demo/沧海巨浪/.venv/bin/python -B /Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/S2/run_safe_tests.py pre paper
TMPDIR=/Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/S2/pre/fixtures /Users/chenyang/Downloads/demo/沧海巨浪/.venv/bin/python -B /Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/S2/run_safe_tests.py pre diagnostic
TMPDIR=/Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/S2/post/fixtures /Users/chenyang/Downloads/demo/沧海巨浪/.venv/bin/python -B /Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/S2/run_safe_tests.py post paper
TMPDIR=/Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/S2/post/fixtures /Users/chenyang/Downloads/demo/沧海巨浪/.venv/bin/python -B /Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/S2/run_safe_tests.py post diagnostic
TMPDIR=/Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/S2/post/fixtures /Users/chenyang/Downloads/demo/沧海巨浪/.venv/bin/python -B /Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/S2/run_safe_tests.py post new
```

## 交付文件与 SHA256

修改：`scripts/execute/run_paper_plan_once.py`、`trading/paper/ledger.py`。
新增：`trading/paper/safety.py`、`tests/test_v1_s2_paper_exit_safety_20261024.py`。
低层 CLI 本身未改，保护落在真实被它调用的 `ledger.execute`。

| 文件 | 最终测试 SHA256 |
|---|---|
| `scripts/execute/run_paper_plan_once.py` | `966599762dd0797a1dbcb50789d8204f441c305aaa9714f8744da44ec624a44b` |
| `scripts/execute/run_paper_trading.py` | `dcfc70a433602b4a54d1d890ba2307234472f1ec0e5576f7921573c4c018409c` |
| `trading/paper/ledger.py` | `40d77a426defe9118d31960412da85e8b5dfd038b35eabd519f904db51ba2175` |
| `trading/paper/safety.py` | `208686a5f1f826ecaaf1b291368bc270b946d4951a07f91a7fdc298d075c744a` |
| `tests/test_v1_s2_paper_exit_safety_20261024.py` | `a4ed8cda0d82a235e04324d60bbe8163279c665fe83aef07819ebbe5e0aecab0` |

源码函数位置、完整闭包 hash、命令、逐项失败详情与范围声明见 `S2-result.json`。原 native JUnit 不经转换；`repair-only.patch` 可与 `before/` 原件核对。

## 待主控验收 / 待签建议

1. **优先独立复核本源码 hash 与原生证据，并裁决旧测试第 365 行原因码契约。** 当前未改断言，不替主控验收。
2. `skill-proposal.diff` 仅建议比例目标/退出优先级/低层默认 kill/隔离器 dir_fd 规则；没有应用到任一技能或 profile，待签后由主控统一处理。
3. 未验证驻留进程加载、生产报价来源真实性、真实交易日历、生产账户表现或全仓测试。不把合成成交计作生产业绩，也不据此开放生产交易。
