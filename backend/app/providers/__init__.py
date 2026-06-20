"""Provider 추상화 + factory.

DEMO_MODE 또는 API 키 부재 시 mock 구현을 반환한다.
"""
from __future__ import annotations

from functools import lru_cache

from ..config import get_settings
from .base import LLMProvider, MarketDataProvider, ReportFetcher, SearchProvider
from .mock import (
    HeuristicLLMProvider,
    MockLLMProvider,
    MockMarketDataProvider,
    MockReportFetcher,
    MockSearchProvider,
)


@lru_cache
def get_market_data_provider() -> MarketDataProvider:
    s = get_settings()
    if s.demo_mode:
        return MockMarketDataProvider()
    # 실모드 기본: 네이버 금융(현재가·시총·일별종가). pykrx 는 KRX 차단 시 실패하므로 보조.
    if s.market_source == "pykrx":
        try:
            from .market_pykrx import PykrxMarketDataProvider

            return PykrxMarketDataProvider()
        except Exception:
            pass
    from .market_naver import NaverMarketDataProvider

    return NaverMarketDataProvider()


@lru_cache
def get_search_provider() -> SearchProvider:
    s = get_settings()
    if s.demo_mode:
        return MockSearchProvider()
    # 실모드 기본: 네이버 금융 리서치(국내 증권사 리포트 집계, 공개·무로그인)
    if s.research_source == "naver":
        from .research_naver import NaverResearchProvider

        return NaverResearchProvider()
    # 대안: 일반 웹 검색(Tavily 등)
    if s.search_api_key:
        from .search_web import WebSearchProvider

        return WebSearchProvider(api_key=s.search_api_key)
    return MockSearchProvider()


@lru_cache
def get_report_fetcher() -> ReportFetcher:
    s = get_settings()
    if s.demo_mode:
        return MockReportFetcher()
    if s.research_source == "naver":
        from .research_naver import NaverResearchProvider

        return NaverResearchProvider()
    from .fetch_http import HttpReportFetcher

    return HttpReportFetcher()


@lru_cache
def get_llm_provider() -> LLMProvider:
    s = get_settings()
    if s.demo_mode:
        return MockLLMProvider()

    provider = (s.llm_provider or "auto").lower()

    def _groq():
        from .llm_openai_compat import OpenAICompatLLMProvider

        return OpenAICompatLLMProvider(
            api_key=s.groq_api_key, model=s.groq_model,
            base_url="https://api.groq.com/openai/v1",
        )

    def _openai_compat():
        from .llm_openai_compat import OpenAICompatLLMProvider

        return OpenAICompatLLMProvider(
            api_key=s.openai_compat_api_key, model=s.openai_compat_model,
            base_url=s.openai_compat_base_url,
        )

    def _gemini():
        from .llm_gemini import GeminiLLMProvider

        return GeminiLLMProvider(api_key=s.gemini_api_key, model=s.gemini_model)

    def _anthropic():
        from .llm_anthropic import AnthropicLLMProvider

        return AnthropicLLMProvider(api_key=s.anthropic_api_key, model=s.llm_model)

    if provider == "groq" and s.groq_api_key:
        return _groq()
    if provider == "openai_compat" and s.openai_compat_api_key and s.openai_compat_base_url:
        return _openai_compat()
    if provider == "gemini" and s.gemini_api_key:
        return _gemini()
    if provider == "anthropic" and s.anthropic_api_key:
        return _anthropic()
    if provider == "heuristic":
        return HeuristicLLMProvider()

    # auto: 사용 가능한 키로 자동 선택 (Groq 우선 — 가장 넉넉한 무료 티어)
    if s.groq_api_key:
        return _groq()
    if s.openai_compat_api_key and s.openai_compat_base_url:
        return _openai_compat()
    if s.gemini_api_key:
        return _gemini()
    if s.anthropic_api_key:
        return _anthropic()
    # 키 없음: 실제 본문에서 상승/하락 문장을 뽑는 휴리스틱(가짜 근거 생성 안 함)
    return HeuristicLLMProvider()
