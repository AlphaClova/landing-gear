"""B(검색/계산) 담당과의 Tool 계약.

여기 정의된 Protocol이 A<->B 핸드셰이크의 실제 인터페이스다. B가
`retrieve_evidence`, `calculate`, `query_products`를 구현해 Provider로
주입하면 되고, 그 전까지는 Mock*Provider로 파이프라인을 끝까지 돌린다.
LLM은 계산하지 않고 이 Tool의 결과만 사용한다 (문서 9장 Failsafe).
"""

import time
from dataclasses import dataclass, field
from typing import Protocol

from pydantic import BaseModel, ValidationError

from app.api.schemas import (
    AppliedRule,
    CalculationResult,
    Citation,
    ClaimValidation,
    ComparisonResult,
    ToolCallTrace,
    WithdrawalComparisonResponse,
)
from app.core.errors import ErrorCode, ToolError
from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# B가 구현할 Provider 인터페이스
# ---------------------------------------------------------------------------


class EvidenceProvider(Protocol):
    def retrieve_evidence(self, query: str, *, topic: str | None, top_k: int) -> list[Citation]: ...


class RuleEngine(Protocol):
    def calculate(self, rule_id: str, params: dict[str, float | int | str]) -> CalculationResult: ...

    def calculate_withdrawal_comparison(
        self, params: dict[str, float | int | str]
    ) -> WithdrawalComparisonResponse: ...


class ProductCatalog(Protocol):
    def query_products(self, *, plan_type: str | None, category: str | None) -> list[dict[str, str]]: ...


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
    params: dict[str, float | int | str] = {}


class QueryProductsArgs(BaseModel):
    plan_type: str | None = None
    category: str | None = None


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
        self, params: dict[str, float | int | str]
    ) -> WithdrawalComparisonResponse:
        return WithdrawalComparisonResponse(
            comparison=ComparisonResult(
                title="[MOCK] 일시금 vs 연금수령 비교",
                options=["lump_sum", "pension"],
                note="B팀 Rule Engine 연결 전 mock 값입니다.",
            ),
            evidence=[],
            applied_rules=[AppliedRule(rule_id="lump_sum_vs_pension", rule_version=None)],
            claim_validation=ClaimValidation(verified=False, issues=["B팀 Rule Engine 미연결 (mock)"]),
        )


class MockProductCatalog:
    def query_products(self, *, plan_type: str | None = None, category: str | None = None) -> list[dict[str, str]]:
        return []


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
    products: list[dict[str, str]] = field(default_factory=list)
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
            result.evidence, trace = self._call_retrieve_evidence(question, intent)
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
            args = WithdrawalComparisonArgs(params=slots)  # type: ignore[arg-type]
        except ValidationError as exc:
            raise ToolError(
                "calculate_withdrawal_comparison", str(exc), code=ErrorCode.TOOL_ARGUMENT_ERROR
            ) from exc

        start = time.monotonic()
        try:
            result = self._rules.calculate_withdrawal_comparison(args.params)
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

    def _call_query_products(self, slots: dict[str, object]) -> tuple[list[dict[str, str]], ToolCallTrace]:
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
