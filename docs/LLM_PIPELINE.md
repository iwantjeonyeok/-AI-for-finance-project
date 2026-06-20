# LLM_PIPELINE — 검색·선정·종합·파싱

Provider 인터페이스: [`backend/app/providers/base.py`](../backend/app/providers/base.py).
프롬프트: [`backend/app/prompts.py`](../backend/app/prompts.py).
DEMO에서는 규칙 기반 `MockLLMProvider`, 실모드에서는 `AnthropicLLMProvider`.

## 단계

### 1. 검색 쿼리 생성 — `generate_search_queries`
종목명·코드 모두 활용, 국내 기관 우선, 최신성+기관 다양성. 출력 `{"queries": [...]}`.

### 2. 검색 — `SearchProvider.search_reports`
실모드는 Tavily 호출 후 국내 증권사 도메인 화이트리스트로 1차 필터. 접근 불가(`accessible=false`)
표시. 실제 URL·발행일 검증. **접근 못하는 자료를 접근한 것처럼 표현 금지.**

### 3. 본문 수집 — `ReportFetcher.fetch`
httpx(timeout/retry) → PDF는 PyMuPDF, HTML은 BeautifulSoup. 4xx/5xx·로그인폼은 `None`(우회 금지).
수집 실패 보고서는 후보에서 제외.

### 4. 점수·선정 — `core/report_scorer.py`
```
reputation        : config(institutions.yaml). 미등록=0.5, 국내 미확인=제외
recency           : 0.5^(경과일 / half_life)
evidence_clarity  : LLM 평가(0~1) — 목표가/산정논리/근거/리스크 식별성
uniqueness        : 1 − max(다른 보고서와의 코사인 유사도)
candidate_score   : 가중합(scoring.yaml)
```
중복 군집(union-find, 유사도 임계값) → 군집당 대표 1개. 기관당 1개 우선 → 부족 시 추가.
종목당 최대 5개, 가능하면 3개 이상 서로 다른 기관.

### 5. 종합 — `synthesize` (텍스트만)
**숫자는 코드가 계산**(목표가 평균·기대수익률). LLM은 핵심근거≤3, 위험≤2, 합의점, 쟁점만 생성.
각 항목에 `supporting_source_ids`를 채워 출처 없는 사실을 배제. 출력은 `LLMSynthesisOutput`로 검증
(근거3/위험2 초과 시 거부). 보고서별 나열 금지, 종합. 낙관 편향 금지.

### 6. 목표주가·기대수익률 (코드)
```
유효 목표가 평균(비정상값 제외) → raw_return → (1+raw)^(H/12)−1 = Q_report
```
목표가 미제시 보고서는 평균에서 제외하되 논거 요약에는 사용 가능.

### 7. 자연어 view 파싱 — `parse_user_view`
`{mode: accept_report|custom_view|abstain, expected_return(decimal|null), confidence(0~1), rationale}`.
없는 숫자 생성 금지. 결과는 **자동 적용하지 않고** 프론트에서 편집 가능한 폼에 채운다.

## 검증·복구
- 모든 LLM 출력은 Pydantic 스키마 검증. 실모드 `synthesize`는 JSON 파싱/검증 실패 시 1회 재시도 후
  빈 결과로 graceful degrade.
- `tests/test_llm_output.py`: 스키마 거부, 숫자 미생성(fixture), 근거3/위험2 상한, source_id 무결성.

## 비용 절감
- 동일 `(ticker, horizon)` 분석 결과 캐싱(`analysis_service._CACHE`).
- 본문은 선정된 보고서만 종합에 투입(chunk 제한 `[:1500]`/`[:6000]`).

## 다른 LLM으로 교체 (GPT/Gemini)
`LLMProvider` Protocol을 구현한 클래스를 추가하고 `providers/__init__.py`의 `get_llm_provider()`에
연결. 스키마/프롬프트는 그대로 재사용한다.
