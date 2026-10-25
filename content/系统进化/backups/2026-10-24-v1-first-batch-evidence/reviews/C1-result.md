# C1有限闭环修复

**本批两项最小生产修复已完成；原F2三日期反例与偏离bid反例共4项实际由失败转通过；仍不能实盘放行。**

## 真实结果（原生JUnit，非复用旧结论）

| 隔离组 | case | pass | failure | error | skip | exit |
|---|---:|---:|---:|---:|---:|---:|
| before/f2 | 86 | 80 | 6 | 0 | 0 | 1 |
| after/f2 | 86 | 84 | 2 | 0 | 0 | 1 |
| after/c1 | 47 | 47 | 0 | 0 | 0 | 0 |
| after/i1 | 71 | 70 | 1 | 0 | 0 | 1 |

各组审计违例均0，固定collection身份/数量已断言。before为本次生产修改前新冻结、新执行的原F2，after逐字节来自本次修后当前源码；F2原测试源码完全未改。多次执行不相加，旧I1不冒充全绿。

## 生产改动（仅3文件）

- `trading/watcher/session_context.py`：`buy_allowed(..., trade_date=None)`只兼容调用形式，不兼容缺授权继续通过；调用者未显式提供非空字符串交易日，或scan日期缺失/异日，均返回`False, ["scan_date_missing_or_mismatch"]`。没有补“今天”、没有从scan倒推授权日期、没有新增报价龄/交易阈值。
- `trading/executors/_buy_common.py`：显式传`qmt_ctx.trade_date`。
- `trading/order/qmt_context.py`：最终买入显式传`self.trade_date`；已有有效bid检查后，最终sell的`limit_price != book_price`直接拒绝`sell_limit_not_authorized`。不改正常sell wrapper、八种退出策略或规则量。

Python调用链AST检查覆盖`trading/src/scripts/tests`：生产函数调用只有上述两个消费者，已全显式传日期；scripts中的同名局部布尔变量不是函数调用。`run_once`仍clear→scan(trade_date)→set→一次dispatch，selector输出本轮传入日期；未改正常watcher。

## 验证覆盖及未改变的边界

- 新增`tests/test_v1_scan_date_binding_20261024.py`，47项全部通过：显式同日成功；异日/缺scan日期与缺调用者日期拒绝；原调用形式缺参数拒绝；两个买入消费者分别live/dry_run同日正例与异日/缺日负例；默认loader dispatch旧/无日scan拒绝、同日正例；合法sell不受scan日期限制；`.01/7.99/8.01`偏离bid均拒绝；正常watcher买100股、后续零买预算/缺成功scan合法卖300移动仓，真实scratch journal readback；两轮两context/两dispatch。300不是1000股全清，不是券商成交。
- 原F2五类真实买入wrapper及八类既有退出wrapper、正常watcher买入、scan缺失合法sell与两轮dispatch在86项中继续通过。此证据只是现有接线/分工未误伤，不把复杂退出type名单称为精确触发/比例量许可。
- 原F2的`[untriggered]`和`[quantity]`仍如实失败：低层直接调用可以在未触发stop时提交100@10，或10%规则提交1000@8；只到合成transport。正常wrapper的未触发stop反例仍skip、无订单。它们是历史残余，未在本批重写精确意图授权。
- 授权绑定仍是plan/context/scan相同日期，不是墙钟当前交易日/交易日历认证。未新增报价年龄阈值。跨进程额度/提交原子性、券商身份/订单成交撤单对账等原阻断继续存在。

## 旧测试fixture冲突：留原失败，回传主控

原I1隔离重跑71项70通过1失败：`test_loader_default_single_dispatch_with_real_context`手工scan缺`trade_date`却期待买入，实际仍一次dispatch、0订单；这是本次明确要求的安全拒绝，不能恢复默认通过去刷绿。本批原件/副本及断言未改。

本轮初始S3旧直接`buy_allowed`调用缺授权日期，部分正常scan payload也缺日期；需单独获授权后仅补正常fixture日期/显式调用日期，不改安全期待。C1未重跑/修改S3/其他旧联合测试，不能宣称联合套件全绿。精确建议在`T1-fixture-followup.md`，`callsites.json`是最终盘点时调用点，由T1/主控裁决权限；未改FINAL harness或旧RR。

## 交付与复跑

- `before/`、`before-sha256.json`：改前源码及当场F2基线；`after/source-sha256.json`、`after/tested-all-sha256.json`为受测闭包/hash，`source-current-sha256.json`为最终3生产+新测试hash。
- `C1-incremental.diff`：仅上述3生产文件与1新增测试相对before的增量。
- `before/f2-junit.xml`、`after/{f2,c1,i1}-junit.xml`：原生JUnit；相邻`*-pytest.log`、`*-run.json`保留精确命令、pytest argv、exit及审计。
- `four-counterexample-transitions.json`、`native-case-index.json`：身份集合程序校验，4条目标failure→passed、2条未修反例仍failure。
- `before/observations`、`after/observations`：关键结果/合成transport与真实scratch JSONL复读记录。
- `C1-result.json`、`real-commands.json`、`callsites.json`、`before-current-comparison.json`及`artifact-sha256.json`。

```sh
'/Users/chenyang/Downloads/demo/沧海巨浪/.venv/bin/python' '-B' '/Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/C1/before/run_safe_tests.py' 'f2'
'/Users/chenyang/Downloads/demo/沧海巨浪/.venv/bin/python' '-B' '/Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/C1/after/run_safe_tests.py' 'f2'
'/Users/chenyang/Downloads/demo/沧海巨浪/.venv/bin/python' '-B' '/Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/C1/after/run_safe_tests.py' 'c1'
'/Users/chenyang/Downloads/demo/沧海巨浪/.venv/bin/python' '-B' '/Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/C1/after/run_safe_tests.py' 'i1'
```

上述复跑运行已冻结的精确受测源码，不自动改写生产；f2预期exit=1（两条保留反例），c1为0，i1为1（旧缺日正例期待）。每次重跑会重写对应输出；本交付首次证据已原样保存，勿将重跑累计计数。

**写集合**：仅授权3生产文件、新增1测试及C1 scratch证据。未做Git写/提交/分支/清理/push，未读写.env/凭据/真实账户/持仓/账本，未连业务网络/QMT/IB/行情，未执行生产任务/服务/重载/推送，未改配置/SOUL/skill/cron/路径或交易新参数。技能同步仅回传建议，未越权写skill。有限收尾完成退出。

并行外部改动（本C1未写、未回滚）：tests/test_canghai_rr_scope_20261023.py, tests/test_v1_integration_authorization_20261024.py, tests/test_v1_s3_trigger_quote_safety_20261024.py。其中I1当前工作树已被补入`trade_date=DATE`，C1的after/I1证据仍是补入前原件，不能冒称它代表当前外部修复后的结果。生产受测闭包及新增C1测试仍与当前工作树逐字节一致；旧测试并行差异见`external-concurrent.diff`/`frozen-source-current-comparison.json`，最新联合验收由主控负责。
