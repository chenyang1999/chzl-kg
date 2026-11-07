#!/usr/bin/env python3
"""
沧海巨浪 · 每日产出健康检查

检查各模块 (R1-R7 + D1 + 午盘 + E1) 的产出是否完整,
输出健康报告到 data/health/daily_check_YYYYMMDD.json。

用法:
    python scripts/health/check_daily_output.py [YYYYMMDD]
    python scripts/health/check_daily_output.py --all   # 检查所有日期

退出码: 0=全部正常, 1=有缺失, 2=严重错误
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KG_ROOT = ROOT / "chzl_kg/投研交易"
RESEARCH_DIR = ROOT / "data/research"
RAW_DIR = ROOT / "data/raw"
HEALTH_DIR = ROOT / "data/health"

# 定义检查项: (模块名, chzl_kg子目录名, data/research JSON 文件名, 必需级别)
# 必需级别: critical=必须每天有, important=最好有, nice=可有可无
CHECK_ITEMS = [
    # R 系列 (research pipeline 产出)
    ("R1 风格研判", "风格研判", "R1_style.json", "critical"),
    ("R2 主线研判", "主线研判", "R2_main_sectors.json", "critical"),
    ("R3 群聊情绪", "群聊情绪", "R3_sentiment.json", "critical"),
    ("R4 消息面", "消息面", "R4_news.json", "critical"),
    ("R5 个股画像", "个股画像", "R5_stock_profiles.json", "critical"),
    ("R6 反证", "反证", "R6_devil_advocate.json", "important"),
    ("R7 资金面", "资金面", "R7_capital_flow.json", "critical"),
    # D 系列 (decision)
    ("D1 盘前预案", "盘前预案", None, "critical"),  # JSON 在 data/runtime/
    # 盘中/盘后
    ("午盘 briefing", "午盘briefing", None, "important"),
    ("每日复盘 E1", "复盘记录", None, "important"),
    # 低频/周更
    ("事件追踪", "事件追踪", None, "nice"),  # 不是每日
    ("催化剂日历", "催化剂", None, "nice"),  # 每周一
    ("周度进化 E2", "周度进化", None, "nice"),  # 每周五
    ("席位与资金", "席位与资金", None, "nice"),  # 每周五
    ("扩池", "扩池", None, "nice"),
    ("红利池", "红利池", None, "nice"),  # 每月1号
    # 公众号（取阅 RSS · 2026-10-12 接入，替代已退场的 mptext/sanji）
    # 文件存在性校验：data/raw/YYYYMMDD/wechat_official_rss.jsonl
    ("公众号 RSS 源", None, "wechat_official_rss", "important"),
    # 历史兼容位：三刀源已停用，保留 optional 不阻塞
    ("公众号三刀源", None, "wechat_official_sanji", "optional"),
]

# 公众号 RSS 文件路径 (data/raw/YYYYMMDD/wechat_official_rss.jsonl)
RSS_FILE_PATTERN = re.compile(r"^wechat_official_rss\.jsonl$")
# 三刀公众号文件路径 (data/raw/YYYYMMDD/wechat_official_sanji_YYYYMMDD.jsonl)
SANJI_FILE_PATTERN = re.compile(r"^wechat_official_sanji_(\d{8})\.jsonl$")

# md 文件日期匹配 (支持 20260706.md 和 2026-07-06.md)
DATE_PATTERNS = [
    re.compile(r"^(\d{8})\.md$"),
    re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$"),
]


def get_trading_days(start: date, end: date) -> list[date]:
    """获取区间内的交易日 (简单按工作日, 不含节假日判断)"""
    days = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def check_date(trade_date: str) -> dict:
    """检查某一天的所有产出, 返回健康报告"""
    result = {
        "trade_date": trade_date,
        "checked_at": datetime.now().isoformat(),
        "items": {},
        "summary": {
            "total": 0,
            "ok": 0,
            "missing": 0,
            "critical_missing": 0,
            "important_missing": 0,
        },
    }

    for name, kg_dir, json_file, level in CHECK_ITEMS:
        item = {"level": level, "md_ok": False, "json_ok": True, "status": "ok"}

        # 检查 markdown (公众号三刀源无 md, 跳过)
        md_path = None
        if kg_dir:
            kg_path = KG_ROOT / kg_dir
            if kg_path.exists():
                for f in kg_path.iterdir():
                    if not f.is_file() or f.suffix != ".md":
                        continue
                    if ".bak" in f.name or f.name == "README.md":
                        continue
                    for pat in DATE_PATTERNS:
                        m = pat.match(f.name)
                        if m:
                            ds = m.group(1).replace("-", "")
                            if ds == trade_date:
                                md_path = f
                                break

        if md_path and md_path.stat().st_size > 100:
            item["md_ok"] = True
            item["md_size"] = md_path.stat().st_size
        else:
            item["md_ok"] = False

        # 检查 JSON (如果有定义)
        if json_file:
            # 公众号 RSS 源: data/raw/YYYYMMDD/wechat_official_rss.jsonl
            # 三刀源:     data/raw/YYYYMMDD/wechat_official_sanji_YYYYMMDD.jsonl
            if json_file in ("wechat_official_rss", "wechat_official_sanji"):
                if json_file == "wechat_official_rss":
                    src_path = RAW_DIR / trade_date / "wechat_official_rss.jsonl"
                else:
                    src_path = RAW_DIR / trade_date / f"wechat_official_sanji_{trade_date}.jsonl"
                if src_path.exists() and src_path.stat().st_size > 100:
                    item["json_ok"] = True
                    item["json_size"] = src_path.stat().st_size
                    # 顺便统计文章数
                    try:
                        n_lines = sum(1 for _ in src_path.open(encoding="utf-8"))
                        item["articles_count"] = n_lines
                    except Exception:
                        pass
                else:
                    item["json_ok"] = False
            else:
                jpath = RESEARCH_DIR / trade_date / json_file
                if jpath.exists() and jpath.stat().st_size > 50:
                    item["json_ok"] = True
                    item["json_size"] = jpath.stat().st_size
                else:
                    item["json_ok"] = False

        # 综合状态 (公众号源无 kg md, 只看 json)
        if kg_dir is None and json_file in ("wechat_official_rss", "wechat_official_sanji"):
            item["status"] = "ok" if item["json_ok"] else "missing"
        elif level == "nice":
            # nice 级别: 不参与 critical 统计
            item["status"] = "ok" if item["md_ok"] else "missing_nice"
        elif item["md_ok"] and item["json_ok"]:
            item["status"] = "ok"
        else:
            item["status"] = "missing"

        result["items"][name] = item
        result["summary"]["total"] += 1
        if item["status"] == "ok":
            result["summary"]["ok"] += 1
        else:
            result["summary"]["missing"] += 1
            if level == "critical":
                result["summary"]["critical_missing"] += 1
            elif level == "important":
                result["summary"]["important_missing"] += 1

    # 整体状态
    if result["summary"]["critical_missing"] > 0:
        result["overall"] = "error"
    elif result["summary"]["important_missing"] > 0:
        result["overall"] = "warning"
    else:
        result["overall"] = "ok"

    return result


def print_report(result: dict) -> None:
    """打印人类可读的健康报告"""
    td = result["trade_date"]
    overall = result["overall"]
    s = result["summary"]

    icon = {"ok": "✅", "warning": "⚠️", "error": "❌"}.get(overall, "❓")
    print(f"\n{icon} {td} · 产出健康检查")
    print(f"   整体: {overall} | 正常 {s['ok']}/{s['total']} | "
          f"缺失 {s['missing']} (critical={s['critical_missing']}, "
          f"important={s['important_missing']})")

    # 按级别分组显示
    for level in ["critical", "important", "nice"]:
        items = [(name, info) for name, info in result["items"].items()
                 if info["level"] == level]
        if not items:
            continue
        missing_items = [(n, i) for n, i in items if i["status"] != "ok"]
        ok_items = [(n, i) for n, i in items if i["status"] == "ok"]

        level_icon = {"critical": "🔴", "important": "🟡", "nice": "🔵"}[level]
        print(f"\n   {level_icon} {level.upper()} 级别:")
        if missing_items:
            for name, info in missing_items:
                reason_parts = []
                if not info["md_ok"]:
                    reason_parts.append("MD缺失")
                if not info.get("json_ok", True):
                    reason_parts.append("JSON缺失")
                print(f"      ✗ {name}: {', '.join(reason_parts)}")
        if ok_items:
            ok_names = ", ".join(n for n, _ in ok_items)
            print(f"      ✓ {len(ok_items)} 个正常: {ok_names}")


def main() -> int:
    parser = argparse.ArgumentParser(description="沧海巨浪 · 每日产出健康检查")
    parser.add_argument("date", nargs="?", default=None,
                        help="交易日 YYYYMMDD, 默认今天")
    parser.add_argument("--all", action="store_true",
                        help="检查所有有数据的日期")
    parser.add_argument("--range", nargs=2, metavar=("START", "END"),
                        help="检查日期范围 YYYYMMDD YYYYMMDD")
    parser.add_argument("--json", action="store_true",
                        help="输出 JSON 格式")
    args = parser.parse_args()

    HEALTH_DIR.mkdir(parents=True, exist_ok=True)

    # 确定检查哪些日期
    if args.all:
        # 找 data/research 下所有日期目录
        dates = sorted([
            p.name for p in RESEARCH_DIR.iterdir()
            if p.is_dir() and p.name.isdigit() and len(p.name) == 8
        ])
    elif args.range:
        start = datetime.strptime(args.range[0], "%Y%m%d").date()
        end = datetime.strptime(args.range[1], "%Y%m%d").date()
        dates = [d.strftime("%Y%m%d") for d in get_trading_days(start, end)]
    elif args.date:
        dates = [args.date]
    else:
        dates = [datetime.now().strftime("%Y%m%d")]

    results = []
    has_critical_error = False

    for td in dates:
        result = check_date(td)
        results.append(result)

        if not args.json:
            print_report(result)

        if result["overall"] == "error":
            has_critical_error = True

        # 保存到文件
        out_path = HEALTH_DIR / f"daily_check_{td}.json"
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    # 汇总 (多日期时)
    if len(dates) > 1 and not args.json:
        error_days = [r["trade_date"] for r in results if r["overall"] == "error"]
        warn_days = [r["trade_date"] for r in results if r["overall"] == "warning"]
        ok_days = [r["trade_date"] for r in results if r["overall"] == "ok"]

        print(f"\n{'='*60}")
        print(f"汇总: 共 {len(dates)} 天 | ✅ {len(ok_days)} | ⚠️ {len(warn_days)} | ❌ {len(error_days)}")
        if error_days:
            print(f"严重缺失天数: {', '.join(error_days)}")

    if args.json:
        if len(results) == 1:
            print(json.dumps(results[0], ensure_ascii=False, indent=2))
        else:
            print(json.dumps(results, ensure_ascii=False, indent=2))

    return 1 if has_critical_error else 0


if __name__ == "__main__":
    sys.exit(main())
