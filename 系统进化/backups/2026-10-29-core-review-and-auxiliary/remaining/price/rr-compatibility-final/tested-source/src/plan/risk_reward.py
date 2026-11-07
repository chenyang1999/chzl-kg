"""
risk_reward.py · 盈亏比判断 + 仓位建议（2026-09-04 · 游资交易纪律落地）

纪律依据（新生代游资交易纪律.md）:
    铁律6: 盈亏比优先于胜率——强于预期加一点仓，弱于预期减仓。大肉来自少数核心单
    仓位纪律: 单票1-2成，到1/3算重仓; 试错期≤3成，主升期6-8成分2-4只; 满仓需三点共振
    铁律7: 合力来自全市场，不是游资抱团

盈亏比 = 预期盈利空间 / 预期亏损空间 = (止盈价-买入价) / (买入价-止损价)

关键: 游资盈亏比是"预期"不是"事后"。要在买入前用买点、止盈、止损三价算出。
按用户方法论: 买入分歧卖出一致，在确定性最高位置上车拿最丰厚利润，人声鼎沸时离场。
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class RiskRewardResult:
    trade_date: str
    ts_code: str
    name: str
    buy_price: float
    take_price: float
    stop_price: float
    risk_reward_ratio: float       # 盈亏比 (take-buy)/(buy-stop)
    profit_pct: float              # 预期盈利 %
    loss_pct: float                # 预期亏损 %
    position_suggestion_pct: float  # 建议仓位 %
    position_tier: str             # 建议仓位档: core_main / core / trial / none
    grade_check: str               # 通过/警告/拒绝
    evidence: list = field(default_factory=list)
    generated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# 盈亏比与仓位映射（按纪律文档: 盈亏比优先于胜率）
# RR >= 3  核心主仓(主升期可 20-33%)
# RR 2-3  正常仓(10-20%)
# RR 1-2  试错仓(5-10%)
# RR < 1  不做
MIN_RR_MAIN = 3.0
MIN_RR_NORMAL = 2.0
MIN_RR_TRIAL = 1.0


def judge_risk_reward(
    trade_date: str,
    ts_code: str,
    name: str,
    buy_price: float,
    take_price: float,
    stop_price: float,
    *,
    emotion_phase: str = "high_chop",   # 情绪周期阶段: low_test/main_up/high_chop/main_down
    is_core: bool = True,               # 是否核心票（core_judge 输出）
) -> RiskRewardResult:
    """
    用买点/止盈/止损三价算盈亏比，并给仓位建议。

    仓位规则（在 position_hard_rules 单票≤15% 之内细化）:
      - 主升期 + 核心 + RR≥3   → 12-15%（主仓）
      - 主升期 + 核心 + RR≥2   → 8-10%
      - 震荡期(high_chop)       → 整体再压半档（纪律: 落袋为安）
      - 主跌期(main_down)       → 只试仓 ≤5%（纪律: 空仓为主）
      - RR<1                    → 不做
    """
    evidence: list[str] = []

    # ── 基本校验 ──
    if stop_price >= buy_price:
        return RiskRewardResult(
            trade_date, ts_code, name, buy_price, take_price, stop_price,
            0.0, 0.0, 0.0, 0.0, "none", "拒绝",
            ["止损价 ≥ 买入价 → 无风险边界，拒绝开仓"], datetime.now().astimezone().isoformat(timespec="seconds"),
        )
    if take_price <= buy_price:
        return RiskRewardResult(
            trade_date, ts_code, name, buy_price, take_price, stop_price,
            0.0, 0.0, 0.0, 0.0, "none", "拒绝",
            ["止盈价 ≤ 买入价 → 无盈利空间，拒绝开仓"], datetime.now().astimezone().isoformat(timespec="seconds"),
        )

    profit_pct = (take_price / buy_price - 1.0) * 100
    loss_pct = (1.0 - stop_price / buy_price) * 100
    rr = (take_price - buy_price) / (buy_price - stop_price)
    evidence.append(f"盈亏比 = ({take_price}-{buy_price})/({buy_price}-{stop_price}) = {rr:.2f}")

    # ── 仓位判定 ──
    # 阶段系数
    phase_mult = {"main_up": 1.0, "high_chop": 0.75, "low_test": 0.5, "main_down": 0.3}.get(emotion_phase, 0.5)
    core_bonus = 1.0 if is_core else 0.5

    if rr >= MIN_RR_MAIN:
        base = 0.15
        tier = "core_main"
        evidence.append(f"盈亏比 {rr:.2f} ≥ 3 → 核心主仓")
    elif rr >= MIN_RR_NORMAL:
        base = 0.10
        tier = "core"
        evidence.append(f"盈亏比 {rr:.2f} ≥ 2 → 正常仓")
    elif rr >= MIN_RR_TRIAL:
        base = 0.05
        tier = "trial"
        evidence.append(f"盈亏比 {rr:.2f} ≥ 1 → 仅试错仓")
    else:
        return RiskRewardResult(
            trade_date, ts_code, name, buy_price, take_price, stop_price,
            round(rr, 2), round(profit_pct, 1), round(loss_pct, 1),
            0.0, "none", "拒绝",
            [f"盈亏比 {rr:.2f} < 1 → 风险大于收益，拒绝开仓"],
            datetime.now().astimezone().isoformat(timespec="seconds"),
        )

    position = round(base * phase_mult * core_bonus, 3)
    position = min(position, 0.15)  # 单票上限 15%（position_hard_rules）

    # 阶段提示
    phase_note = {
        "main_up": "主升期，可给足仓位", "high_chop": "高位震荡，仓位压半档",
        "low_test": "低位试错，轻仓", "main_down": "主跌期，仅试仓或空仓",
    }[emotion_phase]
    evidence.append(f"阶段={emotion_phase}（{phase_note}）× 核心系数={core_bonus} → 仓位 {position:.0%}")

    grade = "通过" if position >= 0.05 else ("警告" if position >= 0.02 else "拒绝")
    if not is_core and position > 0.05:
        evidence.append("非核心票，仅试错仓，不加重")

    return RiskRewardResult(
        trade_date=trade_date,
        ts_code=ts_code,
        name=name,
        buy_price=buy_price,
        take_price=take_price,
        stop_price=stop_price,
        risk_reward_ratio=round(rr, 2),
        profit_pct=round(profit_pct, 1),
        loss_pct=round(loss_pct, 1),
        position_suggestion_pct=position,
        position_tier=tier,
        grade_check=grade,
        evidence=evidence,
        generated_at=datetime.now().astimezone().isoformat(timespec="seconds"),
    )


if __name__ == "__main__":
    cases = [
        # (name, buy, take, stop, phase, is_core)
        ("主升期核心龙头", 10.0, 12.0, 9.3, "main_up", True),    # RR=(12-10)/(10-9.3)=2.86
        ("主升期高盈亏比", 10.0, 13.0, 9.3, "main_up", True),    # RR=3/0.7=4.29 → 核心主仓
        ("震荡期核心", 10.0, 11.5, 9.3, "high_chop", True),      # RR=1.5/0.7=2.14 → 压半档
        ("主跌期杂毛", 10.0, 10.8, 9.3, "main_down", False),     # RR=0.8/0.7=1.14 → 试仓再×0.3
        ("无风险边界", 10.0, 11.0, 10.5, "main_up", True),        # stop>=buy → 拒绝
        ("低盈亏比", 10.0, 10.5, 9.7, "main_up", True),           # RR=0.5/0.3=1.67 → 试错
    ]
    for c in cases:
        r = judge_risk_reward("20260904", "TEST", c[0], c[1], c[2], c[3], emotion_phase=c[4], is_core=c[5])
        print(f"{c[0]}: RR={r.risk_reward_ratio} 仓位={r.position_suggestion_pct:.0%} [{r.position_tier}] {r.grade_check}")
