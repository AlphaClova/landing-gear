# Golden evaluation: smoke

- Production-valid: **False**
- HCX: **real**
- B Provider: **mock**
- PASS: **1/20 (5.0%)**
- FAIL: **19**
- MANUAL_REVIEW: **0**
- Latency avg/p50/p95/max: **128.4 / 0.9 / 1.2 / 2550.4 ms**
- HTTP error rate: **0.0%**

## Category pass rates

- combined: 0.0% (0/1)
- conditional_recommendation: 0.0% (0/1)
- institution: 6.7% (1/15)
- product_compare: 0.0% (0/1)
- tax: 0.0% (0/2)

## Official cases

- G001: FAIL (MISSING_EVIDENCE)
- G002: FAIL (MISSING_EVIDENCE, UNSUPPORTED_CLAIM)
- G003: FAIL (MISSING_EVIDENCE, UNSUPPORTED_CLAIM)
- G004: FAIL (MISSING_EVIDENCE, UNSUPPORTED_CLAIM, MISSED_LIMITATION)
- G005: FAIL (MISSING_EVIDENCE)

## Failure types

- MISSING_EVIDENCE: 19
- UNSUPPORTED_CLAIM: 3
- MISSED_LIMITATION: 1

## Failures grouped by type

### MISSING_EVIDENCE

- G001: DC와 DB, 퇴직금이 정해지는 방식이랑 운용 주체가 어떻게 다른가요?
- G002: 연금저축이랑 IRP에 넣으면 세액공제 얼마까지 되나요? 다 합쳐서요.
- G003: 명퇴하는 교사예요. 명퇴수당을 연금계좌에 넣으면 세금 감면이 어마어마하다던데, 절세법만 알려주세요.
- G004: 솔로몬 국공채 단기 · 중장기 · 장기, 뭐가 달라요? 안정적인 걸 원해요.
- G005: 좋은 연금 상품 하나 추천해 주세요.
- G006: DB형과 DC형에서 퇴직급여 산정 방식은 각각 무엇인가요?
- G007: 확정급여형은 누가 적립금을 운용하나요?
- G008: DC형은 회사가 수익률을 책임지는 제도인가요?
- G009: 퇴직연금이 일반 퇴직금과 어떻게 다른가요?
- G010: 개인사업자 대표도 DB나 DC에 가입할 수 있나요?
- G011: 주 14시간 근무자도 퇴직연금 대상인가요?
- G012: 근속 1년 미만 근로자의 가입 대상 여부를 알려줘
- G013: 공무원도 회사 DB형에 가입할 수 있죠?
- G014: 외국인 근로자 E-9 비자의 가입 조건은?
- G015: 임원도 퇴직연금 가입 가능한가요?
- G017: DB에서 운용손익이 급여에 직접 반영되나요?
- G018: 퇴직연금은 몇 살부터 연금으로 받을 수 있나요?
- G019: IRP와 DC는 같은 제도인가요?
- G020: 연금저축 세액공제 한도와 IRP 합산 한도를 근거와 함께 알려줘

### UNSUPPORTED_CLAIM

- G002: 연금저축이랑 IRP에 넣으면 세액공제 얼마까지 되나요? 다 합쳐서요.
- G003: 명퇴하는 교사예요. 명퇴수당을 연금계좌에 넣으면 세금 감면이 어마어마하다던데, 절세법만 알려주세요.
- G004: 솔로몬 국공채 단기 · 중장기 · 장기, 뭐가 달라요? 안정적인 걸 원해요.

### MISSED_LIMITATION

- G004: 솔로몬 국공채 단기 · 중장기 · 장기, 뭐가 달라요? 안정적인 걸 원해요.
