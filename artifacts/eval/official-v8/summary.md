# Golden evaluation: official

- Production-valid: **True**
- HCX: **real**
- Evidence/Rule/Product: **real / real / real**
- PASS: **0/5 (0.0%)**
- FAIL: **2**
- MANUAL_REVIEW: **3**
- Latency avg/p50/p95/max: **12634.8 / 9854.1 / 35092.4 / 35092.4 ms**
- HTTP error rate: **20.0%**

## Category pass rates

- combined: 0.0% (0/1)
- conditional_recommendation: 0.0% (0/1)
- institution: 0.0% (0/1)
- product_compare: 0.0% (0/1)
- tax: 0.0% (0/1)

## Official cases

- G001: MANUAL_REVIEW (deterministic checks passed)
- G002: FAIL (MISSED_LIMITATION)
- G003: MANUAL_REVIEW (deterministic checks passed)
- G004: FAIL (HTTP_ERROR, SCHEMA_ERROR, WRONG_INTENT, MISSING_EVIDENCE, UNSUPPORTED_CLAIM, MISSED_LIMITATION)
- G005: MANUAL_REVIEW (deterministic checks passed)

## Failure types

- MISSED_LIMITATION: 2
- HTTP_ERROR: 1
- SCHEMA_ERROR: 1
- WRONG_INTENT: 1
- MISSING_EVIDENCE: 1
- UNSUPPORTED_CLAIM: 1

## Failures grouped by type

### MISSED_LIMITATION

- G002: 연금저축이랑 IRP에 넣으면 세액공제 얼마까지 되나요? 다 합쳐서요.
- G004: 솔로몬 국공채 단기 · 중장기 · 장기, 뭐가 달라요? 안정적인 걸 원해요.

### HTTP_ERROR

- G004: 솔로몬 국공채 단기 · 중장기 · 장기, 뭐가 달라요? 안정적인 걸 원해요.

### SCHEMA_ERROR

- G004: 솔로몬 국공채 단기 · 중장기 · 장기, 뭐가 달라요? 안정적인 걸 원해요.

### WRONG_INTENT

- G004: 솔로몬 국공채 단기 · 중장기 · 장기, 뭐가 달라요? 안정적인 걸 원해요.

### MISSING_EVIDENCE

- G004: 솔로몬 국공채 단기 · 중장기 · 장기, 뭐가 달라요? 안정적인 걸 원해요.

### UNSUPPORTED_CLAIM

- G004: 솔로몬 국공채 단기 · 중장기 · 장기, 뭐가 달라요? 안정적인 걸 원해요.
