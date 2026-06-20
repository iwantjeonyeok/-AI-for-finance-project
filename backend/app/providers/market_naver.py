"""네이버 금융 기반 실제 시장 데이터 provider.

- 종목 검색: m.stock.naver.com front-api autoComplete (실시간)
- 현재가/시가총액: finance.naver.com/item/main (HTML)
- 일별 종가: api.finance.naver.com/siseJson (차트 JSON)

pykrx 가 KRX 차단으로 실패하는 환경에서도 동작하도록 만든 기본 실데이터 provider.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import List, Optional

import httpx
import pandas as pd
from bs4 import BeautifulSoup

from ..config import get_settings
from ..schemas.portfolio import StockBrief

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Referer": "https://finance.naver.com/",
}
_AC = "https://m.stock.naver.com/front-api/search/autoComplete"
_MAIN = "https://finance.naver.com/item/main.naver"
_SISE = "https://api.finance.naver.com/siseJson.naver"
_SISE_ROW = re.compile(r"\[\"?(\d{8})\"?,\s*\d+,\s*\d+,\s*\d+,\s*(\d+)")
_TYPE_MAP = {"KOSPI": "KOSPI", "KOSDAQ": "KOSDAQ"}


def _decode(resp: httpx.Response) -> str:
    """응답의 선언된 charset 을 우선 사용하고, 실패 시 utf-8 → euc-kr 순으로 시도."""
    ctype = resp.headers.get("content-type", "")
    m = re.search(r"charset=([\w-]+)", ctype, re.IGNORECASE)
    if m:
        try:
            return resp.content.decode(m.group(1), errors="replace")
        except LookupError:
            pass
    for enc in ("utf-8", "euc-kr", "cp949"):
        try:
            return resp.content.decode(enc)
        except UnicodeDecodeError:
            continue
    return resp.content.decode("utf-8", errors="replace")


def _num(s: str) -> Optional[float]:
    m = re.search(r"[\d,]+", s or "")
    return float(m.group(0).replace(",", "")) if m else None


def _parse_market_cap(text: str) -> float:
    """'2,069조 5,826' → 2069*1e12 + 5826*1e8. '5,826' → 5826*1e8."""
    text = text.strip()
    if "조" in text:
        head, _, tail = text.partition("조")
        jo = _num(head) or 0
        eok = _num(tail) or 0
        return jo * 1e12 + eok * 1e8
    eok = _num(text) or 0
    return eok * 1e8


class NaverMarketDataProvider:
    def __init__(self):
        self.settings = get_settings()

    def _client(self) -> httpx.Client:
        return httpx.Client(
            timeout=self.settings.http_timeout_seconds, headers=_HEADERS, follow_redirects=True
        )

    # ----- 검색 -----
    def search_stocks(self, query: str) -> List[StockBrief]:
        q = query.strip()
        if not q:
            return []
        # 6자리 코드 직접 입력 지원
        if re.fullmatch(r"\d{6}", q):
            b = self.get_brief(q)
            return [b] if b else []
        try:
            with self._client() as c:
                r = c.get(_AC, params={"query": q, "target": "stock,index,etf"})
            data = r.json().get("result", {}).get("items", [])
        except Exception:
            return []
        out: List[StockBrief] = []
        for it in data:
            if it.get("category") != "stock":
                continue
            code = it.get("code", "")
            if not re.fullmatch(r"\d{6}", code):
                continue
            market = _TYPE_MAP.get(it.get("typeCode", ""), it.get("typeName", "KOSPI"))
            brief = self.get_brief(code)
            if brief:
                brief.market = market
                out.append(brief)
            if len(out) >= 12:
                break
        return out

    # ----- 현재가 / 시가총액 -----
    def get_brief(self, ticker: str) -> Optional[StockBrief]:
        try:
            with self._client() as c:
                r = c.get(_MAIN, params={"code": ticker})
            html = _decode(r)  # item/main 은 UTF-8 (research 목록은 EUC-KR — 혼용)
        except Exception:
            return None
        soup = BeautifulSoup(html, "html.parser")
        # 현재가: p.no_today 의 .blind 가 깔끔한 값
        price_el = soup.select_one("p.no_today .blind") or soup.select_one("p.no_today")
        price = _num(price_el.get_text()) if price_el else None
        # 종목명
        name_el = soup.select_one(".wrap_company h2 a") or soup.select_one(".wrap_company h2")
        name = name_el.get_text(strip=True) if name_el else ticker
        # 시가총액
        cap_el = soup.select_one("#_market_sum")
        market_cap = _parse_market_cap(cap_el.get_text(" ", strip=True)) if cap_el else 0.0
        if price is None:
            return None
        return StockBrief(
            ticker=ticker, name=name, market="KOSPI", current_price=price, market_cap=market_cap
        )

    # ----- 일별 종가 이력 -----
    def get_price_history(self, tickers: List[str], lookback_days: int) -> pd.DataFrame:
        end = datetime.now()
        start = end - timedelta(days=int(lookback_days * 1.9) + 15)
        series = {}
        for t in tickers:
            s = self._daily_closes(t, start, end)
            if s is not None and not s.empty:
                series[t] = s
        if not series:
            return pd.DataFrame()
        df = pd.DataFrame(series).sort_index().tail(lookback_days)
        return df

    def _daily_closes(self, ticker: str, start: datetime, end: datetime) -> Optional[pd.Series]:
        params = {
            "symbol": ticker,
            "requestType": "1",
            "startTime": start.strftime("%Y%m%d"),
            "endTime": end.strftime("%Y%m%d"),
            "timeframe": "day",
        }
        try:
            with self._client() as c:
                r = c.get(_SISE, params=params)
            txt = r.text
        except Exception:
            return None
        dates, closes = [], []
        for m in _SISE_ROW.finditer(txt):
            dates.append(pd.to_datetime(m.group(1), format="%Y%m%d"))
            closes.append(float(m.group(2)))
        if not dates:
            return None
        return pd.Series(closes, index=dates, name=ticker)
