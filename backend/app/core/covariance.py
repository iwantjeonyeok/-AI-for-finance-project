"""투자기간(H개월) 공분산 추정.

일별 수익률 -> 일별 공분산 -> H_days 스케일링.
불안정/특이행렬 위험이 있으면 Ledoit–Wolf shrinkage 적용.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from sklearn.covariance import LedoitWolf


def horizon_trading_days(horizon_months: int) -> int:
    return int(round(252 * horizon_months / 12))


def _is_unstable(cov_daily: np.ndarray, n_obs: int, n_assets: int) -> bool:
    """관측치 부족, 비정칙, 큰 조건수 -> 불안정 판정."""
    if n_obs < n_assets + 2:
        return True
    try:
        cond = np.linalg.cond(cov_daily)
    except np.linalg.LinAlgError:
        return True
    if not np.isfinite(cond) or cond > 1e8:
        return True
    eig = np.linalg.eigvalsh(cov_daily)
    return bool(np.min(eig) <= 1e-12)


def estimate_horizon_covariance(
    returns: pd.DataFrame,
    horizon_months: int,
    use_ledoit_wolf: bool = True,
):
    """일별 수익률 DataFrame(열=종목) -> (Sigma_H, shrinkage_applied).

    결측치는 열별로 처리하고, 공통 관측 구간만 사용한다.
    """
    clean = returns.dropna(how="all").copy()
    # 상장기간 부족/결측 종목: 가능한 관측치로 채우되 공통 구간 우선
    clean = clean.dropna()
    n_obs, n_assets = clean.shape

    if n_obs < 2:
        # 데이터가 거의 없으면 단위행렬 기반 보수적 추정
        sigma_daily = np.eye(n_assets) * 1e-4
        shrink = True
    else:
        sample_cov = np.cov(clean.values, rowvar=False)
        sample_cov = np.atleast_2d(sample_cov)
        shrink = False
        if use_ledoit_wolf and _is_unstable(sample_cov, n_obs, n_assets):
            lw = LedoitWolf().fit(clean.values)
            sigma_daily = lw.covariance_
            shrink = True
        else:
            sigma_daily = sample_cov

    h_days = horizon_trading_days(horizon_months)
    sigma_h = sigma_daily * h_days
    # 대칭성 보정
    sigma_h = (sigma_h + sigma_h.T) / 2.0
    return sigma_h, shrink
