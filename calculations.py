from __future__ import annotations

from dataclasses import dataclass


ETF_WEIGHTS = {"VOO": 0.60, "QQQM": 0.20, "SCHD": 0.20}


def clamp(value: float, minimum: float = 0, maximum: float = 100) -> float:
    return max(minimum, min(maximum, value))


def calculate_net_worth(cash: float, investments: float, debt: float) -> float:
    return cash + investments - debt


def debt_to_income_ratio(debt: float, monthly_income: float) -> float:
    if monthly_income <= 0:
        return float("inf") if debt > 0 else 0
    return debt / monthly_income


def financial_score(
    *,
    net_worth: float,
    total_debt: float,
    monthly_income: float,
    minimum_payment_habit: bool,
    emergency_fund: float,
    regular_investment: bool,
) -> tuple[int, list[str]]:
    score = 100
    reasons: list[str] = []

    if net_worth < 0:
        score -= 20
        reasons.append("Net servet negatif: -20")
    if debt_to_income_ratio(total_debt, monthly_income) > 0.30:
        score -= 25
        reasons.append("Kart borcu maaşın %30'undan yüksek: -25")
    if minimum_payment_habit:
        score -= 15
        reasons.append("Asgari ödeme alışkanlığı: -15")
    if emergency_fund <= 0:
        score -= 15
        reasons.append("Acil durum fonu yok: -15")
    if regular_investment:
        score += 10
        reasons.append("Düzenli yatırım: +10")

    return int(clamp(score)), reasons


def etf_allocation(amount_tl: float, usd_rate: float | None = None) -> dict[str, dict[str, float]]:
    allocation: dict[str, dict[str, float]] = {}
    for symbol, weight in ETF_WEIGHTS.items():
        tl_amount = max(amount_tl, 0) * weight
        allocation[symbol] = {
            "weight": weight,
            "tl": tl_amount,
            "usd": tl_amount / usd_rate if usd_rate and usd_rate > 0 else 0,
        }
    return allocation


@dataclass(frozen=True)
class MonthlyDecision:
    remaining_money: float
    debt_payment: float
    emergency_fund: float
    investment: float
    warning: str
    risk_level: str


def monthly_decision(
    *,
    income: float,
    expenses: float,
    total_debt: float,
    current_emergency_fund: float,
    emergency_target: float = 100_000,
    net_worth: float = 0,
) -> MonthlyDecision:
    remaining = max(income - expenses, 0)
    if remaining <= 0:
        return MonthlyDecision(
            remaining_money=remaining,
            debt_payment=0,
            emergency_fund=0,
            investment=0,
            warning="Bu ay serbest nakit oluşmadı. Harcamaları gözden geçir.",
            risk_level="risk",
        )

    ratio = debt_to_income_ratio(total_debt, income)
    if total_debt > 0:
        high_risk = ratio > 0.30 or net_worth < 0
        emergency_share = 0.05 if current_emergency_fund < emergency_target else 0
        investment_share = 0 if high_risk else 0.05
        emergency_amount = remaining * emergency_share
        investment_amount = remaining * investment_share
        debt_amount = min(total_debt, remaining - emergency_amount - investment_amount)
        return MonthlyDecision(
            remaining_money=remaining,
            debt_payment=max(debt_amount, 0),
            emergency_fund=emergency_amount,
            investment=investment_amount,
            warning=(
                "Bu ay yatırım yapma, önce kredi kartı borcunu azalt."
                if high_risk
                else "Borç varken yatırım tutarını düşük tut ve kalan parayı karta yönlendir."
            ),
            risk_level="risk" if high_risk else "warning",
        )

    emergency_gap = max(emergency_target - current_emergency_fund, 0)
    emergency_amount = min(emergency_gap, remaining * 0.50)
    investment_amount = remaining - emergency_amount
    return MonthlyDecision(
        remaining_money=remaining,
        debt_payment=0,
        emergency_fund=emergency_amount,
        investment=investment_amount,
        warning="Borç yok. Acil durum fonundan sonra bu ay yatırım yapılabilir.",
        risk_level="good",
    )


def payoff_priority(cards: list[dict]) -> list[dict]:
    return sorted(
        [card for card in cards if float(card.get("total_debt", 0)) > 0],
        key=lambda card: (float(card.get("total_debt", 0)), str(card.get("name", ""))),
    )

