"""Black–Litterman 엔진 단위 테스트 (명세 14장)."""
import numpy as np
import pytest

from app.core.black_litterman import (
    ViewInput,
    market_prior_weights,
    run_black_litterman,
)
from app.core.covariance import estimate_horizon_covariance
import pandas as pd


@pytest.fixture
def sigma_h():
    # 4종목, 양의 정부호 공분산 (H개월)
    rng = np.random.default_rng(0)
    A = rng.normal(size=(4, 4))
    cov = A @ A.T / 4.0 + np.eye(4) * 0.02
    return cov


@pytest.fixture
def caps():
    return [400e12, 120e12, 40e12, 20e12]


DELTA = 2.5
TAU = 0.05
MAXW = 0.40


def test_1_market_prior_sums_to_one(caps):
    w = market_prior_weights(caps)
    assert abs(w.sum() - 1.0) < 1e-12
    assert np.all(w >= 0)


def test_2_no_views_posterior_equals_prior(caps, sigma_h):
    bl = run_black_litterman(caps, sigma_h, [], DELTA, TAU, MAXW)
    np.testing.assert_allclose(bl.posterior_returns, bl.prior_returns, rtol=1e-10)
    assert bl.n_views == 0


def test_3_zero_confidence_removes_view(caps, sigma_h):
    bl = run_black_litterman(
        caps, sigma_h, [ViewInput(0, 0.20, 0.0)], DELTA, TAU, MAXW
    )
    # confidence 0 -> view 제거 -> posterior == prior
    np.testing.assert_allclose(bl.posterior_returns, bl.prior_returns, rtol=1e-10)
    assert bl.n_views == 0


def test_4_higher_confidence_moves_posterior_toward_view(caps, sigma_h):
    pi = run_black_litterman(caps, sigma_h, [], DELTA, TAU, MAXW).prior_returns
    q = pi[0] + 0.10  # prior 보다 높은 view
    moves = []
    for c in (0.1, 0.5, 0.9):
        bl = run_black_litterman(caps, sigma_h, [ViewInput(0, q, c)], DELTA, TAU, MAXW)
        moves.append(bl.posterior_returns[0])
    # confidence 높을수록 posterior[0] 가 q(=pi+0.1) 방향(더 큰 값)으로 이동
    assert moves[0] < moves[1] < moves[2]
    assert moves[2] <= q + 1e-9


def test_5_negative_view_reduces_weight(caps, sigma_h):
    base = run_black_litterman(caps, sigma_h, [], DELTA, TAU, MAXW)
    pi = base.prior_returns
    # 종목1 에 강한 음수 view
    bl = run_black_litterman(
        caps, sigma_h, [ViewInput(1, pi[1] - 0.20, 0.9)], DELTA, TAU, MAXW
    )
    assert bl.weights[1] < base.weights[1]


def test_6_confidence_not_multiplied_into_q(caps, sigma_h):
    """confidence 가 달라도 동일 Q 면 posterior 가 view 방향으로 단조 이동(곱셈 아님)."""
    pi = run_black_litterman(caps, sigma_h, [], DELTA, TAU, MAXW).prior_returns
    q = pi[0] + 0.10
    # 만약 Q*c 였다면 c=0.4 일 때 posterior 가 prior 아래로 갈 수 있음. 여기선 항상 prior~q 사이.
    for c in (0.2, 0.4, 0.7):
        bl = run_black_litterman(caps, sigma_h, [ViewInput(0, q, c)], DELTA, TAU, MAXW)
        assert pi[0] - 1e-9 <= bl.posterior_returns[0] <= q + 1e-9


def test_7_weights_sum_to_one(caps, sigma_h):
    bl = run_black_litterman(
        caps, sigma_h, [ViewInput(0, 0.15, 0.6)], DELTA, TAU, MAXW
    )
    assert abs(bl.weights.sum() - 1.0) < 1e-6


def test_8_weights_within_bounds(caps, sigma_h):
    views = [ViewInput(0, 0.30, 0.95), ViewInput(1, 0.25, 0.95)]
    bl = run_black_litterman(caps, sigma_h, views, DELTA, TAU, MAXW)
    assert np.all(bl.weights >= -1e-9)
    assert np.all(bl.weights <= MAXW + 1e-6)


def test_9_shrinkage_applied_on_unstable_cov():
    # 관측치 < 종목수 -> 불안정 -> shrinkage 적용
    rng = np.random.default_rng(1)
    df = pd.DataFrame(rng.normal(size=(3, 6)))  # 3 obs, 6 assets
    _, shrink = estimate_horizon_covariance(df, 3, use_ledoit_wolf=True)
    assert shrink is True


def test_10_no_report_stock_keeps_market_prior(sigma_h):
    # 모든 종목 prior 비중이 상한(0.40) 이하가 되도록 균형 시총 사용
    balanced_caps = [300e12, 250e12, 200e12, 150e12]
    # view 가 전혀 없을 때 final weight == market prior 임을 검증
    bl = run_black_litterman(balanced_caps, sigma_h, [], DELTA, TAU, MAXW)
    # cvxpy 최적해는 prior 와 정확히 같지 않을 수 있으나, posterior=prior 이므로
    # 평균분산 최적해가 시장균형 비중(상한 내)으로 수렴해야 한다.
    np.testing.assert_allclose(bl.weights, bl.market_weights, atol=1e-3)
