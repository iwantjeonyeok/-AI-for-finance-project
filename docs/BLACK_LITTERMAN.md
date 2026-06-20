# BLACK_LITTERMAN — 수식과 confidence 매핑

구현: [`backend/app/core/black_litterman.py`](../backend/app/core/black_litterman.py),
[`covariance.py`](../backend/app/core/covariance.py). 검증: `tests/test_black_litterman.py`.

## 기호
| 기호 | 의미 |
|------|------|
| N | 선택 종목 수 |
| w | market prior weight (시총 재정규화, Σw=1) |
| Σ_H | 투자기간 H개월 공분산 |
| δ | 위험회피계수 (`RISK_AVERSION`, 기본 2.5) |
| τ | prior 불확실성 스케일 (`TAU`, 기본 0.05) |
| Π | 시장 균형 기대수익률 |
| P, Q | view 행렬 / view 기대수익률 |
| Ω | view 불확실성(대각) |
| c | 사용자 confidence (0~1) |

## 1. Market prior
```
wᵢ = market_capᵢ / Σⱼ market_capⱼ
```
선택 종목 **내부에서** 재정규화하므로 Σw=1. (시총 전부 0이면 동일가중 fallback)

## 2. 공분산 Σ_H
```
H_days = round(252 · H / 12)
Σ_H    = Σ_daily · H_days
```
수정주가 일별 수익률(기본 252거래일)에서 추정. 관측치 부족·비정칙·조건수 과대 시
**Ledoit–Wolf shrinkage** 적용. Σ_H는 대칭화한다.

## 3. 시장 균형 (역최적화)
```
Π = δ · Σ_H · w
```
view가 하나도 없으면 posterior = Π이며, 평균분산 최적해는 (상한 내) w로 복원된다.

## 4. View 구성
유효 view가 있는 종목 i마다 **절대 view** 한 행:
```
Pₖ = eᵢ (= [0,…,1,…,0]),   Qₖ = Q_report,i  또는  Q_user,i
```
- 보고서 수용(A): `Q = implied_return_portfolio_horizon`
- 직접 입력(B): `Q = user.expected_return`
- 보류(C) 또는 `c=0`: P/Q에서 **제외**

> ★ Q에는 confidence를 곱하지 않는다. confidence는 오직 Ω로만 들어간다. (`test_6`)

## 5. confidence → Ω (Idzorek-style)
```
c   = slider / 100,   c ∈ (0, 0.999]   (상한 클램프)
ωₖ  = ((1 − c) / c) · (Pₖ · τΣ_H · Pₖᵀ) + ε
Ω   = diag(ω₁, …, ω_K)
```
- c → 1 : ω → 0  → view를 강하게 신뢰 → posterior가 Q로 이동
- c → 0 : ω → ∞ → view 무력화 → posterior가 Π로 수축
- c = 0 : view 행 자체 제거 (`test_3`)

`(1−c)/c` 형태이므로 신뢰도와 불확실성이 단조 반비례. 동일 Q에서 c가 커질수록 posterior가
view 방향으로 단조 이동한다 (`test_4`). 단일 절대 view의 닫힌형:
```
μᵢ = Πᵢ + [ τΣ_H,ii / (τΣ_H,ii + ωₖ) ] · (Q − Πᵢ),   계수 ∈ (0,1)
```
→ posterior는 항상 Π와 Q 사이에 위치한다(곱셈 스케일링이 아님을 보장).

## 6. Posterior
```
posterior_cov    = [ (τΣ_H)⁻¹ + Pᵀ Ω⁻¹ P ]⁻¹
posterior_return = posterior_cov · [ (τΣ_H)⁻¹ Π + Pᵀ Ω⁻¹ Q ]
```
view가 없으면 `posterior_return = Π`, `posterior_cov = τΣ_H` (`test_2`).

## 7. 최적화
```
maximize_w   wᵀ μ − (δ/2) wᵀ Σ_H w
s.t.         Σw = 1,   0 ≤ wᵢ ≤ MAX_WEIGHT (기본 0.40)
```
cvxpy로 푼다. 현금·공매도 없음. 해가 비최적/실패면 fallback:
`w* = (1/δ) Σ_H⁻¹ μ`를 양수화·정규화·상한 재분배. fallback 사용 시 `used_fallback=true`로 UI 표시.
`MAX_WEIGHT·N < 1`이면 실현가능성 위해 상한을 일시 완화한다.

## 8. 신뢰도 해석 (사용자 설명)
> "40%는 목표수익률을 40%로 줄이는 것이 아니라, 해당 전망에 대한 신뢰도입니다.
> 신뢰도가 낮을수록 최종 결과는 시장 시가총액 기준 비중에 가까워집니다."

| 입력 | Q | c | 결과 |
|------|---|---|------|
| 보고서 수용·낮은 확신 | Q_report | 작음 | prior로 수축 |
| 반대 견해 | Q_user(예: 음수) | 사용자값 | 그 방향으로 이동, 비중 감소 (`test_5`) |
| 판단 보류 | — | — | view 제외, prior 유지 (`test_10`) |

## 9. 보고서 신호와 BL의 분리
기관 평판도·최신성·보고서 간 분산은 **보고서 선정**에만 쓰이며 Ω에 자동 합성하지 않는다.
Ω에 반영되는 것은 오직 사용자 confidence다(설계 원칙 8.5).
