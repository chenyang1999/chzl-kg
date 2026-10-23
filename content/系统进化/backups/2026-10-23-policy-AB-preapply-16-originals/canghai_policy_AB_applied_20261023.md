# A/B 政策包实际应用与隔离验收 · 2026-10-23

## 结论
- A 后 B 顺序应用，18 包内条目/16 不同目标，最终全部字节 SHA256 与已签提案精确一致。
- 原件 16 份已备份，scratch 副本回滚演练 16/16；未在生产回滚。
- 隔离 pytest：38 passed，exit 0；native JUnit 38 唯一 case，0 failed/error/skipped。
- 两个 profile 的真实 Hermes `load_soul_md` 均返回各自当前 SOUL 完整 strip 后内容；只验加载，无生产新会话。
- 禁新仓保留真实研究观察、不授买点/自动权限；有效零、R6 complete-only/hard_reject、nullable namespace 兼容均有契约或纯函数测试。

## 修改清单（精确哈希及回滚原件）
| target | before SHA256 | after SHA256 | backup |
|---|---|---|---|
| `/Users/chenyang/Downloads/demo/沧海巨浪/docs/10-契约-研究汇总.md` | `99d6d74d8c0abb7d04cd8d74e81035e4eee567588dc29c206509e1ab273cdefb` | `14e57f6ed5e6292aed312973fbfe37cd2fa34efebdc0a914fbb4b9a4e58229e9` | `/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/系统进化/backups/2026-10-23-policy-AB-preapply-16-originals/01/10-契约-研究汇总.md` |
| `/Users/chenyang/Downloads/demo/沧海巨浪/docs/11-契约-盘前预案.md` | `c785655b63a9be5027bbf829f1023b3f3d7b8709819c133d47ea533c4de30652` | `bee1b1fce3a336afac195c3b6a7362054a9ec01c7193781f2d3babfe02d7f9e2` | `/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/系统进化/backups/2026-10-23-policy-AB-preapply-16-originals/02/11-契约-盘前预案.md` |
| `/Users/chenyang/Downloads/demo/沧海巨浪/skills/analyze_devil_advocate_v1/SKILL.md` | `d9721b4145d3ef9c9832a55ad96f56ce83bc5b173c406d49e424d6714cdd1188` | `aeee4559edbb1d095759202b03c33e50dd9fc3a5c6581a254d5d8124b67d0e0d` | `/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/系统进化/backups/2026-10-23-policy-AB-preapply-16-originals/03/SKILL.md` |
| `/Users/chenyang/Downloads/demo/沧海巨浪/skills/auction_amendment_v1/SKILL.md` | `bbff34144e521172d78b38d28f4c4abf555906348d291ba6a4d2719a0114e878` | `d1a6ac6d276774946e4e450017cdcd526895dd626776c0a61809496242b20a6c` | `/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/系统进化/backups/2026-10-23-policy-AB-preapply-16-originals/04/SKILL.md` |
| `/Users/chenyang/Downloads/demo/沧海巨浪/skills/fetch_auction_snapshot_v1/SKILL.md` | `dff225e2c70b77302ac64fe862ac0b3eb937ba7122376ad679494115a71bc478` | `013e8c9d8eb351fdd8695119df5ff26fbe2f4dff52b5e8a8d8bf397802940965` | `/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/系统进化/backups/2026-10-23-policy-AB-preapply-16-originals/05/SKILL.md` |
| `/Users/chenyang/Downloads/demo/沧海巨浪/skills/main_decision_v1/SKILL.md` | `0f0af85c59761520b8616678a53b001c9851fd0737004a719f78ce240c2baf8d` | `b3e8d6d49e42b84a80613e4e63f7f5a578b95a6c1ab009e606cc2eacc6627876` | `/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/系统进化/backups/2026-10-23-policy-AB-preapply-16-originals/06/SKILL.md` |
| `/Users/chenyang/Downloads/demo/沧海巨浪/skills/research_orchestrator_v1/SKILL.md` | `3171c4bc9b7515a30ec6d461799fb7c63eedf97b7e9ef68a9778216e4aed94e3` | `bb6a99cf16c0d55d511e42e75659cf44684090d7d79441679e6b66e428bbe200` | `/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/系统进化/backups/2026-10-23-policy-AB-preapply-16-originals/07/SKILL.md` |
| `/Users/chenyang/Downloads/demo/沧海巨浪/tests/checks/check_md_namespace.py` | `7cc99ec0423c303785bbcd0dcc02e7186d5b9f39a1e06fd22e3454ae367d8040` | `ea1651ee12a058355071d6b943f38b65a6f0687c764942eb03dde5e5f1140634` | `/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/系统进化/backups/2026-10-23-policy-AB-preapply-16-originals/08/check_md_namespace.py` |
| `/Users/chenyang/.hermes/profiles/canghai-plan/SOUL.md` | `5c6c6c28e72a7b1970a852b3d16f2b033b06d5c0bc10c955cc16bb51ae13e3a2` | `2a1497baba4db228927ac7376b32453044d0126c4378e149c7152fc8b64364b1` | `/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/系统进化/backups/2026-10-23-policy-AB-preapply-16-originals/09/SOUL.md` |
| `/Users/chenyang/.hermes/profiles/canghai-research/SOUL.md` | `9dd5bf534052fa41b2762fa999899a87d3f58b65afe76234b10e4d3fa185fb31` | `f3b1d30e494f42ca6efd037a6d793a309c7202c957e043c6a0bafa6a59eb5d35` | `/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/系统进化/backups/2026-10-23-policy-AB-preapply-16-originals/10/SOUL.md` |
| `/Users/chenyang/Downloads/demo/沧海巨浪/skills/_archive/filter_leader_v1/SKILL.md` | `794e312b5bec04787b93b3c6e262b1e6f0fd8dda2a56d2e534b2ea89c3744f03` | `f14c371ab1727af7d1649c60c4da00b54ff6d1b2c60a0f6b125553cd145f845b` | `/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/系统进化/backups/2026-10-23-policy-AB-preapply-16-originals/11/SKILL.md` |
| `/Users/chenyang/Downloads/demo/沧海巨浪/skills/analyze_main_sectors_v1/SKILL.md` | `f8326ea438d7da792a072ee91aef9d4450c87b0b3789c91dba90278389b674c7` | `e327944d4a9a51989b6a6582a1d25a5521e61261170adf14cd996a265dd8aea0` | `/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/系统进化/backups/2026-10-23-policy-AB-preapply-16-originals/12/SKILL.md` |
| `/Users/chenyang/Downloads/demo/沧海巨浪/skills/analyze_stock_profile_v1/SKILL.md` | `a180541fe70ce174e48e181a9e4bc62ea99c63e87f05386b107a290af926d92a` | `3a69092fc6950939f6c9e563031c1df4ca53088b0ffaf5d51240d8e5482da614` | `/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/系统进化/backups/2026-10-23-policy-AB-preapply-16-originals/13/SKILL.md` |
| `/Users/chenyang/Downloads/demo/沧海巨浪/skills/analyze_style_v1/SKILL.md` | `6097bb83402d836101de3348446129d71e6d3ff337b20dc6b9304455e07c6311` | `40ef3105c0495223b52c510302ee4fa452e5bf43b675830c373da44f326faff6` | `/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/系统进化/backups/2026-10-23-policy-AB-preapply-16-originals/14/SKILL.md` |
| `/Users/chenyang/Downloads/demo/沧海巨浪/skills/short_line_thinking_v1/SKILL.md` | `dad7f28dad6779ee40b16ed1cfcdd39348435c5407f63968dfb711e306c49c54` | `aab4dd21f870e1cc13c9920ca8d10731e9ec627966874f0c5cffc353a2a94994` | `/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/系统进化/backups/2026-10-23-policy-AB-preapply-16-originals/15/SKILL.md` |
| `/Users/chenyang/Downloads/demo/沧海巨浪/skills/trade_discipline_v1/SKILL.md` | `076853d910830a033ed05f94830c63debbeb4dea2f972a34094113e4e35e6edf` | `6ee0609a07e3fd93e11ba3162f47455906641ad4d5ce93238de27ab4fb9ba6e1` | `/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/系统进化/backups/2026-10-23-policy-AB-preapply-16-originals/16/SKILL.md` |

## 实际测试命令与证据
```sh
python3 -c 'import shutil;from pathlib import Path;s=Path("/Users/chenyang/.hermes/cache/scratch"); shutil.copy2("tests/test_canghai_policy_AB_20261023.py",s/"test_canghai_policy_AB_20261023.py"); (s/"canghai_policy_AB_pytest_20261023.ini").write_text("[pytest]\n")' && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -B -m pytest --noconftest -c /Users/chenyang/.hermes/cache/scratch/canghai_policy_AB_pytest_20261023.ini -p no:cacheprovider /Users/chenyang/.hermes/cache/scratch/test_canghai_policy_AB_20261023.py --basetemp=/Users/chenyang/.hermes/cache/scratch/canghai_policy_AB_pytest_tmp_20261023 --junitxml=/Users/chenyang/.hermes/cache/scratch/canghai_policy_AB_junit_20261023.xml -q
```
exit=0；输出：......................................                                   [100%]
38 passed in 0.14s
- JUnit：`/Users/chenyang/.hermes/cache/scratch/canghai_policy_AB_junit_20261023.xml`；SHA256 `dba0abfc2cb3aa4f8beb8576e91a2f7e4fda727bce6da8e4782a9369741bcf05`
```sh
/Users/chenyang/.hermes/hermes-agent/venv/bin/python -B /Users/chenyang/.hermes/cache/scratch/canghai_policy_AB_soul_load_20261023.py
```
- exit=0；2 个 SOUL 精确内容加载通过；没有输出 SOUL 正文或凭据。
- 首次加载探针被自身过严 subprocess guard 拒绝：Hermes 内部版本检查执行只读 `git rev-parse HEAD`。定位到 version_info 后仅为该精确 argv/cwd 放行，重试成功；失败原始 output/exit 留在 execution JSON，不记产品失败。

## 保持不变
- 主 SOUL SHA256：`b5c993bef4dfa9475ba64935c03c83629e59175a9c36a8e8175c730589f85752`（前后一致）。
- 全部 index records SHA256：`c24736dd938685a85db19301280d8b9fdafdf6fb2bab56a056068dc026df152b`（前后一致），32 staged。
- `.git/index` 二进制 SHA256：`3f2f0150a437b8b7e8ef55a73bc0f9091dee854dbf8a4734428813a997d13c0e`（前后一致）。
- HEAD：`03c1d25caf94e8c8576765442b55cbf4538559f1`；没有 git add/commit/reset。
- 不改 cron、配置、模型、路径布局、账户权限、北向政策实现、RR、模拟策略；sign_off_log 由父主控统一记录。

## 回滚与边界
- 原件目录：`/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/系统进化/backups/2026-10-23-policy-AB-preapply-16-originals`。逐条先比当前 after 与备份 before，再在有权限回滚时只恢复清单中的目标；不使用整仓 Git 还原。
- scratch 回滚演练：`/Users/chenyang/.hermes/cache/scratch/canghai_policy_AB_rollback_rehearsal_20261023`。
- 仅该精确文档/skill 政策包与 namespace 最小 guard；不是已跑生产研究、不是证明 LLM 本日会实际保留观察对象。
- 未运行生产 fetch/research/D1/QMT/外发，没有启动 fresh 生产身份。需父主控验收后以新 profile 会话加载；驻留会话不追溯生效。

完整机器证据：`/Users/chenyang/.hermes/cache/scratch/canghai_policy_AB_applied_20261023.json`
