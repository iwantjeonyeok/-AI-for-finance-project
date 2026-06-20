"""목표주가 -> 투자기간 기대수익률 변환 + 목표주가 검증(명세 6장)."""
from __future__ import annotations

from typing import List, Optional


def raw_target_return(mean_target_price: float, current_price: float) -> float:
    if current_price <= 0:
        raise ValueError("current_price must be positive")
    return mean_target_price / current_price - 1.0


def horizon_return(raw_return: float, horizon_months: int) -> float:
    """raw(중장기 기준)를 H개월에 맞춰 기하 환산. 음수 raw 도 처리."""
    base = 1.0 + raw_return
    if base <= 0:
        # -100% 이하의 비정상 목표가는 -1 로 클램프
        return -1.0
    return base ** (horizon_months / 12.0) - 1.0


def is_valid_target_price(
    target_price: Optional[float],
    current_price: float,
    *,
    max_upside: float = 5.0,   # +500% 초과 상승여력은 의심(액면분할 등)
    max_downside: float = -0.95,
) -> bool:
    """비정상 숫자/통화오류/액면분할 의심 목표가 필터."""
    if target_price is None:
        return False
    if not (target_price > 0) or current_price <= 0:
        return False
    upside = target_price / current_price - 1.0
    if upside > max_upside:
        return False
    if upside < max_downside:
        return False
    return True


def mean_valid_target_price(
    target_prices: List[Optional[float]],
    current_price: float,
) -> Optional[float]:
    """유효 목표주가들의 산술평균. 유효값이 없으면 None."""
    valid = [tp for tp in target_prices if is_valid_target_price(tp, current_price)]
    if not valid:
        return None
    return sum(valid) / len(valid)


def recency_weighted_target_price(
    items,                      # List[Tuple[Optional[float], Optional[date]]]
    current_price: float,
    today,                      # date
    *,
    half_life_days: float = 21.0,
    default_age_days: float = 45.0,
) -> Optional[float]:
    """발행일이 최근일수록 큰 가중을 주는 목표주가 평균.

    주가가 급등해 과거 목표가가 낡았을 때, 최신 상향 리포트가 평균을 지배하도록 한다.
    가중치 w = 0.5 ** (경과일 / half_life_days). 발행일 불명이면 default_age 적용.
    유효 목표가가 없으면 None.
    """
    num = 0.0
    den = 0.0
    for tp, pub in items:
        if not is_valid_target_price(tp, current_price):
            continue
        if pub is not None:
            age = max((today - pub).days, 0)
        else:
            age = default_age_days
        w = 0.5 ** (age / half_life_days)
        num += w * tp
        den += w
    if den <= 0:
        return None
    return num / den
