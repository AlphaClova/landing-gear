"""공통 계약 schema.

B(검색/계산)와 C(프론트)가 그대로 참조하는 파일이다. 필드명·타입·null 여부를
바꿀 때는 공통 계약 문서와 샘플 JSON을 먼저 수정하고 상대 담당의 확인을
받은 뒤 여기를 고친다 (구두 합의 금지).
"""

import json
from typing import Literal

from pydantic import BaseModel, Field

from app.core.errors import ErrorCode

# ---------------------------------------------------------------------------
# 요청
# ---------------------------------------------------------------------------


class UserProfile(BaseModel):
    """C가 화면 입력에서 전달하는 알려진 정보. 값이 없으면 필드를 생략(None)한다."""

    age: int | None = None
    retirement_amount_won: int | None = None  # B `retirement_amount`로 매핑
    expected_tax_won: int | None = None  # B `deferred_retirement_tax`로 매핑. 연금 수령 감면(70/60/50%) 적용 전 기준 퇴직소득세.
    plan_type: Literal["DB", "DC", "IRP"] | None = None
    extra: dict[str, str | int | float | bool] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    session_id: str
    question: str
    profile: UserProfile = Field(default_factory=UserProfile)


class AnswerRequest(BaseModel):
    """평가 서버가 호출하는 단발성 질의. 세션을 유지하지 않는다."""

    question_id: str
    question: str
    profile: UserProfile = Field(default_factory=UserProfile)


# ---------------------------------------------------------------------------
# 공통 구성요소
# ---------------------------------------------------------------------------


class RequiredSlot(BaseModel):
    name: str
    prompt: str
    reason: str | None = None


class Citation(BaseModel):
    id: str
    document_id: str
    page: int | None = None  # PDF/PPTX 등 페이지가 확정되는 문서만 채움. 없으면 null.
    section: str | None = None  # DOCX 등 page가 없을 때 document_id+id(evidence/chunk)+section으로 추적
    source: str
    excerpt: str
    url: str | None = None
    source_priority: int | None = None
    score: float | None = None


class ProductResult(BaseModel):
    """B `app/data/schemas/models.py`의 ProductResult와 1:1로 대응한다 (손실 없이 매핑)."""

    product_id: str
    product_name: str
    plan_types: list[str] | None = None
    category: str | None = None
    asset_type: str | None = None
    risk_level: int | None = None
    document_id: str
    page: int | None = None
    source: str
    source_priority: int
    plan_type_pages: dict[str, list[int]] = Field(default_factory=dict)
    category_page: int | None = None
    risk_page: int | None = None


class ComparisonRow(BaseModel):
    label: str
    values: dict[str, str] = Field(default_factory=dict)


class ComparisonResult(BaseModel):
    title: str
    options: list[str]
    rows: list[ComparisonRow] = Field(default_factory=list)
    note: str | None = None


class CalculationResult(BaseModel):
    rule_id: str
    rule_version: str | None = None  # B Rule Registry가 내부적으로 선택한 버전 (Agent는 지정하지 않음)
    label: str
    value: float
    unit: str
    rate: str | None = None
    formula: str | None = None


class AppliedRule(BaseModel):
    """계산에 실제 적용된 rule. B Rule Registry가 내부적으로 고른 rule_version을 그대로 기록한다."""

    rule_id: str
    rule_version: str | None = None


class WithdrawalScenario(BaseModel):
    """B `app/data/schemas/models.py`의 `ComparisonScenario`와 1:1로 대응한다."""

    scenario: Literal["lump_sum", "annuity_10_years", "annuity_21_plus_years"]
    tax_value: int
    applicable_rate: float
    difference_vs_lump_sum: int
    formula: str
    rule_id: str
    rule_version: str
    evidence_ids: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class WithdrawalTaxComparison(BaseModel):
    """B `ComparisonResult`(scenarios/result_type/unit)와 1:1로 대응한다. 상단 범용 `ComparisonResult`와는 다른 타입."""

    scenarios: list[WithdrawalScenario]
    result_type: Literal["exact"] = "exact"
    unit: Literal["KRW"] = "KRW"


class WithdrawalEvidenceItem(BaseModel):
    """B `evidence_builder.build_evidence_card()` 출력과 1:1로 대응한다."""

    evidence_id: str
    chunk_id: str
    document_id: str
    page: int | None = None
    section: str | None = None
    quote: str | None = None
    source_priority: int | None = None
    score: float


class ClaimValidationEntry(BaseModel):
    claim_id: str
    supported: bool
    reasons: list[str] = Field(default_factory=list)


class ClaimValidation(BaseModel):
    """B `evidence_builder.validate_claims()` 출력과 1:1로 대응한다."""

    validations: list[ClaimValidationEntry] = Field(default_factory=list)
    unsupported_claim_count: int = 0
    validated_claim_count: int = 0
    unsupported_claim_rate: float = 0.0


class WithdrawalComparisonResponse(BaseModel):
    """일시금 vs 연금수령 비교 전용 응답. `/v1/chat`의 `withdrawal_result`에 원형 그대로 담긴다.

    필드 shape은 B의 실제 production 반환값(`WithdrawalComparisonResult`)과 1:1로
    맞춰뒀다 — B가 새 필드를 추가하지 않는 한 변환 손실이 없다.
    """

    comparison: WithdrawalTaxComparison
    evidence: list[WithdrawalEvidenceItem] = Field(default_factory=list)
    applied_rules: list[AppliedRule] = Field(default_factory=list)
    claim_validation: ClaimValidation


class ToolCallTrace(BaseModel):
    tool_name: str
    args: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    status: Literal["ok", "error", "timeout"]
    duration_ms: float


class ThinkTrace(BaseModel):
    intent: str
    route: Literal["fast_path", "deep_path"]
    route_confidence: float
    fallback_reason: str | None = None
    tool_calls: list[ToolCallTrace] = Field(default_factory=list)
    hcx_invoked: bool = False
    hcx_attempts: int = 0
    hcx_success: bool = False
    hcx_first_pass: bool = False
    hcx_regenerated: bool = False
    deterministic_repaired: bool = False
    hcx_timeout_count: int = 0
    degraded: bool = False
    degraded_reason: str | None = None
    degraded_fallback: str | None = None
    fallback_used: bool = False
    hcx_fallback_reason: str | None = None
    hcx_audit: list[dict[str, object]] = Field(default_factory=list)
    prompt_metrics: dict[str, int] = Field(default_factory=dict)
    rule_results: list[dict[str, object]] = Field(default_factory=list)
    product_facts: list[dict[str, object]] = Field(default_factory=list)
    claim_plan: list[dict[str, object]] = Field(default_factory=list)
    recommendation_constraints: list[dict[str, object]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 내부 응답 (파이프라인 내부 표준형) — Verifier가 최종 생성
# ---------------------------------------------------------------------------


class InternalAnswer(BaseModel):
    type: Literal["clarification", "result", "limitation", "error"]
    message: str
    request_id: str
    session_id: str | None = None
    required_slots: list[RequiredSlot] = Field(default_factory=list)
    comparison: ComparisonResult | None = None
    withdrawal_result: WithdrawalComparisonResponse | None = None
    calculation_results: list[CalculationResult] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = 0.0
    clarification: str | None = None
    trace: ThinkTrace


# ---------------------------------------------------------------------------
# /v1/chat 응답 (C가 소비)
# ---------------------------------------------------------------------------


class ChatResponse(BaseModel):
    type: Literal["clarification", "result", "limitation", "error"]
    message: str
    required_slots: list[RequiredSlot] = Field(default_factory=list)
    comparison: ComparisonResult | None = None
    withdrawal_result: WithdrawalComparisonResponse | None = None
    citations: list[Citation] = Field(default_factory=list)
    request_id: str


class ErrorResponse(BaseModel):
    type: Literal["error"] = "error"
    code: ErrorCode
    message: str
    request_id: str


# ---------------------------------------------------------------------------
# /answer 평가 응답 — EVAL_SCHEMA_MODE=strict일 때 공식 5필드로 직렬화
# ---------------------------------------------------------------------------


class EvalResponse(BaseModel):
    question_id: str
    question: str
    retrieved_context: list[str]
    think_trace: str
    answer: str


def to_chat_response(internal: InternalAnswer) -> ChatResponse:
    return ChatResponse(
        type=internal.type,
        message=internal.message,
        required_slots=internal.required_slots,
        comparison=internal.comparison,
        withdrawal_result=internal.withdrawal_result,
        citations=internal.citations,
        request_id=internal.request_id,
    )


def to_eval_response(internal: InternalAnswer, question_id: str, question: str) -> EvalResponse:
    """EvalResponseSerializer: InternalAnswer -> 공식 5필드.

    정보가 부족해도 역질문만 반환하지 않고
    '현재 답 가능한 내용 → 한계 → 필요한 조건' 순서로 answer를 구성한다.
    """
    if internal.type == "clarification":
        parts = [internal.message]
        if internal.required_slots:
            needed = ", ".join(s.prompt for s in internal.required_slots)
            parts.append(f"[한계] 아래 정보가 없어 확정적으로 답변할 수 없습니다.")
            parts.append(f"[필요한 조건] {needed}")
        answer = "\n".join(parts)
    else:
        answer = internal.message

    tool_names = list(dict.fromkeys(call.tool_name for call in internal.trace.tool_calls))
    public_trace = {
        "intent": internal.trace.intent,
        "route": internal.trace.route,
        "retrieval": "completed" if "retrieve_evidence" in tool_names else "not_used",
        "tools": tool_names,
        "composition": "grounded",
        "verification": "repaired" if internal.trace.deterministic_repaired else "passed",
        "hcx_invoked": internal.trace.hcx_invoked,
        "hcx_success": internal.trace.hcx_success,
        "degraded": internal.trace.degraded,
        "fallback_used": internal.trace.fallback_used,
    }
    return EvalResponse(
        question_id=question_id,
        question=question,
        retrieved_context=[c.excerpt for c in internal.citations],
        think_trace=json.dumps(public_trace, ensure_ascii=False),
        answer=answer,
    )
