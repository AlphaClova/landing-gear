# Golden evaluation: official

- Production-valid: **False**
- HCX: **real**
- B Provider: **mock**
- PASS: **0/5 (0.0%)**
- FAIL: **5**
- MANUAL_REVIEW: **0**
- Latency avg/p50/p95/max: **1.1 / 1.0 / 1.6 / 1.6 ms**
- HTTP error rate: **0.0%**

## Category pass rates

- combined: 0.0% (0/1)
- conditional_recommendation: 0.0% (0/1)
- institution: 0.0% (0/1)
- product_compare: 0.0% (0/1)
- tax: 0.0% (0/1)

## Official cases

- G001: FAIL (MISSING_EVIDENCE)
- G002: FAIL (MISSING_EVIDENCE, UNSUPPORTED_CLAIM)
- G003: FAIL (MISSING_EVIDENCE, UNSUPPORTED_CLAIM)
- G004: FAIL (MISSING_EVIDENCE, UNSUPPORTED_CLAIM, MISSED_LIMITATION)
- G005: FAIL (MISSING_EVIDENCE)

## Failure types

- MISSING_EVIDENCE: 5
- UNSUPPORTED_CLAIM: 3
- MISSED_LIMITATION: 1

## Failures grouped by type

### MISSING_EVIDENCE

- G001: DC와 DB, 퇴직금이 정해지는 방식이랑 운용 주체가 어떻게 다른가요?
- G002: 연금저축이랑 IRP에 넣으면 세액공제 얼마까지 되나요? 다 합쳐서요.
- G003: 명퇴하는 교사예요. 명퇴수당을 연금계좌에 넣으면 세금 감면이 어마어마하다던데, 절세법만 알려주세요.
- G004: 솔로몬 국공채 단기 · 중장기 · 장기, 뭐가 달라요? 안정적인 걸 원해요.
- G005: 좋은 연금 상품 하나 추천해 주세요.

### UNSUPPORTED_CLAIM

- G002: 연금저축이랑 IRP에 넣으면 세액공제 얼마까지 되나요? 다 합쳐서요.
- G003: 명퇴하는 교사예요. 명퇴수당을 연금계좌에 넣으면 세금 감면이 어마어마하다던데, 절세법만 알려주세요.
- G004: 솔로몬 국공채 단기 · 중장기 · 장기, 뭐가 달라요? 안정적인 걸 원해요.

### MISSED_LIMITATION

- G004: 솔로몬 국공채 단기 · 중장기 · 장기, 뭐가 달라요? 안정적인 걸 원해요.
