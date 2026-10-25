# T1 独立裁决

- 旧 S3 十项不是生产穿透：未知 `synthetic_only` 原本就应先被授权拒绝。不能为了触达盘口门禁绕过 `_authorization_reason`。本次保留原十身份/五种坏值/买卖拒绝，改用已绑定的 `leader_breakout` 和 `stop_loss_break`。买真实最先拒因是 `buy_trigger_not_met`，卖是 `missing_or_invalid_executable_quote`；加零客户端和当前真实 journal 实现的 JSONL 全字典复读。
- 未知规则没有被删除：新增 live/dry_run × buy/sell × 有效盘口及五坏盘口共24项，所有未知规则继续先被真实授权拒绝；零客户端、零transport订单、真实拒绝journal。
- RR 三个正向隔离案例原100000×5%/100=50股，整手向下取整必须0；原旧强制100股不应恢复。本次仅这三例显式合成资产/现金200000，使同一5%/100元/原RR1.8参数足一手。其余FixtureContext仍默认100000，未改生产预算/阈值/报价/entry比例/任何RR或卖出观察断言。
- 另新增3种simulate/force组合，在原100000/5%/100元、RR合法、同日scan下明确`zero_buy_qty`、quantity0、零边界调用/事件；证明不靠别的拒因掩盖整手保护。
- 同日证据由测试显式提供。S3所有正常buy_allowed调用明确DATE、重复/本地错误测试的scan明确DATE；原replacement缺日坏输入仍原样。I1旧loader正例仅增加一个trade_date=DATE输入字段，所有断言/参数不变；新增无scan日期最终边界4例与loader1例仍拒绝，不补今天。
- RR cash/holdings/trade_date/同日scan全部在FixtureContext内；FINAL worker原RR自动适配已移除，不能用--rr-adapt。
- C1完成后的新文件已独立纳入runner，原生collect47项后固定47，未代改C1源码/测试。
- 原711不同case身份全部保留，原65subtests身份/结果完全一致。F1已有11项字节未改，不用新增case抵扣旧失败。
