"""보고서 검색 -> 수집 -> 점수 -> 선정 -> 종합 파이프라인(명세 4·5·6장).

결과는 ReportAnalysis 로 검증되어 반환되며, 동일 (ticker, horizon) 입력은 캐싱된다.
"""
from __future__ import annotations

import uuid
from datetime import date
from typing import Dict, List, Optional, Tuple

from ..config import get_settings
from ..core.extract import extract_target_price, extract_upside_return
from ..core.report_scorer import score_candidates, select_reports
from ..core.returns import (
    horizon_return,
    mean_valid_target_price,
    raw_target_return,
    recency_weighted_target_price,
)
from ..providers import (
    get_llm_provider,
    get_market_data_provider,
    get_report_fetcher,
    get_search_provider,
)
from ..providers.mock import _TODAY  # DEMO 기준일
from ..schemas.reports import (
    AnalysisStatus,
    CandidateReport,
    ReportAnalysis,
    SourceItem,
)

_CACHE: Dict[Tuple[str, int], ReportAnalysis] = {}


def _today() -> date:
    s = get_settings()
    if s.demo_mode:
        return _TODAY
    return date.today()


def _target_price_lookup(url: str) -> Optional[float]:
    """DEMO: fixture 의 target_price 를 그대로 사용. 실모드에서는 LLM 추출."""
    from ..providers.mock import _load_reports

    for reports in _load_reports().values():
        for r in reports:
            if r["url"] == url:
                return r.get("target_price")
    return None


def analyze_stock(ticker: str, horizon_months: int, use_cache: bool = True) -> ReportAnalysis:
    key = (ticker, horizon_months)
    if use_cache and key in _CACHE:
        return _CACHE[key]

    settings = get_settings()
    market = get_market_data_provider()
    search = get_search_provider()
    fetcher = get_report_fetcher()
    llm = get_llm_provider()

    brief = market.get_brief(ticker)
    name = brief.name if brief else ticker
    current_price = brief.current_price if brief else 0.0

    # 1. 검색 쿼리 생성 + 검색
    queries = llm.generate_search_queries(ticker, name)
    results = search.search_reports(ticker, name, queries)

    # 2. 후보 구성 + 본문 수집 (접근 불가는 제외). 지연 제한 위해 최신 N개만 수집.
    candidates: List[CandidateReport] = []
    fetch_limit = settings.report_fetch_limit if not settings.demo_mode else len(results)
    today = _today()
    max_age = settings.report_max_age_days
    for r in results[:fetch_limit]:
        if not r.accessible:
            continue
        # 낡은 보고서 배제: 최신 전망만 사용. 너무 오래된 보고서뿐이면 '보고서 없음'으로 처리됨.
        if r.published_at is not None and (today - r.published_at).days > max_age:
            continue
        text = fetcher.fetch(r.url)
        if text is None:  # 접근 실패 -> 선택하지 않음
            continue
        # 목표주가(후보 단계): DEMO fixture / 검색 힌트 / 본문 regex 까지만.
        # LLM 추출은 비용/쿼터 절약 위해 '선정된' 보고서에 한해 선정 후 수행한다(아래).
        tp = _target_price_lookup(r.url) if settings.demo_mode else None
        if tp is None:
            tp = r.target_price_hint
        if tp is None and not settings.demo_mode:
            tp = extract_target_price(text, current_price or None)
            # 목표가 숫자가 이미지에 있어 못 뽑으면, 본문의 '상승여력 XX%' 로 목표가 환산(LLM 불필요)
            if tp is None and current_price:
                up = extract_upside_return(text)
                if up is not None:
                    tp = current_price * (1.0 + up)
        # source_id: 검색 결과 → fixture(url) → uuid
        sid = r.source_id or (_source_id_for(r.url) if settings.demo_mode else None) or (
            "rpt-" + str(uuid.uuid4())[:8]
        )
        cand = CandidateReport(
            source_id=sid,
            stock_code=ticker,
            institution=r.institution or "미상",
            title=r.title,
            url=r.url,
            published_at=r.published_at,
            accessible=True,
            target_price=tp,
            raw_text=text,
            # 네이버 종목분석 집계는 국내 증권사만 등재 → 국내 기관 보장
            domestic_confirmed=(not settings.demo_mode and settings.research_source == "naver"),
        )
        # evidence_clarity 는 비용 절감 위해 휴리스틱(목표가 유무)으로 채운다(scorer 처리).
        # LLM 은 최종 종합 단계에만 사용한다.
        candidates.append(cand)

    if not candidates:
        analysis = ReportAnalysis(
            stock_code=ticker,
            stock_name=name,
            current_price=current_price,
            status=AnalysisStatus.NO_REPORT,
            mean_target_price=None,
            implied_return_portfolio_horizon=None,
            horizon_months=horizon_months,
        )
        _CACHE[key] = analysis
        return analysis

    # 3. 점수 부여 + 선정
    score_candidates(candidates, _today())
    selected = select_reports(candidates)

    # 3.5 선정된 보고서 중 목표가 없는 것만 LLM 으로 보정(필요할 때만 호출).
    if not settings.demo_mode:
        for c in selected:
            if c.target_price is None and c.raw_text:
                c.target_price = llm.extract_target_price(c.raw_text)

    # 4. 목표주가 평균(최신 가중) + 기대수익률
    #    주가 급등으로 과거 목표가가 낡았을 때, 최신 상향 리포트가 평균을 지배하도록 한다.
    mean_tp = recency_weighted_target_price(
        [(c.target_price, c.published_at) for c in selected], current_price, _today()
    )
    tp_count = sum(
        1 for c in selected if c.target_price is not None and _valid(c.target_price, current_price)
    )
    raw_ret = raw_target_return(mean_tp, current_price) if mean_tp else None
    horizon_ret = horizon_return(raw_ret, horizon_months) if raw_ret is not None else None

    # 5. LLM 종합 (텍스트만). 실패/빈 결과면 휴리스틱(실제 본문 문장 추출)으로 차선 대체.
    synth = llm.synthesize(ticker, name, selected)
    if not settings.demo_mode and not synth.core_rationales:
        from ..providers.mock import HeuristicLLMProvider

        synth = HeuristicLLMProvider().synthesize(ticker, name, selected)

    analysis = ReportAnalysis(
        stock_code=ticker,
        stock_name=name,
        current_price=current_price,
        mean_target_price=mean_tp,
        target_price_count=tp_count,
        selected_report_count=len(selected),
        institutions=sorted({c.institution for c in selected}),
        implied_return_raw=raw_ret,
        implied_return_portfolio_horizon=horizon_ret,
        core_rationales=synth.core_rationales,
        major_risks=synth.major_risks,
        consensus_summary=synth.consensus_summary,
        disagreement_summary=synth.disagreement_summary,
        sources=[
            SourceItem(
                source_id=c.source_id,
                institution=c.institution,
                title=c.title,
                published_at=c.published_at.isoformat() if c.published_at else None,
                url=c.url,
                demo_sample=settings.demo_mode,
            )
            for c in selected
        ],
        status=AnalysisStatus.AVAILABLE,
        horizon_months=horizon_months,
    )
    _CACHE[key] = analysis
    return analysis


def _valid(tp, current_price):
    from ..core.returns import is_valid_target_price

    return is_valid_target_price(tp, current_price)


def _source_id_for(url: str) -> Optional[str]:
    from ..providers.mock import _load_reports

    for reports in _load_reports().values():
        for r in reports:
            if r["url"] == url:
                return r["source_id"]
    return None


def get_source_detail(source_id: str) -> Optional[dict]:
    """source_id 로 보고서 메타 + 파생 요약(raw_text)을 찾는다.

    DEMO 모드의 '사용된 보고서' 링크가 죽은 외부 URL 대신 이 요약을 보여주기 위함.
    전체 PDF 원문이 아니라 파생 요약만 제공한다(스펙 16장).
    """
    from ..providers.mock import _load_reports

    for stock_code, reports in _load_reports().items():
        for r in reports:
            if r.get("source_id") == source_id:
                return {
                    "source_id": source_id,
                    "stock_code": stock_code,
                    "institution": r.get("institution", "미상"),
                    "title": r.get("title", ""),
                    "published_at": r.get("published_at"),
                    "url": r.get("url", ""),
                    "target_price": r.get("target_price"),
                    "derived_summary": r.get("raw_text", ""),
                }
    return None


def analyze_many(tickers: List[str], horizon_months: int) -> List[ReportAnalysis]:
    return [analyze_stock(t, horizon_months) for t in tickers]


def clear_cache():
    _CACHE.clear()
