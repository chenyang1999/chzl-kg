"""多周期 K 线视觉识图 + 结构化量价上下文 → 买卖点建议。"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any

from openai import OpenAI

DEFAULT_VISION_MODEL = "deepseek-v4.1-flash-1017"


def _vision_client() -> OpenAI:
    """视觉 LLM 客户端。

    2026-09-30：支持独立配置视觉通道，不再硬绑 OPENAI_API_BASE。
    背景：出图后要调多模态模型识图，原实现只有 apiyi 一条路；用户希望
    可切到火山引擎（ARK）豆包 vision。

    解析顺序（先到先用）：
      1. VISION_API_BASE / VISION_API_KEY   ← 显式视觉连接
      2. OPENAI_API_BASE / OPENAI_API_KEY  ← 原行为（apiyi）
    看图型号单独由 CHART_VISION_MODEL 覆盖；默认用户指定的DeepSeek版本。
    默认不改变现有行为：不设 VISION_* 时完全等同改造前。
    """
    base = (os.environ.get("VISION_API_BASE") or os.environ.get("OPENAI_API_BASE", "")).strip()
    key = (os.environ.get("VISION_API_KEY") or os.environ.get("OPENAI_API_KEY", "")).strip()
    if not base or not key:
        raise ValueError("视觉通道未配置：需要 VISION_API_BASE/VISION_API_KEY 或 OPENAI_API_BASE/OPENAI_API_KEY")
    return OpenAI(base_url=base, api_key=key, timeout=float(os.environ.get("VISION_TIMEOUT", "180")), max_retries=0)


def _complete(**kwargs):
    with _vision_client() as client:
        return client.chat.completions.create(**kwargs)


def _vision_model() -> str:
    """Chart-specific model; do not inherit a stale generic/other-image model."""
    return os.environ.get("CHART_VISION_MODEL", "").strip() or DEFAULT_VISION_MODEL


def analysis_identity() -> dict[str, str]:
    return {"model": _vision_model(), "prompt_sha256": hashlib.sha256(VISION_PROMPT.encode()).hexdigest()}


def _ma(closes: list[float], period: int) -> float | None:
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def _build_period_context(ts_code: str, period: str, days: int, fq: int) -> dict[str, Any]:
    from src.api.market_data import fetch_chart_bars
    data = fetch_chart_bars(ts_code, days=days, period=period, fq=fq)
    candles = data.get("candles") or []
    if not candles:
        return {"period": period, "label": period, "empty": True}

    closes = [float(c["close"]) for c in candles]
    highs = [float(c["high"]) for c in candles]
    lows = [float(c["low"]) for c in candles]
    last = candles[-1]
    prev = candles[-2] if len(candles) > 1 else last

    ma5 = _ma(closes, 5)
    ma20 = _ma(closes, 20)
    ma60 = _ma(closes, 60)
    hi20 = max(highs[-20:]) if len(highs) >= 20 else max(highs)
    lo20 = min(lows[-20:]) if len(lows) >= 20 else min(lows)
    pct = ((closes[-1] - float(prev["close"])) / float(prev["close"]) * 100) if prev else 0

    trend = "震荡"
    if ma20 and ma60:
        if closes[-1] > ma20 > ma60:
            trend = "多头排列"
        elif closes[-1] < ma20 < ma60:
            trend = "空头排列"

    return {
        "period": period,
        "count": len(candles),
        "last_date": last.get("time"),
        "close": round(closes[-1], 4),
        "pct_chg": round(pct, 2),
        "ma5": round(ma5, 4) if ma5 else None,
        "ma20": round(ma20, 4) if ma20 else None,
        "ma60": round(ma60, 4) if ma60 else None,
        "high20": round(hi20, 4),
        "low20": round(lo20, 4),
        "trend": trend,
        "source": data.get("source"),
    }


def build_multi_period_context(
    ts_code: str,
    periods: list[dict[str, Any]],
    fq: int = 2,
) -> list[dict[str, Any]]:
    out = []
    for item in periods:
        period = str(item.get("period", "1d"))
        days = int(item.get("days") or 365)
        ctx = _build_period_context(ts_code, period, days, fq)
        if item.get("label"):
            ctx["label"] = item["label"]
        out.append(ctx)
    return out


VISION_PROMPT = """你是 A 股技术面看盘 Agent。用户上传了一张「多周期 K 线拼图」（通常含日K/周K/60分/15分），并附上各周期量价摘要。

请结合图像形态与同源 JSON 数据，给出关键价位、结构及验证条件，供决策Agent研究。
你不掌握完整主线、市场情绪或账户信息，不直接制定仓位、下单或卖出指令。

关注形态：突破、回踩、低吸、高抛、趋势延续、背离、放量、关键均线/牛熊线位置。

只输出 JSON：
{
  "summary": "2-4句综合判断",
  "bias": "偏多|偏空|震荡",
  "pattern": "1-2句描述真实图形结构",
  "volume_signal": "量能判断及依据，缺失则明确说明",
  "confidence": 0.0-1.0,
  "signals": [
    {
      "type": "突破观察|支撑观察|压力观察|破位风险|观望",
      "period": "日K|周K|60分|15分",
      "confidence": 0.0-1.0,
      "price_hint": 数字或null,
      "reason": "依据"
    }
  ],
  "risks": ["风险1", "风险2"],
  "action": "一句话说明接下来验证什么条件，不是下单指令",
  "disclaimer": "仅供参考，不构成投资建议"
}

signals 至少 1 条、至多 5 条；若无明确机会，type 用「观望」。
这是技术研究参考，不是交易授权。以附带行情的真实日期、价格和price_anchors为依据；
支撑/压力应注明对应日期或结构，无法定位的price_hint为null，不从图片像素编造精确价格。
低吸指预判强势票当日冲涨停时的相对低位介入，不等于大跌接飞刀；仅靠本图不能证明该预判。
明确跨周期矛盾、缺失周期和不确定性，不因缺某个可选指标就否决股票。"""


def analyze_chart_vision(
    image_bytes: bytes,
    mime: str,
    ts_code: str,
    name: str = "",
    periods: list[dict[str, Any]] | None = None,
    fq: int = 2,
    period_context: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    periods = periods or [
        {"period": "1d", "days": 365, "label": "日K"},
        {"period": "1w", "days": 520, "label": "周K"},
        {"period": "60m", "days": 60, "label": "60分"},
        {"period": "15m", "days": 30, "label": "15分"},
    ]
    context = period_context if period_context is not None else build_multi_period_context(ts_code, periods, fq=fq)
    model = _vision_model()
    b64 = base64.b64encode(image_bytes).decode("ascii")

    user_text = (
        f"股票：{name or ts_code} ({ts_code})\n"
        f"复权：{'前复权' if fq == 2 else '不复权' if fq == 1 else f'fq={fq}'}\n"
        f"各周期摘要：\n{json.dumps(context, ensure_ascii=False, indent=2)}"
    )

    resp = _complete(
        model=model,
        messages=[
            {"role": "system", "content": VISION_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            },
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content or "{}"
    result = json.loads(content)
    if not isinstance(result, dict) or not isinstance(result.get("signals"), list) or not result.get("summary"):
        raise ValueError("vision response is missing the structured technical analysis")
    result["ts_code"] = ts_code
    result["name"] = name
    result["fq"] = fq
    result["period_context"] = context
    result["model"] = model
    result["response_model"] = resp.model
    result["analysis_identity"] = analysis_identity()
    result["price_hint_role"] = "technical_reference_not_execution_authorization"
    result["trend"] = result.get("trend") or result.get("bias", "unknown")
    result["pattern"] = result.get("pattern") or result["summary"]
    result["key_levels"] = result.get("key_levels") or [
        {"period": s.get("period"), "price": s["price_hint"], "kind": s.get("type"), "reason": s.get("reason")}
        for s in result["signals"] if isinstance(s, dict) and s.get("price_hint") is not None
    ]
    result["volume_signal"] = result.get("volume_signal") or "模型未单列量能结论，不能视为量能确认"
    return result


def analyze_chart_data_only(
    ts_code: str,
    name: str = "",
    periods: list[dict[str, Any]] | None = None,
    fq: int = 2,
) -> dict[str, Any]:
    """无图时仅用结构化数据（降级）。"""
    periods = periods or [
        {"period": "1d", "days": 365, "label": "日K"},
        {"period": "1w", "days": 520, "label": "周K"},
    ]
    context = build_multi_period_context(ts_code, periods, fq=fq)
    model = _vision_model()
    prompt = (
        f"{VISION_PROMPT}\n\n无截图，仅根据以下数据给建议：\n"
        f"{json.dumps({'ts_code': ts_code, 'name': name, 'periods': context}, ensure_ascii=False)}"
    )
    resp = _complete(
        model=model,
        messages=[
            {"role": "system", "content": "你只输出合法 JSON 对象。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        response_format={"type": "json_object"},
    )
    result = json.loads(resp.choices[0].message.content or "{}")
    result["ts_code"] = ts_code
    result["period_context"] = context
    result["model"] = model
    result["mode"] = "data_only"
    return result
