#!/usr/bin/env python3
"""canghai-plan · D1 安全网 (safety net).

**铁律（2026-09-30 用户钦定）**：决策必须由**大模型**做。Python 量价规则
(`src/plan/d1_algorithm.py`) 只能做"不让预案开天窗"的兜底占位，**永远不是决策者**。

因此本脚本的顺序是 **先重试大模型，失败才落规则兜底**：

  1. 完整 LLM 主路径产物已存在 → 幂等跳过；未就绪安全版仍保留重评义务。
  2. 否则 → 用 hermes CLI 起 canghai-plan / `main_decision_v1` **fresh context 重跑**。
     成功（产出非 fallback plan）→ 结束。
  3. LLM 重跑失败且没有需保留的 LLM 产物 → 才用 python fallback 补齐，并把预案标成
     `decision_source: python_fallback` / `mode: fallback` + 顶部 🚨 横幅。

原版（T1 期）只做第 3 步：LLM 一挂就直接落规则版，且落成 `mode=live`，
人读预案完全看不出今天没有大模型决策 —— 这是 2026-09-30 用户打脸的根因。

设计原则:
  - **幂等**: 合法完整 LLM（含 no_trade）产物绝不覆盖；未就绪版不冒称完成。
  - **不吃陈旧**: 兜底 plan 若早于 R5/R6 落盘，视为陈旧，允许重建。
  - **静默**: 无需补齐时 exit 0 且不输出，适合挂 no_agent cron(空输出=不打扰)。
  - **诚实**: 真的走了兜底就必须显眼自曝，不许伪装成正常预案。
  - **保留原文**: LLM 契约失败不是规则覆盖许可；允许重试修复，但不改写失败版来冒充验收通过。

用法:
  python3 scripts/plan/ensure_watchlist_plan.py [--date YYYYMMDD] [--force] [--no-llm]

退出码:
  0 = 已存在(跳过) / LLM 重跑成功 / 兜底补齐成功
  1 = 上游/JSON/MD/交接阻塞或兜底失败；不伪装交付成功
"""
from __future__ import annotations

import argparse
import json
import fcntl
import time
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.research.pipeline_artifacts import (
    UNIT_FILES, plan_artifact, plan_reassessment_reasons, publish_runtime_plan,
    read_object, research_artifact,
)
_LOCK_FDS: dict[str, int] = {}

#: 上游 artifact 相对 R5/R6 —— D1 必须读到的关键输入（用于时序陈旧判定）
_UPSTREAM_INPUTS = (
    ("R5", "data/research/{date}/R5_stock_profiles.json"),
    ("R6", "data/research/{date}/R6_devil_advocate.json"),
)

#: LLM 重跑配置（与 research_shell.sh 的 D1 段保持一致）
_LLM_PROFILE = "canghai-plan"
_LLM_SKILL = "main_decision_v1"
# 2026-09-30：默认 600s 太短 —— 实测 D1 大模型跑完需 **26~39 分钟**
# （R6 落盘 → plan 落盘：0921=26min / 0925=9min / 0928=26min / 0929=39min），
# 600s 必然超时，等于重试路径形同虚设。默认给 45 分钟，可用环境变量覆盖。
_LLM_TIMEOUT_S = int(os.environ.get("CHZL_D1_LLM_TIMEOUT", "2700"))
_LLM_MAX_TURNS = int(os.environ.get("CHZL_D1_LLM_MAX_TURNS", "70"))

_LLM_PROMPT = (
    "按 main_decision_v1 skill 综合 R1-R7 全部产出 + 四象限叉乘 + 数据源审计。"
    "消费 R6 hard_rejects 从 execution_pool 剔除。trade_date={date}。"
    "仅使用本次 research_summary.json artifacts 列出的主产物；失败或缺研究不视为通过，不读同日旧文件冒充本次研究。"
    "产出 data/plans/{date}/watchlist_plan.json + chzl_kg/投研交易/盘前预案/{date}.md 散文体。"
    "decision_source 明确标注 llm；输出范围仅以上核心 JSON 与 KG 主 MD；不写 runtime 副本或其他附加 MD，超出 profile 白名单的输出须报告阻塞，不越权。完成后退出。"
)


def _is_trading_day(date: str) -> bool:
    """周一到周五视为交易日(不含节假日精判——安全网宁可多跑一次)。"""
    try:
        return datetime.strptime(date, "%Y%m%d").weekday() < 5
    except ValueError:
        return True


def _is_python_fallback(plan: dict) -> bool:
    """是否为 python 兜底 plan（LLM 主路径产物不受本脚本覆盖）。"""
    meta = plan.get("meta") or {}
    source = plan.get("decision_source") or meta.get("decision_source")
    return bool(plan.get("is_fallback") or meta.get("python_fallback") or
                source in {"python_fallback", "rule_v1_standalone"} or
                plan.get("mode") in {"fallback", "python_fallback"} or
                "rule" in str(plan.get("agent_name", "")).lower())


def _has_llm_source(plan: object) -> bool:
    """Provenance only: protect original analysis, never certify its safety.

    Conflicting fallback flags do not authorize destructive rule replacement.
    """
    if not isinstance(plan, dict):
        return False
    meta = plan.get("meta")
    return (plan.get("decision_source") == "llm" or
            isinstance(meta, dict) and meta.get("decision_source") == "llm")


def _stale_inputs(date: str, plan: dict) -> list[str]:
    """返回比 plan.generated_at 更晚落盘的上游 artifact 名。

    2026-09-30 事故：08:30 兜底 plan 生成时 R5(08:33:51)/R6(08:52:36) 尚未落盘，
    于是执行池在无档位数据下算空；而本脚本只按"文件存在"判幂等，
    09:20 再跑也不会重建 → 全链一整天读到陈旧空池。

    修复：兜底 plan 若早于关键上游落盘，视为陈旧，允许重建。
    """
    raw = (plan or {}).get("generated_at")
    if not raw:
        return [name for name, _ in _UPSTREAM_INPUTS]
    try:
        gen = datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return [name for name, _ in _UPSTREAM_INPUTS]
    stale = []
    for name, tmpl in _UPSTREAM_INPUTS:
        p = ROOT / tmpl.format(date=date)
        if p.is_file() and p.stat().st_mtime > gen:
            stale.append(name)
    return stale


def _upstream_ready(date: str) -> list[str]:
    """返回**尚未落盘**的关键上游 artifact 名。

    2026-09-30 二次事故：08:30 安全网跑时 R5(08:33:51)/R6(08:52:36) 还没落盘，
    此时用 d1_algorithm 兜底必然算出**空执行池**（无档位/无画像数据）。
    空池规则版比"暂时没预案"更坏——它看起来像一份正常预案（mode=live），
    会一路流到 P1 竞价校准和 execute，人却完全不知道今天没有决策。

    因此：关键上游不齐时**拒绝兜底**，只报警等下一次 tick。
    """
    missing = []
    since_ns = None
    state_path = ROOT / "data/health" / f"research_pipeline_{date}.json"
    if state_path.is_file():
        try:
            since_ns = read_object(state_path).get("started_ns")
        except (OSError, ValueError):
            # A corrupt current-run health record is not evidence of readiness.
            return [name for name, _ in _UPSTREAM_INPUTS]
    for name, _ in _UPSTREAM_INPUTS:
        try:
            research_artifact(ROOT, date, name, since_ns=since_ns)
        except (OSError, ValueError, TypeError):
            missing.append(name)
    return missing


def _reassessment_inputs_missing(date: str, plan: dict) -> list[str]:
    """Only a newly delivered research batch can reassess an interim decision.

    Never launch research here or reuse pre-interim inputs as proof of refresh.
    Readiness permits reconsideration, not live authorization.
    """
    missing = _upstream_ready(date)
    try:
        since_ns = int(datetime.fromisoformat(
            str(plan.get("generated_at") or "").replace("Z", "+00:00")
        ).timestamp() * 1_000_000_000) + 1
        state_path = ROOT / "data/health" / f"research_pipeline_{date}.json"
        state = read_object(state_path) if state_path.is_file() else {}
        if state:
            since_ns = max(since_ns, int(state["started_ns"]))
        summary_path = ROOT / "data/research" / date / "research_summary.json"
        summary = read_object(summary_path)
        if (summary_path.stat().st_mtime_ns < since_ns
                or str(summary.get("trade_date", "")).replace("-", "") != date
                or summary.get("orchestrator_status") not in {"complete", "partial"}
                or (state and (not state.get("run_id") or summary.get("run_id") != state["run_id"]))
                or plan_reassessment_reasons(summary)):
            raise ValueError("research summary not refreshed/ready")
        pointers = summary.get("artifacts")
        if not isinstance(pointers, dict):
            raise ValueError("research summary artifact pointers missing")
        for unit in UNIT_FILES:
            path, payload = research_artifact(ROOT, date, unit, since_ns=since_ns)
            if (pointers.get(unit) != str(path.relative_to(ROOT))
                    or plan_reassessment_reasons(payload)):
                missing.append(unit)
    except (OSError, ValueError, TypeError, OverflowError, KeyError):
        missing.append("fresh research batch")
    return list(dict.fromkeys(missing))


def _hermes_bin() -> str | None:
    for cand in ("/Users/chenyang/.local/bin/hermes", "hermes"):
        if cand.startswith("/"):
            if Path(cand).is_file():
                return cand
            continue
        from shutil import which

        found = which(cand)
        if found:
            return found
    return None


def _plan_paths(date: str) -> tuple[Path, Path]:
    return (
        ROOT / "data" / "plans" / date / "watchlist_plan.json",
        ROOT / "data" / "runtime" / f"watchlist_plan_{date}.json",
    )


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _lock_path(date: str) -> Path:
    return ROOT / "data" / "runtime" / f"d1_decision_{date}.lock"


def _try_lock(date: str) -> bool:
    """OS-owned nonblocking lock; never steal from a slow live LLM process.

    Keep the existing lock inode after unlock: unlink/recreate can split a
    waiting process and a new process onto different inodes and admit both.
    """
    if date in _LOCK_FDS:
        return False
    lock = _lock_path(date)
    lock.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return False
    os.ftruncate(fd, 0)
    os.write(fd, str(os.getpid()).encode())
    _LOCK_FDS[date] = fd
    return True


def _unlock(date: str) -> None:
    fd = _LOCK_FDS.pop(date, None)
    if fd is not None:
        os.close(fd)


def _observation_only_state(state: dict, date: str) -> bool:
    """A standalone usage observation is not a newly started research run."""
    obs = state.get("resource_observation")
    return (set(state) == {"trade_date", "resource_observation"}
            and state["trade_date"] == date and isinstance(obs, dict)
            and obs.get("trade_date") == date and isinstance(obs.get("attempts"), dict))


def retry_llm(date: str, *, timeout_s: int = _LLM_TIMEOUT_S) -> tuple[bool, str]:
    """用 hermes CLI 重跑 D1 大模型。返回 (成功?, 说明)。

    成功判据：本次新写的契约 JSON + KG MD，显式 decision_source=llm，
    且通过原有 execution staging 边界。空执行池可以是合法不交易决策。
    """
    hermes = _hermes_bin()
    if not hermes:
        return False, "hermes CLI 未找到"

    # Same read-only version contract as the shell's --verify-inputs. The
    # standalone safety net has no shell run env: use the current health owner,
    # never the summary's self-declared run as authority. No new fallback gate.
    from scripts.research.build_research_summary import verify_saved_inputs
    try:
        state_path = ROOT / "data/health" / f"research_pipeline_{date}.json"
        state = read_object(state_path) if state_path.exists() else {}
        if (state_path.exists() and not _observation_only_state(state, date)
                and (not isinstance(state.get("run_id"), str) or not state["run_id"])):
            raise ValueError("current research state has no run identity")
        run_id = os.environ.get("CHZL_RESEARCH_RUN_ID") or state.get("run_id") or ""
        input_version, saved = verify_saved_inputs(date, run_id=run_id, root=ROOT)
        if not saved.get("artifacts"):
            raise ValueError("summary has no authorized primary inputs")
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return False, f"LLM 输入预检失败: {exc}"

    contract, _ = _plan_paths(date)
    before = _read_json(contract) or {}
    before_gen = str(before.get("generated_at") or "")
    started_ns = time.time_ns()

    log_dir = ROOT / "data" / "logs" / "research_shell" / date
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "D1_llm_retry.log"

    # The native usage-file launcher allocates a unique attempt file and binds
    # it to the actual child PID before reading it. Keep subprocess.run as this
    # safety net's transport boundary; the wrapper owns child timeout/accounting.
    cmd = [
        sys.executable, "-B", str(ROOT / "scripts/research/native_usage.py"), "run",
        "--root", str(ROOT), "--date", date, "--run-id", run_id,
        "--stage", "D1_safety_net", "--attempt", "1", "--channel", "safety_net",
        "--hermes", hermes, "-p", _LLM_PROFILE, "-s", _LLM_SKILL,
        "--max-turns", str(_LLM_MAX_TURNS), "--timeout", str(timeout_s),
        "--prompt", _LLM_PROMPT.format(date=date),
    ]
    env = dict(os.environ)
    env.setdefault("HERMES_MEMORY_PROVIDER", "openviking")
    env.setdefault("OVCLI_CONFIG_PATH", "/Users/chenyang/.openviking/ovcli.conf.Livermore")
    env.setdefault("OVCLI_ACTOR_PEER_ID", "canghai-shared")

    print(f"🔁 D1 大模型重跑中（profile={_LLM_PROFILE}, skill={_LLM_SKILL}, 上限 {timeout_s}s）…")
    try:
        with log_path.open("w", encoding="utf-8") as fh:
            proc = subprocess.run(
                cmd, cwd=str(ROOT), env=env, stdout=fh, stderr=subprocess.STDOUT,
                timeout=timeout_s + 30,  # inner launcher records/terminates its actual child first
            )
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        return False, f"LLM 重跑超时({timeout_s}s)，日志 {log_path}"
    except OSError as exc:
        return False, f"LLM 重跑启动失败: {exc}"

    after = _read_json(contract) or {}
    after_gen = str(after.get("generated_at") or "")

    if rc != 0:
        return False, f"LLM 重跑退出码 {rc}，日志 {log_path}"
    if after_gen == before_gen:
        return False, f"LLM 重跑未刷新 plan（generated_at 未变），日志 {log_path}"
    try:
        # Recheck the SAME summary and primary versions after the model exits.
        # A newly valid batch is not evidence of what this invocation consumed.
        if (not run_id and state_path.exists()
                and not _observation_only_state(read_object(state_path), date)):
            raise ValueError("research run appeared during standalone LLM retry")
        current_version, _ = verify_saved_inputs(date, run_id=run_id, root=ROOT)
        if current_version != input_version:
            raise ValueError("summary input version changed during LLM retry")
        # Canonical -> runtime, never the reverse. A valid empty/no-trade plan
        # is legitimate LLM output. JSON-only or old-MD delivery is not complete.
        plan_artifact(ROOT, date, since_ns=started_ns)
        publish_runtime_plan(ROOT, date, since_ns=started_ns)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return False, f"LLM 重跑交付失败: {exc}，日志 {log_path}"
    pending = plan_reassessment_reasons(after)
    if pending:
        return False, f"LLM 安全版已交付，但仍须重评: {'; '.join(pending)}"
    return True, f"LLM 重跑成功：execution_pool={len(after['execution_pool'])} 只"


def main() -> int:
    parser = argparse.ArgumentParser(description="canghai-plan D1 safety net: ensure watchlist_plan.json exists")
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"), help="trade date YYYYMMDD")
    parser.add_argument("--force", action="store_true", help="允许重建已有 fallback；绝不覆盖合法 LLM 预案")
    parser.add_argument("--no-llm", action="store_true",
                        help="跳过 LLM 重跑，直接走 python 兜底（排障/离线用）")
    args = parser.parse_args()

    date = args.date
    if not _is_trading_day(date):
        return 0
    if not _try_lock(date):
        print(f"⏸️ {date} 已有 D1 安全网在跑，本次跳过。")
        return 0
    try:
        return ensure_plan(date, force=args.force, no_llm=args.no_llm)
    finally:
        _unlock(date)


def ensure_plan(date: str, *, force: bool = False, no_llm: bool = False) -> int:
    plan_path, _ = _plan_paths(date)
    existing = _read_json(plan_path)
    protected_llm = _has_llm_source(existing)
    # Even --force cannot replace a complete LLM/no-trade decision with rules.
    pending = []
    delivered = {}
    try:
        _, delivered = plan_artifact(ROOT, date)
    except (OSError, ValueError, TypeError) as exc:
        if protected_llm:
            print(f"[ensure_watchlist_plan] LLM contract blocked: {exc}; original analysis retained, not accepted for trading", file=sys.stderr)
            if no_llm:
                return 1
    else:
        try:
            publish_runtime_plan(ROOT, date)
        except (OSError, ValueError, TypeError) as exc:
            print(f"[ensure_watchlist_plan] D1 JSON exists but delivery blocked: {exc}", file=sys.stderr)
            return 1
        pending = plan_reassessment_reasons(delivered)
        if not pending:
            return 0
        print(f"[ensure_watchlist_plan] safe interim published; reassessment required: {'; '.join(pending)}", file=sys.stderr)
    missing = _reassessment_inputs_missing(date, delivered) if pending else _upstream_ready(date)
    if missing:
        print(f"[ensure_watchlist_plan] upstream missing/invalid: {'/'.join(missing)}; no fabricated fallback", file=sys.stderr)
        return 1
    if pending and no_llm:
        print("[ensure_watchlist_plan] reassessment requires the LLM owner; no rule overwrite", file=sys.stderr)
        return 1
    if existing and not protected_llm and _is_python_fallback(existing) and not force and not _stale_inputs(date, existing):
        return 0
    if not no_llm:
        ok, note = retry_llm(date)
        print(f"{'✅' if ok else '❌'} {note}")
        if ok:
            return 0
        if pending:
            print("[ensure_watchlist_plan] reassessment incomplete; rule fallback cannot replace the interim LLM decision", file=sys.stderr)
            return 1
        print("大模型重跑未成功，兜底必须显式标注非大模型决策。")
    # Inspect the current version after retry: never restore an earlier snapshot
    # over newly written analysis, nor certify/retag rejected model output.
    # Remember provenance if a failed retry removed/corrupted the original JSON.
    if protected_llm or _has_llm_source(_read_json(plan_path)):
        try:
            plan_artifact(ROOT, date)
        except (OSError, ValueError, TypeError) as exc:
            print(f"[ensure_watchlist_plan] LLM contract blocked: {exc}; no rule overwrite", file=sys.stderr)
        else:
            print("[ensure_watchlist_plan] LLM delivery incomplete; no rule overwrite", file=sys.stderr)
        return 1
    from src.execute.fallback import run_plan_fallback
    try:
        run_plan_fallback(date)
    except (FileNotFoundError, ValueError, ImportError) as exc:
        print(f"[ensure_watchlist_plan] FALLBACK FAILED for {date}: {exc}", file=sys.stderr)
        return 1
    result = _read_json(plan_path)
    if not result or not _is_python_fallback(result):
        print(f"[ensure_watchlist_plan] no verified fallback at {plan_path}", file=sys.stderr)
        return 1
    print(f"🚨 D1 {date} 已用 python 兜底 (decision_source=python_fallback · 非大模型决策 · 勿据此下单)。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
