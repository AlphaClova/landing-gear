"""B(검색/계산) 담당과의 Tool 계약.

여기 정의된 Protocol이 A<->B 핸드셰이크의 실제 인터페이스다. B가
`retrieve_evidence`, `calculate`, `query_products`를 구현해 Provider로
주입하면 되고, 그 전까지는 Mock*Provider로 파이프라인을 끝까지 돌린다.
LLM은 계산하지 않고 이 Tool의 결과만 사용한다 (문서 9장 Failsafe).
"""

import re
import time
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

from app.api.schemas import (
    AppliedRule,
    CalculationResult,
    Citation,
    ClaimValidation,
    ClaimValidationEntry,
    ToolCallTrace,
    WithdrawalComparisonResponse,
    WithdrawalEvidenceItem,
    WithdrawalScenario,
    WithdrawalTaxComparison,
)
from app.core.errors import ErrorCode, ToolError
from app.core.logging import get_logger
from app.core.query_normalization import ALIASES, ACCOUNT_TERMINATION_TAX, EARLY_WITHDRAWAL_TAX, RETIREMENT_LUMP_SUM_TAX, RETIREMENT_PENSION_RECEIPT_TAX, has_alias, is_db_dc_question, is_teacher_retirement_domain, procedure_type, tax_intent, tax_source_types
from app.tools.withdrawal_comparison import calculate_withdrawal_comparison as b_calculate_withdrawal_comparison
from app.tools.product_query import query_products as b_query_products
from app.tools.retriever import retrieve_evidence as b_retrieve_evidence
from app.tools.rule_engine import RoundingPolicyUndefinedError, calc_retirement_lump_sum_tax

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# B가 구현할 Provider 인터페이스
# ---------------------------------------------------------------------------


class EvidenceProvider(Protocol):
    def retrieve_evidence(self, query: str, *, topic: str | None, top_k: int) -> list[Citation]: ...


class RuleEngine(Protocol):
    def calculate(self, rule_id: str, params: dict[str, float | int | str]) -> CalculationResult: ...

    # B 내부 WithdrawalComparisonResult(또는 동등 dict) 반환. A는 그대로 받지 않고
    # to_withdrawal_comparison_response()로 변환한다 (B의 내부 결과 타입은 A-facing 계약이 아님).
    def calculate_withdrawal_comparison(
        self, *, retirement_amount: int, deferred_retirement_tax: int
    ) -> Any: ...


class ProductCatalog(Protocol):
    def query_products(self, *, plan_type: str | None, category: str | None) -> list[dict[str, Any]]: ...


# ---------------------------------------------------------------------------
# Tool 인자 schema — B와 공유. 잘못된 인자는 여기서 차단한다.
# ---------------------------------------------------------------------------


class RetrieveEvidenceArgs(BaseModel):
    query: str
    topic: str | None = None
    top_k: int = 5


class CalculateArgs(BaseModel):
    rule_id: str
    params: dict[str, float | int | str] = {}


class WithdrawalComparisonArgs(BaseModel):
    retirement_amount: int
    deferred_retirement_tax: int


class QueryProductsArgs(BaseModel):
    plan_type: str | None = None
    category: str | None = None


def to_withdrawal_comparison_response(raw: object) -> WithdrawalComparisonResponse:
    """B의 WithdrawalComparisonResult(dataclass 또는 dict) -> A `WithdrawalComparisonResponse`.

    필드 shape이 B 산출값과 1:1이므로 이름 변환 없이 그대로 파싱한다.
    """
    if isinstance(raw, WithdrawalComparisonResponse):
        return raw
    if is_dataclass(raw) and not isinstance(raw, type):
        raw = asdict(raw)
    return WithdrawalComparisonResponse.model_validate(raw)


# ---------------------------------------------------------------------------
# Mock Provider — B의 실제 구현이 들어오기 전까지만 사용. 최종 배포 전 교체.
# ---------------------------------------------------------------------------


class MockEvidenceProvider:
    def retrieve_evidence(self, query: str, *, topic: str | None = None, top_k: int = 5) -> list[Citation]:
        return [
            Citation(
                id="mock-evidence-1",
                document_id="mock-doc",
                page=None,
                section=None,
                source="mock://B팀-근거자료-미연결",
                excerpt=f"[MOCK] '{query}'에 대한 근거 자료는 B팀 retrieve_evidence() 연결 후 제공됩니다.",
            )
        ]


class MockRuleEngine:
    def calculate(self, rule_id: str, params: dict[str, float | int | str]) -> CalculationResult:
        return CalculationResult(
            rule_id=rule_id,
            rule_version=None,
            label=f"[MOCK] {rule_id}",
            value=0.0,
            unit="원",
            formula="B팀 Rule Engine 연결 전 mock 값입니다.",
        )

    def calculate_withdrawal_comparison(
        self, *, retirement_amount: int, deferred_retirement_tax: int
    ) -> WithdrawalComparisonResponse:
        applied_rule = AppliedRule(rule_id="RETIRE_TAX_RATE_BY_YEAR", rule_version="mock")
        scenarios = [
            WithdrawalScenario(
                scenario="lump_sum",
                tax_value=deferred_retirement_tax,
                applicable_rate=1.0,
                difference_vs_lump_sum=0,
                formula=f"{deferred_retirement_tax} * 1.00",
                rule_id=applied_rule.rule_id,
                rule_version=applied_rule.rule_version,
                warnings=["B팀 Rule Engine 연결 전 mock 값입니다."],
            ),
            WithdrawalScenario(
                scenario="annuity_10_years",
                tax_value=int(deferred_retirement_tax * 0.7),
                applicable_rate=0.7,
                difference_vs_lump_sum=int(deferred_retirement_tax * 0.3),
                formula=f"{deferred_retirement_tax} * 0.70",
                rule_id=applied_rule.rule_id,
                rule_version=applied_rule.rule_version,
                warnings=["B팀 Rule Engine 연결 전 mock 값입니다."],
            ),
            WithdrawalScenario(
                scenario="annuity_21_plus_years",
                tax_value=int(deferred_retirement_tax * 0.5),
                applicable_rate=0.5,
                difference_vs_lump_sum=int(deferred_retirement_tax * 0.5),
                formula=f"{deferred_retirement_tax} * 0.50",
                rule_id=applied_rule.rule_id,
                rule_version=applied_rule.rule_version,
                warnings=["B팀 Rule Engine 연결 전 mock 값입니다."],
            ),
        ]
        return WithdrawalComparisonResponse(
            comparison=WithdrawalTaxComparison(scenarios=scenarios),
            evidence=[],
            applied_rules=[AppliedRule(rule_id=applied_rule.rule_id, rule_version=applied_rule.rule_version)] * 3,
            claim_validation=ClaimValidation(
                validations=[
                    ClaimValidationEntry(claim_id=f"mock-{s.scenario}", supported=False, reasons=["mock_no_evidence"])
                    for s in scenarios
                ],
                unsupported_claim_count=len(scenarios),
                validated_claim_count=len(scenarios),
                unsupported_claim_rate=1.0,
            ),
        )


class MockProductCatalog:
    def query_products(self, *, plan_type: str | None = None, category: str | None = None) -> list[dict[str, str]]:
        return []


# ---------------------------------------------------------------------------
# B RuleEngine adapter — A rule IDs를 기존 B deterministic 함수에 연결한다.
# ---------------------------------------------------------------------------


class BRuleEngine:
    def calculate(self, rule_id: str, params: dict[str, float | int | str]) -> CalculationResult:
        if rule_id != "retirement_income_tax":
            raise ValueError(f"unsupported production rule_id: {rule_id}")
        raw = calc_retirement_lump_sum_tax(params.get("expected_tax_won"))  # type: ignore[arg-type]
        return CalculationResult(
            rule_id=raw.rule_id,
            rule_version=raw.rule_version,
            label="예상 퇴직소득세",
            value=raw.value,  # type: ignore[arg-type]
            unit="원",
            rate=str(raw.rate) if raw.rate is not None else None,
            formula=raw.formula,
        )

    def calculate_withdrawal_comparison(
        self, *, retirement_amount: int, deferred_retirement_tax: int
    ) -> Any:
        return b_calculate_withdrawal_comparison(retirement_amount, deferred_retirement_tax)


class BEvidenceProvider:
    _TOPICS = {
        "제도": "pension_system",
        "세제": "withdrawal_tax",
        "종합": "withdrawal_tax",
        "상품": "product",
        "절차": "withdrawal_tax",
    }

    def retrieve_evidence(self, query: str, *, topic: str | None = None, top_k: int = 5) -> list[Citation]:
        results = b_retrieve_evidence(query, self._TOPICS.get(topic), top_k)
        return [
            Citation(
                id=item.evidence_id,
                document_id=item.document_id,
                page=item.page,
                section=item.section,
                source=item.source,
                excerpt=item.excerpt,
                source_priority=item.source_priority,
                score=item.score,
            )
            for item in results
        ]


class BProductCatalog:
    _RISK_LABELS = {
        1: "매우 높은 위험",
        2: "높은 위험",
        3: "다소 높은 위험",
        4: "보통 위험",
        5: "낮은 위험",
        6: "매우 낮은 위험",
    }

    def query_products(self, *, plan_type: str | None = None, category: str | None = None) -> list[dict[str, Any]]:
        products = []
        for item in b_query_products(plan_type, category):
            row = asdict(item)
            row["risk_label"] = self._RISK_LABELS.get(item.risk_level)
            products.append(row)
        return products


# ---------------------------------------------------------------------------
# ToolRouter — intent별 허용 도구 선택 + 인자 검증 + 실행
# ---------------------------------------------------------------------------

ALLOWED_TOOLS_BY_INTENT: dict[str, tuple[str, ...]] = {
    "제도": ("retrieve_evidence",),
    "세제": ("retrieve_evidence", "calculate"),
    "종합": ("retrieve_evidence", "calculate_withdrawal_comparison", "query_products"),
    "절차": ("retrieve_evidence",),
    "상품": ("retrieve_evidence", "query_products"),
    "범위 밖": (),
}

# "종합" intent에서 calculate 대신 이 rule_id일 때만 calculate_withdrawal_comparison을 호출한다.
_WITHDRAWAL_COMPARISON_RULE_ID = "lump_sum_vs_pension"


@dataclass
class ToolResult:
    evidence: list[Citation] = field(default_factory=list)
    calculations: list[CalculationResult] = field(default_factory=list)
    withdrawal_result: WithdrawalComparisonResponse | None = None
    products: list[dict[str, Any]] = field(default_factory=list)
    traces: list[ToolCallTrace] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    input_slots: dict[str, object] = field(default_factory=dict)
    tax_intent: str | None = None
    tax_source_types: tuple[str, ...] = ()
    procedure_type: str | None = None
    recommendation_constraints: list[dict[str, object]] = field(default_factory=list)
    product_resolutions: list[dict[str, str]] = field(default_factory=list)


class ToolRouter:
    def __init__(
        self,
        evidence_provider: EvidenceProvider | None = None,
        rule_engine: RuleEngine | None = None,
        product_catalog: ProductCatalog | None = None,
    ) -> None:
        self._evidence = evidence_provider or MockEvidenceProvider()
        self._rules = rule_engine or MockRuleEngine()
        self._products = product_catalog or MockProductCatalog()

    def provider_status(self) -> dict[str, str]:
        """Return provider classes without exposing credentials or configuration values."""
        return {
            "EVIDENCE_PROVIDER": "mock" if isinstance(self._evidence, MockEvidenceProvider) else "real",
            "RULE_PROVIDER": "mock" if type(self._rules) is MockRuleEngine else "real",
            "PRODUCT_PROVIDER": "mock" if isinstance(self._products, MockProductCatalog) else "real",
        }

    def run(
        self,
        intent: str,
        slots: dict[str, object],
        *,
        question: str,
        rule_id: str | None = None,
    ) -> ToolResult:
        allowed = ALLOWED_TOOLS_BY_INTENT.get(intent, ())
        # Preserve the user's institution-comparison intent.  In Korean,
        # "정해지는" contains the character sequence "해지"; treating that as
        # an account-termination request corrupts the repair contract.
        semantic_procedure = None if is_db_dc_question(question) else procedure_type(question)
        semantic_tax = tax_intent(question)
        compact_question = question.replace(" ", "")
        if (
            ("연말정산" in question and any(x in question for x in ("인정", "상한", "한도")))
            or (has_alias(question, "irp") and "넣" in question and "세금" in question and "줄" in question and "연금수령" not in compact_question)
        ):
            semantic_tax = "TAX_CREDIT"
        result = ToolResult(input_slots=dict(slots), tax_intent=semantic_tax, tax_source_types=tax_source_types(question), procedure_type=semantic_procedure)

        if "retrieve_evidence" in allowed:
            queries = self._evidence_queries(question, intent, result)
            seen: set[str] = set()
            for query, topic in queries:
                evidence, trace = self._call_retrieve_evidence(query, topic)
                result.traces.append(trace)
                for item in evidence:
                    if item.id not in seen and (is_teacher_retirement_domain(question) or item.document_id != "doc26"):
                        result.evidence.append(item)
                        seen.add(item.id)

        if "calculate" in allowed and rule_id and slots.get("expected_tax_won") is not None:
            calc, trace = self._call_calculate(rule_id, slots)
            result.calculations.append(calc)
            result.traces.append(trace)

        if (
            "calculate_withdrawal_comparison" in allowed
            and rule_id == _WITHDRAWAL_COMPARISON_RULE_ID
            and slots.get("expected_tax_won") is not None
        ):
            try:
                result.withdrawal_result, trace = self._call_calculate_withdrawal_comparison(slots)
            except ToolError as exc:
                if not isinstance(exc.__cause__, RoundingPolicyUndefinedError):
                    raise
                trace = ToolCallTrace(
                    tool_name="calculate_withdrawal_comparison",
                    args={"rule_id": _WITHDRAWAL_COMPARISON_RULE_ID},
                    status="error",
                    duration_ms=0.0,
                )
                result.limitations.append(
                    "[한계] Rule Engine에 문서화된 원 단위 반올림 정책이 없어 이 입력값의 연금수령 세액을 계산할 수 없습니다."
                )
            result.traces.append(trace)
            if result.withdrawal_result is not None:
                result.calculations.extend(self._withdrawal_calculations(result.withdrawal_result))
                result.evidence.extend(self._withdrawal_citations(result.withdrawal_result))

        needs_catalog = "예금" not in question and (
            has_alias(question, "product_family")
            or ("위험등급" in question and re.search(r"[1-6]\s*등급", question) is not None)
            or any(marker in question for marker in ("펀드", "채권", "상품 목록", "상품을 보여", "상품 후보", "상품 비교", "상품 선택", "추천", "골라"))
        )
        recommendation_needs_plan = any(marker in question for marker in ("상품 선택", "상품 추천", "추천", "골라")) and not slots.get("plan_type")
        if "query_products" in allowed and needs_catalog and not recommendation_needs_plan:
            products, trace, resolutions = self._call_query_products(slots, question)
            result.products = products
            result.product_resolutions = resolutions
            result.traces.append(trace)
            result.evidence.extend(self._product_citations(products))

        recommendation_or_compare = any(marker in question for marker in ("후보", "추천", "골라", "상품 선택", "상품 비교", "상품만", "상품을", "보여"))
        if recommendation_or_compare:
            if slots.get("plan_type"):
                result.recommendation_constraints.append({
                    "constraint": "account_type", "value": slots["plan_type"], "kind": "hard",
                    "applied": bool(result.products), "support": "product_fact.plan_types",
                    "reason": "filtered by supported account field" if result.products else "no matching products",
                })
            if slots.get("risk_tolerance") == "stable":
                result.recommendation_constraints.append({
                    "constraint": "risk_preference", "value": "stable", "kind": "soft",
                    "applied": bool(result.products), "support": "product_fact.risk_level>=5",
                    "reason": "mapped to supported risk scale",
                })
            requested_grade = re.search(r"([1-6])\s*등급", question)
            if requested_grade:
                grade = int(requested_grade.group(1))
                result.recommendation_constraints.append({
                    "constraint": "risk_grade", "value": grade, "kind": "hard",
                    "applied": bool(result.products) and all(item.get("risk_level") == grade for item in result.products),
                    "support": "product_fact.risk_level", "reason": "filtered by supported risk field",
                })
            horizon_label = slots.get("investment_horizon_label")
            if horizon_label:
                result.recommendation_constraints.append({
                    "constraint": "investment_horizon", "value": horizon_label, "kind": "soft",
                    "applied": False, "support": None, "reason": "no supported horizon suitability field",
                })
            if slots.get("principal_guarantee_required"):
                result.recommendation_constraints.append({
                    "constraint": "principal_guarantee", "value": True, "kind": "hard",
                    "applied": False, "support": None, "reason": "no supported principal guarantee field",
                })
            if slots.get("fee_ceiling_percent") is not None:
                result.recommendation_constraints.append({
                    "constraint": "fee_ceiling_percent", "value": slots["fee_ceiling_percent"], "kind": "hard",
                    "applied": False, "support": None, "reason": "no normalized comparable fee field",
                })

        distinctive = [
            item for item in result.recommendation_constraints
            if item.get("constraint") not in {"account_type"}
        ]
        unsupported_hard = any(
            item.get("kind") == "hard" and not item.get("applied")
            for item in result.recommendation_constraints
        )
        cannot_narrow = bool(distinctive) and not any(item.get("applied") for item in distinctive)
        catalog_dump = not distinctive and len(result.products) > 8
        if (unsupported_hard or cannot_narrow or catalog_dump) and result.products:
            result.products = []
            result.evidence = [item for item in result.evidence if not str(item.id).startswith("product-")]
        elif result.products and not has_alias(question, "product_family"):
            kept_ids = {str(item.get("product_id")) for item in result.products[:5]}
            result.products = result.products[:5]
            result.evidence = [
                item for item in result.evidence
                if not str(item.id).startswith("product-") or str(item.id) in {f"product-{pid}" for pid in kept_ids}
            ]

        return result

    @staticmethod
    def _evidence_queries(question: str, intent: str, result: ToolResult) -> list[tuple[str, str]]:
        queries = [(question, intent)]
        if has_alias(question, "db") or has_alias(question, "dc"):
            queries.append((f"{question} 확정급여형 확정기여형 운용 주체 최종 퇴직급여", "제도"))
        if is_db_dc_question(question):
            # A short canonical retrieval query reliably locates the supplied
            # DB/DC definition document without changing B's relevance policy.
            queries.append(("DB DC 회사 근로자 운용 퇴직금", "제도"))
        if result.tax_intent == "TAX_CREDIT":
            queries.append(("연금저축 IRP 세액공제 납입한도 합산 600만원 900만원", "세제"))
        if result.tax_intent == RETIREMENT_PENSION_RECEIPT_TAX:
            queries.append((f"{question} 실제수령연차 이연퇴직소득세 70% 60% 50%", "세제"))
        if result.tax_intent == RETIREMENT_LUMP_SUM_TAX:
            queries.append(("퇴직금 일시금 퇴직소득세 100% 즉시 납부", "세제"))
        if result.tax_intent == EARLY_WITHDRAWAL_TAX:
            queries.append((f"{question} IRP 중도인출 해지 과세 사유", "세제"))
        if result.tax_intent == ACCOUNT_TERMINATION_TAX:
            queries.append((f"{question} IRP 해지 과세 인출 재원", "세제"))
        if any(marker in question for marker in ("근무", "근로시간", "가입 대상", "대상인가요", "대상인가")):
            queries.append(("퇴직연금 가입 대상 근로시간 계속근로기간", "제도"))
        if result.tax_source_types:
            queries.append((f"{question} 연금계좌 재원별 인출 과세 퇴직금 운용수익", "세제"))
        if result.procedure_type == "ACCOUNT_TERMINATION":
            queries.append((f"{question} DB DC 계약 종료 해지", "절차"))
        elif result.procedure_type == "ACCOUNT_OPENING":
            queries.append((f"{question} 신규 계좌 개설 필요서류", "절차"))
        elif result.procedure_type == "ACCOUNT_TRANSFER" or (has_alias(question, "dc") and "연금저축" in question):
            queries.append((f"{question} DC 퇴직금 IRP 수령 후 연금저축 계약이전", "절차"))
        elif result.procedure_type == "EARLY_WITHDRAWAL":
            queries.append((f"{question} IRP 중도인출 해지 과세 수령계좌", "절차"))
        return queries

    def _call_retrieve_evidence(self, question: str, topic: str) -> tuple[list[Citation], ToolCallTrace]:
        try:
            args = RetrieveEvidenceArgs(query=question, topic=topic)
        except ValidationError as exc:
            raise ToolError("retrieve_evidence", str(exc), code=ErrorCode.TOOL_ARGUMENT_ERROR) from exc

        start = time.monotonic()
        try:
            evidence = self._evidence.retrieve_evidence(args.query, topic=args.topic, top_k=args.top_k)
            status = "ok"
        except Exception as exc:  # noqa: BLE001 - B의 구현 예외를 표준 오류로 전환
            raise ToolError("retrieve_evidence", str(exc)) from exc
        duration_ms = (time.monotonic() - start) * 1000
        trace = ToolCallTrace(tool_name="retrieve_evidence", args=args.model_dump(), status=status, duration_ms=duration_ms)
        return evidence, trace

    def _call_calculate(self, rule_id: str, slots: dict[str, object]) -> tuple[CalculationResult, ToolCallTrace]:
        try:
            args = CalculateArgs(rule_id=rule_id, params=slots)  # type: ignore[arg-type]
        except ValidationError as exc:
            raise ToolError("calculate", str(exc), code=ErrorCode.TOOL_ARGUMENT_ERROR) from exc

        start = time.monotonic()
        try:
            calc = self._rules.calculate(args.rule_id, args.params)
            status = "ok"
        except Exception as exc:  # noqa: BLE001
            raise ToolError("calculate", str(exc)) from exc
        duration_ms = (time.monotonic() - start) * 1000
        trace = ToolCallTrace(tool_name="calculate", args={"rule_id": rule_id}, status=status, duration_ms=duration_ms)
        return calc, trace

    def _call_calculate_withdrawal_comparison(
        self, slots: dict[str, object]
    ) -> tuple[WithdrawalComparisonResponse, ToolCallTrace]:
        try:
            args = WithdrawalComparisonArgs(
                retirement_amount=slots.get("retirement_amount_won", 0),  # type: ignore[arg-type]
                deferred_retirement_tax=slots.get("expected_tax_won"),  # type: ignore[arg-type]
            )
        except ValidationError as exc:
            raise ToolError(
                "calculate_withdrawal_comparison", str(exc), code=ErrorCode.TOOL_ARGUMENT_ERROR
            ) from exc

        start = time.monotonic()
        try:
            raw = self._rules.calculate_withdrawal_comparison(
                retirement_amount=args.retirement_amount,
                deferred_retirement_tax=args.deferred_retirement_tax,
            )
            result = to_withdrawal_comparison_response(raw)
            status = "ok"
        except Exception as exc:  # noqa: BLE001
            raise ToolError("calculate_withdrawal_comparison", str(exc)) from exc
        duration_ms = (time.monotonic() - start) * 1000
        trace = ToolCallTrace(
            tool_name="calculate_withdrawal_comparison",
            args={"rule_id": _WITHDRAWAL_COMPARISON_RULE_ID},
            status=status,
            duration_ms=duration_ms,
        )
        return result, trace

    def _call_query_products(self, slots: dict[str, object], question: str) -> tuple[list[dict[str, Any]], ToolCallTrace, list[dict[str, str]]]:
        try:
            args = QueryProductsArgs(
                plan_type=slots.get("plan_type"),  # type: ignore[arg-type]
                category=slots.get("category"),  # type: ignore[arg-type]
            )
        except ValidationError as exc:
            raise ToolError("query_products", str(exc), code=ErrorCode.TOOL_ARGUMENT_ERROR) from exc

        start = time.monotonic()
        try:
            products = self._products.query_products(plan_type=args.plan_type, category=args.category)
            if "위험등급" in question:
                grade = re.search(r"([1-6])\s*등급", question)
                if grade:
                    products = [item for item in products if item.get("risk_level") == int(grade.group(1))][:1]
            family_marker = next((marker for marker in ALIASES["product_family"] if marker.lower() in question.lower()), None)
            resolutions: list[dict[str, str]] = []
            if family_marker:
                if family_marker.lower() in {"솔로몬", "solomon"}:
                    products = [item for item in products if "솔로몬" in str(item.get("product_name", ""))]
                else:
                    products = [item for item in products if (
                        "국공채" in str(item.get("product_name", ""))
                        or item.get("asset_type") == "국공채"
                    )]
                compact = question.replace(" ", "")
                requested_periods = self._requested_product_periods(question)
                explicit_multi = len(requested_periods) > 1 or "·" in question or "각" in question or "기간별" in question
                # 여러 기간을 함께 묻는 비교 질문에서는 한 기간으로 축소하지 않는다.
                if explicit_multi:
                    resolved: list[dict[str, Any]] = []
                    for period in requested_periods:
                        match = next((item for item in products if self._product_period(item) == period), None)
                        if match is not None:
                            resolved.append(match)
                    if requested_periods:
                        products = resolved
                        resolved_periods = {self._product_period(item) for item in resolved}
                        resolutions = [
                            {"entity": period, "status": "RESOLVED" if period in resolved_periods else "NOT_FOUND"}
                            for period in requested_periods
                        ]
                elif "중장기" in compact:
                    products = [item for item in products if "중장기" in str(item.get("product_name", ""))]
                elif "초단기" in compact:
                    products = [item for item in products if "초단기" in str(item.get("product_name", ""))]
                elif "단기" in compact:
                    products = [item for item in products if "단기" in str(item.get("product_name", "")) and "초단기" not in str(item.get("product_name", ""))]
                elif "장기" in compact:
                    products = [item for item in products if "장기" in str(item.get("product_name", "")) and "중장기" not in str(item.get("product_name", ""))]
            if slots.get("risk_tolerance") == "stable":
                products = [item for item in products if isinstance(item.get("risk_level"), int) and item["risk_level"] >= 5]
                products.sort(key=lambda item: (-item["risk_level"], str(item.get("product_id", ""))))
                products = products[:5]
            status = "ok"
        except Exception as exc:  # noqa: BLE001
            raise ToolError("query_products", str(exc)) from exc
        duration_ms = (time.monotonic() - start) * 1000
        trace = ToolCallTrace(tool_name="query_products", args=args.model_dump(), status=status, duration_ms=duration_ms)
        return products, trace, resolutions

    @staticmethod
    def _requested_product_periods(question: str) -> list[str]:
        """Extract explicitly requested maturity variants in user order."""
        compact = question.replace(" ", "")
        matches: list[tuple[int, str]] = []
        for label in ("초단기", "중장기", "단기", "장기"):
            start = 0
            while (index := compact.find(label, start)) >= 0:
                # Do not double-count 장기 inside 중장기 or 단기 inside 초단기.
                if label == "단기" and index >= 1 and compact[index - 1] == "초":
                    start = index + len(label)
                    continue
                if label == "장기" and index >= 1 and compact[index - 1] == "중":
                    start = index + len(label)
                    continue
                matches.append((index, label))
                start = index + len(label)
        return list(dict.fromkeys(label for _, label in sorted(matches)))

    @staticmethod
    def _product_period(item: dict[str, Any]) -> str | None:
        name = str(item.get("product_name", "")).replace(" ", "")
        for label in ("초단기", "중장기", "단기", "장기"):
            if label in name:
                return label
        return None

    @staticmethod
    def _product_citations(products: list[dict[str, Any]]) -> list[Citation]:
        citations: list[Citation] = []
        for item in products:
            name = item.get("product_name")
            if not name or not item.get("document_id"):
                continue
            excerpt = (
                f"상품명: {name}; 자산유형: {item.get('asset_type')}; "
                f"위험등급: {item.get('risk_level')}등급({item.get('risk_label')}); "
                f"가입계좌: {item.get('plan_types')}"
            )
            citations.append(
                Citation(
                    id=f"product-{item['product_id']}",
                    document_id=str(item["document_id"]),
                    page=item.get("page"),
                    source=str(item.get("source", "")),
                    excerpt=excerpt,
                    source_priority=item.get("source_priority"),
                )
            )
        return citations

    @staticmethod
    def _withdrawal_calculations(value: WithdrawalComparisonResponse) -> list[CalculationResult]:
        return [
            CalculationResult(
                rule_id=scenario.rule_id,
                rule_version=scenario.rule_version,
                label=scenario.scenario,
                value=scenario.tax_value,
                unit=value.comparison.unit,
                rate=str(scenario.applicable_rate),
                formula=scenario.formula,
            )
            for scenario in value.comparison.scenarios
        ]

    @staticmethod
    def _withdrawal_citations(value: WithdrawalComparisonResponse) -> list[Citation]:
        return [
            Citation(
                id=item.evidence_id,
                document_id=item.document_id,
                page=item.page,
                section=item.section,
                source=item.document_id,
                excerpt=item.quote or "",
                source_priority=item.source_priority,
                score=item.score,
            )
            for item in value.evidence
        ]
