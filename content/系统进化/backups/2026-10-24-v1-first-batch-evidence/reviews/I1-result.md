# I1 最终授权边界与跨 S1/S3 集成

## 结论

授权写集合内修复完成：**新整链用例71通过；S1原文件回归93通过；两组0失败/错误/跳过、审计违例0。不是实盘放行。** 原生JUnit独立解析合计164通过；早期57/69用例迭代不重复计数。

本次只改4份授权源码，新增1份授权测试；未改S1/S2/S3既有测试断言、paper、配置、SOUL、技能或cron。改前原字节及SHA256在`before/`与`before-sha256.json`，仅本轮增量为`I1-repair-only.diff`。

## 实际实现

- `trading/execution_authorization.py`：沿用`resolve_execution_mode`、`merge_risk_limits`、`buy_budget_reasons`。新增不可变、脱离原件的计划/账户JSON快照及绑定函数；最终重新检查模式、日期、显式权限、风险交集与就绪标记。live请求不补任何许可，dry_run也不补买入自主/确认权限。
- `trading/load_plan.py`、`trading/watcher/run_once.py`：真实QMTContext显式接收绑定；持仓观察票exit-only投影后重新绑定当前计划。保留`dispatch=False`准备、每轮唯一dispatcher、坏正式文件拒绝、限制版本不自动晋升、同日T状态等现有保护。缺省单票上限不再经schema默认变成正值预算。
- `trading/order/qmt_context.py`：`place_order`保留kill优先，然后执行最终授权；未绑定/类型不对/内容无效/模式或日期不匹配均在任何订单客户端调用前拒绝。买入检查执行池、逐票自主/确认、四个显式全局买入预算、计划门禁、禁区/ST、唯一计划规则、实际拟限价RR、原触发谓词与扫描证据。最终精确限价不得由低层调用任意改写。
- 合法明确卖出仅跳过**买入**预算、买入auto与扫描门禁；仍要共同live许可、明确计划退出规则、kill、有效bid与`available_qty`，后续真实Amygdala检查照常。
- 正数额度使用现有6个字段，不新增阈值或配置平台。读既有模式/日期隔离订单JSONL，只计该模式已接收的buy（live=`submitted`、dry_run=`dry_run`），复读后执行日买入/逐票买入次数、持仓数、全局总仓、单票仓、单规则金额、现金检查。已接收买入名义金额保守预留；拒绝与dry_run不占用live次数。坏账本/未知持仓估值拒绝买入，不拦合法退出。

## 真实隔离链与证据

`WatchlistPlan`实际模型序列化 → 正式计划原子交接/校验 → loader准备 → watcher → 真实dispatcher/registry → 真实executor → 真实QMTContext → 合成末端transport → 真实scratch JSONL复读。

仅替换`src.settings`路径根、市场扫描输入及QMT末端transport；账户YAML严格reader、schema、权限交集、风控Amygdala、持仓状态、规则/触发/RR/扫描门禁及journal实现均为审阅后源码副本。没有全链mock替代。输出中的`submitted`只代表**合成transport响应记录**，不是券商委托或成交，也没有paper fills。

71项覆盖：合法有授权买入（reload开/关）、loader旧默认一次分派、纯准备无context/客户端、两轮两次dispatch及日次数上限、计划/账户各模式与许可拒绝、逐票auto/确认拒绝、缺失/无效live上下文双向零客户端调用、最终快照再验证、四种零/缺失预算、缺失/零单票上限、观察票、缺扫描、未突破、实际限价RR不达标、零预算/缺扫描合法卖、卖出kill/available/bid/live/退出规则拒绝、正数实际金额与次数边界、重建context后计数及预留、dry_run/force不授权、坏账本隔离、after_close只读不误伤、正式坏文件拒绝、不晋升及同日T状态保持。

|本轮分组|通过|失败|错误|跳过|JUnit|
|---|---:|---:|---:|---:|---|
|新实际整链/最终边界|71|0|0|0|`after/i1-junit.xml`|
|S1逐字节未改原测试|93|0|0|0|`s1-regression/s1-junit.xml`|

`after/i1-run.json`、`s1-regression/s1-run.json`保留真实命令、exit=0、空审计违例。34份整链源码hash：`snapshot-sha256.json`；两组全部源码与harness完整受测hash：`tested-all-sha256.json`。最终脚本核对当前工作树源码、冻结副本与受测manifest完全一致。

### 可复跑命令

```sh
python3 -B /Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/I1/prepare_snapshot.py
'/Users/chenyang/Downloads/demo/沧海巨浪/.venv/bin/python' -B /Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/I1/run_safe_tests.py
python3 -B /Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/I1/prepare_s1_regression.py
'/Users/chenyang/Downloads/demo/沧海巨浪/.venv/bin/python' -B /Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/I1/s1-regression/run_safe_tests.py
python3 -B /Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/I1/finalize_evidence.py
```

审计守卫阻止网络、DB、子进程、凭据/生产读写、sandbox外写；只允许解释器/已安装库读取。插件自动装载关闭，`--noconftest -p no:cacheprovider`、指定测试文件与scratch basetemp，全部`-B`。

## 全部生产构造/调用追查

1. `trading/load_plan.py:389`：订单上下文，已绑定。
2. `trading/watcher/run_once.py:69`：订单上下文，已绑定。
3. `trading/after_close.py:14`：仅refresh_holdings/状态同步，不调用place_order；保持可不绑定，真实函数合成隔离用例通过。没有将授权门禁错误放进所有`_ensure_client`读取操作。
4. 最终订单调用仅`trading/executors/_buy_common.py:112`、`_sell_common.py:129`；二者都落入新最终边界，未改所有权外源码。
5. `scripts/trading_tools.py:78`同名函数只是直接返回`submitted`字典的旧stub，不是QMTContext或券商调用；未执行、未改，也不将该stub结果称为真实委托。
6. S3既有测试自己构造未绑定context；I1未将其历史129项冒充本次通过。若联合全套验收，要在scratch专用fixture显式绑定有效计划/账户再认证，不能改其断言或削弱最终门禁。其他两份旧测试/paper由并行所有者处理，本次未触碰。

## 未闭环：明确阻断实盘

- 本地journal检查→提交→追加不是跨线程/跨进程原子事务；其他进程或手工订单不一定在此日志中。本轮测试仅单进程隔离，不能保证账户全局并发上限。
- 尚无券商在途、成交、撤单对账和提交未知结果恢复。保守预留不因未验证撤单/成交释放，也可能与刷新后持仓重复占用，可能更早拒买；不能称为精确可用券商额度。需要真实订单网关/对账所有者后续闭环，不在I1里另造额度平台。
- 绑定的是本轮严格读取的AccountConfig许可快照，不是经券商验证的账户身份，也不是跨进程连续撤权机制。入口每轮重读且最终重验快照，不能证明生产账户身份/撤权传播闭环。
- S3原129用例未在新上下文合同下完整再认证。不存在“原测试已全绿”的暗示；本轮实际可核验为71+93。
- 未设置新仓位/RR/报价年龄/流动性阈值；未认证真实报价时效、交易日/时段、委托确认、真实成交或生产服务重载。S1/S3报告既有的其他范围外算法缺口不因本轮集成消失。

不读.env/凭据/真实账户/真实持仓和成交库，不连QMT/IB/行情业务，不跑生产任务、不重载、不推送、不做任何Git写/提交/分支/推送。实际改动名单及修前/后hash见`I1-result.json`。技能只能建议，`I1-skill-proposal.diff`未应用。
