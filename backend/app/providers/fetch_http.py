"""httpx + PyMuPDF/BeautifulSoup 기반 보고서 본문 추출.

- timeout/retry 적용
- PDF 는 PyMuPDF, HTML 은 BeautifulSoup 로 텍스트 추출
- 유료/로그인/접근불가(4xx/5xx, 로그인 폼)는 None 반환 (우회 금지)
"""
from __future__ import annotations

import time
from typing import Optional

import httpx

from ..config import get_settings


class HttpReportFetcher:
    def __init__(self):
        self.settings = get_settings()

    def fetch(self, url: str) -> Optional[str]:
        s = self.settings
        last_exc = None
        for attempt in range(s.http_max_retries + 1):
            try:
                with httpx.Client(
                    timeout=s.http_timeout_seconds, follow_redirects=True,
                    headers={"User-Agent": "Mozilla/5.0 (research-bot)"},
                ) as client:
                    resp = client.get(url)
                if resp.status_code >= 400:
                    return None
                ctype = resp.headers.get("content-type", "").lower()
                if "pdf" in ctype or url.lower().endswith(".pdf"):
                    return self._extract_pdf(resp.content)
                return self._extract_html(resp.text)
            except Exception as exc:  # 네트워크 오류 -> 재시도
                last_exc = exc
                time.sleep(0.5 * (attempt + 1))
        return None

    @staticmethod
    def _extract_pdf(content: bytes) -> Optional[str]:
        try:
            import fitz

            doc = fitz.open(stream=content, filetype="pdf")
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            return text.strip() or None
        except Exception:
            return None

    @staticmethod
    def _extract_html(html: str) -> Optional[str]:
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            # 로그인 폼이 본문 대부분이면 접근 불가로 간주
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            if "로그인" in text and len(text) < 400:
                return None
            return text or None
        except Exception:
            return None
