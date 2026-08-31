# Golden evaluation: full

- Run kind: **ORIGINAL_SINGLE_RUN**
- Production-valid: **False**
- HCX: **real**
- Evidence/Rule/Product: **real / real / real**
- PASS: **2/18 (11.1%)**
- FAIL: **3**
- MANUAL_REVIEW: **13**
- Latency avg/p50/p95/max: **3743.7 / 2920.5 / 12002.0 / 12002.0 ms**
- HTTP error rate: **5.6%**

## Category pass rates

- combined: 0.0% (0/11)
- conditional_recommendation: 0.0% (0/2)
- institution: 50.0% (1/2)
- out_of_scope: 100.0% (1/1)
- product_compare: 0.0% (0/1)
- tax: 0.0% (0/1)

## Official cases

- G001: MANUAL_REVIEW (deterministic checks passed)
- G002: FAIL (MISSED_LIMITATION)
- G004: MANUAL_REVIEW (deterministic checks passed)
- G005: FAIL (MISSED_CLARIFICATION)

## Failure types

- MISSED_LIMITATION: 1
- MISSED_CLARIFICATION: 1
- TIMEOUT: 1
- SCHEMA_ERROR: 1
- MISSING_EVIDENCE: 1

## Failures grouped by type

### MISSED_LIMITATION

- G002: 연금저축이랑 IRP에 넣으면 세액공제 얼마까지 되나요? 다 합쳐서요.

### MISSED_CLARIFICATION

- G005: 좋은 연금 상품 하나 추천해 주세요.

### TIMEOUT

- G050: 퇴직소득세만 알고 퇴직금은 몰라요. 연금 절세액 계산해줘

### SCHEMA_ERROR

- G050: 퇴직소득세만 알고 퇴직금은 몰라요. 연금 절세액 계산해줘

### MISSING_EVIDENCE

- G050: 퇴직소득세만 알고 퇴직금은 몰라요. 연금 절세액 계산해줘
