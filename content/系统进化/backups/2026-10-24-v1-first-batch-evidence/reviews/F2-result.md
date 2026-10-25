# F2 独立最终安全审查

**结论：未确认I1新增的正常链可达退化；确认1项本批范围内调用链未闭环（扫描日期），另有1项既有低层sell能力边界不能称完整订单授权。不能实盘放行。**

原生独立断言 **86个不同case：80通过、6失败、0错误/跳过；exit=1，审计违例0**。6个失败均保留安全期望，实际合成transport接收到超出该期望的请求；没有改断言求绿，也没有真实委托/成交。早期迭代不累加。

## 必修阻断／本批范围内未闭环

### F2-01｜扫描成功未绑定授权交易日（P1，非已证I1新增回归）

- **位置**：`trading/watcher/session_context.py:27-31,62-81`只保存scan日期，不消费；`trading/order/qmt_context.py:286-298`、`trading/executors/_buy_common.py:79-93`只按symbol/style检查；`trading/load_plan.py:418-421`默认执行不先重建或校验扫描日期。
- **最小反例**：计划与授权context日期`20990105`，真实session输入`20990104`的同票`buy_breakout/sise_pass=true`，其余权限/风险/触发/RR均合法。直接`place_order`收到合成live `submitted buy 100@10`；无scan日期同样通过。真实`run_load_plan(..., mode='live')`默认dispatch整链也在异日scan下向合成transport提交100@10。
- **证据**：`test_counterexample_scan_date_must_match_authorized_plan[20990104/None]`两例，`test_counterexample_loader_dispatch_cannot_reuse_other_day_scan`一例；真实journal已readback，原生失败详情及独立保存记录见XML和`observations/`。
- **影响/可达性**：保留的默认loader执行API在同进程存在旧session时真实可达，不是仅恶意拼授权对象。正常watcher每轮clear→本轮scan→set，**未证明正常watcher同轮也复用异日结果**；不扩大此结论。
- **最小修改**：`buy_allowed`明确接收授权交易日并严格要求`scan_meta.trade_date`相同；两个买入消费者均传`qmt_ctx.trade_date`。缺日期不补“今天”，不新增年龄阈值，不影响卖出。详见`minimal-diff-suggestions.md`，未应用。

## 未证边界／低层sell职责裁决

### F2-02｜退出type存在不是精确订单许可（P1条件性最终边界项，**既有残余、非I1新增误卖**）

- **位置**：`qmt_context.py:252-258`的sell分支只查exit type存在和available；`:154-161`只核bid存在/正数，不核实际sell限价等于bid；`:214-221`随后转发调用参数。
- **三个最小反例**：绑定`stop_loss_break(trigger=9, quantity_pct=.1)`、total/available=1000：①last/bid=10仍低层提交100@10；②有效bid=8，却低层提交100@0.01；③规则10%，低层可改为1000@8。全部真实走最终授权、真实Amygdala、合成transport及scratch journal复读，均为`submitted`；不等于券商接受或成交。
- **职责与历史**：已读I1修前`before/trading/order/qmt_context.py:141-181`，同类缺口原本存在。当前生产源码扫描`place_order`调用只有`_buy_common.py:112`与`_sell_common.py:129`；正常live sell wrapper在`:46-50,105-129`做触发、规则算量并取bid。**额外正例已实测正常live stop wrapper在last10>stop9时skip且零transport订单。未证明当前正常watcher能绕过wrapper，不能把三个直调反例写成I1新引入的可达实盘误卖。**
- **最小建议**：最终有效bid后至少绑定sell限价等于该bid（不改变正常wrapper合同）。若本批要求“低层独立完整订单授权”，应由现有wrapper向最终边界绑定精确规则选择/已验证数量/报价意图，而非仅rule_type；不借机重造八类退出策略。若只承诺共同许可/退出名单/kill/有效bid/available，必须收窄最终授权声明。本项边界未闭环，不能称低层直调已完全安全。

## 已确认保护

1. **真实正向五类买入**：实际schema序列化→loader准备→watcher→dispatcher/registry→五个真实wrapper→共同执行器→真实QMTContext，在live模式均到合成transport；五wrapper直接调用正向也通过。`t_add_pullback`具合成存量持仓及真实T状态。市场scan输入与券商末端均合成，未执行真实行情采集。
2. **八类既有退出wrapper保留**：八类配置正向均到合成live transport；这只证明接线/未被新增授权一刀切拦截，不认证`exit_if_no_new_high`等委托watcher的真实市场条件。
3. **零/缺预算、禁新条件不误伤合法live退出**：四全局预算同时为0、同时缺失、全局`no_trade_conditions`买入条件激活、研究就绪字段缺失的legacy输入，分别经execution持仓与watch持仓投影运行，均在缺扫描情况下真正得到合成live `submitted sell`，journal `dry_run=false`，不是dry_run卖出充数。
4. **共同许可不能补授**：计划/账户自主=false、确认=true或mode=dry_run，最终买卖均拒；未绑定/错误对象拒绝且零客户端。绑定快照脱离原模型；模式与context日期不符拒绝。仅证明快照权限，不冒充经券商验证身份或连续撤权传播。
5. **买入范围与金额**：四全局及单票零/缺失预算均拒，未从schema正默认恢复授权；实际拟限价RR、缺扫描、未突破和调用者改买价均拒。正数总仓/单票/现金/持仓数/单规则金额/未知估值与日买次数、逐票次数经真实journal复读断言；拒绝发生在合成订单transport前。
6. **缺证不猜量、kill优先**：available缺失/bool/负数/非整数/NaN/无效字符串/0拒绝；只有last没有bid不能卖；kill优先于无授权对象。没有放宽有效可卖量来源。
7. **准备/执行唯一dispatch**：真实daemon两轮恰2context/2dispatch；loader准备无context/客户端；watcher reload两轮仍各一次dispatch。daemon市场刷新依赖被封死stub且`refresh_snapshot_every=0`，未运行生产刷新任务。

## 主控追加问题：no_trade／缺研究是否误伤live卖出

**有限审查内未证新增误伤，不应删门禁提权。** 必须区分三个语义：

| 输入 | 实测与合同裁决 |
|---|---|
| 预算零/缺失、`no_trade_conditions`等买入门禁；共同live许可仍有效 | 实际watcher+明确退出+有效bid/available可合成live卖出，正反观察池均通过 |
| `no_trade=true`、`decision_status=no_trade`、`production_ready=false`、`research_completion_passed=false`及meta同字段 | 已有loader要求整份安全dry_run/无自主/需确认；带live旗标原输入在loader、binder、watcher前门禁拒绝，零客户端。最终快照在place_order前重复拒绝sell与此合同一致，不是I1首创误伤 |
| 就绪字段**完全不存在** | `pipeline_artifacts.py:110-125`明确将absence视为legacy；本轮live退出正常。不将absence当“真实研究已完成”的证明 |

历史独立依据是实际读取I1修前loader`:79-107`，其no_trade与unready整份门禁已在；当前`:83-111`语义不变。`ExecutionAuthorization.validated_plan:124-128`确实早于sell分支拦截，但不能因此擅自给本来无整份live许可的预案补权。若要在整份安全发布之外运行存量live风险退出，需要另有明确既存许可合同，本F2未读取真实账户、不新建该权限。

## 日期与明确范围外

- 授权目前严格绑定的是**plan.trade_date==context.trade_date**及mode；**不是墙钟当前有效交易日/交易日历授权**。合成future日期`20990105`同样能到合成live transport已有characterization；不把本轮伪未来fixture当真实生产交易日认证。
- 跨线程/进程检查→提交→journal原子性、券商账户身份与在途/成交/撤单对账、提交未知结果恢复仍未闭环；既有保守预留可能与刷新后持仓重复占用，不新造额度平台。
- 报价龄阈值未配、真实报价时效、交易日/时段/跨日daemon与生产重载仍未认证，不暗设阈值。
- 本轮为有限独立安全审查，不是全仓pytest；最新联合回归由F1负责，本F2不把S1/S3/I1旧计数累计成当前全绿。

## 交付与复跑

所有新建文件只在`/Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/F2`；生产源码与仓库测试未改。

- `F2-result.json`：机器摘要、问题行号/最小复现、保护与未证边界。
- `app/tests/test_f2_final_safety.py`：独立断言/反例源码；逐字节复用I1合成fixture只为bootstrap，未复用其结论或将其71项计入F2。
- `f2-junit.xml`、`f2-pytest.log`、`f2-run.json`：原生结果、命令、exit=1、守卫违例空。
- `source-sha256.json`、`tested-all-sha256.json`、`source-current-comparison.json`：冻结34份生产源码+1份fixture及完整受测harness hash、最终与当前源码一致性；`native-case-index.json`按classname/name程序去重。
- `observations/`、`readback-observations-index.json`：关键订单结果与真实scratch journal全字段相等复读后的留存，包含六条失败反例。`artifact-sha256.json`为交付hash。
- `minimal-diff-suggestions.md`：仅建议，未改生产。`attempt1/2/3`保留早期扩覆盖/补readback证据的原生迭代，不计最终病例总数。

```sh
'/Users/chenyang/Downloads/demo/沧海巨浪/.venv/bin/python' -B /Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/F2/run_safe_tests.py
python3 -B /Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/F2/finalize_evidence.py
```

复跑第一条预期仍exit=1，因本F2只读生产且保留反例；不将6失败隐藏为xfail。审计钩子禁止生产/凭据读写、网络、DB、业务子进程与F2外写，关闭插件autoload、`--noconftest -p no:cacheprovider`、固定scratch basetemp与`-B`。

**未做实盘、未新开权限；无Git写/提交/push/分支/清理，无配置/.env/真实账户/账本/持仓读取，无QMT/IB/行情业务连接，无生产任务/服务/重载/推送，无技能/SOUL/cron/路径/阈值修改。**
