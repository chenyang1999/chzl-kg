# R6 局部补审四项修复 · 最终交接

## 结论

- 当前最终证据为本目录 **v5**：JUnit **94 passed / 0 failed / 0 error / 0 skipped**，pytest exit=0，11.42秒。本项57（原50身份+主控原函数4+直接边界3），共同summary28，native9。
- 原v3全部87个JUnit身份保留；原本项所有assert、参数化装饰器和函数签名未改。主控四函数与`r6-parent-review-20261029/parent_cases.py`逐函数AST相同，四项均通过。核对记录：`delivery-verification.json`。
- 使用v3逐字相同的收集前`sitecustomize.py`及子进程隔离。44个Python守卫回执、41个原生合成子进程全部有守卫，0未守卫、0违规。真实state/receipt/summary消费者及OS sandbox执行，未把校验器整体stub。
- 测前、测后及交接核查源码SHA相同；索引仍为`ac7ff7479ac6a4bc2f9f0bdbb50b45e405e26164731dd8dfbe0a5f21ba950143`。没有stage/commit/reset/stash。

## 本轮实际改动（相对v3仅三文件）

1. `scripts/research/pipeline_state.py`
   - 删除“已修订summary只能拒绝”的一次性限制。从当前真实消费者已接受的最新summary/R6继续补不同未完成对象/模式。
   - 六份原报告及终态state继续原身份/版本复用；最新R6接收的trade_date/run/stages/receipt扁平复制，不包含递归baseline，也不给六份旧报告盖新run回执。
   - 错/旧summary或R6基准在模型前拒绝；同请求已接收免模型返回、失败提案delivery-only重交付继续有效。
   - 后续模型OS禁写所有先前revision目录；接收前后核上次受信state版本。实际子进程尝试改先前state/原件被拒，失败发布后先前summary仍可由真实消费者读取，免模型重交付成功。
2. `scripts/research/pipeline_artifacts.py`
   - 仅新增hard_reject校验docs/10 §4非空字符串字段、`evidence`非空字符串数组、`source_agent=R6`、原mode6/7绑定；不能只提交code/mode标签。新增counter_arguments校验原模板中的反面主张、证据source/detail、建议与身份。只做结构/作用域绑定，不实施新风险语义或阈值。历史旧格式反面发现不补字段、不删改。
   - 指定未完成单元用本轮当前核验引用替换旧引用，不把旧null/错误指针并进completed。原始JSON/MD保存在不可变基线备份，未涉及/已完成单元和原全部发现保留。
   - 明确0且可核身份的已审数量随有据去重覆盖更新，不再等全部必要项完成才更新。未知旧数量不按0、不简单相加、不改类型；覆盖回执保留`evaluation_statistics`依据、可证下界及旧数身份未证。正式必要完成仍独立按四项全批覆盖计算。
3. `tests/pipeline/test_r6_local_revision.py`
   - 原正例新增反面发现仅补合法模板字段，原身份和assert全部保留。
   - 原样并入父控四函数；另补新增字段/类型与历史保留、未知统计不凑数、连续模式补审+失败免模型重交付+先前接收OS禁写三个直接边界测试。

本轮没有改另外三份允许源码（shell/build_summary/native_usage）；其v3实现随完整累计patch一起可回放。没有改skill/docs/SOUL、D1、价格引擎、已签事件、计划、资格、准入或预算。

## 保留的红测与修复检查点

- v3完整87绿及其源码原件未覆盖：`/Users/chenyang/.hermes/cache/scratch/r6-local-delivery-20261029-v3/`。
- 父控原四红未覆盖：`/Users/chenyang/.hermes/cache/scratch/r6-parent-review-20261029/first-parent-red/`（前三）与`count-parent-red/`（第四）。主控原函数文件未改。
- 本轮首个v4有界组执行为92绿/2红：扁平R6 owner漏带trade_date，被真实`verified_delivery`拒绝。只补该原身份字段后执行v5最终组94绿；v4原JUnit/log/source/guard均保留，未把其冒作成功。
- 历史关键文件SHA已写入`delivery-verification.json`，不抹旧红、不以本次绿测覆盖原隔离边界说明。

## 可复用命令与交付文件

仓库工作目录：`/Users/chenyang/Downloads/demo/沧海巨浪`。

本次实际最终命令：

```sh
.venv/bin/python -B /Users/chenyang/.hermes/cache/scratch/r6-local-delivery-20261029-v5/run_acceptance.py
```

主控复用时指定一个**全新scratch目录**，原runner拒绝覆盖已有JUnit：

```sh
R6_ACCEPTANCE_OUT=/Users/chenyang/.hermes/cache/scratch/r6-parent-final-reuse-20261029 \
  .venv/bin/python -B /Users/chenyang/.hermes/cache/scratch/r6-local-delivery-20261029-v5/run_acceptance.py
```

- `run_acceptance.py`：从v3原runner最小复制，只调整输出目录、证据保护和精确同版bootstrap复制；不是新runner平台。
- `command.json`：完整实际pytest argv、显式去认证白名单环境、cwd；无选择性排除，原本项全组+共同summary全28+原native指定9。
- `junit.xml` / `pytest.log` / `result.json`：真实最终运行。
- `source-before.json` / `source-after.json` / `tested-source/`：同版SHA与源件；`guards/`：每进程守卫。
- `repair-only.patch`：从原批准实施前五源码+新增本项test的完整累计增量，SHA256 `a4b7f0bafcd90119ab673a0cc775a6eabcdebd8133dda091ac9e28abb1d019cd`。
- `v3-to-final.patch`：本轮仅三文件增量，SHA256 `a3eb4b4f31c37c36a4874a701f198953bce7543ca0aae6e13eca67186c571425`。
- `verify_delivery.py` / `delivery-verification.json`：原87身份、原assert/签名/参数化、父控四AST、历史SHA、当前SHA及累计patch在scratch批准原件上的`git apply --check`/应用成功（所有6目标SHA精确一致）。该证据核查脚本不导入应用、不跑模型。

## 当前源码SHA（五个生产依赖）

| 路径 | SHA256 |
|---|---|
| scripts/research/pipeline_state.py | `7390067f5298fe69ebc97e3770a5b503101db5067de260dcf6e7f6f84bcf83ee` |
| scripts/research/pipeline_artifacts.py | `b7e1c4913ad564f96c2556da9fa180d121c7f8f71b7affc76ce28e9fd9f12384` |
| scripts/research/build_research_summary.py | `afd5a5b4ea09ed12f3ad4c3ad3fe456ae3312f01759c911d1e782d0669c67c44` |
| scripts/research/native_usage.py | `a1dd43f16d814ee9c75387103be2f07c4cd708d7aac8fe7df01eb3aaa7e7c1c0` |
| scripts/research/run_research_shell.sh | `b146e3923ceef93e6dc9953532c6afe69fa0319c7f040fdc34c29b80a8e3759b` |

本项test：`bfafcb87a13bee6722e3c89b69aa50df18d09edb688f0003384327e7c1199b3a`。获批skill/docs SHA仍分别为`b6ab02eaf3f7b7b6ebb775d3a5b5f38cb4009e715494e14236b4ca00019e1d25` / `3d73fb06585f629bc206c4ad4dcbb1c787982a101d91544af3455e56ce605bb9`。

## 剩余未证边界

- 没有真实模型、行情、账户、业务DB、网络服务、生产补跑或自然采用证据；未用认证/.env。全部对象与模型输出为合成运输。
- 校验只证明结构/输入绑定/指针存在；反面语义、同票关联、事实观察窗口由R6负责。未知旧数量身份仍未证，只披露下界，不宣称精确全量总账。
- 六份原资料版本不变；原材料缺失不抓新数，仍应incomplete。既有有效硬拒、计划/原池/零预算不因研究补齐而解除。
- 继承v3已测macOS sandbox-exec依赖；没有验证Linux替代或任意断电跨文件事务。合作锁及版本检查不能承诺不合作写者在最后检查后的任意并发行为。
- 未重跑无关40/54或D1/价格/事件队列；父控另负责其独立分支。未发现本轮目标及共同依赖并行漂移。
- 证据留scratch，归档和主控独立最终接收由父控办理。本轮不新增技能变更；可复用流程沿现有隔离/身份/红绿留证纪律，不另造技能或平台。
