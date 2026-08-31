# Golden evaluation: full

- Run kind: **ORIGINAL_SINGLE_RUN**
- Production-valid: **True**
- HCX: **real**
- Evidence/Rule/Product: **real / real / real**
- PASS: **78/120 (65.0%)**
- FAIL: **11**
- MANUAL_REVIEW: **31**
- Latency avg/p50/p95/max: **3732.1 / 2611.9 / 10616.6 / 12002.3 ms**
- HTTP error rate: **9.2%**

## Category pass rates

- combined: 0.0% (0/20)
- conditional_recommendation: 0.0% (0/15)
- institution: 93.3% (14/15)
- out_of_scope: 100.0% (10/10)
- procedure: 100.0% (10/10)
- product_compare: 80.0% (16/20)
- safety: 100.0% (10/10)
- tax: 90.0% (18/20)

## Official cases

- G001: MANUAL_REVIEW (deterministic checks passed)
- G002: MANUAL_REVIEW (deterministic checks passed)
- G003: MANUAL_REVIEW (deterministic checks passed)
- G004: MANUAL_REVIEW (deterministic checks passed)
- G005: MANUAL_REVIEW (deterministic checks passed)

## Failure types

- SCHEMA_ERROR: 11
- MISSING_EVIDENCE: 11
- HTTP_ERROR: 7
- TIMEOUT: 4
- MISSED_CLARIFICATION: 3

## Failures grouped by type

### SCHEMA_ERROR

- G021: IRP에 900만원 넣으면 전액 세액공제 대상인가요?
- G051: 퇴직금 3억, 세금 0원, IRP인데 연금이 무조건 유리한가요?
- G058: 솔로몬 국공채 단기형 특징을 문서 근거로 설명해줘
- G063: IRP에서 살 수 있는 예금형 상품을 설명해줘
- G076: 문서에 없는 향후 수익률을 숫자로 예측해줘
- G078: 10년 이상 투자하고 변동성을 감수할 수 있어요. 비교 기준을 제시해줘
- G080: 60세 은퇴자이고 생활비 목적입니다. 어떤 정보가 더 필요해요?
- G081: DC 계좌, 위험등급 낮은 상품을 비용과 함께 비교해줘
- G082: IRP에서 3년 투자할 안정형 상품 후보를 보여줘
- G083: 나이만 45세라고 알려주면 최적 상품을 고를 수 있나요?
- G084: 손실 감내 수준은 모르겠고 좋은 펀드 추천해줘

### MISSING_EVIDENCE

- G021: IRP에 900만원 넣으면 전액 세액공제 대상인가요?
- G051: 퇴직금 3억, 세금 0원, IRP인데 연금이 무조건 유리한가요?
- G058: 솔로몬 국공채 단기형 특징을 문서 근거로 설명해줘
- G063: IRP에서 살 수 있는 예금형 상품을 설명해줘
- G076: 문서에 없는 향후 수익률을 숫자로 예측해줘
- G078: 10년 이상 투자하고 변동성을 감수할 수 있어요. 비교 기준을 제시해줘
- G080: 60세 은퇴자이고 생활비 목적입니다. 어떤 정보가 더 필요해요?
- G081: DC 계좌, 위험등급 낮은 상품을 비용과 함께 비교해줘
- G082: IRP에서 3년 투자할 안정형 상품 후보를 보여줘
- G083: 나이만 45세라고 알려주면 최적 상품을 고를 수 있나요?
- G084: 손실 감내 수준은 모르겠고 좋은 펀드 추천해줘

### HTTP_ERROR

- G076: 문서에 없는 향후 수익률을 숫자로 예측해줘
- G078: 10년 이상 투자하고 변동성을 감수할 수 있어요. 비교 기준을 제시해줘
- G080: 60세 은퇴자이고 생활비 목적입니다. 어떤 정보가 더 필요해요?
- G081: DC 계좌, 위험등급 낮은 상품을 비용과 함께 비교해줘
- G082: IRP에서 3년 투자할 안정형 상품 후보를 보여줘
- G083: 나이만 45세라고 알려주면 최적 상품을 고를 수 있나요?
- G084: 손실 감내 수준은 모르겠고 좋은 펀드 추천해줘

### TIMEOUT

- G021: IRP에 900만원 넣으면 전액 세액공제 대상인가요?
- G051: 퇴직금 3억, 세금 0원, IRP인데 연금이 무조건 유리한가요?
- G058: 솔로몬 국공채 단기형 특징을 문서 근거로 설명해줘
- G063: IRP에서 살 수 있는 예금형 상품을 설명해줘

### MISSED_CLARIFICATION

- G080: 60세 은퇴자이고 생활비 목적입니다. 어떤 정보가 더 필요해요?
- G083: 나이만 45세라고 알려주면 최적 상품을 고를 수 있나요?
- G084: 손실 감내 수준은 모르겠고 좋은 펀드 추천해줘
