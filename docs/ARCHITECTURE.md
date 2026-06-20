# ARCHITECTURE

## 디렉터리
```
bl_portfolio/
├── backend/
│   ├── app/
│   │   ├── config.py              설정(env) + YAML 로더
│   │   ├── prompts.py             LLM system prompt
│   │   ├── main.py                FastAPI 진입점
│   │   ├── core/                  ── 순수 계산(외부 의존 없음, 테스트 용이)
│   │   │   ├── black_litterman.py   Π, view행렬, Ω, posterior, 최적화(+fallback)
│   │   │   ├── covariance.py        Σ_H 추정 + Ledoit–Wolf
│   │   │   ├── returns.py           목표가→기간수익률, 목표가 검증
│   │   │   ├── report_scorer.py     평판/recency/uniqueness 점수 + 선정
│   │   │   └── explain.py           템플릿 기반 설명문
│   │   ├── providers/             ── 외부 I/O 추상화(Protocol) + mock/real
│   │   │   ├── base.py  mock.py  llm_anthropic.py  search_web.py
│   │   │   └── fetch_http.py  market_pykrx.py
│   │   ├── schemas/               Pydantic 검증 스키마(reports, portfolio)
│   │   ├── services/              analysis_service, portfolio_service (오케스트레이션)
│   │   ├── db/models.py           SQLAlchemy 모델 + 세션
│   │   ├── api/routes.py          REST 엔드포인트
│   │   └── fixtures/              stocks.json, reports.json
│   ├── config/                    institutions.yaml, scoring.yaml
│   └── tests/                     BL/선정/LLM/E2E
└── frontend/                      Next.js 단계형 마법사
```

## 계층
```
API(routes) → Services → Core(순수계산)  +  Providers(I/O)  +  DB
```
- **core/** 는 numpy/pandas만 의존하는 순수 함수 → 단위 테스트가 쉽고 결정론적.
- **providers/** 는 Protocol로 추상화. factory(`providers/__init__.py`)가 `DEMO_MODE`/키 유무로
  mock ↔ real 선택. 앱 나머지는 구현을 모른다.
- **services/** 는 provider+core를 묶어 ReportAnalysis / PortfolioResult를 만든다.

## 데이터 흐름

### 보고서 분석 (`POST /api/reports/analyze`)
```
LLM.generate_search_queries → Search.search_reports → (접근가능)ReportFetcher.fetch
 → CandidateReport[] → score_candidates(평판/recency/uniqueness) → select_reports
 → mean_valid_target_price → horizon_return → LLM.synthesize(텍스트만)
 → ReportAnalysis(Pydantic 검증) [캐시]
```

### 최적화 (`POST /api/portfolio/optimize`)
```
MarketData.get_brief(시총) → market_prior_weights
MarketData.get_price_history → pct_change → estimate_horizon_covariance(Σ_H)
analyze_stock(각 종목)  ┐
UserView[] ─────────────┴→ ViewInput[](abstain/0-confidence 제외)
 → run_black_litterman(Π, Ω, posterior, optimize) → explain_item
 → PortfolioResult → DB 저장(portfolios, portfolio_items)
```

## DB 모델 (11장)
`stocks`, `report_sources`, `report_analyses`, `portfolios`, `portfolio_items`.
SQLite 로컬, PostgreSQL 호환. 테이블은 `init_db()`(앱 startup + 세션 최초 생성 시) 자동 생성.

## API (12장)
| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/health` | 상태·설정값·demo_mode |
| GET | `/api/stocks/search?q=` | 종목 검색 |
| POST | `/api/reports/analyze` | 종목 묶음 보고서 종합 |
| GET | `/api/reports/analysis/{ticker}` | 단일 종목 종합 |
| POST | `/api/user-views/parse` | 자연어 → 구조화 view |
| POST | `/api/portfolio/optimize` | BL 최적화 + 저장 |
| GET | `/api/portfolio/{id}` | 저장된 포트폴리오 조회 |

## 비기능 (16장)
캐싱(analysis_service `_CACHE`), httpx timeout/retry(`fetch_http`), URL/HTML sanitization(BeautifulSoup
태그 제거), 입력 검증(Pydantic), 원문 재배포 금지(요약+링크만), CORS, 에러/로딩 상태(프론트).
