"""End-to-end 수용 시나리오 (명세 14장 A/B/C)."""
import numpy as np

from app.schemas.portfolio import OptimizeRequest, UserView, ViewMode
from app.services.analysis_service import clear_cache
from app.services.portfolio_service import optimize_portfolio


def setup_function():
    clear_cache()


def test_scenario_A_mixed_views():
    # 5종목: 4개 보고서 존재(005930,000660,035420,005380), 1개 보고서 없음(454910 두산로보틱스)
    tickers = ["005930", "000660", "035420", "005380", "454910"]
    views = [
        UserView(ticker="005930", mode=ViewMode.ACCEPT_REPORT, confidence=0.7),
        UserView(ticker="000660", mode=ViewMode.ACCEPT_REPORT, confidence=0.6),
        UserView(ticker="035420", mode=ViewMode.CUSTOM_VIEW, expected_return=-0.02, confidence=0.6),
        UserView(ticker="005380", mode=ViewMode.ABSTAIN),
        # 454910 view 없음
    ]
    result = optimize_portfolio(OptimizeRequest(tickers=tickers, horizon_months=3, views=views))

    assert len(result.items) == 5
    # 비중 합 1, 상한 이내
    w = np.array([it.final_weight for it in result.items])
    assert abs(w.sum() - 1.0) < 1e-6
    assert np.all(w <= result.max_asset_weight + 1e-6)
    assert np.all(w >= -1e-9)

    by = {it.ticker: it for it in result.items}
    # 보고서 없는 종목 표시
    assert by["454910"].has_report is False
    # 보고서 수용 종목은 used_view 가 보고서 기대수익률과 동일
    assert by["005930"].used_view == by["005930"].report_expected_return
    # custom view 음수 -> used_view 음수
    assert by["035420"].used_view == -0.02
    # abstain / no-view 종목은 used_view None
    assert by["005380"].used_view is None
    assert by["454910"].used_view is None
    # 설명문 존재
    assert all(it.explanation for it in result.items)


# 균형 시총 universe: 어떤 종목의 prior 비중도 MAX_WEIGHT(0.40) 미만이라
# cap 제약에 막히지 않고 prior/posterior 효과를 그대로 관찰할 수 있다.
BALANCED = ["035420", "207940", "005380", "035720", "068270"]


def test_scenario_B_all_abstain_equals_prior():
    views = [UserView(ticker=t, mode=ViewMode.ABSTAIN) for t in BALANCED]
    result = optimize_portfolio(OptimizeRequest(tickers=BALANCED, horizon_months=3, views=views))
    # 모든 prior 가 상한 미만임을 확인(테스트 전제)
    assert all(it.market_prior_weight < result.max_asset_weight for it in result.items)
    for it in result.items:
        # view 없음 -> posterior=prior -> 최적해가 market prior 에 근접
        assert abs(it.final_weight - it.market_prior_weight) < 5e-3


def test_scenario_C_confidence_monotonicity():
    finals = []
    for c in (0.2, 0.5, 0.9):
        # 035420(NAVER): 보고서 기대수익률 양수, prior 비중 여유(상한 미달)
        views = [UserView(ticker="035420", mode=ViewMode.ACCEPT_REPORT, confidence=c)]
        result = optimize_portfolio(
            OptimizeRequest(tickers=BALANCED, horizon_months=3, views=views)
        )
        by = {it.ticker: it for it in result.items}
        finals.append(by["035420"].final_weight)
    # 보고서 기대수익률이 양수 -> confidence 높을수록 비중 증가 (cap 에 막히지 않음)
    assert finals[0] < finals[1] < finals[2]
