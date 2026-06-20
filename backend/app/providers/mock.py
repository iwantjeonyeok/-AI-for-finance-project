"""Fixture 기반 mock provider. 외부 API 없이 전체 흐름을 구동한다."""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from ..schemas.portfolio import ParsedView, StockBrief, ViewMode
from ..schemas.reports import (
    CandidateReport,
    LLMSynthesisOutput,
    RationaleItem,
    SearchResult,
)

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"
_TODAY = date(2026, 6, 20)  # DEMO 기준일 (재현성)


@lru_cache
def _load_stocks() -> Dict[str, dict]:
    with open(FIXTURE_DIR / "stocks.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return {s["ticker"]: s for s in data}


@lru_cache
def _load_reports() -> Dict[str, list]:
    with open(FIXTURE_DIR / "reports.json", "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# MarketData
# ---------------------------------------------------------------------------
class MockMarketDataProvider:
    def search_stocks(self, query: str) -> List[StockBrief]:
        q = query.strip().lower()
        out = []
        for s in _load_stocks().values():
            if q in s["name"].lower() or q in s["ticker"]:
                out.append(self._to_brief(s))
        return out

    def get_brief(self, ticker: str) -> Optional[StockBrief]:
        s = _load_stocks().get(ticker)
        return self._to_brief(s) if s else None

    @staticmethod
    def _to_brief(s: dict) -> StockBrief:
        return StockBrief(
            ticker=s["ticker"],
            name=s["name"],
            market=s["market"],
            current_price=float(s["current_price"]),
            market_cap=float(s["market_cap"]),
        )

    def get_price_history(self, tickers: List[str], lookback_days: int) -> pd.DataFrame:
        """결정론적 GBM 기반 합성 가격 시계열. 종목별 상관을 공통팩터로 부여."""
        stocks = _load_stocks()
        n_days = lookback_days
        # 공통 시장 팩터 (재현성: ticker-독립 seed)
        rng = np.random.default_rng(20260620)
        market_factor = rng.normal(0, 0.008, n_days)

        dates = pd.bdate_range(end=_TODAY, periods=n_days)
        prices = {}
        for t in tickers:
            s = stocks.get(t)
            if s is None:
                continue
            seed = int(t) % (2**32)
            r = np.random.default_rng(seed)
            ann_vol = s.get("annual_vol", 0.30)
            drift = s.get("drift", 0.03)
            daily_vol = ann_vol / np.sqrt(252)
            daily_drift = drift / 252
            beta = 0.6 + (seed % 50) / 100.0  # 0.6~1.1
            idio = r.normal(0, daily_vol * 0.8, n_days)
            rets = daily_drift + beta * market_factor + idio
            p = s["current_price"] * np.exp(np.cumsum(rets) - rets.sum())
            prices[t] = p
        df = pd.DataFrame(prices, index=dates)
        return df


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
class MockSearchProvider:
    def search_reports(self, ticker: str, name: str, queries: List[str]) -> List[SearchResult]:
        reports = _load_reports().get(ticker, [])
        out = []
        for r in reports:
            pub = r.get("published_at")
            out.append(
                SearchResult(
                    title=r["title"],
                    url=r["url"],
                    snippet=(r.get("raw_text") or "")[:120],
                    published_at=datetime.strptime(pub, "%Y-%m-%d").date() if pub else None,
                    institution=r.get("institution"),
                    accessible=r.get("accessible", True),
                )
            )
        return out


# ---------------------------------------------------------------------------
# ReportFetcher
# ---------------------------------------------------------------------------
class MockReportFetcher:
    def fetch(self, url: str) -> Optional[str]:
        for reports in _load_reports().values():
            for r in reports:
                if r["url"] == url:
                    if not r.get("accessible", True):
                        return None  # 유료/접근 불가
                    return r.get("raw_text") or ""
        return None


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------
class MockLLMProvider:
    def generate_search_queries(self, ticker: str, name: str) -> List[str]:
        return [f"{name} 목표주가 리포트", f"{ticker} 기업분석", f"{name} 증권사 보고서"]

    def evaluate_evidence_clarity(self, report: CandidateReport) -> float:
        # fixture 에 미리 지정된 값이 있으면 그것을, 없으면 목표가 유무로 근사
        return report.evidence_clarity_score or (0.7 if report.target_price is not None else 0.3)

    def extract_target_price(self, text: str) -> Optional[float]:
        # mock 에서는 fixture 의 target_price 를 직접 사용하므로 여기선 텍스트 파싱 데모만
        m = re.search(r"목표주가[^\d]*(\d[\d,]*)", text)
        if m:
            return float(m.group(1).replace(",", ""))
        return None

    def synthesize(
        self, ticker: str, name: str, reports: List[CandidateReport]
    ) -> LLMSynthesisOutput:
        """선정 보고서 본문에서 공통 논거/리스크를 '종합'한 결과(템플릿 기반 mock).

        실제 LLM 은 본문에 근거해 생성하지만, mock 은 fixture 텍스트에서 키워드를 모아
        결정론적으로 구성한다. 숫자는 생성하지 않는다.
        """
        ids = [r.source_id for r in reports]
        # 본문에서 자주 등장하는 근거/리스크를 휴리스틱으로 추출
        rationales: List[RationaleItem] = []
        risks: List[RationaleItem] = []

        rationale_keys = {
            "HBM": "HBM 출하 확대와 가격 프리미엄이 실적을 견인",
            "메모리": "메모리 업황 회복과 가격 반등",
            "파운드리": "파운드리 가동률·수율 개선",
            "AI": "AI 서버·가속기 수요 증가",
            "커머스": "커머스 거래액 회복과 광고 단가 안정화",
            "광고": "광고 매출 성장률 회복",
            "하이브리드": "하이브리드 믹스 개선에 따른 수익성 향상",
            "주주환원": "자사주 매입 등 주주환원 강화",
            "수주": "대형 수주 및 캐파 확대",
            "공장": "신규 공장 가동에 따른 캐파 확대",
        }
        risk_keys = {
            "중국": "중국 수요 둔화",
            "환율": "환율 변동성",
            "경쟁": "경쟁 심화",
            "관세": "미국 관세 정책 불확실성",
            "규제": "규제 리스크",
            "재고": "고객사 재고 조정 가능성",
            "capex": "capex 부담",
            "둔화": "전방 수요 둔화",
        }
        body = " ".join(r.raw_text for r in reports)
        for key, txt in rationale_keys.items():
            if key in body and len(rationales) < 3:
                support = [r.source_id for r in reports if key in r.raw_text]
                rationales.append(RationaleItem(text=txt, supporting_source_ids=support[:3]))
        for key, txt in risk_keys.items():
            if key.lower() in body.lower() and len(risks) < 2:
                support = [r.source_id for r in reports if key.lower() in r.raw_text.lower()]
                risks.append(RationaleItem(text=txt, supporting_source_ids=support[:3]))

        institutions = sorted({r.institution for r in reports})
        consensus = (
            f"{', '.join(institutions)} 등 {len(institutions)}개 기관은 대체로 긍정적 전망을 제시합니다."
            if institutions
            else ""
        )
        disagreement = "목표주가 수준과 단기 모멘텀 강도에 대해서는 기관별 편차가 있습니다."

        return LLMSynthesisOutput(
            core_rationales=rationales[:3],
            major_risks=risks[:2],
            consensus_summary=consensus,
            disagreement_summary=disagreement,
        )

    def parse_user_view(self, ticker: str, text: str, horizon_months: int) -> ParsedView:
        """자연어 -> 구조화. 규칙 기반 mock 파서."""
        t = text.strip()
        lower = t.lower()

        # confidence: "확신은 60%" / "신뢰 70%" / "60% 신뢰"
        conf = 0.5
        cm = re.search(r"(?:확신|신뢰|confidence)[^\d]*(\d{1,3})\s*%", t)
        if not cm:
            cm = re.search(r"(\d{1,3})\s*%\s*(?:신뢰|확신)", t)
        if cm:
            conf = min(max(int(cm.group(1)) / 100.0, 0.0), 1.0)

        # 보류 표현
        if any(k in t for k in ["판단 보류", "모르겠", "판단할 수 없", "잘 모르"]):
            return ParsedView(mode=ViewMode.ABSTAIN, expected_return=None, confidence=0.0, rationale=t)

        # 기대수익률: "3% 상승" / "하락" / "-2%" / "4% 정도"
        er: Optional[float] = None
        rm = re.search(r"([+-]?\d+(?:\.\d+)?)\s*%", _strip_confidence(t))
        if rm:
            val = float(rm.group(1)) / 100.0
            if any(k in t for k in ["하락", "내릴", "빠질", "마이너스"]) and val > 0:
                val = -val
            er = val

        # custom view 인지 accept_report 인지
        if er is not None and any(
            k in t for k in ["내가", "나는", "직접", "본다", "예상", "전망한다", "생각"]
        ):
            return ParsedView(
                mode=ViewMode.CUSTOM_VIEW, expected_return=er, confidence=conf, rationale=t
            )
        if er is not None:
            return ParsedView(
                mode=ViewMode.CUSTOM_VIEW, expected_return=er, confidence=conf, rationale=t
            )
        return ParsedView(mode=ViewMode.ACCEPT_REPORT, expected_return=None, confidence=conf, rationale=t)


class HeuristicLLMProvider(MockLLMProvider):
    """실모드에서 LLM 키가 없을 때 사용. 가짜 근거를 만들지 않고, 실제 보고서 본문에서
    상승/하락 근거 '문장'을 추출해 사실 기반으로 제공한다(LLM 키 설정 시 실제 LLM 으로 대체)."""

    def extract_target_price(self, text: str) -> Optional[float]:
        # 휴리스틱 모드: 목표주가 추출은 core(현재가 대비 타당성 검증 포함)가 전담.
        # 여기서 무분별하게 추측하면 비정상 값(예: 종목코드 숫자)이 새어 들어가므로 None.
        return None

    def synthesize(self, ticker, name, reports) -> LLMSynthesisOutput:
        from ..core.extract import classify_thesis_sentences

        sources = [(r.source_id, r.raw_text) for r in reports if r.raw_text]
        bull, bear = classify_thesis_sentences(sources)

        core = [
            RationaleItem(text=s, supporting_source_ids=[sid]) for s, sid in bull[:5]
        ]
        risks = [
            RationaleItem(text=s, supporting_source_ids=[sid]) for s, sid in bear[:4]
        ]
        # 본문 추출이 빈약하면(이미지 PDF 등) 최소한 보고서 제목을 근거로 사용
        if not core:
            core = [
                RationaleItem(text=r.title, supporting_source_ids=[r.source_id])
                for r in reports[:3]
                if r.title
            ]

        tps = [r.target_price for r in reports if r.target_price]
        institutions = sorted({r.institution for r in reports})
        consensus = (
            f"{', '.join(institutions)} 등 {len(institutions)}개 기관의 보고서를 종합했습니다."
            if institutions
            else ""
        )
        disagreement = ""
        if len(tps) >= 2:
            lo, hi = min(tps), max(tps)
            disagreement = (
                f"제시된 목표주가는 {lo:,.0f}원 ~ {hi:,.0f}원으로 기관별 편차가 있습니다."
            )
        return LLMSynthesisOutput(
            core_rationales=core,
            major_risks=risks,
            consensus_summary=consensus,
            disagreement_summary=disagreement,
        )


def _strip_confidence(t: str) -> str:
    """기대수익률 파싱 전 confidence 표현을 제거해 오인식을 막는다."""
    t = re.sub(r"(?:확신|신뢰|confidence)[^\d]*\d{1,3}\s*%", "", t)
    t = re.sub(r"\d{1,3}\s*%\s*(?:신뢰|확신)", "", t)
    return t
