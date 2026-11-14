"""Pure, shared plan views. Never fetch prices, score, promote or authorise.

Only consume fields already present in the supplied plan. Ordinal scenario keys
are display identifiers, not new execution/schema fields. Unbound stock-wide
exits remain visibly stock-wide; prices from other entries/pools are not merged.
"""
from __future__ import annotations

from html import escape
import math
from typing import Any

MISSING = "⚠️未给"


def text(value: Any) -> str:
    """Escape untrusted cells before adding our own Markdown separators."""
    if value is None or value == "" or value == [] or value == {}:
        return MISSING
    if isinstance(value, dict):
        return "；".join(f"{text(k)}: {text(v)}" for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return "；".join(text(v) for v in value) or MISSING
    return (escape(str(value), quote=False).replace("|", "&#124;")
            .replace("`", "&#96;").replace("\r\n", "\n")
            .replace("\r", "\n").replace("\n", "<br>"))


def price(value: Any) -> str:
    if isinstance(value, bool):
        return MISSING
    try:
        number = float(value)
    except (TypeError, ValueError):
        return MISSING
    return f"{number:.2f}" if math.isfinite(number) and number > 0 else MISSING


def percent(value: Any) -> str:
    if isinstance(value, bool):
        return MISSING
    try:
        number = float(value)
    except (TypeError, ValueError):
        return MISSING
    return f"{number * 100:g}%" if math.isfinite(number) else MISSING


def table(headers: list[str], rows: list[list[str]]) -> list[str]:
    return ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)] + [
        "| " + " | ".join(row) + " |" for row in rows] + [""]


def _items(value: Any) -> list[dict]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def decision_origin(plan: dict) -> tuple[str, bool]:
    """One source policy for both reports; any fallback evidence wins conflicts."""
    meta = plan.get("meta") or {}
    fallback = bool(plan.get("is_fallback") or meta.get("python_fallback")
                    or plan.get("decision_source") == "python_fallback"
                    or meta.get("decision_source") == "python_fallback")
    source = "python_fallback" if fallback else (
        plan.get("decision_source") or meta.get("decision_source") or "unknown")
    return str(source), fallback


def _fields(obj: dict, fields: tuple[str, ...], percentages: tuple[str, ...] = ()) -> str:
    """Display supplied structured gates, including zero/False/empty lists.

    Do not infer defaults or borrow a gate from another entry. Retain field names
    so a generic narrative cannot masquerade as the actual execution threshold.
    """
    return "；".join(f"{key}=" + (percent(obj[key]) if key in percentages else
        "[]" if obj[key] == [] else text(obj[key])) for key in fields if key in obj)


def _permissions(stock: dict) -> str:
    return (f"auto_trade_enabled={text(stock.get('auto_trade_enabled'))}；"
            f"requires_user_confirmation={text(stock.get('requires_user_confirmation'))}")


def _sector_name(stock: dict) -> str:
    return str(stock.get("sector") or stock.get("theme") or "独立／关系未确认")


def _directions(plan: dict) -> list[dict]:
    return _items((plan.get("seesaw_plan") or {}).get("seesaw_directions"))


def _sectors(plan: dict) -> list[dict]:
    # Keep the supplied independent sector judgement; membership is not evidence
    # of diffusion, leadership or causality. Do not infer strength from prices.
    sectors = list(_items(plan.get("sector_core_watchlist")))
    names = {s.get("sector") for s in sectors}
    stocks = _items(plan.get("execution_pool")) + _items(plan.get("watch_pool"))
    for direction in _directions(plan):
        stocks += _items(direction.get("candidates"))
    for stock in stocks:
        name = _sector_name(stock)
        if name not in names:
            sectors.append({"sector": name})
            names.add(name)
    return sectors


def render_sector_overview(plan: dict) -> list[str]:
    rows = []
    for s in _sectors(plan):
        leaders = s.get("core_leaders") or s.get("leaders")
        scenes = []
        for key, label in (("execution_pool", "主剧本／执行"), ("watch_pool", "观察")):
            if any(_sector_name(stock) == s.get("sector") for stock in _items(plan.get(key))):
                scenes.append(label)
        for direction in _directions(plan):
            if any(_sector_name(stock) == s.get("sector") for stock in _items(direction.get("candidates"))):
                scenes.append("反向：" + text(direction.get("direction")) + "；触发 " + text(direction.get("trigger")))
        rows.append([text(s.get("sector")), text(s.get("round") or s.get("stage")),
            text(s.get("sector_status")), text(leaders),
            text(s.get("source_evidence")) if s.get("source_evidence") else "关系证据未给（概念归属不证明联动）",
            "；".join(scenes) or MISSING,
            text(s.get("trigger") or s.get("intraday_low_absorption_rules")),
            text(s.get("invalidation")), text(s.get("captured_at") or s.get("data_date"))])
    lines = ["## 板块机会总览", "", "市场背景：" + text((plan.get("market_context") or {}).get("structure")), "",
             "> 先市场／板块效应，再个股地位；未提供关系证据不推断龙头带动或板块扩散。", ""]
    lines += table(["板块／本轮行情", "阶段／窗口", "效应与延续", "核心与梯队（上游标签）",
                    "共振／分离证据", "主／反向剧本（名单归属非关系证明）", "确认条件", "共同失效条件", "观测时点"], rows)
    return lines


def _review_overview(plan: dict) -> list[str]:
    """Keep completion, review result and explicit counts independent."""
    meta = plan.get("meta")
    r6 = meta.get("r6_devil_advocate") if isinstance(meta, dict) else None
    r6 = r6 if isinstance(r6, dict) else {}
    unknown = "未知（未提供或类型无效）"

    def flag(value: Any, yes: str, no: str) -> str:
        return yes if value is True else no if value is False else unknown

    def count(value: Any) -> str:
        return str(value) if type(value) is int and value >= 0 else unknown

    rows = [
        ["研究是否完成（research_completion_passed）",
         flag(plan.get("research_completion_passed"), "已完成", "未完成")],
        ["正式反证是否完成（meta.r6_devil_advocate.formal_review_completed）",
         flag(r6.get("formal_review_completed"), "已完成", "未完成")],
        ["正式反证是否通过（meta.r6_devil_advocate.review_passed）",
         flag(r6.get("review_passed"), "通过", "未通过（不等于硬否决）")],
        ["正式评估数（meta.r6_devil_advocate.candidates_evaluated）",
         count(r6.get("candidates_evaluated"))],
        ["已阅读研究对象数（meta.r6_devil_advocate.research_objects_inspected）",
         count(r6.get("research_objects_inspected"))],
        ["硬否决数（meta.r6_devil_advocate.hard_rejects_applied）",
         str(len(r6["hard_rejects_applied"])) if isinstance(r6.get("hard_rejects_applied"), list) else unknown],
        ["生产就绪（production_ready）", flag(plan.get("production_ready"), "是", "否")],
        ["需要重评（reassessment_required）", flag(plan.get("reassessment_required"), "是", "否")],
    ]
    return ["### 研究与正式反证状态（仅展示）", "",
        "> 未完成不等于已审否决；已阅读不等于正式评估；硬否决数仅为已应用清单条数，0不等于反证通过。缺字段显式未知，不从池数量或原因文字推断；本表不改变买卖权限。", ""] + table(
            ["指标（已有JSON字段）", "状态／数量"], rows)


def render_constraints(plan: dict) -> list[str]:
    rl = plan.get("risk_limits") or {}
    lines = ["## 全局约束与数据边界", "",
        f"- 模式：{text(plan.get('mode'))}；自动交易：{text(plan.get('autonomous_trading_enabled'))}；需用户确认：{text(plan.get('requires_user_confirmation'))}",
        f"- 总仓上限：{percent(rl.get('target_total_position_pct'))}；持仓上限：{text(rl.get('max_positions'))}；每日买单上限：{text(rl.get('max_buy_orders_per_day'))}",
        f"- 单票上限：{percent(rl.get('single_stock_max_pct'))}；单板块上限：{percent(rl.get('single_sector_max_pct'))}",
        "- 表格仅展示已给计划，不构成自动下单授权；观察／反向候选不自动晋级。候选数量不等于持仓名额。",
        "- 评分未校准：未批准评分公式，不采用旧 score／默认50／板块分充个股分；原序展示，不另行排名。",
        "- 静态价位非实时；数据日、复权／报价口径、有效期或动态线更新时间未给时均未核验，不以计划生成时间冒充价格时点。",
        "- 新买入当日不可卖（T+1）；底仓是否可卖未核验。触发信号不保证可卖或成交。", ""]
    lines += _review_overview(plan)
    hard_limits = _fields(rl, ("account_hard_stop_loss_pct", "block_prefixes", "block_st",
        "max_orders_per_symbol_per_day", "kill_switch_file"), ("account_hard_stop_loss_pct",))
    if hard_limits:
        lines += ["- 强制风控（原字段）：" + hard_limits, ""]
    for sector in _items(plan.get("sector_core_watchlist")):
        if "off_limit" in sector:
            lines.append(f"- 板块禁入 {text(sector.get('sector'))}：" +
                         _fields(sector, ("off_limit",)))
    if plan.get("no_trade"):
        lines += ["> 全局禁止开仓（no_trade）；研究与观察保留。", ""]
    for c in _items(plan.get("no_trade_conditions")):
        active = c.get("active")
        state = ("触发中／禁止开仓" if active is True else
                 "未触发" if active is False else "未知／未核验（不得视为已解除）")
        lines.append(f"- 不交易条件 {text(c.get('code'))}：{state}；{text(c.get('description'))}")
    return lines + [""]


def _stamp(stock: dict, entry: dict) -> str:
    # No fallback to generated_at: production date is not quote date.
    fields = ("data_date", "reference_date", "captured_at", "updated_at", "price_source", "price_src", "price_fq", "valid_until")
    parts = [f"{key}={text(entry.get(key, stock.get(key)))}" for key in fields
             if entry.get(key, stock.get(key)) is not None]
    return ("；".join(parts) + "；" if parts else "") + "数据日／有效期未核验；非实时"


def _exits(stock: dict, entry: dict) -> tuple[list[dict], str]:
    if "exit_rules" in entry:
        return _items(entry["exit_rules"]), "本场景"
    if len(_items(stock.get("entry_rules"))) > 1:
        return [], "多场景未绑定（个股共用退出见逐票说明）"
    return _items(stock.get("exit_rules")), "个股共用"


def _exit_text(rule: dict) -> str:
    return (f"{text(rule.get('type'))} @ {price(rule.get('trigger_price'))}；比例 {percent(rule.get('quantity_pct'))}；"
            f"条件 {text(rule.get('trigger_condition'))}；理由 {text(rule.get('reason'))}；"
            f"生效 {text(rule.get('effective_from'))}；窗口 {text(rule.get('time_window'))}")


def _group(stock: dict, pool: str) -> str:
    reason = str(stock.get("watch_reason_code") or "")
    if stock.get("research_anchor_only") or reason in {
        "sentiment_anchor_no_trade", "height_thermometer", "event_map_only",
        "institution_distribution", "distribution_alert", "fundamental_rejected_recheck"}:
        return "仅观察／禁买（不建议开仓）"
    # Display explicit existing evidence only; do not evaluate or promote.
    qualification = stock.get("buy_eligibility")
    qualification = qualification if isinstance(qualification, dict) else {}
    status = qualification.get("status")
    if status == "blocked":
        return "买入资格受阻／当前禁止新买（非永久否决）"
    if status == "unknown":
        return "买入资格未知／待复核（非已审否决）"
    if stock.get("review_required") is True or qualification.get("review_required") is True:
        return "买入资格待复核（非已审否决）"
    if pool == "观察池":
        if status == "eligible":
            return "等待条件（非自动晋级／非买入授权）"
        return "等待条件／资格未核验" if stock.get("entry_rules") else "仅观察／缺证待补"
    return "反向条件待确认（非自动激活）" if pool.startswith("B计划") else "执行候选／交易资格仍依原门禁"


def render_pool_reference(plan: dict, stocks: list[dict], pool: str, context: dict | None = None) -> list[str]:
    """Paired rows use the same display-only ordinal key, without truncation."""
    context = context or {}
    lines = [f"### {text(pool)}逐票说明", ""]
    buys, risks = [], []
    sector_map = {s.get("sector"): s for s in _sectors(plan)}
    for index, stock in enumerate(stocks, 1):
        lines += [f"- {text(stock.get('name'))} {text(stock.get('ts_code'))}：{text(stock.get('reason') or stock.get('entry_note'))}；状态 {text(stock.get('plan_status'))}；{_group(stock, pool)}；单票上限 {percent(stock.get('max_position_pct'))}；逐票权限 {_permissions(stock)}"]
        for field, label in (("alpha_logic", "买入依据"), ("t1_game_analysis", "T+1博弈（原判断）"),
                             ("r6_suggestion", "反证")):
            if stock.get(field):
                lines.append(f"  - {label}：{text(stock[field])}")
        character = stock.get("stock_character") or {}
        metrics = {k: v for k, v in character.items() if k != "score"}
        if metrics:
            lines.append("  - 股性已有字段（非综合质量分）：" + text(metrics))
            lines.append("    - 保真提示：上游缺值／非法值／NaN可能已补0，0不必然是实测零；统计窗口／样本数／数据时点以显式提供值为准，未给部分不可推断；不代表当前策略胜率。")
        entries = _items(stock.get("entry_rules"))
        if len(entries) > 1:
            for rule in _items(stock.get("exit_rules")):
                lines.append("  - 个股共用退出（多场景未绑定，不指派给任一买入场景）：" + _exit_text(rule))
        # B-plan price engine already writes scalar levels on the candidate.
        # This is its own scene, never a lookup/merge from the watch pool.
        fallback = stock if (stock.get("buy_zone") or stock.get("pullback_zone")
                             or price(stock.get("trigger_price")) != MISSING) else {}
        for ordinal, entry in enumerate(entries or [fallback], 1):
            key = f"{pool}:{index}:{stock.get('ts_code', '未给')}:{ordinal}"
            ident = text(key) + "<br>" + text(stock.get("name"))
            sector = sector_map.get(_sector_name(stock), {})
            zone = entry.get("buy_zone") or entry.get("pullback_zone")
            zone_text = " ~ ".join(price(v) for v in zone) if isinstance(zone, (list, tuple)) and len(zone) == 2 else MISSING
            confirms = ["板块：" + text(sector.get("trigger") or sector.get("intraday_low_absorption_rules")),
                        "量价：" + text(entry.get("execution_logic")),
                        "反向触发：" + text(context.get("trigger"))] if context else [
                        "板块：" + text(sector.get("trigger") or sector.get("intraday_low_absorption_rules")),
                        "量价：" + text(entry.get("execution_logic"))]
            confirms += ["本场景依据：" + text(entry.get("derivation_reason") or entry.get("engine_formula")),
                         "需盘中确认：" + text(entry.get("requires_intraday_confirm")),
                         "原建议仓位：" + percent(entry.get("position_pct"))]
            gates = _fields(entry, ("entry_target_price", "max_premium_pct", "confirm_price",
                "reclaim_price", "sealed_bid_threshold", "max_break_count_today", "only_first_seal",
                "t_round_limit", "one_word_no_chase", "post_event_only"), ("max_premium_pct",))
            if gates:
                confirms.append("执行硬门槛（原字段）：" + gates)
            invalid = "；".join([text(sector.get("invalidation")),
                "逐票权限 " + _permissions(stock),
                "板块禁入 " + _fields(sector, ("off_limit",)),
                "场景禁令 " + text(entry.get("no_trade_conditions")),
                "个股禁令 " + text(stock.get("no_trade_conditions")),
                "观察原因 " + text(stock.get("watch_reason_code")),
                "原资格 " + text(stock.get("buy_eligibility")),
                "利空反证 " + text(stock.get("bearish_hit"))])
            if entry.get("one_word_no_chase"):
                invalid += "；一字不追，等开板承接"
            if plan.get("no_trade") or any(c.get("active") is True for c in _items(plan.get("no_trade_conditions"))):
                invalid += "；全局禁止开仓"
            buys.append([ident, f"原序{index}／{text(stock.get('priority'))}", text(pool) + "／" + _group(stock, pool),
                text(_sector_name(stock)) + "／" + text(stock.get("role")),
                "未校准／评分时点未给", text(entry.get("type")) + "／" + text(stock.get("reason") or stock.get("entry_note")),
                text(entry.get("time_window")), price(entry.get("trigger_price")), zone_text,
                price(entry.get("max_acceptable_ask")), "；".join(confirms), invalid])
            exits, binding = _exits(stock, entry)
            # Never apply the first entry's/global scalar prices to every entry.
            scalar_source = stock if len(entries) <= 1 else {}
            stop = entry.get("stop_loss", scalar_source.get("stop_loss"))
            take = entry.get("take_profit", scalar_source.get("take_profit"))
            engine = stock.get("engine_levels") or {}
            engine_note = ("；引擎参考（非场景绑定）：止损 " + price(engine.get("stop_loss"))
                           + "／止盈 " + price(engine.get("take_profit"))
                           + "；来源 " + text(engine.get("price_src"))) if engine else ""
            stop_rules = [r for r in exits if r.get("type") == "stop_loss_break"]
            take_rules = [r for r in exits if r.get("type") == "take_profit_hit"]
            other_rules = [r for r in exits if r.get("type") not in {"stop_loss_break", "take_profit_hit"}]
            risks.append([ident, price(stop) + "；" + binding,
                "<br>".join(_exit_text(r) for r in stop_rules) or MISSING,
                price(take) + "；" + ("<br>".join(_exit_text(r) for r in take_rules) or MISSING),
                "<br>".join(_exit_text(r) for r in other_rules) or "移动止盈／其他退出未给",
                invalid, "T+1：新增仓当日不可卖；底仓可卖数量未给；触价不保证成交",
                "昨收 " + price(stock.get("reference_close")) + "；" + _stamp(stock, entry) + engine_note])
    lines += ["", f"### {text(pool)}机会与买入", ""]
    lines += table(["股票／场景键", "优先级（原计划）", "池／当前状态", "所属板块／角色", "质量分／评分时点",
                    "机会类型与理由", "时间窗", "触发价", "可买区间", "最高接受价", "板块／量价确认", "不做／取消条件"], buys)
    lines += [f"### {text(pool)}退出与风险", ""]
    lines += table(["股票／对应场景键", "初始止损／绑定范围", "止损依据与动作", "分档止盈价及动作",
                    "移动止盈／其他退出", "失效／取消条件", "可卖限制", "数据时点与缺口"], risks)
    if not stocks:
        lines += ["> 本池为空；无对象不凑数，原因须由决策者提供。", ""]
    return lines


def render_seesaw_reference(plan: dict) -> list[str]:
    b = plan.get("seesaw_plan") or {}
    lines = ["## 反向剧本／B计划", "", "总触发：" + text(b.get("trigger_conditions")),
             "互斥／共同失效：" + text(b.get("opposite_side_note")),
             "关系：仅展示原剧本，不推断主／反向可同时买入；不得跨池借用未绑定场景价位。", ""]
    for index, direction in enumerate(_directions(plan), 1):
        lines += [f"方向：{text(direction.get('direction'))}；触发：{text(direction.get('trigger'))}；证据：{text(direction.get('source_evidence'))}", ""]
        lines += render_pool_reference(plan, _items(direction.get("candidates")), f"B计划{index}", direction)
    if not _directions(plan):
        lines += ["> 反向方向／候选未给，不自动补票。", ""]
    return lines
