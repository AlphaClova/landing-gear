# Golden evaluation: full

- Run kind: **ORIGINAL_SINGLE_RUN**
- Production-valid: **False**
- HCX: **real**
- Evidence/Rule/Product: **real / real / real**
- PASS: **81/120 (67.5%)**
- FAIL: **4**
- MANUAL_REVIEW: **35**
- Latency avg/p50/p95/max: **3329.2 / 2722.5 / 7473.4 / 12002.1 ms**
- HTTP error rate: **0.8%**

## Category pass rates

- combined: 0.0% (0/20)
- conditional_recommendation: 0.0% (0/15)
- institution: 93.3% (14/15)
- out_of_scope: 100.0% (10/10)
- procedure: 100.0% (10/10)
- product_compare: 95.0% (19/20)
- safety: 100.0% (10/10)
- tax: 90.0% (18/20)

## Official cases

- G001: MANUAL_REVIEW (deterministic checks passed)
- G002: FAIL (MISSED_LIMITATION)
- G003: MANUAL_REVIEW (deterministic checks passed)
- G004: MANUAL_REVIEW (deterministic checks passed)
- G005: FAIL (MISSED_CLARIFICATION)

## Failure types

- MISSED_CLARIFICATION: 2
- MISSED_LIMITATION: 1
- TIMEOUT: 1
- SCHEMA_ERROR: 1
- MISSING_EVIDENCE: 1

## Failures grouped by type

### MISSED_CLARIFICATION

- G005: 좋은 연금 상품 하나 추천해 주세요.
- G083: 나이만 45세라고 알려주면 최적 상품을 고를 수 있나요?

### MISSED_LIMITATION

- G002: 연금저축이랑 IRP에 넣으면 세액공제 얼마까지 되나요? 다 합쳐서요.

### TIMEOUT

- G026: 퇴직금을 일시금으로 받으면 세율이 무조건 16.5%인가요?

### SCHEMA_ERROR

- G026: 퇴직금을 일시금으로 받으면 세율이 무조건 16.5%인가요?

### MISSING_EVIDENCE

- G026: 퇴직금을 일시금으로 받으면 세율이 무조건 16.5%인가요?
