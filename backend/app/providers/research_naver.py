"""네이버 금융 리서치 기반 실제 국내 증권사 리포트 provider.

공개·무로그인으로 접근 가능한 '종목분석 리포트' 집계 페이지를 사용한다.
- 목록:  https://finance.naver.com/research/company_list.naver?searchType=itemCode&itemCode={code}
  → 증권사명 / 제목 / 작성일 / PDF 링크(stock.pstatic.net) / 상세 nid
- 본문:  PDF 다운로드 후 PyMuPDF 로 텍스트 추출

SearchProvider 와 ReportFetcher 인터페이스를 한 클래스로 구현한다(검색·수집 출처가 동일).
유료/로그인/접근 불가 자료는 사용하지 않으며 우회하지 않는다.
"""
from __future__ import annotations

import re
from datetime import date
from typing import List, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from ..config import get_settings
from ..schemas.reports import SearchResult

_BASE = "https://finance.naver.com/research/"
_LIST = _BASE + "company_list.naver"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://finance.naver.com/research/",
}
_DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{2})")
_NID_RE = re.compile(r"nid=(\d+)")


def _parse_date(s: str) -> Optional[date]:
    m = _DATE_RE.search(s or "")
    if not m:
        return None
    yy, mm, dd = (int(x) for x in m.groups())
    try:
        return date(2000 + yy, mm, dd)
    except ValueError:
        return None


class NaverResearchProvider:
    """search_reports + fetch 동시 구현."""

    def __init__(self):
        self.settings = get_settings()

    # ----- SearchProvider -----
    def search_reports(self, ticker: str, name: str, queries: List[str]) -> List[SearchResult]:
        params = {"searchType": "itemCode", "itemCode": ticker}
        try:
            with httpx.Client(timeout=self.settings.http_timeout_seconds, headers=_HEADERS) as c:
                r = c.get(_LIST, params=params, follow_redirects=True)
            r.raise_for_status()
        except Exception:
            return []

        html = r.content.decode("euc-kr", errors="replace")
        soup = BeautifulSoup(html, "html.parser")

        results: List[SearchResult] = []
        seen = set()
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 5:
                continue
            links = [a.get("href", "") for a in tr.find_all("a") if a.get("href")]
            pdf = next((u for u in links if u.lower().endswith(".pdf")), None)
            if not pdf:
                continue  # PDF 없는 행(헤더/광고 등) 제외
            cells = [td.get_text(strip=True) for td in tds]
            # 컬럼: [종목명, 제목, 증권사, '', 작성일, 조회수]
            title = cells[1] if len(cells) > 1 else ""
            institution = cells[2] if len(cells) > 2 else ""
            published = None
            for cell in cells:
                d = _parse_date(cell)
                if d:
                    published = d
                    break
            detail = next((u for u in links if "company_read" in u), "")
            nidm = _NID_RE.search(detail)
            source_id = f"naver-{nidm.group(1)}" if nidm else f"naver-{abs(hash(pdf)) % 10**8}"
            if source_id in seen:
                continue
            seen.add(source_id)
            results.append(
                SearchResult(
                    title=title,
                    url=pdf,
                    snippet="",
                    published_at=published,
                    institution=institution or None,
                    accessible=True,
                    source_id=source_id,
                )
            )
            if len(results) >= 15:
                break
        return results

    # ----- ReportFetcher -----
    def fetch(self, url: str) -> Optional[str]:
        s = self.settings
        for attempt in range(s.http_max_retries + 1):
            try:
                with httpx.Client(
                    timeout=s.http_timeout_seconds, headers=_HEADERS, follow_redirects=True
                ) as c:
                    resp = c.get(url)
                if resp.status_code >= 400:
                    return None
                if url.lower().endswith(".pdf") or "pdf" in resp.headers.get(
                    "content-type", ""
                ).lower() or resp.content[:4] == b"%PDF":
                    return self._extract_pdf(resp.content)
                # PDF 가 아니면(접근불가/안내페이지) 사용하지 않음
                return None
            except Exception:
                continue
        return None

    @staticmethod
    def _extract_pdf(content: bytes) -> Optional[str]:
        try:
            import fitz

            doc = fitz.open(stream=content, filetype="pdf")
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            text = text.strip()
            return text or None
        except Exception:
            return None
