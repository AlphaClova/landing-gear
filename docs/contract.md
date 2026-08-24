# A-B-C 공통 계약 문서

`/v1/chat` 연동 관련 A(Agent·API)·B(검색/계산)·C(프론트) 3자 합의 사항.
필드명·타입·null 여부를 바꿀 때는 이 문서와 `docs/samples/`의 샘플 JSON을
먼저 수정하고 상대 담당 확인을 받은 뒤 `app/api/schemas.py`를 고친다
(구두 합의 금지 — `app/api/schemas.py` 상단 docstring과 동일 원칙).

## 1. 입력값 매핑 (A `profile` → B 계산 입력)

| A `ChatRequest.profile` 필드 | B 계산 입력 | 의미 |
| --- | --- | --- |
| `retirement_amount_won` | `retirement_amount` | 퇴직급여 총액(원) |
| `expected_tax_won` | `deferred_retirement_tax` | **연금 수령에 따른 감면(70%/60%/50%) 적용 전** 기준 퇴직소득세(원). B가 계산하는 결과값이 아니라 사용자가 입력/확인한 값이다. |

B는 위 `deferred_retirement_tax`를 기준으로 아래 감면율을 적용해 계산한다 (A는 이 로직을 갖지 않는다 — 문서 9장 Failsafe: LLM/A는 계산하지 않고 B의 결과만 사용).

| 수령 형태 | 적용 세율 |
| --- | --- |
| 일시금 | 100% |
| 연금 수령 1~10년차 | 70% |
| 연금 수령 11~20년차 | 60% |
| 연금 수령 21년 이상 | 50% |

## 2. `withdrawal_result` (`/v1/chat` 응답)

기존 `comparison`(`title/options/rows`)은 일반 상담용 범용 비교로 그대로 유지한다.
일시금 vs 연금수령 비교처럼 B의 전체 계산 결과(비교표 + 근거 + 적용 rule + 검증 결과)를
그대로 전달해야 하는 경우에는 `ChatResponse.withdrawal_result` 필드에 담는다.

```
withdrawal_result: WithdrawalComparisonResponse | null
```

`WithdrawalComparisonResponse` (`app/api/schemas.py`):

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `comparison` | `ComparisonResult` | 기존 `title/options/rows/note` 구조 재사용. `options`는 비교 대상 id(예: `lump_sum`, `pension`) |
| `evidence` | `Citation[]` | 계산 근거 문서 인용. 기존 `citations`와 동일한 `Citation` 타입 |
| `applied_rules` | `AppliedRule[]` | 실제 계산에 적용된 `rule_id` + B Rule Registry가 내부적으로 고른 `rule_version` |
| `claim_validation` | `ClaimValidation` | Verifier가 계산 결과 ↔ 근거 연결을 검증한 결과. `verified: bool`, `issues: string[]` |

C는 `withdrawal_result`가 `null`이 아닐 때만 전용 ViewModel Adapter로 렌더링하고,
`null`이면 기존 `comparison`(있는 경우) 또는 `message`만으로 일반 상담 화면을 그린다.

현재 상태: A는 위 타입과 Tool Protocol(`RuleEngine.calculate_withdrawal_comparison`)까지
정의하고 Mock 구현으로 파이프라인 종단까지 연결해 두었다 (`app/agent/tools.py`
`MockRuleEngine.calculate_withdrawal_comparison`). B가 실제 Rule Engine을 넘기면
`app/api/dependencies.py`의 `get_tool_router()`에서 주입만 교체하면 된다.

## 3. 오류 응답

`ErrorResponse` (및 `type="limitation"` 정상 응답 내 오류 성격 메시지)는 아래 두 필드를
A↔B 파이프라인 내부에서 항상 유지한다.

| 필드 | 대응 |
| --- | --- |
| `code` (B/C 논의에서 `error_type`으로 지칭) | `app/core/errors.py`의 `ErrorCode` enum 값 |
| `message` | 원인 설명 문자열 |

C는 `message`를 사용자 화면에 원문 그대로 노출하지 않고, `code` 기준으로 안전한
안내 문구로 변환해서 보여준다. A/B는 `message`에 내부 진단 정보(예외 원문 등)를
그대로 담아도 된다 — 최종 사용자 노출은 C 책임.

## 4. 샘플 JSON

- [`samples/chat_withdrawal_result.json`](samples/chat_withdrawal_result.json) — `withdrawal_result` 포함 정상 응답
- [`samples/chat_error.json`](samples/chat_error.json) — 오류 응답
