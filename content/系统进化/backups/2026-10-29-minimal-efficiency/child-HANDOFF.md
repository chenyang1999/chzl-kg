# 图像快照最小减法：限定交接

## 结果
- 删除固定 12 票 fallback。R2 缺失、不可解析、空候选及显式空 universe：实际 main/argparse 返回 0，零 renderer/vision 调用；显式缺失文件返回 2，不回填旧票。
- R2 status=partial 与 complete 均可读取其中原有候选；未将 partial 改写成 complete，也未改研究／交易资格。
- 同日合法缓存逐票复用，归档优先、latest 只补缺；拒绝跨日、error、空对象、非对象及身份不一致记录。有效记录定义保持现有 summary 审计消费者口径：非空对象、无 error、ts_code 若显式声明必须匹配 key；本批不引入模型内容质量评分。
- 删除 50% 整批跳过策略；只计算 miss，缓存原记录保留。显式 universe 优先；--force 只重算选中票池，不扩池。保留原有同日旧记录合并逻辑。
- dotenv 从模块导入推迟到确定需要计算之后；已有 VISION_API_KEY 通道不再被 OPENAI_API_KEY 前置检查误挡。

## 文件与恢复证据
唯一修改：
1. scripts/fetch/run_chart_vision_snapshot.py
2. src/research/candidate_pool.py
新增有界测试：tests/pipeline/test_chart_vision_snapshot_minimal.py

本目录 before/ 保存修改前字节（包括用户既存修改）；before.json 为原始 SHA256。
repair-only.diff 是相对这些字节的修复增量，不是相对 Git HEAD 的大脏树 diff。
after/ 为最终受测源码冻结副本；receipt-final.json 保存真实命令、环境、前后 SHA256、退出码和 30 个展开 case 身份。

## 真实验证
最终完整专项：30 passed in 0.15s；pytest 子进程退出码 0；受测闭包前后摘要一致。

首次收集退出码 2：最小 settings 替身不含 DATA_DIR，而 research/__init__.py 会加载整套 orchestrator；这是夹具隔离闭包问题，无模型/网络/正式数据访问。保留 pytest.log / receipt.json。只修测试启动隔离，保留真实 candidate_pool、r5_stock_profiles._collect_leaders 和真实 main / _run_all / _analyze_one；最终完整专项一次重跑通过。

测试在 collection 前安装审计守卫；阻断网络/DNS/子进程、.env、正式 data/chzl_kg 与账户目录读取，非 scratch 写入。仅替代 dotenv、settings 及包初始化副作用，renderer/vision 外部边界。所有测试 guard 断言无违规；正向输入和图像返回明确为合成，不代表真实服务输出。TMPDIR 与 pytest basetemp 均显式指向 /Users/chenyang/.hermes/cache/scratch。

## 主控亲跑（仅这一组）
在 /Users/chenyang/Downloads/demo/沧海巨浪 中使用 receipt-final.json 的 command；basetemp 和 junitxml 换成新的 scratch 目录，保留原回执。环境使用该回执中的最小环境：不继承真实 API key，PYTEST_DISABLE_PLUGIN_AUTOLOAD=1，PYTHONDONTWRITEBYTECODE=1，TMPDIR 显式为 scratch。

## 边界／未完成
- 验证到实际 Python main/argparse 路径及线程池图像边界；没有真实凭据、真实网络、独立生产 shell、自然调度、真实绘图或真实模型验收。
- src.research 包初始化会导入整套 orchestrator；测试仅屏蔽这个无关启动副作用，不声称已优化全局包导入。该处不在授权写权内。
- 未补跑 2026-10-29 业务，未动服务／实盘／配置／研究数据／shell／技能，未执行 git add/commit/reset/stash/rollback。
- 技能语义建议（仅待签）：把默认固定池 fallback 与“覆盖 50% 跳过”说明改为“真实候选、同日逐票有效缓存、仅补 miss”；本批不自行编辑技能。
