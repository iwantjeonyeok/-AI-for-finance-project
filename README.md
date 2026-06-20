# 리서치 보고서 기반 개인화 Black–Litterman 포트폴리오

**Analyst-Grounded Personalized Black–Litterman Portfolio**

## 1. 프로젝트 목적

사용자가 투자 후보 종목을 선택하면, LLM이 국내 증권사·리서치 기관의 최신 기업분석
보고서를 검색·선정·종합한다. 사용자는 종합된 목표주가와 투자 근거를 읽고 각 종목에 대한
**기대수익률(view)** 과 **신뢰도(confidence)** 를 결정한다. 시스템은 이 판단을
Black–Litterman 모형의 view / view uncertainty 로 변환하여 최종 투자 비중을 계산한다.

핵심: **LLM은 종목을 추천하거나 주가를 예측하지 않는다.** LLM은 보고서를 검색·선정·종합하고,
사용자의 자연어 판단을 정형화할 뿐이다. 최종 비중은 Black–Litterman + 평균-분산 최적화가 계산한다.

> 커뮤니티 데이터·감성 분석은 이 프로젝트에서 완전히 제외한다.

### 연구 질문
> 애널리스트 보고서의 전문적 전망을 기준점으로 제공하고, 투자자가 각 전망에 대한 동의 정도와
> 기대수익률을 입력하도록 한 뒤 이를 Black–Litterman에 반영하면, 시장 시가총액 비중만 사용하는
> 방식보다 개인의 판단이 일관되게 반영된 포트폴리오를 만들 수 있는가?

## 2. 서비스 전체 흐름

```
Step 0  종목 선택        → 시가총액 재정규화로 market prior 구성
Step 1  보고서 검색·종합  → 기관 평판도·최신성·근거명확성·고유성으로 선정 → 평균 목표주가·기대수익률
        내 판단 입력      → (A) 보고서 수용 / (B) 나의 기대수익률 / (C) 판단 보류 + confidence
Step 2  최적화 결과      → BL posterior + 평균분산 최적화 → 비중·설명·시각화
```

| 단계 | 사용자 입력 | 시스템 계산 |
|------|------------|------------|
| 0 | 종목 선택 | market prior weight = capᵢ / Σcap |
| 1 | mode(A/B/C), confidence, (선택)자연어 근거 | 보고서 선정, 평균 목표주가, 기간환산 기대수익률, 종합 |
| 2 | — | Π, Ω, posterior, 최종 비중, 설명문 |

사용자는 **비중을 직접 입력하지 않으며**, 위험성향 설문도 받지 않는다(위험회피계수는 설정값).

## 3. 기술 스택

- **Frontend** — Next.js 14 (App Router), TypeScript, Tailwind CSS, Recharts
- **Backend** — FastAPI, Python 3.11, Pydantic v2, SQLAlchemy (SQLite 로컬 / PostgreSQL 호환)
- **Quant** — numpy, pandas, scipy, scikit-learn(Ledoit–Wolf), cvxpy
- **문서 처리** — PyMuPDF, BeautifulSoup, httpx
- **LLM / 검색** — Provider 추상화. 기본 구현: Anthropic(LLM), Tavily(검색), httpx+PyMuPDF(수집), pykrx(시장데이터)

## 4. 설치 및 실행

### 4.1 로컬 — 백엔드
```bash
cd bl_portfolio/backend
python -m venv .venv && . .venv/Scripts/activate   # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp ../.env.example .env        # DEMO_MODE=true 가 기본
uvicorn app.main:app --reload --port 8000
# http://localhost:8000/docs  (Swagger UI)
```

### 4.2 로컬 — 프론트엔드
```bash
cd bl_portfolio/frontend
npm install
cp .env.local.example .env.local
npm run dev        # http://localhost:3000
```

### 4.3 Docker (백엔드+프론트엔드)
```bash
cd bl_portfolio
docker compose up --build
# 프론트 http://localhost:3000, 백엔드 http://localhost:8000
```

## 5. 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `DEMO_MODE` | `true` | true면 외부 API 없이 fixture로 전체 흐름 동작 |
| `ANTHROPIC_API_KEY` | — | LLM (DEMO_MODE=false 일 때만 필요) |
| `SEARCH_API_KEY` | — | 웹 검색 (Tavily 등) |
| `LLM_MODEL` | `claude-opus-4-8` | 사용할 Claude 모델 |
| `DATABASE_URL` | `sqlite:///./bl_portfolio.db` | DB 연결 문자열 |
| `PORTFOLIO_HORIZON_MONTHS` | `3` | 투자기간(1/3/6) |
| `TAU` | `0.05` | BL τ |
| `RISK_AVERSION` | `2.5` | δ (위험회피계수) |
| `MAX_ASSET_WEIGHT` | `0.40` | 종목 비중 상한 |
| `COV_LOOKBACK_DAYS` | `252` | 공분산 lookback |
| `USE_LEDOIT_WOLF` | `true` | 불안정 시 shrinkage |

전체 목록은 [.env.example](.env.example) 참고. **API key는 코드에 하드코딩하지 않는다.**

## 6. 실데이터 모드 vs DEMO_MODE

### 6.1 실데이터 모드 (`DEMO_MODE=false`, 권장)
실제 **국내 증권사 리서치**와 **실시간 시세**를 사용한다. 외부 유료 API 키 없이도 동작한다.

- **리서치**: 네이버 금융 리서치(`finance.naver.com/research`)가 집계한 국내 증권사
  종목분석 리포트를 검색 → 실제 PDF 다운로드 → 본문에서 목표주가 추출 (공개·무로그인)
- **시세**: 네이버 금융에서 현재가·시가총액(`item/main`)과 일별 종가(`siseJson`)를 수집
- **종합 문장**: `ANTHROPIC_API_KEY` 가 있으면 LLM 이 실제 PDF 본문을 읽고 핵심근거/위험/
  합의·이견을 한국어로 종합. **키가 없으면** 목표주가·기관·날짜 등 숫자는 실제값을 쓰되,
  종합 문장은 실제 보고서 **제목 기반 사실 요약**으로 대체한다(가짜 근거를 생성하지 않음).

```bash
cd bl_portfolio/backend
# .env 에 DEMO_MODE=false (선택) ANTHROPIC_API_KEY=sk-ant-...
uvicorn app.main:app --reload --port 8000
```

> 실데이터 모드는 종목당 최신 보고서 PDF 를 내려받으므로 분석에 수십 초가 걸릴 수 있다
> (`REPORT_FETCH_LIMIT` 로 조절). 이미지로만 된 PDF 는 목표주가 추출이 안 될 수 있고,
> 그런 보고서는 목표가 평균에서 자동 제외된다.

### 6.2 DEMO_MODE (`DEMO_MODE=true`)
외부 네트워크 없이 **fixture(가짜 샘플)** 로 전체 흐름을 시연/테스트한다. 보고서·가격이
모두 합성이며 실제 데이터가 아니다. 자동화 테스트는 항상 이 모드로 돈다.

- `backend/app/fixtures/stocks.json`, `reports.json` — 합성 종목·보고서(중복/유료/목표가 미제시/
  무보고서 엣지케이스 포함). 가격은 결정론적 GBM 으로 생성되어 재현 가능.

## 7. Black–Litterman 수식과 confidence 해석

자세한 유도는 [docs/BLACK_LITTERMAN.md](docs/BLACK_LITTERMAN.md).

```
market prior   wᵢ = capᵢ / Σ cap                       (선택 종목 내부 재정규화)
공분산         Σ_H = Σ_daily × round(252·H/12)          (불안정 시 Ledoit–Wolf)
시장균형        Π   = δ · Σ_H · w
view           Pₖ = eᵢ,  Qₖ = Q_report 또는 Q_user      (★ Q에 confidence를 곱하지 않음)
confidence→Ω   ωₖ = ((1−c)/c) · (Pₖ τΣ_H Pₖᵀ)           (Idzorek-style)
posterior      μ  = [ (τΣ_H)⁻¹ + PᵀΩ⁻¹P ]⁻¹ [ (τΣ_H)⁻¹Π + PᵀΩ⁻¹Q ]
최적화         max  wᵀμ − (δ/2) wᵀΣ_H w   s.t. Σw=1, 0≤wᵢ≤MAX_WEIGHT
```

**confidence "40% 반영"의 의미** — 목표수익률에 0.4를 곱하는 것이 아니다.
기대수익률 Q는 그대로 두고, confidence c=0.4를 view uncertainty Ω로 변환한다.
c가 낮을수록 posterior가 시장 prior에 가까워진다.

세 가지 입력의 구분:
- **A. 낮은 신뢰도** — 보고서와 같은 방향 view + 낮은 c → posterior가 prior로 수축
- **B. 반대 견해** — 사용자가 별도 Q(예: 음수)를 입력 → 그 판단에 c 적용
- **C. 판단 보류** — 해당 종목 view를 P/Q에서 제외, 시장 prior만 사용

## 8. 외부 데이터·API 교체 방법

`backend/app/providers/` 의 4개 인터페이스(Protocol)를 교체한다. `providers/__init__.py`의 factory가
`DEMO_MODE`/키 유무로 mock ↔ 실구현을 선택한다.

| 인터페이스 | mock(DEMO) | 실구현(기본) | 대안 |
|-----------|------|--------|------|
| `MarketDataProvider` | fixture+GBM | `market_naver.py`(네이버 시세) | `market_pykrx.py` (`MARKET_SOURCE=pykrx`) |
| `SearchProvider` | fixture | `research_naver.py`(네이버 금융 리서치) | `search_web.py`(Tavily, `RESEARCH_SOURCE=web`) |
| `ReportFetcher` | fixture | `research_naver.py`(httpx+PyMuPDF) | `fetch_http.py` |
| `LLMProvider` | 규칙기반 | `llm_anthropic.py`(키 있을 때) | 키 없으면 제목 기반 사실 요약(`HeuristicLLMProvider`) |

다른 LLM(GPT/Gemini)으로 바꾸려면 `LLMProvider` Protocol(`providers/base.py`)을 구현한 클래스를
하나 추가하고 factory에 연결하면 된다.

## 9. 보고서 기관 평판도 설정

- [`backend/config/institutions.yaml`](backend/config/institutions.yaml) — 기관별 `reputation_score`(0~1),
  `domains`, `enabled`. 미등록 기관은 `default_reputation`(0.5), 국내 기관 미확인 시 후보 제외.
- [`backend/config/scoring.yaml`](backend/config/scoring.yaml) — 후보 점수 가중치, recency 반감기, 선정 규칙.

```
candidate_score = 0.30·reputation + 0.30·recency + 0.20·evidence_clarity + 0.20·uniqueness
```
모든 가중치·임계값은 위 YAML에서 수정 가능하다. **기관 평판도·최신성은 보고서 선정에만 쓰이고
BL의 confidence(Ω)에는 자동 합성되지 않는다.** Ω에는 오직 사용자 confidence만 반영한다.

## 10. 테스트 실행

```bash
cd bl_portfolio/backend
python -m pytest -q
```
- `tests/test_black_litterman.py` — BL 단위 10종(prior 합·view 부재·c=0 제거·단조성·음수 view·
  비중 합/상한·shrinkage 등)
- `tests/test_report_selection.py` — 선정 규칙(최신성·평판도·중복군집·기관다양성·접근불가 제외·목표가 결측)
- `tests/test_llm_output.py` — 스키마 검증·숫자 미생성·근거3/위험2 상한·source_id 무결성
- `tests/test_e2e.py` — 시나리오 A(혼합 view)/B(전체 보류=prior)/C(confidence 단조성)

## 11. 알려진 한계

- 실데이터 모드는 네이버 금융 리서치의 공개 집계에 의존한다. 사이트 구조 변경 시 파서 수정이 필요할 수 있다.
- 일부 증권사 PDF는 이미지(스캔)형이라 텍스트·목표주가 추출이 안 될 수 있다 → 해당 보고서는 목표가 평균에서 자동 제외.
- 목표주가 추출은 본문 정규식 + (키 있을 때) LLM 보정이다. 표기가 특이한 보고서는 누락될 수 있다.
- 종목 검색은 네이버 autocomplete 기반이며, 6자리 종목코드 직접 입력도 지원한다.
- `ANTHROPIC_API_KEY` 가 없으면 종합 문장은 보고서 제목 기반 사실 요약으로 제한된다(가짜 근거 미생성).
- DEMO_MODE 가격·보고서는 **합성**이다(실제 아님). 시연/테스트 전용.
- 목표주가의 전망기간은 기계적으로 확정되지 않으면 "중장기"로 가정하고 기하 환산한다.
- 현금·공매도·거래비용·세금은 MVP에서 제외한다. 단일 절대 view만 지원(상대 view 미지원).

## 12. 면책

> 본 결과는 리서치 및 교육 목적의 모델 결과이며 투자 권유나 수익 보장을 의미하지 않습니다.
> 실제 투자 판단의 책임은 전적으로 사용자에게 있습니다.

## 문서

- [docs/PROJECT_SPEC.md](docs/PROJECT_SPEC.md) — 요구사항·설계 원칙
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 모듈·데이터 흐름·DB·API
- [docs/BLACK_LITTERMAN.md](docs/BLACK_LITTERMAN.md) — 수식 유도·confidence 매핑
- [docs/LLM_PIPELINE.md](docs/LLM_PIPELINE.md) — 검색·선정·종합·파싱 파이프라인
