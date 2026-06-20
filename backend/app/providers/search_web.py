"""웹 검색 provider (Tavily/Serper 호환 추상화). SEARCH_API_KEY 필요.

기본 구현은 Tavily API 형식을 사용한다. Serper 등으로 교체하려면 _call 만 수정.
"""
from __future__ import annotations

from datetime import datetime
from typing import List
from urllib.parse import urlparse

import httpx

from ..config import get_settings
from ..schemas.reports import SearchResult

# 국내 증권사/리서치 도메인 화이트리스트(검색 결과 1차 필터)
_DOMESTIC_HINT = (
    "miraeasset", "nhqv", "samsungpop", "kbsec", "truefriend", "kiwoom",
    "shinhan", "hanaw", "daishin", "meritz", "myasset", "hi-ib", "hankyung",
    "mk.co.kr", "fnguide", "wisereport",
)


class WebSearchProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.settings = get_settings()

    def _call(self, query: str) -> list[dict]:
        with httpx.Client(timeout=self.settings.http_timeout_seconds) as client:
            resp = client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": self.api_key,
                    "query": query,
                    "search_depth": "advanced",
                    "max_results": 8,
                },
            )
            resp.raise_for_status()
            return resp.json().get("results", [])

    def search_reports(self, ticker: str, name: str, queries: List[str]) -> List[SearchResult]:
        seen = set()
        out: List[SearchResult] = []
        for q in queries:
            try:
                for item in self._call(q):
                    url = item.get("url", "")
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    host = (urlparse(url).hostname or "").lower()
                    if not any(h in host for h in _DOMESTIC_HINT):
                        continue
                    pub = item.get("published_date")
                    published = None
                    if pub:
                        try:
                            published = datetime.fromisoformat(pub[:10]).date()
                        except ValueError:
                            published = None
                    out.append(
                        SearchResult(
                            title=item.get("title", ""),
                            url=url,
                            snippet=item.get("content", "")[:200],
                            published_at=published,
                            accessible=True,
                        )
                    )
            except Exception:
                continue
        return out
