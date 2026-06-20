"""사용자 view + 보고서 종합 -> Black–Litterman -> 최종 포트폴리오(명세 7·8·9장)."""
from __future__ import annotations

from typing import Dict, List

import numpy as np

from ..config import get_settings
from ..core.black_litterman import ViewInput, run_black_litterman
from ..core.covariance import estimate_horizon_covariance
from ..core.explain import explain_item
from ..providers import get_market_data_provider
from ..schemas.portfolio import (
    OptimizeRequest,
    PortfolioItemResult,
    PortfolioResult,
    UserView,
    ViewMode,
)
from .analysis_service import analyze_stock


def optimize_portfolio(req: OptimizeRequest) -> PortfolioResult:
    settings = get_settings()
    market = get_market_data_provider()
    tickers = req.tickers
    if len(tickers) < 2:
        raise ValueError("최소 2개 이상의 종목이 필요합니다.")

    # 1. 종목 정보 + 시가총액
    briefs = {t: market.get_brief(t) for t in tickers}
    if any(b is None for b in briefs.values()):
        missing = [t for t, b in briefs.items() if b is None]
        raise ValueError(f"종목 정보를 찾을 수 없습니다: {missing}")
    market_caps = [briefs[t].market_cap for t in tickers]

    # 2. 공분산 (H개월)
    prices = market.get_price_history(tickers, settings.cov_lookback_days)
    prices = prices.reindex(columns=tickers)
    returns = prices.pct_change()
    sigma_h, shrink = estimate_horizon_covariance(
        returns, req.horizon_months, settings.use_ledoit_wolf
    )

    # 3. 보고서 종합(각 종목)
    analyses = {t: analyze_stock(t, req.horizon_months) for t in tickers}

    # 4. view 구성
    views_by_ticker: Dict[str, UserView] = {v.ticker: v for v in req.views}
    view_inputs: List[ViewInput] = []
    used_view_q: Dict[str, float] = {}

    for idx, t in enumerate(tickers):
        uv = views_by_ticker.get(t)
        if uv is None or uv.mode == ViewMode.ABSTAIN or uv.confidence <= 0.0:
            continue
        analysis = analyses[t]
        if uv.mode == ViewMode.ACCEPT_REPORT:
            q = analysis.implied_return_portfolio_horizon
            if q is None:  # 보고서 없음 -> view 제외 (시장 prior 유지)
                continue
        else:  # CUSTOM_VIEW
            if uv.expected_return is None:
                continue
            q = uv.expected_return
        view_inputs.append(ViewInput(asset_index=idx, q=float(q), confidence=uv.confidence))
        used_view_q[t] = float(q)

    # 5. BL 실행
    bl = run_black_litterman(
        market_caps=market_caps,
        sigma_h=sigma_h,
        views=view_inputs,
        delta=settings.risk_aversion,
        tau=settings.tau,
        max_weight=settings.max_asset_weight,
    )

    # 6. 결과 조립
    items: List[PortfolioItemResult] = []
    for idx, t in enumerate(tickers):
        uv = views_by_ticker.get(t)
        analysis = analyses[t]
        has_report = analysis.status.value == "available"
        prior_w = float(bl.market_weights[idx])
        final_w = float(bl.weights[idx])
        item = PortfolioItemResult(
            ticker=t,
            name=briefs[t].name,
            market_prior_weight=prior_w,
            mean_target_price=analysis.mean_target_price,
            report_expected_return=analysis.implied_return_portfolio_horizon,
            used_view=used_view_q.get(t),
            user_view_mode=uv.mode if uv else ViewMode.ABSTAIN,
            user_confidence=(uv.confidence if uv and uv.mode != ViewMode.ABSTAIN else None),
            posterior_expected_return=float(bl.posterior_returns[idx]),
            final_weight=final_w,
            weight_change=final_w - prior_w,
            has_report=has_report,
        )
        item.explanation = explain_item(item)
        items.append(item)

    result = PortfolioResult(
        horizon_months=req.horizon_months,
        tau=settings.tau,
        risk_aversion=settings.risk_aversion,
        max_asset_weight=settings.max_asset_weight,
        items=items,
        used_fallback=bl.used_fallback,
        fallback_reason=bl.fallback_reason,
    )
    return result
