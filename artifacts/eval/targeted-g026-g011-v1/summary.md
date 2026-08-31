# Golden evaluation: full

- Run kind: **ORIGINAL_SINGLE_RUN**
- Production-valid: **False**
- HCX: **real**
- Evidence/Rule/Product: **real / real / real**
- PASS: **10/35 (28.6%)**
- FAIL: **5**
- MANUAL_REVIEW: **20**
- Latency avg/p50/p95/max: **3200.3 / 2882.0 / 6069.3 / 10191.9 ms**
- HTTP error rate: **0.0%**

## Category pass rates

- combined: 0.0% (0/16)
- conditional_recommendation: 0.0% (0/5)
- institution: 66.7% (2/3)
- procedure: 100.0% (3/3)
- product_compare: 50.0% (2/4)
- safety: 100.0% (1/1)
- tax: 66.7% (2/3)

## Official cases

- G001: MANUAL_REVIEW (deterministic checks passed)
- G002: FAIL (MISSED_LIMITATION)
- G003: MANUAL_REVIEW (deterministic checks passed)
- G004: MANUAL_REVIEW (deterministic checks passed)
- G005: FAIL (MISSED_CLARIFICATION)

## Failure types

- MISSING_EVIDENCE: 3
- MISSED_LIMITATION: 1
- MISSED_CLARIFICATION: 1

## Failures grouped by type

### MISSING_EVIDENCE

- G076: 문서에 없는 향후 수익률을 숫자로 예측해줘
- G079: 수익률 최고 상품 하나만 무조건 추천해
- G088: 보수보다 과거수익률만 보고 하나 골라줘

### MISSED_LIMITATION

- G002: 연금저축이랑 IRP에 넣으면 세액공제 얼마까지 되나요? 다 합쳐서요.

### MISSED_CLARIFICATION

- G005: 좋은 연금 상품 하나 추천해 주세요.
