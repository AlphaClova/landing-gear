"""B(검색/계산) 담당과의 Tool 계약.

여기 정의된 Protocol이 A<->B 핸드셰이크의 실제 인터페이스다. B가
`retrieve_evidence`, `calculate`, `query_products`를 구현해 Provider로
주입하면 되고, 그 전까지는 Mock*Provider로 파이프라인을 끝까지 돌린다.
LLM은 계산하지 않고 이 Tool의 결과만 사용한다 (문서 9장 Failsafe).
"""

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
    ProductResult,
    ToolCallTrace,
    WithdrawalComparisonResponse,
    WithdrawalEvidenceItem,
    WithdrawalScenario,
    WithdrawalTaxComparison,
)
from app.core.errors import ErrorCode, ToolError
from app.core.logging import get_logger
from app.tools.product_query import query_products as b_query_products
from app.tools.retriever import retrieve_evidence as b_retrieve_evidence
from app.tools.withdrawal_comparison import calculate_withdrawal_comparison as b_calculate_withdrawal_comparison

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
    def query_products(self, *, plan_type: str | None, category: str | None) -> list[ProductResult]: ...


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


def to_citation(raw: object) -> Citation:
    """B EvidenceResult(dataclass 또는 dict) -> A `Citation`. 필드명이 일부 다르다
    (evidence_id -> id) — chunk_id/source_priority/score는 Citation 계약에 없어 버린다."""
    if isinstance(raw, Citation):
        return raw
    if is_dataclass(raw) and not isinstance(raw, type):
        raw = asdict(raw)
    return Citation(
        id=raw["evidence_id"],
        document_id=raw["document_id"],
        page=raw.get("page"),
        section=raw.get("section"),
        source=raw["source"],
        excerpt=raw["excerpt"],
    )


def to_product_result(raw: object) -> ProductResult:
    """B ProductResult(dataclass 또는 dict) -> A `ProductResult`. 필드 shape이 1:1이라
    손실 없이 그대로 파싱한다 (provenance 필드 포함)."""
    if isinstance(raw, ProductResult):
        return raw
    if is_dataclass(raw) and not isinstance(raw, type):
        raw = asdict(raw)
    return ProductResult.model_validate(raw)


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
    def query_products(self, *, plan_type: str | None = None, category: str | None = None) -> list[ProductResult]:
        return []


# ---------------------------------------------------------------------------
# B RuleEngine — calculate_withdrawal_comparison만 B의 실제 구현으로 연결한다.
# calculate()는 B가 아직 generic dispatcher를 제공하지 않아 Mock을 유지한다.
# ---------------------------------------------------------------------------


class BRuleEngine(MockRuleEngine):
    def calculate_withdrawal_comparison(
        self, *, retirement_amount: int, deferred_retirement_tax: int
    ) -> Any:
        return b_calculate_withdrawal_comparison(retirement_amount, deferred_retirement_tax)


class BEvidenceProvider:
    def retrieve_evidence(self, query: str, *, topic: str | None = None, top_k: int = 5) -> list[Citation]:
        return [to_citation(item) for item in b_retrieve_evidence(query, topic, top_k)]


class BProductCatalog:
    def query_products(self, *, plan_type: str | None = None, category: str | None = None) -> list[ProductResult]:
        return [to_product_result(item) for item in b_query_products(plan_type, category)]


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
    products: list[ProductResult] = field(default_factory=list)
    traces: list[ToolCallTrace] = field(default_factory=list)


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

    def run(
        self,
        intent: str,
        slots: dict[str, object],
        *,
        question: str,
        rule_id: str | None = None,
    ) -> ToolResult:
        allowed = ALLOWED_TOOLS_BY_INTENT.get(intent, ())
        result = ToolResult()

        if "retrieve_evidence" in allowed:
            # A의 intent 라벨("종합"/"세제"...)과 B의 chunk topic 키(pension_system/withdrawal_tax)가
            # 서로 다른 taxonomy라 intent를 그대로 topic 필터로 넘기면 항상 0건이 된다.
            # 매핑이 B와 확정되기 전까지는 topic 필터 없이(relevance만으로) 검색한다.
            result.evidence, trace = self._call_retrieve_evidence(question, None)
            result.traces.append(trace)

        if "calculate" in allowed and rule_id:
            calc, trace = self._call_calculate(rule_id, slots)
            result.calculations.append(calc)
            result.traces.append(trace)

        if "calculate_withdrawal_comparison" in allowed and rule_id == _WITHDRAWAL_COMPARISON_RULE_ID:
            result.withdrawal_result, trace = self._call_calculate_withdrawal_comparison(slots)
            result.traces.append(trace)

        if "query_products" in allowed:
            products, trace = self._call_query_products(slots)
            result.products = products
            result.traces.append(trace)

        return result

    def _call_retrieve_evidence(self, question: str, topic: str | None) -> tuple[list[Citation], ToolCallTrace]:
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
                retirement_amount=slots.get("retirement_amount_won"),  # type: ignore[arg-type]
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

    def _call_query_products(self, slots: dict[str, object]) -> tuple[list[ProductResult], ToolCallTrace]:
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
            status = "ok"
        except Exception as exc:  # noqa: BLE001
            raise ToolError("query_products", str(exc)) from exc
        duration_ms = (time.monotonic() - start) * 1000
        trace = ToolCallTrace(tool_name="query_products", args=args.model_dump(), status=status, duration_ms=duration_ms)
        return products, trace
