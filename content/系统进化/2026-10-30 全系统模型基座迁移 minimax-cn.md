# 2026-10-30 全系统模型基座迁移到 minimax-cn / MiniMax-M3.1-Flash

## 一、授权与要求

用户原话口径：**"我换了一个模型基座，我发现 Minimax 的跟耐用，apikey 是 sk-cp-Gf5FlY3kQlJ5ap2l3_… 我想你帮我全部切过去，有脚本的，切完冒烟跑一下"**。

回答的问题是：会话层已经换到 MiniMax，但整套定时研究/决策/复盘链还挂在别处，需要一次性对齐，并证明切换真的生效。

用户给了具体 API key，并明确"全部"范围。凭据指纹 sha256:eb4d0fda，与 `~/.hermes/.env` 中既有的 `MINIMAX_CN_API_KEY` **完全一致**——即该 key 此前已被写进默认 profile，本次不需要新增任何凭证文件内容，只是让其余 4 个 profile 对齐到同一把。

## 二、结论速览表

| 入口 | 改前 | 改后 | 状态 |
|---|---|---|---|
| 默认 profile `~/.hermes/config.yaml` | minimax-cn / MiniMax-M3.1-Flash | 不变 | 本就已就位 |
| 默认 profile `~/.hermes/.env` | key 指纹 eb4d0fda | 不变 | 本就已就位 |
| canghai-fetch / plan / research / review `config.yaml` | openai-codex / gpt-6.1-sol | minimax-cn / MiniMax-M3.1-Flash | ✅ 已改并回读 |
| 同 4 个 profile 的 `.env` | key 指纹 4c01f5a9 | key 指纹 eb4d0fda | ✅ 已改并回读 |
| default cron 库 12 个 agent 型 job | openai-codex / gpt-6.1-sol | minimax-cn / MiniMax-M3.1-Flash | ✅ 已改并回读 |
| profile cron 库 3 个 agent 型 job | openai-codex / gpt-6.1-sol | minimax-cn / MiniMax-M3.1-Flash | ✅ 已改并回读 |
| default cron 库 9 个 no_agent job | 字节通道 pin + 8 个带 ark base_url | minimax-cn / MiniMax-M3.1-Flash，base_url 置空 | ✅ 已改并回读 |
| default cron 库 13 个未 pin 的 no_agent job | 无 pin | 不动 | 本就跟随主模型 |
| 项目 `.env` 的 `OPENAI_API_BASE=api.apiyi.com` | — | 不动 | K线识图专用链，超出授权范围 |

## 三、逐项真相（硬数据）

**入口盘点（四类）**
- 默认 profile：`model = {default: MiniMax-M3.1-Flash, provider: minimax-cn, base_url: https://api.minimaxi.com/anthropic}`
- 4 个真实 profile（fetch/plan/research/review）：改前 `model.default=gpt-6.1-sol`、`model.provider=openai-codex`
- default cron 库 34 个 job = 12 agent 型（全部 pin openai-codex）+ 22 no_agent（其中 9 个带字节通道 pin，8 个带 ark base_url，13 个无 pin）
- profile cron 库：fetch 1、plan 1、review 1 个 agent 型 job（均 pin openai-codex），research 库 0 个 job

**凭证指纹（sha256 前 8 位）**
- 用户提供 / 默认 `.env`：`eb4d0fda`（125 字符，sk-cp- 前缀）
- 4 个 profile 改前的 `.env`：`4c01f5a9`（同一长度同族前缀，但是**另一把 key**）
- 两把 key 都实测可用：MiniMax 中国端点 `https://api.minimaxi.com/anthropic/v1/messages`，`Authorization: Bearer`，HTTP 200，模型回显 `MiniMax-M3.1-Flash`
  - 首次探测用 `x-api-key` 头得到 401，报错明确要求 `X-Api-Key`——**但这是错误的头**。MiniMax 走 `Authorization: Bearer`（官方 `_auth_style` 逻辑：MiniMax 属 bearer 类通道）。用错头会误判 key 失效
  - profile 旧 key 返回 200 但正文为空；加大 max_tokens 后确认正常返回 `MIGRATION_OK`

**canghai-execute 不是角色**
该目录无 `config.yaml`、无 `auth.json`、无 `cron/jobs.json`（只有 executions.db 与锁文件）。`hermes -p canghai-execute config get model` 报 "Profile 'canghai-execute' does not exist"。按"用真实身份发现目标，不数裸目录"的判据，不创建新角色。

**执行路径判定（no_agent 是否会被 job 的 pin 影响）**
- `cron/scheduler.py:2270`：`if job.get("no_agent"): return _run_no_agent_job(...)` — 短路发生在任何模型解析之前
- `cron/scheduler.py:1773` 注释：不得把 `HERMES_INFERENCE_PROVIDER` 当 requested 传入，否则会复活过期 provider
- 脚本内部起 agent 走 `hermes -p <profile>`，读的是**该 profile 自己** config 的 `model.provider`/`model.default`，不读外层 job 的 pin → profile 切换即覆盖，无需改 job 标签
- 涉及脚本：`run_research_shell.sh`（`-p canghai-research`）、`ensure_watchlist_plan.py`（`_LLM_PROFILE = "canghai-plan"`）、`reprompt_failed_agents.sh`（`-p canghai-research`）

**CLI 行为实测**
- `hermes cron edit <id> --provider minimax-cn --model MiniMax-M3.1-Flash` 在 base_url 为 null 时干净切换，schedule/skills/workdir 不动
- 在 base_url 仍指向 ark 时**被拒**："base_url '…/api/coding/v3' is not allowed for provider 'minimax-cn'"——这是正确的保护，防止新 provider 配旧厂商端点
- `hermes cron edit` 无 `--base-url` 参数，故 8 个 job 的 base_url 需直改 jobs.json（备份 + 原子替换 + 回读）

**cron 任务库最终读回**
- default：34 个 job = 21 个 pin minimax-cn/MiniMax-M3.1-Flash（base_url 全 None）+ 13 个无 pin，**非 minimax pin = 0，base_url 残留 = 0**
- fetch 1 / plan 1 / review 1：均 minimax-cn/MiniMax-M3.1-Flash，base_url None
- research 库 0 个 job

## 四、前后对比表

| 项 | 改前 | 改后 |
|---|---|---|
| 角色主模型 | openai-codex / gpt-6.1-sol（4 profile + 15 cron job） | minimax-cn / MiniMax-M3.1-Flash |
| profile 凭证 | 指纹 4c01f5a9 | 指纹 eb4d0fda（用户所给） |
| cron base_url 覆盖 | 8 个 job 指向 ark coding v3 | 0 个 |
| cron 端点解析 | provider=minimax-cn 时若留 ark 地址会被 CLI 拒绝 | 全部 https://api.minimaxi.com/anthropic |
| 字节通道状态 | credential_pool 记 volcengine-coding-plan exhausted / 429 | 已无任何 job 指向字节通道 |
| 冒烟延迟 | — | 4 profile 各 11.7–14.8s 完成一轮真实调用 |

## 五、根因

**为什么之前是"两套模型"**：2026-10-26 全系统统一替换为 GPT 6.1 sol 时，把 4 个 profile 的 config.yaml 与 15 个 agent 型 cron job 的 pin 一起改成了 openai-codex，但**没有同步 profile 的 .env 凭证**，也没有清理 default 库里 9 个 no_agent job 上更早的字节通道标签。于是三层各说各话：会话层已是 MiniMax、profile 层是 GPT 6.1、job 层一半 GPT 6.1 一半字节。

**为什么 no_agent job 的历史标签也值得清**：它们本身不烧 token（短路在模型解析前），但残留的 `base_url=ark…/coding/v3` 是一颗哑雷——任何 job 从 no_agent 转成 agent 模式，或运维误把它当真实推理路径，都会把 minimax 的凭证发到字节端点。

**为什么这次必须验证 provider 与 base_url 的同族**：CLI 层面已把"新 provider + 旧端点"变成硬拒绝，这是 2026-08 之前批量迁移只改 provider 字段、导致整批 job 401 的根治点（`clear_job_base_url.py` 的同族判据）。

## 六、改进建议

| 级别 | 建议 | 省什么 | 风险 | 需签核 |
|---|---|---|---|---|
| P0 | 保留 `~/.hermes/backups/minimax-migration-20261030T073351Z/`，下次迁移前直接复用备份+回读流程 | 省一次全量盘点（约 30 分钟） | 无 | 否 |
| P0 | 迁移后**等下一次自然调度**确认 job 真正跑通，而不是手动重跑当日产物 | 避免覆盖当日预案/复盘产物 | 无 | 否 |
| P1 | 把 `scripts/health/repin_cron_models.py` 扩展为多任务库扫描（现在只扫 default 库，且 provider 取自 `hermes config get provider`——该键在当前版本并不存在，应改读 `model.provider`） | 避免下次只修一半 job | 改 src 代码，需同步 SKILL.md | 是 |
| P1 | `scripts/health/check_cron_failures.py` 增加"provider 指向已 exhausted 通道"检查项 | 提前发现挂死通道 | 低 | 是 |
| P2 | 各 profile config.yaml 的 `providers:` 块仍保留 volcengine-* 的 api_key 与 base_url 注册项（当前不参与路由）。可在确认不再回退到字节通道后清理 | 减少凭证面 | 清错就回不去 | 是 |
| P2 | 项目 `.env` 的 `OPENAI_API_BASE=api.apiyi.com`（K线识图专用 OpenAI 兼容链）不在本次范围内，可评估是否也并入统一基座 | 统一治理 | K线识图有独立验收基线，动了要重验 | 是 |

**明确推荐先做 P0 的第二项**：等明天早上 09:10 早盘简报和 09:27/09:28 竞价链自然跑一次，看 `agent.log` 里的 provider 行。这比现在手动触发更真实，也不碰当日产物。

## 七、变更文件清单 + 未尽事项

**已改（含备份）**
- `~/.hermes/profiles/{canghai-fetch,canghai-plan,canghai-research,canghai-review}/config.yaml` — model 块
- `~/.hermes/profiles/{canghai-fetch,canghai-plan,canghai-research,canghai-review}/.env` — MINIMAX_CN_API_KEY
- `~/.hermes/cron/jobs.json` — 21 个 job 的 provider/model，8 个 job 的 base_url
- `~/.hermes/profiles/{canghai-fetch,canghai-plan,canghai-review}/cron/jobs.json` — 各 1 个 agent job
- 备份：`~/.hermes/backups/minimax-migration-20261030T073351Z/`（15 文件 + sha256 清单，0700/0600）
- 二次快照：`~/.hermes/cron/jobs.json.prebaseurl-20261030-153704`
- 留痕：`data/evolution/2026-W44/sign_off_log.md`

**未尽事项**
1. 未触发任何生产 cron 重跑当日产物 —— 迁移正确性已由配置回读 + 运行时解析 + 4 profile 真实新会话证明，但**生产链本身未验收**（研究质量、并发容量、剩余额度均未测）
2. `hermes cron doctor` 仍列出迁移前的 Codex 429 历史 last_run 记录（`retry after 535513s` 等），那是旧账，需下一次自然调度刷新
3. 各 profile `providers:` 块的字节通道注册项未清（超本次授权）
4. 项目 `.env` 的 apiyi 链路未动（K线识图专用）
5. `model_snapshot` / `provider_snapshot` 字段保留原值 —— 官方测试明确其为 legacy 字段、不参与路由（"follows the main model"），属历史审计痕迹
