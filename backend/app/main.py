"""FastAPI 진입점."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .config import get_settings
from .db.models import init_db

app = FastAPI(
    title="리서치 보고서 기반 개인화 Black–Litterman 포트폴리오",
    description="애널리스트 보고서 종합 + 사용자 confidence -> Black–Litterman 포트폴리오",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/api/health")
def health():
    s = get_settings()
    return {
        "status": "ok",
        "demo_mode": s.demo_mode,
        "horizon_months": s.portfolio_horizon_months,
        "tau": s.tau,
        "risk_aversion": s.risk_aversion,
        "max_asset_weight": s.max_asset_weight,
    }
