"""설명 가능한 결과(명세 9.3): 계산 결과 기반 템플릿 문장 생성.

LLM 이 수치 원인을 임의 해석하지 않도록, 문장은 전적으로 계산값에서 만든다.
"""
from __future__ import annotations

from ..schemas.portfolio import PortfolioItemResult, ViewMode


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def explain_item(item: PortfolioItemResult) -> str:
    prior = _pct(item.market_prior_weight)
    final = _pct(item.final_weight)
    direction = "증가" if item.weight_change > 1e-6 else ("감소" if item.weight_change < -1e-6 else "거의 유지")

    if not item.has_report and item.user_view_mode == ViewMode.ABSTAIN:
        return (
            f"{item.name}은(는) 리서치 보고서가 없고 별도 견해도 반영하지 않아, "
            f"시장 시가총액 기준 prior 비중({prior})을 그대로 사용했습니다. 최종 비중은 {final}입니다."
        )

    if item.user_view_mode == ViewMode.ABSTAIN:
        return (
            f"{item.name}은(는) 판단을 보류하여 view 를 반영하지 않았고, "
            f"prior 비중 {prior}에서 다른 종목의 view 영향으로 최종 {final}로 조정되었습니다."
        )

    conf = _pct(item.user_confidence) if item.user_confidence is not None else "-"

    if item.user_view_mode == ViewMode.ACCEPT_REPORT:
        rr = _pct(item.report_expected_return) if item.report_expected_return is not None else "-"
        return (
            f"{item.name}은(는) 선택 종목 내 prior 비중이 {prior}였습니다. "
            f"리서치 보고서의 투자기간 환산 기대수익률은 {rr}였고, 사용자가 이를 {conf} 신뢰하여 "
            f"최종 비중은 {final}로 {direction}했습니다."
        )

    # custom_view
    uv = _pct(item.used_view) if item.used_view is not None else "-"
    contrarian = item.used_view is not None and item.report_expected_return is not None and (
        item.used_view < item.report_expected_return
    )
    note = "보고서보다 보수적인 " if contrarian else ""
    return (
        f"{item.name}은(는) prior 비중 {prior}에서, 사용자가 {note}기대수익률 {uv}를 "
        f"{conf} 신뢰도로 직접 입력하여 최종 비중이 {final}로 {direction}했습니다."
    )
