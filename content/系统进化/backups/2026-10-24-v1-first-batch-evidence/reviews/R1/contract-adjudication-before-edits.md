# R1 旧合同裁决（修改测试前）

- 独立解析 S2 pre/post 原生 XML、读取实现增量与原件，并在 R1 独立复制闭包重跑：pre 三旧组156通过、诊断2失败；post 三旧组155通过1失败、诊断2通过、新增34通过。两个历史诊断均可复现，历史driver唯一失败仍是第365行；第364行未失败。
- `fractional_partial_sell_retry_unsupported_requires_reassessment` 是旧无冻结目标时的保护性拒绝；新冻结目标5000且累计5000完成，与余仓5000不是同一概念。新原因 `fractional_exit_stage_completed` 正确表达不应重复卖档位。精确字符串全仓源码/文档消费者扫描仅找到driver发出和这一旧测试断言，无业务分支依赖。裁决：允许迁移原因码断言，必须保留原code==2、不新成交、余仓5000，并增加目标/完成状态/订单及账本不变验证。
- S1 冻结 after 原生XML及R1重跑均为旧staging56通过1失败(:424)；真实daemon→loader→watcher→dispatcher回归93通过，其中两轮总分派2、context2明确通过。源码显示旧daemon原先每轮loader先分派、watcher再分派；新daemon显式dispatch=False，watcher唯一执行。旧fake_watcher未调用分派，统计0不代表生产丢分派。裁决：过期mock合同，许可仅迁移该用例fixture，保留canonical刷新/loaded消费/mode/reload/总dispatch2/staged==second等断言，并增强真实watcher和真实dispatcher调用及loader准备无分派验证。
- 改前原字节与SHA256保留至original-tests/和original-test-hashes.json。原生失败XML和R1重现保留不覆盖；不删例、skip/xfail、不改其他旧测试、不改生产源码。
- 上述是两条旧契约的裁决，不是对所有新代码或最终I1集成的生产放行；独立补充反例与最终测试仍须完成。
