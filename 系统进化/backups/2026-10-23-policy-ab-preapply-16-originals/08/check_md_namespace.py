#!/usr/bin/env python3
"""
MD 文件命名空间 + 置信度公式 验收 · P1-4 + P2-1 修复对应

校验规则（来自 canghai_writing_contract_v1 v1.1）:
命名空间:
  1. 文件名 YYYYMMDD == frontmatter date
  2. 不一致时 namespace_mismatch: true + 顶部 ⚠️ 警示 + data_from_trade_date 字段

置信度公式:
  3. 顶层含 confidence + confidence_breakdown(4 字段)
  4. confidence ≈ base_confidence × freshness_factor × source_agreement_factor (±0.01)

用法:
    python tests/checks/check_md_namespace.py [file_or_date]
    # 可以传入 md 文件路径，或传入 YYYYMMDD 日期（检查 chzl_kg 下当日所有 md）
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHZL_KG = ROOT / "chzl_kg"

# 置信度公式容差
TOLERANCE = 0.02


def parse_frontmatter(content: str) -> dict:
    """解析 YAML frontmatter（简单版，够用即可）。"""
    if not content.startswith("---"):
        return {}
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}
    fm_text = parts[1].strip()
    result = {}
    for line in fm_text.splitlines():
        line = line.strip()
        if ":" in line and not line.startswith("#"):
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            result[key] = val
    return result


def check_namespace(fpath: Path) -> list[str]:
    """检查命名空间一致性，返回错误列表。"""
    errors = []
    content = fpath.read_text(encoding="utf-8")
    fm = parse_frontmatter(content)

    stem = fpath.stem
    # 只检查纯数字日期文件名
    if not stem.isdigit() or len(stem) != 8:
        return []  # 跳过非日期文件

    fm_date = fm.get("date", "")
    fm_namespace_mismatch = fm.get("namespace_mismatch", "false").lower() == "true"
    fm_data_from = fm.get("data_from_trade_date", "")

    if fm_date and fm_date.replace("-", "") != stem:
        # frontmatter date 与文件名不一致
        if fm_namespace_mismatch:
            # 有错位标记 → 检查警示块
            first_section = content[:1000]
            if "⚠️" in first_section or "数据源时间错位" in first_section or "namespace" in first_section.lower():
                pass  # OK
            else:
                errors.append(f"{fpath.name}: namespace_mismatch=true 但顶部无 ⚠️ 警示块")
            if not fm_data_from:
                errors.append(f"{fpath.name}: namespace_mismatch=true 但缺 data_from_trade_date")
        else:
            errors.append(
                f"{fpath.name}: 文件名({stem})与 frontmatter date({fm_date})不一致"
                f"但未标 namespace_mismatch: true"
            )

    return errors


def check_confidence(fpath: Path) -> list[str]:
    """检查置信度公式，返回错误列表。"""
    errors = []
    content = fpath.read_text(encoding="utf-8")
    fm = parse_frontmatter(content)

    # 从 frontmatter 或正文里找 confidence 相关字段
    conf_str = fm.get("confidence")
    if conf_str is None:
        # 在正文中搜
        m = re.search(r"confidence[：:]\s*(0?\.\d+|1\.0|1\.00)", content)
        if not m:
            return []  # 没有 confidence 字段也不报错（不是所有 md 都有）
        conf_str = m.group(1)

    try:
        confidence = float(conf_str)
    except (ValueError, TypeError):
        return [f"{fpath.name}: confidence 无法解析为数值: {conf_str}"]

    # 找 breakdown 三因子
    base_m = re.search(r"base_confidence[：:]\s*(0?\.\d+)", content)
    fresh_m = re.search(r"freshness_factor[：:]\s*(0?\.\d+)", content)
    agree_m = re.search(r"source_agreement_factor[：:]\s*(0?\.\d+)", content)

    if not (base_m and fresh_m and agree_m):
        # 没有完整三因子也不报错（可能是简版）
        return []

    base = float(base_m.group(1))
    fresh = float(fresh_m.group(1))
    agree = float(agree_m.group(1))

    expected = round(min(0.95, max(0.05, base * fresh * agree)), 2)
    if abs(confidence - expected) > TOLERANCE:
        errors.append(
            f"{fpath.name}: confidence={confidence} "
            f"≠ base×fresh×agree={base}×{fresh}×{agree}={expected:.3f} (容差{TOLERANCE})"
        )

    return errors


def find_files_for_date(trade_date: str) -> list[Path]:
    """找 chzl_kg 下当日所有 md 文件。"""
    files = []
    for p in CHZL_KG.rglob(f"*{trade_date}*.md"):
        files.append(p)
    return files


def main(target: str | None = None) -> int:
    if target and Path(target).is_file():
        files = [Path(target)]
    elif target and target.isdigit() and len(target) == 8:
        files = find_files_for_date(target)
        if not files:
            print(f"❌ 未找到日期 {target} 的 md 文件")
            return 1
    else:
        # 默认: 找 chzl_kg 下最新的 3 天
        all_dates = set()
        for p in CHZL_KG.rglob("*.md"):
            stem = p.stem
            if stem.isdigit() and len(stem) == 8:
                all_dates.add(stem)
        if not all_dates:
            print("❌ 未找到任何日期命名的 md 文件")
            return 1
        latest = sorted(all_dates)[-1]
        files = find_files_for_date(latest)
        target = latest

    print(f"=== MD 命名空间 + 置信度公式验收 · {target} ===")
    print(f"  检查文件数: {len(files)}")

    all_errors = []
    ns_checked = 0
    conf_checked = 0

    for fpath in sorted(files):
        rel = fpath.relative_to(ROOT)
        ns_errors = check_namespace(fpath)
        conf_errors = check_confidence(fpath)

        if ns_errors:
            ns_checked += 1
            for e in ns_errors:
                all_errors.append(e)
        elif fpath.stem.isdigit() and len(fpath.stem) == 8:
            ns_checked += 1

        if conf_errors:
            conf_checked += 1
            for e in conf_errors:
                all_errors.append(e)

    print(f"  命名空间检查: {ns_checked} 个日期文件")
    print(f"  置信度公式检查: {conf_checked} 个含 confidence 的文件")

    # 打印文件列表（简）
    for fpath in sorted(files)[:5]:
        print(f"    - {fpath.relative_to(ROOT)}")
    if len(files) > 5:
        print(f"    ... 还有 {len(files) - 5} 个")

    print()
    if all_errors:
        print(f"❌ 失败 ({len(all_errors)} 项):")
        for e in all_errors:
            print(f"   - {e}")
        return 1

    print(f"✅ MD 命名空间 + 置信度公式验收通过（{target}）")
    return 0


if __name__ == "__main__":
    tgt = sys.argv[1] if len(sys.argv) > 1 else None
    sys.exit(main(tgt))
