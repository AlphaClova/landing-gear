# Golden evaluation: full

- Run kind: **ORIGINAL_SINGLE_RUN**
- Production-valid: **True**
- HCX: **real**
- Evidence/Rule/Product: **real / real / real**
- PASS: **0/8 (0.0%)**
- FAIL: **4**
- MANUAL_REVIEW: **4**
- Latency avg/p50/p95/max: **4503.6 / 4480.6 / 6830.7 / 6830.7 ms**
- HTTP error rate: **0.0%**

## Category pass rates

- combined: 0.0% (0/4)
- procedure: 0.0% (0/2)
- tax: 0.0% (0/2)

## Official cases

- G003: FAIL (MISSING_EVIDENCE)

## Failure types

- MISSING_EVIDENCE: 4
- WRONG_INTENT: 2

## Failures grouped by type

### MISSING_EVIDENCE

- G003: 명퇴하는 교사예요. 명퇴수당을 연금계좌에 넣으면 세금 감면이 어마어마하다던데, 절세법만 알려주세요.
- BLIND-A: 명퇴 예정인 교사인데 명퇴수당 절세 방법 알려줘
- BLIND-B: 교직원 명예퇴직수당을 연금계좌에 넣을 수 있나요?
- BLIND-C: 공무원 명퇴수당을 받은 뒤 세금 환급 절차가 있나요?

### WRONG_INTENT

- BLIND-B: 교직원 명예퇴직수당을 연금계좌에 넣을 수 있나요?
- BLIND-C: 공무원 명퇴수당을 받은 뒤 세금 환급 절차가 있나요?
