"""REST API 라우터 (명세 12장)."""
from __future__ import annotations

import json
from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from ..db.models import (
    Portfolio,
    PortfolioItem,
    Stock,
    get_session_local,
)
from ..providers import get_llm_provider, get_market_data_provider
from ..schemas.portfolio import (
    NLParseRequest,
    OptimizeRequest,
    ParsedView,
    PortfolioResult,
    StockBrief,
)
from ..schemas.reports import ReportAnalysis
from ..services.analysis_service import analyze_many, analyze_stock, get_source_detail
from ..services.portfolio_service import optimize_portfolio

router = APIRouter(prefix="/api")


# --------------------------------------------------------------------------
# 종목 검색
# --------------------------------------------------------------------------
@router.get("/stocks/search", response_model=List[StockBrief])
def search_stocks(q: str):
    if not q or not q.strip():
        return []
    return get_market_data_provider().search_stocks(q)


# --------------------------------------------------------------------------
# 보고서 분석
# --------------------------------------------------------------------------
class AnalyzeRequest(BaseModel):
    tickers: List[str]
    horizon_months: int = 3


@router.post("/reports/analyze", response_model=List[ReportAnalysis])
def analyze_reports(req: AnalyzeRequest):
    if not req.tickers:
        raise HTTPException(status_code=400, detail="tickers 가 비어 있습니다.")
    return analyze_many(req.tickers, req.horizon_months)


@router.get("/reports/analysis/{ticker}", response_model=ReportAnalysis)
def get_analysis(ticker: str, horizon_months: int = 3):
    return analyze_stock(ticker, horizon_months)


def _esc(s) -> str:
    s = "" if s is None else str(s)
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )


@router.get("/reports/source/{source_id}/view", response_class=HTMLResponse)
def view_source(source_id: str):
    """보고서 파생 요약 페이지(HTML). DEMO 샘플의 '사용된 보고서' 링크 대상.

    전체 원문 PDF 가 아니라 파생 요약만 제공한다(스펙 16장). 원문 URL 은 텍스트로만 표기.
    """
    d = get_source_detail(source_id)
    if d is None:
        raise HTTPException(status_code=404, detail="보고서를 찾을 수 없습니다.")
    tp = f"{d['target_price']:,.0f}원" if d.get("target_price") else "미제시"
    html = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(d['title'])}</title>
<style>
  body {{ font-family: system-ui, -apple-system, 'Malgun Gothic', sans-serif; max-width: 720px;
         margin: 0 auto; padding: 32px 20px; color: #1e293b; line-height: 1.7; }}
  .badge {{ display:inline-block; background:#fef3c7; color:#b45309; font-size:12px;
            font-weight:700; padding:3px 10px; border-radius:9999px; }}
  h1 {{ font-size: 20px; margin: 16px 0 4px; }}
  .meta {{ color:#64748b; font-size:14px; margin-bottom:20px; }}
  .card {{ border:1px solid #e2e8f0; border-radius:12px; padding:18px 20px; background:#f8fafc; }}
  .label {{ font-size:12px; color:#64748b; }}
  .note {{ margin-top:24px; font-size:13px; color:#94a3b8; border-top:1px solid #e2e8f0; padding-top:16px; }}
  .src {{ word-break: break-all; color:#64748b; font-size:13px; }}
</style></head>
<body>
  <span class="badge">DEMO 샘플 — 파생 요약</span>
  <h1>{_esc(d['title'])}</h1>
  <div class="meta">{_esc(d['institution'])} · {_esc(d['published_at']) or '발행일 미상'}</div>
  <div class="card">
    <div class="label">목표주가</div>
    <div style="font-size:18px;font-weight:700;margin-bottom:12px;">{_esc(tp)}</div>
    <div class="label">파생 요약</div>
    <p>{_esc(d['derived_summary']) or '요약 본문이 없습니다.'}</p>
  </div>
  <div class="note">
    본 페이지는 DEMO 모드의 <b>샘플 보고서</b>입니다. 실제 원문이 아니며, 원문 PDF 를 재배포하지 않습니다.<br>
    표기상의 원문 위치: <span class="src">{_esc(d['url'])}</span><br>
    실제 운영 모드(API 키 연결)에서는 이 링크가 검색·수집된 실제 보고서 URL 로 연결됩니다.
  </div>
</body></html>"""
    return HTMLResponse(content=html)


# --------------------------------------------------------------------------
# 자연어 view 파싱
# --------------------------------------------------------------------------
@router.post("/user-views/parse", response_model=ParsedView)
def parse_user_view(req: NLParseRequest):
    return get_llm_provider().parse_user_view(req.ticker, req.text, req.horizon_months)


# --------------------------------------------------------------------------
# 포트폴리오 최적화 + 저장
# --------------------------------------------------------------------------
@router.post("/portfolio/optimize", response_model=PortfolioResult)
def optimize(req: OptimizeRequest):
    try:
        result = optimize_portfolio(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # 저장
    SessionLocal = get_session_local()
    with SessionLocal() as db:
        pf = Portfolio(
            horizon_months=result.horizon_months,
            tau=result.tau,
            risk_aversion=result.risk_aversion,
            max_asset_weight=result.max_asset_weight,
        )
        db.add(pf)
        db.flush()
        views_by_ticker = {v.ticker: v for v in req.views}
        for it in result.items:
            uv = views_by_ticker.get(it.ticker)
            db.add(
                PortfolioItem(
                    portfolio_id=pf.id,
                    ticker=it.ticker,
                    market_prior_weight=it.market_prior_weight,
                    report_expected_return=it.report_expected_return,
                    user_view_mode=it.user_view_mode.value,
                    user_expected_return=(uv.expected_return if uv else None),
                    user_confidence=it.user_confidence,
                    user_rationale=(uv.rationale if uv else None),
                    posterior_expected_return=it.posterior_expected_return,
                    final_weight=it.final_weight,
                )
            )
        db.commit()
        result.portfolio_id = pf.id
    return result


@router.get("/portfolio/{portfolio_id}", response_model=PortfolioResult)
def get_portfolio(portfolio_id: int):
    SessionLocal = get_session_local()
    with SessionLocal() as db:
        pf = db.get(Portfolio, portfolio_id)
        if pf is None:
            raise HTTPException(status_code=404, detail="포트폴리오를 찾을 수 없습니다.")
        from ..schemas.portfolio import PortfolioItemResult, ViewMode

        items = []
        for it in pf.items:
            items.append(
                PortfolioItemResult(
                    ticker=it.ticker,
                    name=it.ticker,
                    market_prior_weight=it.market_prior_weight,
                    report_expected_return=it.report_expected_return,
                    used_view=it.user_expected_return,
                    user_view_mode=ViewMode(it.user_view_mode),
                    user_confidence=it.user_confidence,
                    posterior_expected_return=it.posterior_expected_return,
                    final_weight=it.final_weight,
                    weight_change=it.final_weight - it.market_prior_weight,
                )
            )
        return PortfolioResult(
            portfolio_id=pf.id,
            horizon_months=pf.horizon_months,
            tau=pf.tau,
            risk_aversion=pf.risk_aversion,
            max_asset_weight=pf.max_asset_weight,
            items=items,
        )
