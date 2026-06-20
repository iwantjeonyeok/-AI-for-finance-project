"""애플리케이션 설정. 모든 값은 환경변수로 오버라이드 가능하다."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BACKEND_DIR / "config"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- 외부 서비스 ---
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    # Groq: 무료(카드 불필요, 30 RPM / 1000 RPD). https://console.groq.com
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    # OpenAI 호환 임의 제공자(OpenRouter/Cerebras/OpenAI 등)
    openai_compat_api_key: str = Field(default="", alias="OPENAI_COMPAT_API_KEY")
    openai_compat_base_url: str = Field(default="", alias="OPENAI_COMPAT_BASE_URL")
    openai_compat_model: str = Field(default="", alias="OPENAI_COMPAT_MODEL")
    search_api_key: str = Field(default="", alias="SEARCH_API_KEY")
    llm_model: str = Field(default="claude-opus-4-8", alias="LLM_MODEL")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")
    # LLM provider 강제 지정: auto | groq | gemini | anthropic | openai_compat | heuristic
    llm_provider: str = Field(default="auto", alias="LLM_PROVIDER")
    database_url: str = Field(default="sqlite:///./bl_portfolio.db", alias="DATABASE_URL")

    # --- 동작 모드 ---
    # DEMO_MODE=true 이면 외부 API 없이 fixture 기반 mock provider 만 사용한다.
    demo_mode: bool = Field(default=True, alias="DEMO_MODE")

    # 실모드 리서치 출처: "naver"(네이버 금융 리서치, 기본) | "web"(Tavily 등)
    research_source: str = Field(default="naver", alias="RESEARCH_SOURCE")
    # 실모드 시장데이터 출처: "naver"(기본) | "pykrx"
    market_source: str = Field(default="naver", alias="MARKET_SOURCE")

    # --- 포트폴리오 / BL 파라미터 ---
    portfolio_horizon_months: int = Field(default=3, alias="PORTFOLIO_HORIZON_MONTHS")
    tau: float = Field(default=0.05, alias="TAU")
    risk_aversion: float = Field(default=2.5, alias="RISK_AVERSION")
    max_asset_weight: float = Field(default=0.40, alias="MAX_ASSET_WEIGHT")
    report_max_count: int = Field(default=5, alias="REPORT_MAX_COUNT")
    # 실모드에서 본문(PDF)을 실제로 내려받아 평가할 최대 후보 수(지연 제한). 최신순으로 자른다.
    report_fetch_limit: int = Field(default=8, alias="REPORT_FETCH_LIMIT")
    # 이 일수보다 오래된 보고서는 사용하지 않는다(낡은 전망 배제). 최신 보고서가 없으면 '보고서 없음'.
    report_max_age_days: int = Field(default=180, alias="REPORT_MAX_AGE_DAYS")

    # --- 공분산 ---
    cov_lookback_days: int = Field(default=252, alias="COV_LOOKBACK_DAYS")
    use_ledoit_wolf: bool = Field(default=True, alias="USE_LEDOIT_WOLF")

    # --- 네트워크 ---
    http_timeout_seconds: float = Field(default=15.0, alias="HTTP_TIMEOUT_SECONDS")
    http_max_retries: int = Field(default=2, alias="HTTP_MAX_RETRIES")

    @property
    def config_dir(self) -> Path:
        return CONFIG_DIR


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def load_institutions_config() -> dict:
    path = CONFIG_DIR / "institutions.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache
def load_scoring_config() -> dict:
    path = CONFIG_DIR / "scoring.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
