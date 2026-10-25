# S3 修复验收（2026-10-24）

## 结果

指定5份源码与1份新测试已完成；最终隔离回归 **129通过、0失败/错误/跳过**。历史四AST诊断＋缺扫描反例：**修前5失败 → 修后5通过**；D04是S1同期修复，只读验证、不归功于S3。所有本轮运行守卫违规记录均为0。

验证对象为冻结工作树闭包，不是干净Git提交或生产认证。所有买卖结果只为合成dry_run意图，未产生模拟账本fill或真实委托。

## 修复内容与边界

### C05/H04
- 修前：No opportunity / scan exception returned pass-through; stale scan rows survived replacement; cheap-price branch preceded negative patterns.
- 修后：No evidence/exception/malformed or unmatched signal denies buys only; replacement invalidates old success; existing confirmed washout+support or breakout+SISE still pass; fetch and SISE failures isolated per symbol.

### D08
- 修前：last9.8 ask9.9 trigger10 cap10.3 returned True.
- 修后：Finite positive trigger and quotes; last must reach trigger plus explicit confirm/reclaim, ask obeys cap. Existing 3% absent-cap fallback kept; explicit zero/invalid does not fall back. Active unknown constraints explicitly unsupported.

### D07
- 修前：100000 asset, 10 target and 100 neighbor quote produced 100 shares; zero/unknown budget hard-minimum 100.
- 修后：compute_buy_qty requires ts_code and exact limit_price; min(rule notional, cash, remaining explicit stock cap) rounded down to whole lot, else zero. Only production call is _buy_common and is updated.

### D06
- 修前：Missing available_qty returned total_qty1000; quote refresh could turn holdings.last into bid/ask.
- 修后：Unknown/negative/fractional/bool/nonfinite sellable becomes zero, valid zero retained; integer numeric strings remain compatible. Refresh no longer synthesizes books; failed live refresh invalidates requested quotes, supplied dry-run books remain usable. Final context requires valid side-specific executable book; legal exits with books and known availability pass independently of scans.

### D04/S1-owned
- 修前：Historical audited loader AST converted plan zero to account .75.
- 修后：S1 working-tree helper and loader, copied read-only into exact snapshot, preserve zero. Not an S3 code change; include in four historical AST counterexamples only.

## 文件与最终SHA256

|路径|变更|SHA256|
|---|---|---|
|`trading/entry_selector.py`|modified|`b3c11a6562806258c73e46f79330ead5cde80ab3b9a033b672f4571478bf2b35`|
|`trading/watcher/session_context.py`|modified|`04a0f79af3f856c83cd863900e12348cb0ebb63cffe2d9b05090676636bdd1f3`|
|`trading/executors/base.py`|modified|`21f630bbcda3588e0afa63cb27fc907f6ad2d50d5f01774e82707257924c9f9b`|
|`trading/executors/_buy_common.py`|modified|`7060315f1939b2bff0fd388ab5b6b66dcf2b45b5d50948a6a261d50f1fa07028`|
|`trading/order/qmt_context.py`|modified|`3099411922d5d6391417f32acc9e53399e2150a0a46bcef7af1a3316d1ff9ae5`|
|`tests/test_v1_s3_trigger_quote_safety_20261024.py`|created|`472724558ac74f518701c4b80248c2023b81339a14892825f801913cfd782ade`|

修前原件及hash：`before/`、`before-sha256.json`；最终闭包：`snapshot-sha256.json`；仅本write set增量：`S3-repair-only.diff`。

## 实测命令/JUnit

准备闭包：`python3 -B /Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/S3/prepare_snapshot.py`；该脚本仅复制审阅过的源码到S3，绝不执行生产入口。

- **before_diagnostic**：`/Users/chenyang/miniforge3/bin/python3 -B /Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/S3/run_safe_tests.py before --diagnostic`；exit=1，原生case分布 `{'passed': 0, 'failure': 5, 'error': 0, 'skipped': 0}`。
  - JUnit：`/Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/S3/before/diagnostic-junit.xml`；SHA256=`449e208f5a793e0fcb6c90b7bdb9db6ec0c29039d16c89587a157e886dbba6b7`。
- **after_diagnostic**：`/Users/chenyang/miniforge3/bin/python3 -B /Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/S3/run_safe_tests.py after --diagnostic`；exit=0，原生case分布 `{'passed': 5, 'failure': 0, 'error': 0, 'skipped': 0}`。
  - JUnit：`/Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/S3/after/diagnostic-junit.xml`；SHA256=`8b5f8855e0cfd803d6f81e11b9ce9e763a150954d99e7f384f25ff189caeaf20`。
- **after_safety**：`/Users/chenyang/miniforge3/bin/python3 -B /Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/S3/run_safe_tests.py after`；exit=0，原生case分布 `{'passed': 129, 'failure': 0, 'error': 0, 'skipped': 0}`。
  - JUnit：`/Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/S3/after/safety-junit.xml`；SHA256=`fa8e6e222f118fcf278923e0a3223694b4c1fcc25433b0640d76366e089f2a4c`。

日志/run元数据在同目录`*-pytest.log`及`*-run.json`。早期105/112用例迭代已保留在`iteration-1/2`；不与最终129重复累计。

## 正向链与隔离

- 实际WatchlistPlan完整序列化→session→真实dispatch/registry→五类买入wrapper→_buy_common→真实QMTContext dry_run边界均有正向意图用例；t_add具备合成已有持仓。
- 实际scan_entry_opportunities→session→共同执行器覆盖成功、daily/minute缺抓数、抓数异常、SISE异常；坏票不能传染同次正常邻票。
- 旧scan成功后空/失败重算失效；未突破即使simulate+force也拒绝；真实dispatcher在缺扫描时仍允许有合法bid/available的退出。
- 导入前审阅并替换settings/collector/账户状态/券商构造/日志依赖；全局audit hook拒绝网络/进程/数据库、凭据/生产读写及sandbox外写；测试局部守卫也记录被生产fallback吞掉的违例。
- 未运行全仓pytest；未改旧测试期待；未改Git、配置、凭据、cron、模型、技能、SOUL或生产数据。

## 未尽事项与接口待整合

- **S1/parent**：Integrate S1 shared authorization helper at final QMTContext.place_order; S3 did not create a competing consent rule. Preserve S3 kill-switch precedence, executable-book validation, sell availability and dry_run intent separation. S3 QMTContext still has no final plan/account consent object.
- **parent/tests**：Legacy RR test fixtures omit cash and scan and some expect simulate+force_trigger to bypass price/scan. Do not loosen gates or edit their assertions to green them; parent should coordinate authorized synthetic fixture completion. S3 did not execute or modify those old tests. Exact proposed-limit RR contract was preserved.
- **parent**：_sell_common remains outside S3 write set: it still computes fallback plan-trigger sell prices and simulated available-or1000. Missing book/unknown available now cannot cross actual QMTContext order boundary (validated with real context + fixture risk adapter). Remove misleading synthetic helper results only under coordinated ownership.
- **production_validation**：No live quotes, accounts, holdings databases, QMT/IB, network business, service, scheduler reload or real fills were exercised. No quote-age, liquidity-cap or seal-amount thresholds were invented. Active unsupported board/time predicates remain unsupported until explicitly implemented.

## 技能diff建议

`skill-diff-suggestions.md`仅为建议，未经主控确认未应用。
