# PROJECT_SPEC — 요구사항과 설계 원칙

## 목적
애널리스트 보고서의 전문적 전망을 **기준점**으로 제시하고, 투자자의 동의 정도(view + confidence)를
Black–Litterman에 결합하여 개인화된 포트폴리오 비중을 산출한다. LLM은 추천·예측이 아니라
검색·선정·종합·정형화만 담당한다.

## 반드시 지키는 설계 원칙

### P1. "40% 반영"은 confidence이지 수익률 스케일이 아니다
- 잘못: `Q = 0.4 × 10% = 4%`
- 올바름: `Q = 10%` 유지, `c = 0.4`를 Ω로 변환. c가 낮을수록 posterior가 prior로 수축.

### P2. 낮은 신뢰도 vs 반대 견해 구분
- **A 낮은 신뢰도**: 보고서 방향 view + 낮은 c → prior로 수축
- **B 반대 견해**: 사용자 별도 Q(예: 음수) + 그 판단의 c
- **C 판단 보류**: 해당 종목 view를 P/Q에서 제외, prior만 사용

### P3. 사용자는 비중을 직접 입력하지 않는다
입력은 mode(A/B/C), confidence(0~100%), 선택적 자연어 근거뿐. 비중은 최적화가 계산.

### P4. 위험 성향 입력 없음
위험회피계수 δ, 비중 상한은 시스템 설정값(`RISK_AVERSION`, `MAX_ASSET_WEIGHT`).

## 보고서 선정 기준 (4장)
1. 국내 기관 평판도 (config) 2. 최신성 3. 다기관 중복 회피 4. 근거 명확성 5. 기관 다양성

```
candidate_score = 0.30·reputation + 0.30·recency + 0.20·evidence_clarity + 0.20·uniqueness
```
- 종목당 최대 5개, 가능하면 3개 이상 서로 다른 기관, 기관당 1개 우선
- 중복 군집은 대표 1개만, 유료/접근불가 우회 금지, 미확인 국내기관 제외
- 검색 실패 시 사용자 URL/PDF 직접 추가(fallback), 보고서 0건이면 "시장 prior만 사용"

## 투자기간 변환 (6장)
기본 3개월(1/3/6 선택). 목표주가를 중장기 가정으로 보고 기하 환산.
```
raw_return       = mean_TP / current_price − 1
horizon_return   = (1 + raw_return)^(H/12) − 1
```
비정상 목표가(통화오류·액면분할 의심 등)는 검증 실패 처리하여 평균에서 제외.

## 사용자 판단 입력 (7장)
- A 보고서 수용: `Q = Q_report`, confidence만 사용자 결정
- B 직접 입력: `Q = Q_user`(기간 기준 %, 저장 시 decimal)
- C 보류: view 제외
- 자연어 입력은 LLM이 `{mode, expected_return, confidence, rationale}`로 구조화 → 사용자가 확인/편집

## 결과 화면 (9장)
종목별 표(prior/목표가/보고서기대/사용view/confidence/posterior/최종비중/변화),
4종 차트, 템플릿 기반 설명문, 면책문구.

## 수용 시나리오 (14장)
- **A** 5종목(보고서 4 + 무보고서 1), 수용2/직접1/보류1/무보고서1 → BL 산출
- **B** 전체 보류 → market prior와 (제약 내) 동일
- **C** 동일 종목 confidence 20/50/90% → 비중이 view 방향으로 단조 변화

모든 시나리오는 `tests/test_e2e.py`에서 자동 검증된다.
