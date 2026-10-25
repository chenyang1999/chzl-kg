# T1 测试契约迁移结果

**实测14组：790个不同case全部通过，failure/error/skip=0；另65个原subtests全过。原711身份全部保留，原13失败逐身份真实转通过；未改生产保护。**

## 原生分组

| 组 | case | pass |
|---|---:|---:|
| s1 | 93 | 93 |
| i1 | 71 | 71 |
| paper | 156 | 156 |
| s2diagnostic | 2 | 2 |
| s2new | 34 | 34 |
| r1 | 12 | 12 |
| staging | 57 | 57 |
| s3 | 129 | 129 |
| s3diagnostic | 5 | 5 |
| rrparent | 32 | 32 |
| rrscope | 109 | 109 |
| f1 | 11 | 11 |
| closeout | 32 | 32 |
| c1 | 47 | 47 |

## 修改与裁决

详见`adjudication.md`、`incremental.diff`、`assertion-preservation.json`。仓库只修改S3该方法/必要DATE及真实journal依赖fixture、RR FixtureContext和三例资金fixture、I1 loader正例的一行明确DATE；新增`tests/test_v1_regression_contract_closeout_20261024.py`32例。F1现有11例原字节不变。未知规则24例、原整手不足3例、缺扫描日期5例均为新增独立负向覆盖。三例200000仅为合成RR隔离资金，不是生产预算提高；原100000仍默认且专门负测。

维护FINAL runner/worker：移除RR隐式适配；原12组计数原封保留；新增closeout32与C1 47均先原生collect再固定；额外冻结`case-identity-contract.json`，同时核对完整collection/JUnit身份、数量、重复及禁skip。固定身份来自原711历史与新增79原生实测，不是改数字掩缺例。

## 本轮证据与源码版本

- 执行：`/Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/FINAL/T1-final-contract-20261024T144934Z-afa9ca74`，直接runner退出0。
- 原生全组collection：`/Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/FINAL/T1-final-collection-20261024T144944Z-07866665`，collected=790，退出0。
- 两组首次新组collect以占位expected0运行，父runner如实退出1并保留coverage差异；原生pytest collection均exit0。随后按真实32/47固定，历史目录未覆盖。
- 当前冻结源码/分组副本/执行结束工作树hash一致；受测生产与父控旧证据相比仅C1三文件变化，本T1没写生产代码。`tested-source-manifest.json`明确这次实际源码。
- `native/`原样复制14组JUnit、log、run命令、收集身份与失败receipts；`real-commands.json`提供精确父/子命令。
- `originals/`与`original-hashes.json`是改前原件；`before-failure-evidence/`和`before-13-failures.json`保留父控13失败及旧脚本。
- `case-identities-before.json`/`after.json`/CSV、`case-identity-comparison.json`和`subtest-identity-comparison.json`程序证明无删例、无身份替换、无subtest充case。
- 所有子进程audit violations=[]；-B、禁autoload、noconftest、无cacheprovider、scratch basetemp、仅合成末端。

## 父控统一复跑

```sh
'/Users/chenyang/Downloads/demo/沧海巨浪/.venv/bin/python' -B '/Users/chenyang/.hermes/cache/scratch/v1-repair-20261024/FINAL/run_parent_verification.py'
```

每次都从当前白名单源码新冻结，不复用本轮输出；默认14组790项，另65subtests，不再需要RR harness适配。C1组已加入，无需父控再手工添加。**这里只承诺上述实际冻结版本；后续源码改动须父控统一重跑。不等于实盘放行、券商委托/成交或全仓审计。**

未执行Git写/提交/推送、真实业务/账户/账本/凭据/网络/重载/推送，未改配置/skill/SOUL/cron/生产路径/阈值。没有skip/xfail/删例，没有绕过或mock最终授权。
