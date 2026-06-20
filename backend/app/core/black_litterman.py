"""Black–Litterman 모형 + 평균-분산 최적화.

설계 원칙(명세 3장)을 코드로 강제한다:
  * 사용자 confidence c 는 Q 에 곱하지 않는다. 오직 view uncertainty Ω 로만 변환된다.
  * c=0 인 view 는 완전히 제거된다(P/Q 에서 빠짐).
  * c 가 커질수록 posterior 가 view 방향으로 이동한다.
  * view 가 하나도 없으면 posterior_return == Pi (시장 균형).

수식(명세 8장):
  Pi              = delta * Sigma_H * w_market
  omega_k         = ((1-c)/c) * (P_k @ tau*Sigma_H @ P_k^T)        (Idzorek-style)
  posterior_cov   = inv( inv(tau*Sigma_H) + P^T inv(Omega) P )
  posterior_ret   = posterior_cov @ ( inv(tau*Sigma_H) Pi + P^T inv(Omega) Q )
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

import numpy as np

try:  # cvxpy 는 선택적: 없으면 scipy/정규화 fallback 사용
    import cvxpy as cp

    _HAS_CVXPY = True
except Exception:  # pragma: no cover
    _HAS_CVXPY = False

_EPS = 1e-10
_MAX_CONFIDENCE = 0.999


@dataclass
class ViewInput:
    """단일 absolute view. asset_index 종목의 H개월 기대수익률 q, 신뢰도 confidence."""

    asset_index: int
    q: float
    confidence: float  # 0~1


@dataclass
class BLResult:
    prior_returns: np.ndarray          # Pi
    posterior_returns: np.ndarray
    posterior_cov: np.ndarray
    weights: np.ndarray                # 최종 최적 비중
    market_weights: np.ndarray
    used_fallback: bool = False
    fallback_reason: str = ""
    n_views: int = 0


def market_prior_weights(market_caps: Sequence[float]) -> np.ndarray:
    """선택 종목 내부에서 시가총액을 재정규화한 prior weight. 합 == 1."""
    caps = np.asarray(market_caps, dtype=float)
    if caps.size == 0:
        raise ValueError("market_caps is empty")
    if np.any(caps < 0):
        raise ValueError("market_caps must be non-negative")
    total = caps.sum()
    if total <= 0:
        # 모든 시총이 0/결측이면 동일가중으로 안전 처리
        return np.full(caps.shape, 1.0 / caps.size)
    return caps / total


def equilibrium_returns(delta: float, sigma_h: np.ndarray, w_market: np.ndarray) -> np.ndarray:
    """Pi = delta * Sigma_H * w_market."""
    return delta * sigma_h @ w_market


def build_view_matrices(
    views: Sequence[ViewInput],
    n_assets: int,
    tau: float,
    sigma_h: np.ndarray,
):
    """유효 view 들로 P, Q, Omega(대각) 를 만든다.

    confidence==0 인 view 는 제외한다. 유효 view 가 없으면 (None, None, None).
    """
    active = [v for v in views if v.confidence is not None and v.confidence > 0.0]
    if not active:
        return None, None, None

    k = len(active)
    P = np.zeros((k, n_assets))
    Q = np.zeros(k)
    omega_diag = np.zeros(k)

    for row, v in enumerate(active):
        P[row, v.asset_index] = 1.0
        Q[row] = v.q  # ★ Q 는 confidence 와 무관하게 그대로 사용
        c = min(max(v.confidence, _EPS), _MAX_CONFIDENCE)
        pk = P[row]
        view_var = float(pk @ (tau * sigma_h) @ pk.T)
        omega_diag[row] = ((1.0 - c) / c) * view_var + _EPS

    Omega = np.diag(omega_diag)
    return P, Q, Omega


def posterior(
    pi: np.ndarray,
    tau: float,
    sigma_h: np.ndarray,
    P: Optional[np.ndarray],
    Q: Optional[np.ndarray],
    Omega: Optional[np.ndarray],
):
    """BL posterior (return, cov). view 가 없으면 prior 그대로 반환."""
    tau_sigma = tau * sigma_h
    tau_sigma_inv = np.linalg.inv(tau_sigma)

    if P is None or P.shape[0] == 0:
        return pi.copy(), tau_sigma.copy()

    omega_inv = np.linalg.inv(Omega)
    post_cov = np.linalg.inv(tau_sigma_inv + P.T @ omega_inv @ P)
    post_ret = post_cov @ (tau_sigma_inv @ pi + P.T @ omega_inv @ Q)
    return post_ret, post_cov


def optimize_weights(
    expected_returns: np.ndarray,
    sigma_h: np.ndarray,
    delta: float,
    max_weight: float,
):
    """maximize w^T mu - (delta/2) w^T Sigma w  s.t. sum w=1, 0<=w<=max_weight.

    반환: (weights, used_fallback, reason)
    """
    n = len(expected_returns)
    # max_weight 가 sum==1 을 만족 불가능하게 작으면 완화
    if max_weight * n < 1.0:
        max_weight = 1.0  # 제약 비활성화(실현 불가능 방지)

    if _HAS_CVXPY:
        try:
            w = cp.Variable(n)
            objective = cp.Maximize(
                expected_returns @ w - (delta / 2.0) * cp.quad_form(w, cp.psd_wrap(sigma_h))
            )
            constraints = [cp.sum(w) == 1, w >= 0, w <= max_weight]
            prob = cp.Problem(objective, constraints)
            prob.solve()
            if w.value is not None and prob.status in ("optimal", "optimal_inaccurate"):
                weights = np.clip(np.asarray(w.value).flatten(), 0, None)
                s = weights.sum()
                if s > 0:
                    return weights / s, False, ""
        except Exception as exc:  # pragma: no cover - solver edge cases
            return _fallback_weights(expected_returns, sigma_h, delta, max_weight, str(exc))
        return _fallback_weights(expected_returns, sigma_h, delta, max_weight, "cvxpy non-optimal")
    return _fallback_weights(expected_returns, sigma_h, delta, max_weight, "cvxpy unavailable")


def _fallback_weights(expected_returns, sigma_h, delta, max_weight, reason):
    """제약 없는 해 w* = (1/delta) Sigma^-1 mu 를 구해 양수화·정규화·상한 적용."""
    try:
        raw = (1.0 / delta) * np.linalg.solve(sigma_h, expected_returns)
    except np.linalg.LinAlgError:
        raw = expected_returns.copy()
    w = np.clip(raw, 0, None)
    if w.sum() <= 0:
        w = np.ones_like(w)
    w = w / w.sum()
    w = _apply_cap(w, max_weight)
    return w, True, reason


def _apply_cap(w: np.ndarray, max_weight: float) -> np.ndarray:
    """반복적으로 상한을 적용하고 초과분을 나머지에 재분배."""
    w = w.copy()
    for _ in range(100):
        over = w > max_weight + 1e-12
        if not over.any():
            break
        excess = (w[over] - max_weight).sum()
        w[over] = max_weight
        under = ~over
        if not under.any() or w[under].sum() <= 0:
            break
        w[under] += excess * w[under] / w[under].sum()
    return w / w.sum()


def run_black_litterman(
    market_caps: Sequence[float],
    sigma_h: np.ndarray,
    views: Sequence[ViewInput],
    delta: float,
    tau: float,
    max_weight: float,
) -> BLResult:
    """전체 BL 파이프라인 실행."""
    w_market = market_prior_weights(market_caps)
    n = len(w_market)
    sigma_h = np.asarray(sigma_h, dtype=float)

    pi = equilibrium_returns(delta, sigma_h, w_market)
    P, Q, Omega = build_view_matrices(views, n, tau, sigma_h)
    post_ret, post_cov = posterior(pi, tau, sigma_h, P, Q, Omega)
    weights, used_fallback, reason = optimize_weights(post_ret, sigma_h, delta, max_weight)

    return BLResult(
        prior_returns=pi,
        posterior_returns=post_ret,
        posterior_cov=post_cov,
        weights=weights,
        market_weights=w_market,
        used_fallback=used_fallback,
        fallback_reason=reason,
        n_views=0 if P is None else P.shape[0],
    )
