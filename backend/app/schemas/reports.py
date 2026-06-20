"""보고서 검색·선정·종합 관련 Pydantic 스키마.

LLM 의 모든 출력은 이 스키마로 검증된다. 검증 실패 시 서비스 계층에서 재시도/복구한다.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class AnalysisStatus(str, Enum):
    AVAILABLE = "available"
    NO_REPORT = "no_report"


# ---------------------------------------------------------------------------
# 검색 결과 (SearchProvider 출력)
# ---------------------------------------------------------------------------
class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str = ""
    published_at: Optional[date] = None
    institution: Optional[str] = None  # 추정 기관명(검색 단계, 미확정)
    accessible: bool = True            # 유료/로그인 전용/접근 불가면 False
    source_id: Optional[str] = None    # 출처 고유 id(예: 네이버 리서치 nid)
    target_price_hint: Optional[float] = None  # 목록에서 즉시 보이는 목표가(있으면)


# ---------------------------------------------------------------------------
# 후보 보고서 (점수 부여 후)
# ---------------------------------------------------------------------------
class CandidateReport(BaseModel):
    source_id: str
    stock_code: str
    institution: str
    title: str
    url: str
    published_at: Optional[date] = None
    accessible: bool = True

    # 평가 점수 (0~1)
    reputation_score: float = 0.5
    recency_score: float = 0.0
    evidence_clarity_score: float = 0.0
    uniqueness_score: float = 0.0
    candidate_score: float = 0.0

    duplicate_cluster: Optional[int] = None
    selected: bool = False
    # 국내 기관임이 출처로 보장됨(예: 네이버 종목분석 집계는 국내 증권사만 등재)
    domestic_confirmed: bool = False

    # 추출된 사실 (있으면)
    target_price: Optional[float] = None
    raw_text: str = ""  # 추출 본문(요약용, 화면 재배포 금지)


# ---------------------------------------------------------------------------
# LLM 종합 출력 스키마 (사용자 표시용)
# ---------------------------------------------------------------------------
class RationaleItem(BaseModel):
    text: str
    supporting_source_ids: List[str] = Field(default_factory=list)


class SourceItem(BaseModel):
    source_id: str
    institution: str
    title: str
    published_at: Optional[str] = None
    url: str
    # DEMO 모드의 보고서는 실제 원문이 아닌 fixture 샘플이다(원문 URL 미존재).
    # true 이면 프론트는 외부 링크 대신 백엔드의 파생 요약 페이지로 연결한다.
    demo_sample: bool = False


class ReportAnalysis(BaseModel):
    """`POST /api/reports/analyze` 의 종목별 결과."""

    stock_code: str
    stock_name: str
    current_price: float = 0.0
    mean_target_price: Optional[float] = None
    target_price_count: int = 0
    selected_report_count: int = 0
    institutions: List[str] = Field(default_factory=list)

    # raw = 목표주가 기준 상승여력, portfolio_horizon = H개월 기하 환산
    implied_return_raw: Optional[float] = None
    implied_return_portfolio_horizon: Optional[float] = None

    core_rationales: List[RationaleItem] = Field(default_factory=list)
    major_risks: List[RationaleItem] = Field(default_factory=list)
    consensus_summary: str = ""
    disagreement_summary: str = ""
    sources: List[SourceItem] = Field(default_factory=list)

    status: AnalysisStatus = AnalysisStatus.AVAILABLE
    horizon_months: int = 3

    @field_validator("core_rationales")
    @classmethod
    def _cap_rationales(cls, v: List[RationaleItem]) -> List[RationaleItem]:
        return v[:6]  # 상승 근거 최대 6개

    @field_validator("major_risks")
    @classmethod
    def _cap_risks(cls, v: List[RationaleItem]) -> List[RationaleItem]:
        return v[:5]  # 하락 근거/리스크 최대 5개


# LLM 이 보고서 본문에서 종합한 1차 산출물 (검증 대상).
# 숫자(target_price 평균 등)는 코드가 계산하므로 LLM 은 텍스트만 담당한다.
# core_rationales = 상승 근거(bull), major_risks = 하락 근거/리스크(bear).
class LLMSynthesisOutput(BaseModel):
    core_rationales: List[RationaleItem] = Field(default_factory=list, max_length=6)
    major_risks: List[RationaleItem] = Field(default_factory=list, max_length=5)
    consensus_summary: str = ""
    disagreement_summary: str = ""
