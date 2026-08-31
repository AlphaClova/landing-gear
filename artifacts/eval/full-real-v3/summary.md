# Golden evaluation: full

- Run kind: **ORIGINAL_SINGLE_RUN**
- Production-valid: **False**
- HCX: **real**
- Evidence/Rule/Product: **real / real / real**
- PASS: **81/120 (67.5%)**
- FAIL: **4**
- MANUAL_REVIEW: **35**
- Latency avg/p50/p95/max: **3770.4 / 2730.5 / 10509.4 / 12001.9 ms**
- HTTP error rate: **3.3%**

## Category pass rates

- combined: 0.0% (0/20)
- conditional_recommendation: 0.0% (0/15)
- institution: 93.3% (14/15)
- out_of_scope: 100.0% (10/10)
- procedure: 100.0% (10/10)
- product_compare: 90.0% (18/20)
- safety: 100.0% (10/10)
- tax: 95.0% (19/20)

## Official cases

- G001: MANUAL_REVIEW (deterministic checks passed)
- G002: MANUAL_REVIEW (deterministic checks passed)
- G003: MANUAL_REVIEW (deterministic checks passed)
- G004: MANUAL_REVIEW (deterministic checks passed)
- G005: MANUAL_REVIEW (deterministic checks passed)

## Failure types

- SCHEMA_ERROR: 4
- MISSING_EVIDENCE: 4
- HTTP_ERROR: 2
- TIMEOUT: 2

## Failures grouped by type

### SCHEMA_ERROR

- G072: 총보수 0% 상품만 찾아줘
- G086: 금리 하락을 예상할 때 장기채를 무조건 사야 하나요?
- G089: 투자기간 6개월, 원금보장 필요, IRP 상품 비교
- G090: 투자기간 20년, 중위험 선호, DC 상품 비교

### MISSING_EVIDENCE

- G072: 총보수 0% 상품만 찾아줘
- G086: 금리 하락을 예상할 때 장기채를 무조건 사야 하나요?
- G089: 투자기간 6개월, 원금보장 필요, IRP 상품 비교
- G090: 투자기간 20년, 중위험 선호, DC 상품 비교

### HTTP_ERROR

- G072: 총보수 0% 상품만 찾아줘
- G089: 투자기간 6개월, 원금보장 필요, IRP 상품 비교

### TIMEOUT

- G086: 금리 하락을 예상할 때 장기채를 무조건 사야 하나요?
- G090: 투자기간 20년, 중위험 선호, DC 상품 비교
