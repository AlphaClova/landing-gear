# 인출 의사결정 프론트엔드 계약

## 1. 계약 목적

이 계약은 담당 B의 Rule Engine 계산 결과와 담당 A의 프론트 API 응답을 담당 C의 인출 의사결정 화면에서 동일한 View Model로 소비하기 위한 경계다. 공식 평가 API의 기존 top-level 필드와 `ChatResponse`, `PensionApiClient`는 변경하지 않는다. 이 계약은 화면 전용 변환 결과이며 계산 규칙 자체가 아니다.

## 2. 담당 범위

- 담당 A(API): `/v1/chat` 운송 계약, 오류·timeout 표현, Rule Engine 결과 전달 및 화면 계약으로 변환 가능한 식별자를 제공한다.
- 담당 B(Rule Engine): 세금·연금 계산, 적용 규칙, 계산 기준 버전, 근거·claim·tool result 연결 정보를 생성한다.
- 담당 C(프론트엔드): 전달받은 값을 `WithdrawalDecisionViewModel`로 변환하고 basis에 맞게 표시한다. 세금, 연금, 건강보험료 또는 금융소득 과세를 계산하거나 추론하지 않는다.

## 3. 요청 입력 필드

`WithdrawalDecisionInput`의 모든 금액·나이·비율 입력은 nullable이다. 정보가 없으면 기본값을 만들지 않는다.

| 필드 | 의미 |
| --- | --- |
| `retirementBenefitAmount` | 퇴직급여 금액 |
| `currentAge` | 현재 나이 |
| `pensionStartAge` | 연금 수령 시작 나이 |
| `desiredMonthlyIncome` | 희망 월 수령액 |
| `expectedReturnRate` | 예상 수익률 |
| `otherPensionIncome` | 다른 연금소득 |
| `otherFinancialIncome` | 다른 금융소득 |
| `healthInsuranceStatus` | 직장·지역·피부양자·미확인 건강보험 자격 |

`healthInsuranceStatus: "unknown"`은 사용자가 상태를 모르는 경우다. 다른 nullable 필드는 미제공 상태를 `null`로 전달한다.

## 4. 응답 필드

화면은 `WithdrawalDecisionViewModel`을 사용한다.

- `status`: `complete | needs_input | limited | error`
- `scenarioTitle`: 비교 시나리오 제목
- `input`, `missingFields`: 전달된 입력과 부족한 입력
- `summary`, `limitations`: 현재 가능한 답변과 제한
- `options`: `lump_sum`, `pension_10y`, `pension_21y_plus` 결과
- `assumptions`: 사용자·규칙·시나리오 가정
- `evidence`: 계산 결과와 연결되는 근거
- `baselineOptionId`: 차액 계산 기준 옵션
- `highlightedOptionId`, `highlightReason`: 현재 조건에서 비교상 강조할 옵션과 이유
- `canCompare`, `canRetry`: 비교·재시도 가능 여부

`highlightedOptionId`는 보편적인 추천이 아니다. 입력이 부족하거나 단정할 수 없으면 `null`이며, 값이 있으면 `highlightReason`도 함께 제공해야 한다.

## 5. 계산 basis

- `exact`: Rule Engine이 확정 조건과 적용 규칙으로 계산한 값
- `scenario`: 수익률·기간 등 명시된 가정을 사용한 예상값
- `conditional`: 추가 조건에 따라 발생 여부나 금액이 달라지는 영향
- `unavailable`: 현재 입력 또는 규칙으로 계산할 수 없는 값

프론트는 basis를 재판정하지 않고 서버 또는 변환 계층의 값을 그대로 표시한다.

## 6. null 처리 원칙

- 계산할 수 없는 금액은 `0`이 아니라 `amount: null`이다.
- `basis: unavailable`인 금액은 원화 숫자 대신 계산 불가 설명을 표시한다.
- `conditional`인데 금액을 산출할 수 없으면 `amount: null`과 조건 설명을 함께 전달한다.
- `differenceFromBaseline: null`은 기준 옵션이 없거나 차액을 비교할 수 없다는 뜻이다.
- 선택적 문서 정보가 확인되지 않으면 `validFrom`, `validTo`는 `null` 또는 생략하고, URL을 확인할 수 없으면 `url`을 생략한다.
- 프론트는 누락값을 임의의 금액, 기관, 문서, 날짜 또는 페이지 번호로 채우지 않는다.

## 7. 건강보험료 처리 원칙

건강보험료 영향은 `healthInsuranceImpact`로만 표현한다. Rule Engine이 확정할 수 있을 때만 `basis: exact`와 `status: confirmed`를 사용할 수 있다. 자격·다른 소득 등 추가 조건이 필요하면 `conditional/possible`, 계산 규칙 또는 입력이 부족하면 `unavailable/unavailable`을 사용하고 `amount`는 `null`로 둔다. 프론트는 건강보험료를 계산하지 않는다.

## 8. 금융소득 과세 처리 원칙

금융소득 과세 영향은 `financialIncomeTaxImpact`로 표현한다. 다른 금융소득 등 필요한 조건이 없으면 과세 여부를 임의로 판단하지 않는다. 확정할 수 없는 경우 `conditional` 또는 `unavailable`, `amount: null`, 조건을 설명하는 `description`을 반환한다.

## 9. 확정 세후금액과 예상 현금흐름 분리

`confirmedAfterTaxAmount`는 확정 조건으로 계산된 세후금액이고, `estimatedTotalCashflow`와 `estimatedMonthlyCashflow`는 기간·수익률 등의 가정을 포함할 수 있는 예상 현금흐름이다. 같은 카드에 표시하더라도 basis 레이블을 분리하며 두 값을 합치거나 하나를 다른 하나처럼 표현하지 않는다.

## 10. 근거 ID와 계산 결과 연결

각 `WithdrawalOptionResult.evidenceIds`는 `WithdrawalDecisionViewModel.evidence[].id`를 참조한다. 존재하지 않는 ID를 참조하면 변환 오류로 처리한다. 하나의 근거는 여러 옵션에 연결될 수 있고, 옵션은 여러 근거를 참조할 수 있다.

## 11. Claim–Evidence 연결

`WithdrawalEvidence.claimIds`는 해당 근거가 뒷받침하는 계산·설명 claim 식별자다. 담당 A/B가 claim 목록 또는 결과의 claim 참조 위치를 합의해야 한다. 프론트는 claim 내용을 생성하지 않고, ID 연결을 이용해 해당 결과에서 근거 카드를 노출한다.

## 12. toolResultId 사용

`toolResultId`는 Rule Engine 또는 계산 도구의 원본 실행 결과를 추적하기 위한 선택적 식별자다. 화면의 금액 계산이나 재현을 위해 프론트가 해석하지 않는다. 로그·상세 근거 조회·장애 분석에 사용할 형식과 보존 범위는 담당 A/B가 결정한다.

## 13. needs_input 처리

`needs_input`은 현재 답할 수 있는 내용, 계산에 부족한 조건, 사용자가 추가로 입력할 항목의 순서로 표시한다.

- `summary`: 현재 제공 가능한 일반 안내
- `limitations`: 정확한 비교가 불가능한 이유
- `missingFields`: 추가 입력이 필요한 필드
- `options: []`, `canCompare: false`
- 재요청이 아니라 입력 보완이 필요한 상태이므로 일반적으로 `canRetry: false`

## 14. limited 처리

`limited`는 일부 결과는 제공할 수 있지만 다른 영향은 단정할 수 없는 상태다. 제공 가능한 범위는 `summary`와 `options`에, 단정할 수 없는 범위는 `limitations` 및 각 영향의 `conditional/unavailable` basis에 표현한다. 제한된 항목을 0 또는 영향 없음으로 바꾸지 않는다.

## 15. 프론트 화면 표시 순서

1. 입력 조건
2. 비교 요약
3. 일시금, 10년 연금, 21년 이상 연금 비교
4. 확정 계산
5. 가정 기반 예상
6. 차이가 발생한 이유
7. 건강보험료와 금융소득 과세의 조건부 영향
8. 확인할 조건
9. 가정
10. 근거와 출처

## 16. mock client와 실제 API 교체 경계

`PensionApiClient.answer()`와 기존 `ChatResponse`는 운송 경계로 유지한다. mock과 실제 HTTP client는 동일한 공개 계약을 반환한다. 별도 어댑터가 `response.type`, Rule Engine payload 또는 `/v1/chat` 확장 데이터에서 `WithdrawalDecisionViewModel`을 생성한다. mock과 실제 API 모두 같은 어댑터 입력 형식을 사용해야 하며, UI는 client 종류를 알지 못한다. 이번 단계에서는 mock 금액이나 계산 결과를 추가하지 않는다.

## 17. A와 B의 합의가 필요한 항목

- [ ] 금액 단위가 원 단위인지
- [ ] 금액 반올림 규칙
- [ ] 세금 항목의 세부 분류
- [ ] 10년 연금의 수령 기간 기준
- [ ] 21년 이상 연금의 수령 기간 기준
- [ ] 비교 기준 옵션 결정 방식
- [ ] `differenceFromBaseline`의 부호 규칙
- [ ] `toolResultId` 형식
- [ ] 건강보험료 금액 반환 가능 여부
- [ ] 건강보험료가 조건부 설명만 가능한 경우의 응답 형식
- [ ] 금융소득 과세 영향의 반환 범위
- [ ] `evidenceId` 형식
- [ ] `claimId` 형식
- [ ] 오류 코드
- [ ] timeout 처리
- [ ] 계산 기준 버전 표시 방식
- [ ] 확정 계산과 시나리오 계산의 서버 구분 방식

## 18. 프론트 연결 전 A·B 확정 필요 항목

아래 항목은 아직 프론트에서 확정하거나 추정하지 않는다. 확정 전 HTTP 인출 결과는 명시적인 `limited` 경계로 처리한다.

- [ ] 최종 엔드포인트 (`VITE_API_BASE_URL` 뒤 `/answer` 사용 여부 포함)
- [ ] `AnswerRequest`를 사용하는 요청 스키마와 인출 입력 전달 방식
- [ ] 응답 discriminator 및 인출 결과 payload 위치
- [ ] 서버 timeout과 프론트 timeout의 책임 및 권장 시간
- [ ] HTTP 오류 본문 형식, 오류 코드, 재시도 가능 여부
- [ ] 계산 기준 버전 필드와 보존 기간
- [ ] evidence ID, claim ID, tool result ID의 형식과 참조 무결성
- [ ] 모든 금액의 단위, 반올림 규칙, `null`/필드 생략 정책

현재 프론트는 공개 `ChatResponse`, `AnswerRequest`, `PensionApiClient`를 변경하지 않는다. 확정되지 않은 인출 금액, 계산 기준, 근거 ID는 생성하거나 `0`으로 보정하지 않는다.
