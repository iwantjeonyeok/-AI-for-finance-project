"""Provider 인터페이스 정의 (Protocol)."""
from __future__ import annotations

from typing import List, Optional, Protocol

import pandas as pd

from ..schemas.portfolio import ParsedView, StockBrief
from ..schemas.reports import CandidateReport, LLMSynthesisOutput, SearchResult


class MarketDataProvider(Protocol):
    def search_stocks(self, query: str) -> List[StockBrief]: ...

    def get_brief(self, ticker: str) -> Optional[StockBrief]: ...

    def get_price_history(self, tickers: List[str], lookback_days: int) -> pd.DataFrame:
        """일별 수정주가 DataFrame (index=date, columns=ticker)."""
        ...


class SearchProvider(Protocol):
    def search_reports(self, ticker: str, name: str, queries: List[str]) -> List[SearchResult]: ...


class ReportFetcher(Protocol):
    def fetch(self, url: str) -> Optional[str]:
        """URL 에서 텍스트 추출. 접근 불가/실패 시 None."""
        ...


class LLMProvider(Protocol):
    def generate_search_queries(self, ticker: str, name: str) -> List[str]: ...

    def evaluate_evidence_clarity(self, report: CandidateReport) -> float: ...

    def extract_target_price(self, text: str) -> Optional[float]: ...

    def synthesize(
        self, ticker: str, name: str, reports: List[CandidateReport]
    ) -> LLMSynthesisOutput: ...

    def parse_user_view(self, ticker: str, text: str, horizon_months: int) -> ParsedView: ...
