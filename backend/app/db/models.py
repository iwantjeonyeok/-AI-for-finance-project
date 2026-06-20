"""SQLAlchemy 모델 (명세 11장). SQLite 로컬, PostgreSQL 호환 스키마."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

from ..config import get_settings


class Base(DeclarativeBase):
    pass


class Stock(Base):
    __tablename__ = "stocks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    market: Mapped[str] = mapped_column(String(20), default="KOSPI")
    current_price: Mapped[float] = mapped_column(Float, default=0.0)
    market_cap: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReportSource(Base):
    __tablename__ = "report_sources"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"))
    institution: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(300))
    published_at: Mapped[str | None] = mapped_column(String(20), nullable=True)
    url: Mapped[str] = mapped_column(String(500))
    local_file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reputation_score: Mapped[float] = mapped_column(Float, default=0.5)
    recency_score: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_clarity_score: Mapped[float] = mapped_column(Float, default=0.0)
    uniqueness_score: Mapped[float] = mapped_column(Float, default=0.0)
    candidate_score: Mapped[float] = mapped_column(Float, default=0.0)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReportAnalysisRow(Base):
    __tablename__ = "report_analyses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id"))
    current_price: Mapped[float] = mapped_column(Float, default=0.0)
    mean_target_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    raw_implied_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    horizon_implied_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    core_rationales_json: Mapped[str] = mapped_column(Text, default="[]")
    major_risks_json: Mapped[str] = mapped_column(Text, default="[]")
    consensus_summary: Mapped[str] = mapped_column(Text, default="")
    disagreement_summary: Mapped[str] = mapped_column(Text, default="")
    llm_model: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(30), default="available")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Portfolio(Base):
    __tablename__ = "portfolios"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    horizon_months: Mapped[int] = mapped_column(Integer, default=3)
    tau: Mapped[float] = mapped_column(Float, default=0.05)
    risk_aversion: Mapped[float] = mapped_column(Float, default=2.5)
    max_asset_weight: Mapped[float] = mapped_column(Float, default=0.40)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    items: Mapped[list["PortfolioItem"]] = relationship(
        back_populates="portfolio", cascade="all, delete-orphan"
    )


class PortfolioItem(Base):
    __tablename__ = "portfolio_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id"))
    stock_id: Mapped[int | None] = mapped_column(ForeignKey("stocks.id"), nullable=True)
    ticker: Mapped[str] = mapped_column(String(20), default="")
    market_prior_weight: Mapped[float] = mapped_column(Float, default=0.0)
    report_expected_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    user_view_mode: Mapped[str] = mapped_column(String(30), default="abstain")
    user_expected_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    user_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    user_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    posterior_expected_return: Mapped[float] = mapped_column(Float, default=0.0)
    final_weight: Mapped[float] = mapped_column(Float, default=0.0)
    portfolio: Mapped["Portfolio"] = relationship(back_populates="items")


_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        url = get_settings().database_url
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        _engine = create_engine(url, connect_args=connect_args)
    return _engine


def get_session_local():
    global _SessionLocal
    if _SessionLocal is None:
        init_db()  # 테이블이 없으면 생성(앱 startup 이벤트와 무관하게 안전)
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _SessionLocal


def init_db():
    Base.metadata.create_all(bind=get_engine())
