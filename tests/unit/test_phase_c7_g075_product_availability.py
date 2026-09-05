from app.agent.composer import Composer
from app.agent.router import IntentRouter
from app.agent.slots import SlotManager
from app.agent.tools import BEvidenceProvider, BProductCatalog, BRuleEngine, ToolResult, ToolRouter
from app.api.schemas import Citation
from app.core.query_normalization import (
    allows_dc_irp_account_transfer_claim,
    excerpt_supports_dc_irp_retirement_transfer,
    is_product_availability_question,
    plan_types_from_question,
)
from tests.contract.test_public_evidence_pruning_gates import _public


G075 = "IRP와 DC에서 같은 상품을 살 수 있나요?"
G019 = "IRP와 DC는 같은 제도인가요?"
G047 = "DB와 DC 급여 차이 및 퇴직 후 IRP 이전을 한 번에 설명해줘"
G063 = "IRP에서 살 수 있는 예금형 상품을 설명해줘"
G081 = "DC 계좌, 위험등급 낮은 상품을 비용과 함께 비교해줘"
_TRANSFER_TEXT = "반면 DC퇴직금은 나이와 무관하게 반드시 IRP로 이전해야 한다."
_COEXIST_TEXT = "원리금보장형 상품을 DC에서 퇴직급여지급 신청 시 특별중도해지1)가 적용되고, DC에서 IRP로 현물이전 후 중도해지 시 중도해지이자율이 적용됩니다."
_ELIGIBILITY_TEXT = "개인사업 대표는 일반 IRP(개인형 퇴직연금)를 통해 자영업자로 가입할 수 있습니다. DB 또는 DC 퇴직연금에 가입할 수 있나요?"


def _run(question: str):
    decision = IntentRouter().classify(question)
    result = ToolRouter(BEvidenceProvider(), BRuleEngine(), BProductCatalog()).run(
        decision.intent,
        SlotManager.extract(question),
        question=question,
    )
    return decision, result


def _claim_plan(question: str, excerpts: list[tuple[str, str]]) -> list[dict]:
    evidence = [
        Citation(
            id=f"ev-{index}",
            document_id=document_id,
            page=1,
            source="wiki",
            excerpt=excerpt,
        )
        for index, (document_id, excerpt) in enumerate(excerpts)
    ]
    composer = Composer.__new__(Composer)
    return composer._build_claim_plan(question, ToolResult(evidence=evidence))


def test_g075_availability_is_product_focused_and_queries_catalog() -> None:
    decision, result = _run(G075)
    assert decision.intent == "상품"
    assert [trace.tool_name for trace in result.traces] == ["query_products"]
    assert result.products == []
    assert result.evidence == []
    assert plan_types_from_question(G075) == ("IRP", "DC")
    shared = next(item for item in result.recommendation_constraints if item["constraint"] == "shared_account_types")
    assert shared["value"] == ["IRP", "DC"]
    assert shared["applied"] is False
    assert "DC" in shared["missing_account_types"]
    assert "IRP" in shared["present_account_types"]
    assert not any(item.get("constraint") == "account_type" for item in result.recommendation_constraints)


def test_g075_does_not_emit_account_transfer_from_dc_irp_cooccurrence() -> None:
    assert allows_dc_irp_account_transfer_claim(G075) is False
    plan = _claim_plan(G075, [("doc55", _COEXIST_TEXT), ("doc10", _ELIGIBILITY_TEXT)])
    assert not any(item.get("subtask") == "account_transfer" for item in plan)
    assert "DC 법정퇴직금은 IRP로 이전할 수 있습니다" not in " ".join(
        str(claim.get("text", ""))
        for item in plan
        for claim in item.get("claims") or []
        if isinstance(claim, dict)
    )


def test_transfer_marker_allows_claim_only_with_direct_same_item_support() -> None:
    transfer_question = "퇴직 후 DC에서 IRP로 이전할 수 있나요?"
    assert allows_dc_irp_account_transfer_claim(transfer_question) is True
    assert excerpt_supports_dc_irp_retirement_transfer(_TRANSFER_TEXT) is True
    assert excerpt_supports_dc_irp_retirement_transfer(_COEXIST_TEXT) is False
    allowed = _claim_plan(transfer_question, [("doc51", _TRANSFER_TEXT)])
    blocked = _claim_plan(transfer_question, [("doc55", _COEXIST_TEXT)])
    assert any(item.get("subtask") == "account_transfer" for item in allowed)
    assert not any(item.get("subtask") == "account_transfer" for item in blocked)


def test_same_product_with_entity_is_availability_not_institution() -> None:
    assert is_product_availability_question(G075) is True
    assert is_product_availability_question("IRP와 DC가 같은가요?") is False
    assert is_product_availability_question(G019) is False
    assert IntentRouter().classify("IRP와 DC가 같은 제도인가요?").intent == "제도"
    assert IntentRouter().classify("DB와 DC 차이 알려줘").intent == "제도"
    assert IntentRouter().classify("퇴직 후 DC에서 IRP로 이전할 수 있나요?").intent == "절차"
    assert IntentRouter().classify("IRP에서 살 수 있는 상품 알려줘").intent == "상품"
    assert IntentRouter().classify(G075).intent == "상품"


def test_g075_limitation_does_not_generalize_market_absence() -> None:
    _, context = _public(G075, "G075")
    assert context.retrieved_context == ""
    assert "DC 법정퇴직금은 IRP로 이전할 수 있습니다" not in context.answer
    assert "공통으로 가입 가능한 상품이 있는지 확정할 수 없습니다" in context.answer
    assert "DC" in context.answer
    assert "IRP 가입 가능 상품이 없" not in context.answer
    assert "시장" not in context.answer
    assert "존재하지 않" not in context.answer
    assert all(document_id not in context.retrieved_context for document_id in ("doc10", "doc51", "doc55"))


def test_g019_g047_g063_g081_freeze_paths() -> None:
    assert IntentRouter().classify(G019).intent == "제도"
    assert allows_dc_irp_account_transfer_claim(G019) is True
    g019_plan = _claim_plan(G019, [("doc51", _TRANSFER_TEXT)])
    assert any(item.get("subtask") == "account_transfer" for item in g019_plan)

    g047_decision, g047_result = _run(G047)
    assert g047_decision.intent != "상품"
    assert any(
        item.document_id == "doc51"
        and excerpt_supports_dc_irp_retirement_transfer(item.excerpt)
        for item in g047_result.evidence
    )
    assert allows_dc_irp_account_transfer_claim(G047) is True

    g081_decision, g081_result = _run(G081)
    assert g081_decision.intent == "상품"
    assert [trace.tool_name for trace in g081_result.traces] == ["query_products"]
    assert g081_result.products == []
    _, g081_public = _public(G081, "G081")
    assert "요청한 계좌 유형" in g081_public.answer

    g063_decision, g063_result = _run(G063)
    assert g063_decision.intent == "상품"
    assert g063_result.products == []
