"""pykrx 기반 MarketDataProvider. 설치/네트워크가 가능할 때만 사용.

pykrx 미설치 시 ImportError -> factory 가 mock 으로 fallback.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

import pandas as pd

from ..schemas.portfolio import StockBrief


class PykrxMarketDataProvider:
    def __init__(self):
        from pykrx import stock  # noqa: F401  (존재 확인)

        self.stock = stock

    def _all_tickers_map(self) -> dict:
        today = datetime.now().strftime("%Y%m%d")
        m = {}
        for market in ("KOSPI", "KOSDAQ"):
            for t in self.stock.get_market_ticker_list(today, market=market):
                m[t] = (self.stock.get_market_ticker_name(t), market)
        return m

    def search_stocks(self, query: str) -> List[StockBrief]:
        q = query.strip().lower()
        out = []
        for t, (name, market) in self._all_tickers_map().items():
            if q in name.lower() or q in t:
                brief = self.get_brief(t)
                if brief:
                    out.append(brief)
                if len(out) >= 20:
                    break
        return out

    def get_brief(self, ticker: str) -> Optional[StockBrief]:
        today = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=10)).strftime("%Y%m%d")
        try:
            name = self.stock.get_market_ticker_name(ticker)
            ohlcv = self.stock.get_market_ohlcv(start, today, ticker)
            price = float(ohlcv["종가"].iloc[-1])
            cap_df = self.stock.get_market_cap(start, today, ticker)
            mcap = float(cap_df["시가총액"].iloc[-1])
            return StockBrief(ticker=ticker, name=name, current_price=price, market_cap=mcap)
        except Exception:
            return None

    def get_price_history(self, tickers: List[str], lookback_days: int) -> pd.DataFrame:
        end = datetime.now()
        start = end - timedelta(days=int(lookback_days * 1.6) + 10)
        series = {}
        for t in tickers:
            try:
                df = self.stock.get_market_ohlcv(
                    start.strftime("%Y%m%d"), end.strftime("%Y%m%d"), t
                )
                series[t] = df["종가"].astype(float)
            except Exception:
                continue
        if not series:
            return pd.DataFrame()
        out = pd.DataFrame(series).tail(lookback_days)
        return out
