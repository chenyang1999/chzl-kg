# S1｜订单入口权限、零预算与唯一分派修复

**已落地5个授权源码/测试文件。S1隔离验收93通过，0失败/错误/跳过；旧staging套件56通过、1项mock合同断言失败，未修改旧测试。未进行生产重载或真实账户操作。**

## 范围与恢复点

- 原字节/hash：`originals/`、`baseline.json`；仅增量diff：`S1-repair-only.diff`。已存在的工作树改动不并入该增量。
- 可选授权路径`src/execute/load_plan.py`实际不存在，未创建。共享schema、account_config、dispatch及QMTContext均未改。
- 验收是冻结的工作树依赖闭包，不冒称干净Git版本；受测source manifest逐项hash与最终源码一致。

## 逐问题修前/修后

### S1-RISK（D04）

- **修前：** 账户字典覆盖正式预算：target_total_position_pct=0 被账户1覆盖；其余次数/持仓上限同样可扩大。禁区/ST/止损限制也可被账户覆盖。
- **修后：** 四个既有买入上限取明确值交集；禁区有序并集；ST取或；可选硬止损的0/None沿用禁用语义，不可抹掉另一方有效保护；杀开关冲突显式拒绝。
- **证据：** before/s1-junit.xml: formal_caps_are_intersections 的8项与 restriction semantics 源码；after:16项交集+可选止损4项与并集正例。
- **位置：** `trading/execution_authorization.py:20-81`；`trading/load_plan.py:182-209`

### S1-CONSENT（D03）

- **修前：** watcher把 --mode live 直接当dry_run=False，未查计划或账户自主/确认权限；无reload的6个拒绝用例均反例失败。
- **修后：** loader与watcher共享纯模式门禁；live仅请求，账户与计划共同许可；unknown mode与非布尔权限拒绝于QMT构造之前。显式dry_run仍可收紧。
- **证据：** before/s1-junit.xml: live_request_never_supplies_consent(False)6项；after全部12项拒绝及6项合法schema序列化正例。
- **位置：** `trading/execution_authorization.py:84-103`；`trading/load_plan.py:364-373`；`trading/watcher/run_once.py:42-75`

### S1-SINGLE-DISPATCH（D05）

- **修前：** 真实隔离daemon两轮实际调用dispatcher4次；reload也先loader执行后watcher再执行。
- **修后：** run_load_plan新增dispatch=False准备模式：不构造QMT、不读持仓、不写/重置positions、不执行规则；默认dispatch=True保留旧调用者。daemon准备后watcher唯一分派，两轮2次context/dispatch。
- **证据：** before/s1-junit.xml: daemon两轮assert4==2；after:准备无外效、旧loader默认单分派、watcher reload单分派及daemon两轮2分派。
- **位置：** `trading/load_plan.py:340-415`；`trading/watcher/run_once.py:47-50,105`；`src/execute/watcher_daemon.py:167-170`

### S1-MISSING-UNKNOWN（D04）

- **修前：** 全量model_dump写出schema正值默认；账户风险覆盖可填入计划缺失预算；风险extra=allow导致未知谓词未被执行仍继续。未知风险2项反例失败。
- **修后：** _plan_payload按risk字段显式性序列化，缺失不上补正值；四个预算missing/zero分别留理由并禁买。显式null/bool/string/非有限/越界拒绝；未知风险字段拒绝，不猜min/max语义。
- **证据：** after:4项missing→落盘→watcher再读、14项异常比例、5项次数异常、2项未知风险；before missing为静态源码反例，不把新dispatch API缺失算产品反例。
- **位置：** `trading/load_plan.py:43-47,121,198-208,307-308`；`trading/execution_authorization.py:20-81`

### S1-STOCK-CONSENT（D03）

- **修前：** apply_qmt_overrides按全局自主许可把auto_trade_enabled改True，还对持仓退出状态强开；2个逐票许可拒绝反例失败。
- **修后：** 持仓和账户不补逐票买入许可；原auto=false或逐票requires_confirmation=true保持禁买。合法卖出不使用auto买入开关。
- **证据：** before及after: stock_consent_cannot_be_granted_by_holdings_or_global_flags 的2项。
- **位置：** `trading/load_plan.py:203-208,260-280`

### S1-BUY-SELL（D09/D04）

- **修前：** 买入禁区合规剔除整行/观察池不运行退出，已有明确退出规则的持仓可能消失；次数零预算被dispatcher忽略（只有总仓0有原生买入门禁）。
- **修后：** 零/缺失买入预算与合法退出分离；买入禁区行有退出时保留exit-only。held watch行有明确退出规则时仅投影exit-only至dispatcher执行池，原观察行仍在；不持仓不投影，不增加买入资格。
- **证据：** before:零预算8项均失败（1项重复卖出分派、3项次数零仍买、4项观察持仓未退出），另有symbol_buy_compliance两项；after:8项零预算分池、2项禁区合法退出、非持仓观察不提权、no_trade保留研究/退出。规则执行及可卖量最终认证属S2/S3。
- **位置：** `trading/load_plan.py:221-249,272-280`

### S1-CURRENT-SOURCE（D03/D05）

- **修前：** 当前canonical为零预算或dry_run时直接watcher仍读旧live/正预算loaded：分别产生合成buy意图或未拒绝live。
- **修后：** canonical存在时即便reload=False也先准备当前计划；无canonical的同日runtime-only输入保留旧兼容路径，但仍严格重查账户及计划授权。
- **证据：** before及after: direct_watcher_canonical两项；坏canonical不执行旧loaded。
- **位置：** `trading/watcher/run_once.py:44-57`

### S1-TSTATE-RAW-ACCOUNT（D05/D03）

- **修前：** 每次loader重置同日T状态，t_add_done=True/t_add_qty=100被清成False/0；旧账户reader把字符串false等按truthiness处理。
- **修后：** 仅日期不同时使用既有TState日切；同日完成状态保持。局部严格账户reader先查原始权限类型，再保留该已验证快照的mode/flags/risk，未改共享account_config.py或任何真实配置。
- **证据：** before及after: same_day_loader一项与raw_account_consent三项；after合法原始账户正例。
- **位置：** `trading/load_plan.py:26-40,393-407`；`trading/watcher/run_once.py:77-92`

## 真实隔离回归

| 分组 | 原生JUnit病例 | 通过 | 失败 | 错误 | 跳过 | exit |
|---|---:|---:|---:|---:|---:|---:|
| repair acceptance | 93 | 93 | 0 | 0 | 0 | 0 |
| unchanged legacy staging suite | 57 | 56 | 1 | 0 | 0 | 1 |
| pre-repair behavioural counterexamples | 49 | 14 | 35 | 0 | 0 | 1 |

- 修前35个失败是保留原源码的行为反例，不计修后产品失败；修前同时有14个正常控制通过，44项未纳入该反例选择。
- 受测真实链：schema完整序列化→loader/账户交集→watcher→daemon→真实dispatcher；规则函数与QMT/扫描/行情为recording fakes，合法卖出用明确合成持仓/可卖量。没有把合成意图称为成交。
- 所有roots/TMPDIR在scratch，禁插件自动加载/全仓collection，审计钩子禁止生产读写、凭据、DB、网络和子进程；最终三组guard violations均0。
- 初次harness缺scratch目录、OS库版本读取被误拦、修前新fixture尚不兼容旧接口、旧套件priming改变cwd的失败日志/原生JUnit均保留。详见JSON failed_harness_history。

### 可复跑命令（项目.venv、-B）

```sh
'/Users/chenyang/Downloads/demo/沧海巨浪/.venv/bin/python' -B /Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/S1/after/run_safe_tests.py
```
原生JUnit：`after/s1-junit.xml`；命令/exit/审计：`after/s1-run.json`。

```sh
'/Users/chenyang/Downloads/demo/沧海巨浪/.venv/bin/python' -B /Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/S1/after/run_safe_tests.py --old-staging
```
原生JUnit：`after/old-staging-junit.xml`；命令/exit/审计：`after/old-staging-run.json`。

```sh
'/Users/chenyang/Downloads/demo/沧海巨浪/.venv/bin/python' -B /Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/S1/before/run_safe_tests.py --diagnostic-all
```
原生JUnit：`before/s1-junit.xml`；命令/exit/审计：`before/s1-run.json`。

## 修改hash（与tested manifest一致）

| 路径 | 操作 | 修前SHA256 | 修后/受测SHA256 |
|---|---|---|---|
| `trading/load_plan.py` | modified | `40bddfcb8573ffa5cd35cf592fd6bba7c9fdb3291fd620358fc4e228be0e26cb` | `77cd603b077d28ff183084eeebbc9c0ce1aa1db4b5c2f9e885998a0ca182e71b` |
| `trading/watcher/run_once.py` | modified | `23fe3981c64463f99fcbf55fa5a68d406c4294e4ad528d4d843a4e90dcf4678c` | `42b70b3169c1b6c26d16d1e30512fe3ae8880f25a815dda19ece60955bf2a4e7` |
| `src/execute/watcher_daemon.py` | modified | `a7713d4c2e9a344704a7182ef0cff43345a8946517b5428fb0c7ab766c28b96e` | `c304050e486a893d55de8821f36f54d66dc5265f024921066e2d3071e7caae9f` |
| `trading/execution_authorization.py` | created | `absent` | `bdbca8b7ce6dd067b9e75e12649009061a047a6dc68dd758bae4fe1affc613a4` |
| `tests/test_v1_s1_execution_boundaries_20261024.py` | created | `absent` | `fb7b7e4138d5cf79d2754a7699d94df875d5b95e39c16e9b37295515214bb81a` |

## 未尽项与集成建议

1. 未改trading/order/qmt_context.py（S3所有）。最终place_order还需绑定受验证计划/账户快照，不能把入口检查误当低层最终订单授权；正数总仓/次数/单票上限的实际占用与成交后约束仍须S3执行边界闭环。
2. 给主控/S3接口建议：复用resolve_execution_mode、merge_risk_limits、buy_budget_reasons；QMTContext需显式接收validated plan/account/effective_mode授权上下文。买入另查缺失/零预算与实际使用量；卖出仅跳过买入预算，不跳过live许可、杀开关、报价及真实available_qty。未越权改S3源码。
3. 旧staging套件仍有1项失败：其fake_watcher不执行dispatch，却继续断言loader的dispatch记录为2；新合同loader只准备，因此记录为0。新套件贯通真实daemon→loader→watcher→dispatcher断言总2。旧测试文件逐字节未改；需主控按新装载/执行合同单独协调回归测试所有者。
4. run_load_plan默认仍执行一次（兼容已有CLI/调用者），不是纯装载函数；准备调用必须显式dispatch=False。加载模块本身仍沿用现有src.settings的导入行为，本次未认证其无.env副作用；隔离测试以stub替代真实settings，未读取.env。
5. 未知风险谓词及不可表示的两个杀开关路径会显式拒绝整个装载；未猜测策略语义，也未把未知状态伪装可交易。
6. tighten_stop_loss既有计算以stop_loss为cost_hint，未证明能落实account_hard_stop_loss_pct的实际止损保护；此处只修合并不放宽，不声称该独立算法已修复。
7. 最终报价可靠性/年龄/盘口量/可卖量、真实T+1、委托确认、幂等、跨进程锁、daemon交易日/午休/跨日规则不在S1修复范围。未新选仓位、RR或报价年龄阈值。
8. 没有Git写/提交/切分支/清理/推送，没有改配置、模型、cron、SOUL、技能、共享schema；没有真实QMT/IB/行情/网络/服务/任务/推送，没有打开真实持仓或成交库，未重载生产进程。

## 技能差异（仅建议、未应用）

`S1-skill-proposal.diff`：供主控审阅签核；本子任务没有改任何技能。

## 验收边界

不是生产放行：没有真实报价、真实委托/成交、驻留重载、全仓pytest或跨组集成回归。最终订单边界与跨组联合验收由主控协调。
