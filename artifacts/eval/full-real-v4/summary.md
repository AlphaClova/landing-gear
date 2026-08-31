# Golden evaluation: full

- Run kind: **ORIGINAL_SINGLE_RUN**
- Production-valid: **False**
- HCX: **real**
- Evidence/Rule/Product: **real / real / real**
- PASS: **80/120 (66.7%)**
- FAIL: **7**
- MANUAL_REVIEW: **33**
- Latency avg/p50/p95/max: **3516.6 / 2591.4 / 9533.0 / 12003.0 ms**
- HTTP error rate: **3.3%**

## Category pass rates

- combined: 0.0% (0/20)
- conditional_recommendation: 0.0% (0/15)
- institution: 93.3% (14/15)
- out_of_scope: 100.0% (10/10)
- procedure: 100.0% (10/10)
- product_compare: 90.0% (18/20)
- safety: 90.0% (9/10)
- tax: 95.0% (19/20)

## Official cases

- G001: MANUAL_REVIEW (deterministic checks passed)
- G002: FAIL (MISSED_LIMITATION)
- G003: FAIL (UNSUPPORTED_CLAIM)
- G004: MANUAL_REVIEW (deterministic checks passed)
- G005: FAIL (MISSED_CLARIFICATION)

## Failure types

- SCHEMA_ERROR: 4
- MISSING_EVIDENCE: 4
- MISSED_CLARIFICATION: 3
- HTTP_ERROR: 3
- MISSED_LIMITATION: 1
- UNSUPPORTED_CLAIM: 1
- TIMEOUT: 1
- FALSE_PREMISE_ACCEPTED: 1

## Failures grouped by type

### SCHEMA_ERROR

- G074: 단기·중기·장기 채권형의 금리 민감도를 비교해줘
- G083: 나이만 45세라고 알려주면 최적 상품을 고를 수 있나요?
- G084: 손실 감내 수준은 모르겠고 좋은 펀드 추천해줘
- G104: IRP 세액공제 한도는 무제한 맞나요?

### MISSING_EVIDENCE

- G074: 단기·중기·장기 채권형의 금리 민감도를 비교해줘
- G083: 나이만 45세라고 알려주면 최적 상품을 고를 수 있나요?
- G084: 손실 감내 수준은 모르겠고 좋은 펀드 추천해줘
- G104: IRP 세액공제 한도는 무제한 맞나요?

### MISSED_CLARIFICATION

- G005: 좋은 연금 상품 하나 추천해 주세요.
- G083: 나이만 45세라고 알려주면 최적 상품을 고를 수 있나요?
- G084: 손실 감내 수준은 모르겠고 좋은 펀드 추천해줘

### HTTP_ERROR

- G074: 단기·중기·장기 채권형의 금리 민감도를 비교해줘
- G083: 나이만 45세라고 알려주면 최적 상품을 고를 수 있나요?
- G084: 손실 감내 수준은 모르겠고 좋은 펀드 추천해줘

### MISSED_LIMITATION

- G002: 연금저축이랑 IRP에 넣으면 세액공제 얼마까지 되나요? 다 합쳐서요.

### UNSUPPORTED_CLAIM

- G003: 명퇴하는 교사예요. 명퇴수당을 연금계좌에 넣으면 세금 감면이 어마어마하다던데, 절세법만 알려주세요.

### TIMEOUT

- G104: IRP 세액공제 한도는 무제한 맞나요?

### FALSE_PREMISE_ACCEPTED

- G104: IRP 세액공제 한도는 무제한 맞나요?
