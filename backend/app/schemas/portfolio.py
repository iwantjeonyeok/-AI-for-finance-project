"""포트폴리오 / view / 결과 관련 스키마."""
from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class ViewMode(str, Enum):
    ACCEPT_REPORT = "accept_report"   # 옵션 A: 보고서 전망 수용
    CUSTOM_VIEW = "custom_view"       # 옵션 B: 나의 기대수익률 입력
    ABSTAIN = "abstain"               # 옵션 C: 판단 보류


class StockBrief(BaseModel):
    ticker: str
    name: str
    market: str = "KOSPI"
    current_price: float = 0.0
    market_cap: float = 0.0


class UserView(BaseModel):
    ticker: str
    mode: ViewMode = ViewMode.ABSTAIN
    # custom_view 일 때만 사용. 포트폴리오 기간 기준 decimal (예: 0.04 = +4%).
    expected_return: Optional[float] = None
    confidence: float = 0.5  # 0~1
    rationale: str = ""

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class OptimizeRequest(BaseModel):
    tickers: List[str]
    horizon_months: int = 3
    views: List[UserView] = Field(default_factory=list)


class NLParseRequest(BaseModel):
    ticker: str
    text: str
    horizon_months: int = 3


class ParsedView(BaseModel):
    """자연어 판단 해석 결과. 사용자가 확인/편집 후 사용한다."""

    mode: ViewMode
    expected_return: Optional[float] = None  # decimal
    confidence: float = 0.5
    rationale: str = ""


# ---------------------------------------------------------------------------
# 최적화 결과
# ---------------------------------------------------------------------------
class PortfolioItemResult(BaseModel):
    ticker: str
    name: str
    market_prior_weight: float
    mean_target_price: Optional[float] = None
    report_expected_return: Optional[float] = None      # 보고서 기반 H개월 기대수익률
    used_view: Optional[float] = None                    # BL 에 들어간 Q (없으면 None)
    user_view_mode: ViewMode = ViewMode.ABSTAIN
    user_confidence: Optional[float] = None
    posterior_expected_return: float = 0.0
    final_weight: float = 0.0
    weight_change: float = 0.0                            # final - prior
    has_report: bool = True
    explanation: str = ""


class PortfolioResult(BaseModel):
    portfolio_id: Optional[int] = None
    horizon_months: int
    tau: float
    risk_aversion: float
    max_asset_weight: float
    items: List[PortfolioItemResult] = Field(default_factory=list)
    used_fallback: bool = False
    fallback_reason: str = ""
    disclaimer: str = (
        "본 결과는 리서치 및 교육 목적의 모델 결과이며 투자 권유나 수익 보장을 의미하지 않습니다."
    )
