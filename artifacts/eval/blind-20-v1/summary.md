# Golden evaluation: smoke

- Production-valid: **True**
- HCX: **real**
- Evidence/Rule/Product: **real / real / real**
- PASS: **0/20 (0.0%)**
- FAIL: **8**
- MANUAL_REVIEW: **12**
- Latency avg/p50/p95/max: **10286.6 / 10364.1 / 18804.3 / 23825.8 ms**
- HTTP error rate: **0.0%**

## Category pass rates

- institution: 0.0% (0/5)
- product: 0.0% (0/5)
- tax: 0.0% (0/10)

## Official cases


## Failure types

- WRONG_NUMBER: 5
- UNSUPPORTED_CLAIM: 2
- MISSED_LIMITATION: 1
- WRONG_INTENT: 1
- MISSING_EVIDENCE: 1

## Failures grouped by type

### WRONG_NUMBER

- BTX01: 연금저축 400 넣고 IRP도 넣으려는데 공제 한도 전체가 얼마죠?
- BTX02: 세금공제 받을 때 pension savings랑 IRP 합산 cap 알려줘.
- BTX03: 연금계좌 두 개 공제최대랑 적용 세율까지 한 번에 정리해 주실래요?
- BTX04: IRP+연저축 세액 공제한도 얼마임? 내 절세액도 확정해줘.
- BTX05: 공제 한도와 공제율 차이를 같이 설명하되 모르는 개인 세액은 선을 그어줘.

### UNSUPPORTED_CLAIM

- BDB02: Defined Benefit vs 확정기여형의 운용 책임과 받는 돈 차이를 대조해 줘.
- BPR04: Solomon 단기 vs 중장기 vs 장기, 위험 label과 안정성 판단 한계까지 알려줘.

### MISSED_LIMITATION

- BTR03: 교원이 조기퇴직 보상금을 받는데 명예퇴직수당 규칙을 그대로 써도 돼?

### WRONG_INTENT

- BPR04: Solomon 단기 vs 중장기 vs 장기, 위험 label과 안정성 판단 한계까지 알려줘.

### MISSING_EVIDENCE

- BPR04: Solomon 단기 vs 중장기 vs 장기, 위험 label과 안정성 판단 한계까지 알려줘.
