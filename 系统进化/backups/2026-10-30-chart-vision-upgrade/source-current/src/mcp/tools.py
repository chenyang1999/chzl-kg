"""MCP 工具实现：直接调用现有 Service，不复制业务逻辑。"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

_IWENCAI_LOCK = threading.Lock()

from src.backtest.runner import run_backtest
from src.kb.database import Database, load_industry_map, resolve_track_id
from src.observability.agent_audit import log_tool_run
from src.orchestrator.pipeline import ResearchPipeline
from src.screener.sise_intraday_monitor import scan_intraday_vol4_color_resonance
from src.screener.sise_scanner import get_sise_status, scan_vol4_color_resonance
from src.screener.sise_trigger_price import scan_trigger_watchlist

_MOCK_BACKTEST_CASES = [
    {
        "ts_code": "688017.SH",
        "name": "绿的谐波",
        "financials": {
            "roe": 0.15,
            "rd_ratio": 0.08,
            "gross_margin": 0.45,
            "revenue_growth": 0.35,
            "net_profit_growth": 0.30,
            "ocf_to_net_profit": 1.1,
            "track_revenue_ratio": 0.80,
            "goodwill_to_equity": 0.05,
        },
        "events": {},
    },
]


def _wrap(tool_name: str, agent_id: str, fn, **kwargs) -> dict[str, Any]:
    run_id = uuid4().hex
    t0 = time.time()
    try:
        result = fn(**kwargs)
        latency = int((time.time() - t0) * 1000)
        log_tool_run(
            run_id=run_id,
            agent_id=agent_id,
            tool_name=tool_name,
            input_data=kwargs,
            output_data=result if isinstance(result, dict) else {"result": result},
            status="completed",
            latency_ms=latency,
        )
        if isinstance(result, dict):
            result["run_id"] = run_id
            return result
        return {"run_id": run_id, "result": result}
    except Exception as exc:
        latency = int((time.time() - t0) * 1000)
        log_tool_run(
            run_id=run_id,
            agent_id=agent_id,
            tool_name=tool_name,
            input_data=kwargs,
            output_data={},
            status="failed",
            latency_ms=latency,
            error_stage=tool_name,
            error=str(exc),
        )
        return {"run_id": run_id, "error": str(exc), "tool": tool_name}


def sise_intraday_scan(
    *,
    mode: str = "candidates",
    include_minute: bool = True,
    agent_id: str = "hermes",
) -> dict[str, Any]:
    return _wrap(
        "sise_intraday_scan",
        agent_id,
        scan_intraday_vol4_color_resonance,
        mode=mode,
        include_minute=include_minute,
    )


def sise_trigger_prices(
    *,
    mode: str = "candidates",
    limit: int = 30,
    sort_by: str = "dist",
    agent_id: str = "hermes",
) -> dict[str, Any]:
    return _wrap(
        "sise_trigger_prices",
        agent_id,
        scan_trigger_watchlist,
        mode=mode,
        limit=limit,
        sort_by=sort_by,
    )


def sise_daily_scan(*, days: int = 7, agent_id: str = "hermes") -> dict[str, Any]:
    def _run(days: int = 7) -> dict[str, Any]:
        hits = scan_vol4_color_resonance(days=days)
        return {
            "hits": hits,
            "count": len(hits),
            "days": days,
            "disclaimer": "技术面筛选结果，不构成投资建议",
        }

    return _wrap("sise_daily_scan", agent_id, _run, days=days)


def stock_tech_lookup(*, ts_code: str, trade_date: str | None = None, agent_id: str = "hermes") -> dict[str, Any]:
    from src.screener.tech_query import get_stock_tech

    def _run(ts_code: str, trade_date: str | None) -> dict[str, Any]:
        row = get_stock_tech(ts_code, trade_date=trade_date)
        if not row:
            return {"error": "not_found", "ts_code": ts_code, "trade_date": trade_date}
        return row

    return _wrap("stock_tech_lookup", agent_id, _run, ts_code=ts_code, trade_date=trade_date)


def stock_tech_query_full_red(
    *,
    trade_date: str | None = None,
    limit: int = 200,
    agent_id: str = "hermes",
) -> dict[str, Any]:
    from src.screener.tech_query import query_full_red, tech_status

    def _run(trade_date: str | None, limit: int) -> dict[str, Any]:
        items = query_full_red(trade_date=trade_date, limit=limit)
        return {"count": len(items), "items": items, "status": tech_status()}

    return _wrap("stock_tech_query_full_red", agent_id, _run, trade_date=trade_date, limit=limit)


def run_research_pipeline(
    *,
    track: str = "机器人核心零部件",
    risk: str = "steady",
    agent_id: str = "hermes",
) -> dict[str, Any]:
    def _run(track: str, risk: str) -> dict[str, Any]:
        pipeline = ResearchPipeline()
        try:
            return pipeline.run(track, risk_profile=risk)
        finally:
            pipeline.db.close()

    return _wrap("run_research_pipeline", agent_id, _run, track=track, risk=risk)


def run_rule_backtest(*, strategy: str = "default", agent_id: str = "hermes") -> dict[str, Any]:
    def _run(strategy: str) -> dict[str, Any]:
        result = run_backtest(_MOCK_BACKTEST_CASES)
        result["strategy"] = strategy
        return result

    return _wrap("run_rule_backtest", agent_id, _run, strategy=strategy)


def get_track_status(*, track: str | None = None, agent_id: str = "hermes") -> dict[str, Any]:
    def _run(track: str | None) -> dict[str, Any]:
        db = Database()
        try:
            sise = get_sise_status(db)
            tracks = db.conn.execute(
                "SELECT track_id, track_name, rating, cagr FROM industry_tracks ORDER BY track_name"
            ).fetchall()
            track_info = None
            if track:
                tid = resolve_track_id(track)
                try:
                    imap = load_industry_map(tid)
                    companies = db.list_companies(tid)
                    track_info = {
                        "track_id": tid,
                        "track_name": imap.get("track_name"),
                        "company_count": len(companies),
                        "sample_codes": imap.get("sample_codes", [])[:10],
                    }
                except FileNotFoundError:
                    track_info = {"error": f"赛道不存在: {track}"}
            return {
                "sise": sise,
                "tracks": [dict(r) for r in tracks],
                "track_detail": track_info,
            }
        finally:
            db.close()

    return _wrap("get_track_status", agent_id, _run, track=track)


def wechat_search_accounts(*, keyword: str, agent_id: str = "hermes") -> dict[str, Any]:
    from src.collectors.wechat_mp_client import WechatMpClient

    def _run(keyword: str) -> dict[str, Any]:
        client = WechatMpClient()
        accounts = client.search_accounts(keyword)
        return {"keyword": keyword, "accounts": accounts, "count": len(accounts)}

    return _wrap("wechat_search_accounts", agent_id, _run, keyword=keyword)


def wechat_list_articles(
    *,
    fakeid: str,
    begin: int = 0,
    size: int = 10,
    keyword: str = "",
    agent_id: str = "hermes",
) -> dict[str, Any]:
    from src.collectors.wechat_mp_client import WechatMpClient

    def _run(fakeid: str, begin: int, size: int, keyword: str) -> dict[str, Any]:
        client = WechatMpClient()
        return client.list_articles(fakeid, begin=begin, size=size, keyword=keyword)

    return _wrap(
        "wechat_list_articles",
        agent_id,
        _run,
        fakeid=fakeid,
        begin=begin,
        size=size,
        keyword=keyword,
    )


def wechat_download_article(
    *,
    url: str,
    fmt: str = "text",
    agent_id: str = "hermes",
) -> dict[str, Any]:
    from src.collectors.wechat_mp_client import WechatMpClient

    def _run(url: str, fmt: str) -> dict[str, Any]:
        client = WechatMpClient()
        content = client.download_article(url, fmt=fmt)
        return {"url": url, "format": fmt, "content": content, "length": len(content)}

    return _wrap("wechat_download_article", agent_id, _run, url=url, fmt=fmt)


def wechat_fetch_latest(
    *,
    account_keyword: str,
    limit: int = 5,
    download_content: bool = True,
    agent_id: str = "hermes",
) -> dict[str, Any]:
    from src.collectors.wechat_mp_client import WechatMpClient

    def _run(account_keyword: str, limit: int, download_content: bool) -> dict[str, Any]:
        client = WechatMpClient()
        return client.fetch_account_latest(
            account_keyword,
            limit=limit,
            download=download_content,
        )

    return _wrap(
        "wechat_fetch_latest",
        agent_id,
        _run,
        account_keyword=account_keyword,
        limit=limit,
        download_content=download_content,
    )


def wechat_analyze_latest(
    *,
    account_keyword: str = "财闻私享",
    limit: int = 2,
    agent_id: str = "hermes",
) -> dict[str, Any]:
    from src.agents.llm_client import LLMClient
    from src.collectors.wechat_mp_client import WechatMpClient

    def _run(account_keyword: str, limit: int) -> dict[str, Any]:
        client = WechatMpClient()
        fetched = client.fetch_account_latest(
            account_keyword,
            limit=limit,
            download=True,
            content_max_chars=5000,
        )
        if fetched.get("error"):
            return fetched

        blocks: list[str] = []
        for i, art in enumerate(fetched.get("articles") or [], 1):
            body = art.get("content") or art.get("digest") or ""
            blocks.append(
                f"【文章{i}】{art.get('title')} ({art.get('update_time_str')})\n{body}"
            )
        prompt = (
            f"请分析公众号「{account_keyword}」以下最新文章，输出：\n"
            "1) 核心观点摘要（3-5条）\n"
            "2) 涉及板块/标的线索\n"
            "3) 对 A 股短期交易的可能影响（偏多/中性/偏空 + 理由）\n"
            "4) 风险提示\n"
            "文末注明：以上内容来自公众号公开文章整理，不构成投资建议。\n\n"
            + "\n\n".join(blocks)
        )
        try:
            llm = LLMClient()
            analysis = llm.complete_text(prompt)
        except Exception as exc:
            analysis = f"LLM 分析失败: {exc}"
        return {
            **fetched,
            "analysis": analysis,
            "disclaimer": "公众号文章 AI 解读，不构成投资建议",
        }

    return _wrap(
        "wechat_analyze_latest",
        agent_id,
        _run,
        account_keyword=account_keyword,
        limit=limit,
    )


def _tushare_market_context(*, days: int = 90) -> dict[str, Any]:
    """近 N 日指数与全市场涨跌概况（优先本地库，回退 Tushare API）。"""
    from datetime import datetime, timedelta

    from src.kb.database import Database

    indices = {
        "000300.SH": "沪深300",
        "399006.SZ": "创业板指",
        "000001.SH": "上证指数",
    }
    out: dict[str, Any] = {"days": days, "indices": [], "market_breadth": None}

    db = Database()
    try:
        latest = db.latest_bar_trade_date()
        if not latest:
            return out
        since_rows = db.conn.execute(
            """
            SELECT DISTINCT trade_date FROM market_daily_bars
            WHERE trade_date <= ? ORDER BY trade_date DESC LIMIT ?
            """,
            (latest, days + 5),
        ).fetchall()
        if not since_rows:
            return out
        since = str(since_rows[-1]["trade_date"])

        for code, name in indices.items():
            rows = db.conn.execute(
                """
                SELECT trade_date, close FROM market_daily_bars
                WHERE ts_code = ? AND trade_date >= ? ORDER BY trade_date
                """,
                (code, since),
            ).fetchall()
            if len(rows) < 2:
                continue
            start = float(rows[0]["close"])
            end = float(rows[-1]["close"])
            if start <= 0:
                continue
            rets = []
            for i in range(1, len(rows)):
                p0, p1 = float(rows[i - 1]["close"]), float(rows[i]["close"])
                if p0 > 0:
                    rets.append(p1 / p0 - 1)
            out["indices"].append(
                {
                    "ts_code": code,
                    "name": name,
                    "since": since,
                    "end_date": str(rows[-1]["trade_date"]),
                    "return_pct": round((end / start - 1) * 100, 2),
                    "volatility_pct": round(
                        (sum((r - sum(rets) / len(rets)) ** 2 for r in rets) / len(rets)) ** 0.5 * 100,
                        2,
                    )
                    if rets
                    else None,
                }
            )
    finally:
        db.close()

    if not out["indices"]:
        try:
            import os
            import tushare as ts

            token = os.environ.get("TUSHARE_TOKEN", "").strip()
            if token:
                pro = ts.pro_api(token)
                end = datetime.now().strftime("%Y%m%d")
                start = (datetime.now() - timedelta(days=days + 10)).strftime("%Y%m%d")
                for code, name in indices.items():
                    df = pro.index_daily(ts_code=code, start_date=start, end_date=end)
                    if df is None or df.empty or len(df) < 2:
                        continue
                    df = df.sort_values("trade_date")
                    s, e = float(df.iloc[0]["close"]), float(df.iloc[-1]["close"])
                    out["indices"].append(
                        {
                            "ts_code": code,
                            "name": name,
                            "return_pct": round((e / s - 1) * 100, 2),
                            "source": "tushare_api",
                        }
                    )
        except Exception as exc:
            out["tushare_error"] = str(exc)
    return out


def wechat_analyze_trading_logic(
    *,
    account_keyword: str = "沧海自流",
    days: int = 90,
    sample_full_articles: int = 10,
    agent_id: str = "hermes",
) -> dict[str, Any]:
    """拉取公众号近 N 日文章，结合 Tushare 市场数据提炼交易逻辑。"""
    from src.agents.llm_client import LLMClient
    from src.collectors.wechat_mp_client import WechatMpClient

    def _run(account_keyword: str, days: int, sample_full_articles: int) -> dict[str, Any]:
        client = WechatMpClient()
        fetched = client.fetch_articles_since(
            account_keyword,
            days=days,
            download_sample=sample_full_articles,
        )
        if fetched.get("error"):
            return fetched

        market = _tushare_market_context(days=days)
        meta_lines = []
        for art in fetched.get("articles") or []:
            meta_lines.append(
                f"- {art.get('update_time_str')} | {art.get('title')} | {art.get('digest', '')[:120]}"
            )

        full_blocks = []
        for art in fetched.get("articles") or []:
            if art.get("content"):
                full_blocks.append(
                    f"【{art.get('update_time_str')}】{art.get('title')}\n{art.get('content')}"
                )

        prompt = (
            f"你是 A 股量化/交易逻辑研究员。请基于公众号「{account_keyword}」近 {days} 天 "
            f"共 {fetched.get('count')} 篇文章，提炼作者的交易逻辑体系，并结合 Tushare 市场数据做对照验证。\n\n"
            "## 输出结构（Markdown）\n"
            "1. **交易哲学与风格**（价投/趋势/事件驱动/赛道轮动等）\n"
            "2. **买入逻辑**（触发条件、选股标准、节奏）\n"
            "3. **卖出与风控**（止盈止损、回避情形）\n"
            "4. **近三月主线复盘**（反复出现的赛道/叙事，按时间线）\n"
            "5. **提及标的/板块清单**（尽可能从文中提取）\n"
            "6. **与 Tushare 市场数据对照**（指数涨跌、行情结构是否支撑其观点；哪些判断被市场验证/证伪）\n"
            "7. **可复用的交易框架** + **盲区/风险**\n"
            "8. **disclaimer**：公众号观点整理，不构成投资建议\n\n"
            f"## Tushare/本地市场快照\n{json.dumps(market, ensure_ascii=False, indent=2)}\n\n"
            f"## 全部文章标题与摘要（{len(meta_lines)}篇）\n" + "\n".join(meta_lines) + "\n\n"
            f"## 抽样正文（{len(full_blocks)}篇）\n" + "\n\n---\n\n".join(full_blocks)
        )
        try:
            llm = LLMClient()
            analysis = llm.complete_text(
                prompt,
                system="你是资深 A 股交易逻辑分析师，善于从自媒体文章中抽象可验证的交易框架。",
            )
        except Exception as exc:
            analysis = f"LLM 分析失败: {exc}"

        return {
            **fetched,
            "market_context": market,
            "analysis": analysis,
            "disclaimer": "公众号交易逻辑 AI 解读，不构成投资建议",
        }

    return _wrap(
        "wechat_analyze_trading_logic",
        agent_id,
        _run,
        account_keyword=account_keyword,
        days=days,
        sample_full_articles=sample_full_articles,
    )


def wechat_sync_account(
    *,
    account_keyword: str,
    download_content: bool = True,
    agent_id: str = "hermes",
) -> dict[str, Any]:
    """同步公众号全量文章到 data/raw/wechat/<账号>/。"""
    import subprocess
    import sys
    from pathlib import Path

    def _run(account_keyword: str, download_content: bool) -> dict[str, Any]:
        root = Path(__file__).resolve().parents[2]
        cmd = [sys.executable, str(root / "scripts" / "sync_wechat_account.py"), account_keyword]
        if download_content:
            cmd.append("--download")
            cmd.append("--skip-existing")
        proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True)
        index_path = root / "data" / "raw" / "wechat" / account_keyword / "index_latest.json"
        summary: dict[str, Any] = {
            "account_keyword": account_keyword,
            "exit_code": proc.returncode,
            "stdout": proc.stdout[-2000:] if proc.stdout else "",
            "stderr": proc.stderr[-500:] if proc.stderr else "",
        }
        if index_path.exists():
            summary["index_path"] = str(index_path)
            summary["corpus"] = json.loads(index_path.read_text(encoding="utf-8"))
        return summary

    return _wrap(
        "wechat_sync_account",
        agent_id,
        _run,
        account_keyword=account_keyword,
        download_content=download_content,
    )


def _load_canghai_skill_rules(max_chars: int = 4500) -> str:
    skill_ref = (
        Path.home() / ".cursor/skills/research/canghai-ziliu-decision/reference.md"
    )
    if not skill_ref.exists():
        return ""
    return skill_ref.read_text(encoding="utf-8")[:max_chars]


def canghai_market_action_plan(
    *,
    core_preset: str = "active",
    sise_days: int = 14,
    agent_id: str = "hermes",
) -> dict[str, Any]:
    """沧海自流框架：最新行情下的交易标的与三情景预案（结合 Tushare + 四色四量）。"""
    from src.agents.llm_client import LLMClient
    from src.collectors.wechat_mp_client import WechatMpClient
    from src.indicators.sise_siliang import SIGNAL_MAGENTA_TO_RED
    from src.screener.core_universe import filter_signal_hits
    from src.screener.sise_scanner import scan_sise_signals

    def _run(core_preset: str, sise_days: int) -> dict[str, Any]:
        market = _tushare_market_context(days=90)
        sise_status = get_track_status()
        skill_rules = _load_canghai_skill_rules()

        wechat = WechatMpClient().fetch_account_latest(
            "沧海自流", limit=3, download=True, content_max_chars=2500
        )

        raw_buys = scan_sise_signals(
            sise_days,
            signal_type=SIGNAL_MAGENTA_TO_RED,
            limit=500,
            require_ma30_up=False,
        )
        active_hits = filter_signal_hits(raw_buys, core_preset)
        vol_hits = sise_daily_scan(days=sise_days)
        triggers = sise_trigger_prices(mode="candidates", limit=20, sort_by="dist")

        prompt = (
            "你是按「沧海自流」交易决策框架做盘前/盘后行动的 Agent。\n"
            "请基于下列实时数据，输出 **最新市场行情下的交易标的与预案**。\n\n"
            "## 决策规则（节选）\n"
            f"{skill_rules}\n\n"
            "## Tushare/本地指数（近90日）\n"
            f"{json.dumps(market, ensure_ascii=False, indent=2)}\n\n"
            "## 四色四量系统\n"
            f"{json.dumps(sise_status.get('sise', {}), ensure_ascii=False, indent=2)}\n\n"
            f"## 紫转红信号（{core_preset} 池，近{sise_days}日，{len(active_hits)}条）\n"
            f"{json.dumps(active_hits[:25], ensure_ascii=False, indent=2)}\n\n"
            f"## 四量转强（近{sise_days}日，{vol_hits.get('count', 0)}条）\n"
            f"{json.dumps((vol_hits.get('hits') or [])[:20], ensure_ascii=False, indent=2)}\n\n"
            f"## 触发价接近标的\n"
            f"{json.dumps(triggers, ensure_ascii=False, indent=2)}\n\n"
            f"## 沧海自流最新观点（{wechat.get('count', 0)}篇）\n"
            f"{json.dumps(wechat.get('articles') or [], ensure_ascii=False, indent=2)}\n\n"
            "## 输出要求（Markdown + 末尾 JSON 代码块）\n"
            "1. **市场研判**：结构（挤压式/普涨普跌）、主线、风险\n"
            "2. **核心标的（3-5只）**：代码、名称、决策类型、评分、逻辑、仓位建议\n"
            "3. **观察池（3-5只）**：未满足全部必须项但值得跟踪\n"
            "4. **三情景预案**：乐观/基准/悲观 — 各写触发条件、标的动作、仓位调整\n"
            "5. **本周执行清单**：最多 3 条可执行动作\n"
            "6. **disclaimer**\n\n"
            "JSON 代码块字段：date, market_regime, primary_targets[], watchlist[], "
            "scenarios{bull,base,bear}, action_checklist[], disclaimer"
        )
        try:
            llm = LLMClient()
            plan = llm.complete_text(
                prompt,
                system="严格遵循沧海自流框架；不得推荐回避清单标的；必须含 disclaimer。",
            )
        except Exception as exc:
            plan = f"生成失败: {exc}"

        return {
            "date": __import__("datetime").datetime.now().strftime("%Y-%m-%d"),
            "core_preset": core_preset,
            "market_context": market,
            "sise_status": sise_status.get("sise"),
            "active_signal_count": len(active_hits),
            "vol_strengthen_count": vol_hits.get("count"),
            "wechat_latest": wechat.get("articles"),
            "action_plan": plan,
            "disclaimer": "沧海自流框架 AI 预案，不构成投资建议",
        }

    return _wrap(
        "canghai_market_action_plan",
        agent_id,
        _run,
        core_preset=core_preset,
        sise_days=sise_days,
    )


def weflow_sise_morning_forecast(
    *,
    core_preset: str = "active",
    sise_days: int = 7,
    weflow_snapshot_path: str | None = None,
    weflow_preset: str = "3d",
    agent_id: str = "hermes",
) -> dict[str, Any]:
    """WeFlow 群聊情绪 × 四色四量短线：明日强势板块与核心标的预判。"""
    from src.agents.llm_client import LLMClient
    from src.analytics.weflow_sise_forecast import (
        build_forecast_payload,
        load_weflow_snapshot,
        render_llm_prompt,
        save_weflow_snapshot,
    )

    def _run(
        core_preset: str,
        sise_days: int,
        weflow_snapshot_path: str | None,
        weflow_preset: str,
    ) -> dict[str, Any]:
        snapshot = load_weflow_snapshot(weflow_snapshot_path)
        if not snapshot:
            return {
                "error": "缺少 WeFlow 快照",
                "hint": (
                    "请先用 weflow-analytics MCP 调用 export_analytics_snapshot，"
                    f"将 JSON 保存到 data/cache/weflow_snapshot_latest.json，"
                    "或传入 weflow_snapshot_path"
                ),
                "weflow_preset_suggested": weflow_preset,
            }

        payload = build_forecast_payload(
            snapshot, core_preset=core_preset, sise_days=sise_days
        )
        try:
            llm = LLMClient()
            narrative = llm.complete_text(
                render_llm_prompt(payload),
                system="短线四色四量模式；不得推荐未在 core_targets 列表中的股票。",
            )
        except Exception as exc:
            narrative = f"LLM 生成失败: {exc}"

        return {
            **payload,
            "forecast_narrative": narrative,
        }

    return _wrap(
        "weflow_sise_morning_forecast",
        agent_id,
        _run,
        core_preset=core_preset,
        sise_days=sise_days,
        weflow_snapshot_path=weflow_snapshot_path,
        weflow_preset=weflow_preset,
    )


def weflow_sentiment_events(
    *,
    weflow_snapshot_path: str | None = None,
    term: str = "",
    spike_threshold: float = 2.0,
    top_events: int = 8,
    include_mlcc_case: bool = False,
    agent_id: str = "hermes",
) -> dict[str, Any]:
    """WeFlow 情绪发酵事件驱动：检测热词突变 → 映射概念核心票 → T+N 收益。"""
    from src.analytics.weflow_event_quant import (
        analyze_mlcc_may22_case,
        build_event_trade_plan,
        load_river_from_snapshot,
        merge_event_signals,
        resolve_concept_stocks,
    )
    from src.analytics.weflow_sise_forecast import load_weflow_snapshot

    def _run(
        weflow_snapshot_path: str | None,
        term: str,
        spike_threshold: float,
        top_events: int,
        include_mlcc_case: bool,
    ) -> dict[str, Any]:
        snapshot = load_weflow_snapshot(weflow_snapshot_path)
        if not snapshot:
            return {
                "error": "缺少 WeFlow 快照",
                "hint": "先用 weflow_save_snapshot 保存 export_analytics_snapshot 结果",
            }
        river = snapshot.get("river") or {}
        if term.strip():
            concept = resolve_concept_stocks(term.strip())
            return {
                "term": term.strip(),
                "concept_stocks": concept,
                "disclaimer": "情绪发酵事件驱动研究，不构成投资建议",
            }
        plan = build_event_trade_plan(
            river,
            snapshot=snapshot,
            top_events=top_events,
            spike_threshold=spike_threshold,
        )
        plan["merged_events_preview"] = merge_event_signals(
            river, snapshot, spike_threshold=spike_threshold, top_n=top_events
        )
        if include_mlcc_case:
            plan["mlcc_case_study"] = analyze_mlcc_may22_case()
        return plan

    return _wrap(
        "weflow_sentiment_events",
        agent_id,
        _run,
        weflow_snapshot_path=weflow_snapshot_path,
        term=term,
        spike_threshold=spike_threshold,
        top_events=top_events,
        include_mlcc_case=include_mlcc_case,
    )


def weflow_save_snapshot(
    *,
    snapshot_json: str,
    agent_id: str = "hermes",
) -> dict[str, Any]:
    """保存 WeFlow export_analytics_snapshot 结果到本地缓存，供短线预判工具读取。"""
    from src.analytics.weflow_sise_forecast import save_weflow_snapshot

    def _run(snapshot_json: str) -> dict[str, Any]:
        data = json.loads(snapshot_json)
        path = save_weflow_snapshot(data)
        return {
            "saved": True,
            "path": str(path),
            "range": data.get("range"),
            "term_count": len(data.get("terms") or []),
        }

    return _wrap("weflow_save_snapshot", agent_id, _run, snapshot_json=snapshot_json)


def chart_fast_render_kline(
    *,
    ts_code: str,
    name: str = "",
    fq: int = 2,
    agent_id: str = "hermes",
) -> dict[str, Any]:
    """极速四周期 K 线拼图（matplotlib Agg，并行拉数）。"""
    from src.analytics.fast_chart_renderer import render_multi_period_kline

    return _wrap(
        "chart_fast_render_kline",
        agent_id,
        render_multi_period_kline,
        ts_code=ts_code,
        name=name,
        fq=fq,
    )


def chart_fast_render_intraday(
    *,
    ts_code: str,
    name: str = "",
    trade_date: str = "",
    fq: int = 1,
    agent_id: str = "hermes",
) -> dict[str, Any]:
    """极速分时图（当日或指定 trade_date=YYYY-MM-DD）。"""
    from src.analytics.fast_chart_renderer import render_intraday_chart

    return _wrap(
        "chart_fast_render_intraday",
        agent_id,
        render_intraday_chart,
        ts_code=ts_code,
        name=name,
        trade_date=trade_date or None,
        fq=fq,
    )


def chart_vision_analyze(
    *,
    ts_code: str,
    name: str = "",
    fq: int = 2,
    data_only: bool = False,
    agent_id: str = "hermes",
    macd: bool = False,
    moving_averages: list[int] | None = None,
) -> dict[str, Any]:
    """出图 + 多模态 LLM 技术面分析（或 data_only 仅结构化数据）。"""
    from src.agents.chart_vision_agent import analyze_chart_data_only, analyze_chart_vision

    def _run(ts_code: str, name: str, fq: int, data_only: bool) -> dict[str, Any]:
        if data_only:
            return analyze_chart_data_only(ts_code=ts_code, name=name, fq=fq)

        from src.analytics.lwc_chart_renderer import render_lwc_multi_period_kline

        render_info = render_lwc_multi_period_kline(ts_code, name=name, fq=fq, macd=macd, moving_averages=moving_averages)
        path = Path(render_info["path"])
        image_bytes = path.read_bytes()
        analysis = analyze_chart_vision(
            image_bytes=image_bytes,
            mime="image/png",
            ts_code=ts_code,
            name=name,
            fq=fq,
            period_context=render_info["period_context"],
        )
        analysis["chart"] = {
            "path": str(path),
            "fetch_ms": render_info.get("fetch_ms"),
            "render_ms": render_info.get("render_ms"),
            "total_ms": render_info.get("total_ms"),
            "renderer": render_info.get("renderer"),
            "indicators": render_info.get("indicators"),
            "lwc_timings": render_info.get("lwc_timings"),
            "input_digest": render_info.get("input_digest"),
            "as_of": render_info.get("as_of"),
            "render_identity": render_info.get("render_identity"),
        }
        return analysis

    return _wrap(
        "chart_vision_analyze",
        agent_id,
        _run,
        ts_code=ts_code,
        name=name,
        fq=fq,
        data_only=data_only,
    )


def chart_lwc_render_kline(
    *,
    ts_code: str,
    name: str = "",
    fq: int = 2,
    agent_id: str = "hermes",
    macd: bool = False,
    moving_averages: list[int] | None = None,
) -> dict[str, Any]:
    """清晰K线、成交量和时价轴；均线与MACD可选。"""
    from src.analytics.lwc_chart_renderer import render_lwc_multi_period_kline

    return _wrap(
        "chart_lwc_render_kline",
        agent_id,
        render_lwc_multi_period_kline,
        ts_code=ts_code,
        name=name,
        fq=fq,
        macd=macd,
        moving_averages=moving_averages,
    )


def iwencai_search(
    *,
    question: str,
    wait_ms: int = 4000,
    max_pages: int = 0,
    headful: bool = False,
    limit: int = 0,
    agent_id: str = "hermes",
) -> dict[str, Any]:
    """同花顺问财自然语言选股（Playwright + 本机 Chrome，见 iwencai-cli）。"""

    def _run(
        question: str,
        wait_ms: int,
        max_pages: int,
        headful: bool,
        limit: int,
    ) -> dict[str, Any]:
        if not question.strip():
            raise ValueError("question 不能为空")
        try:
            from iwencai_cli.query import query_iwencai
        except ImportError as exc:
            raise RuntimeError(
                "iwencai-cli 未安装：pip install "
                "'git+https://github.com/shaw-baobao/iwencai-cli.git@v1.0.0'"
            ) from exc

        with _IWENCAI_LOCK:
            raw = query_iwencai(
                question.strip(),
                headless=not headful,
                wait_ms=wait_ms,
                max_pages=max_pages if max_pages > 0 else None,
            )

        rows = list(raw.get("rows") or [])
        total = len(rows)
        if limit > 0:
            rows = rows[:limit]

        return {
            "question": question.strip(),
            "count": len(rows),
            "total_scraped": total,
            "headers": raw.get("headers") or [],
            "pages": raw.get("pages") or 0,
            "rows": rows,
            "source": "iwencai-cli",
            "disclaimer": "问财筛选结果仅供参考，非投资建议",
        }

    return _wrap(
        "iwencai_search",
        agent_id,
        _run,
        question=question,
        wait_ms=wait_ms,
        max_pages=max_pages,
        headful=headful,
        limit=limit,
    )
