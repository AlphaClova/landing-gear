from app.agent.router import IntentRouter
from app.agent.slots import SlotManager
from app.agent.tools import BEvidenceProvider, BProductCatalog, BRuleEngine, ToolResult, ToolRouter
from app.core.query_normalization import (
    RETIREMENT_PENSION_RECEIPT_TAX,
    TAX_CREDIT,
    procedure_type,
    tax_intent,
    tax_source_types,
)
from tests.contract.test_public_evidence_pruning_gates import _public


G016 = "DC 부담금은 어떻게 정해지나요?"
G047 = "DB와 DC 급여 차이 및 퇴직 후 IRP 이전을 한 번에 설명해줘"
G050 = "퇴직소득세만 알고 퇴직금은 몰라요. 연금 절세액 계산해줘"


def _queries(question: str) -> list[tuple[str, str]]:
    decision = IntentRouter().classify(question)
    result = ToolResult(
        tax_intent=tax_intent(question),
        tax_source_types=tax_source_types(question),
        procedure_type=procedure_type(question),
    )
    return ToolRouter._evidence_queries(question, decision.intent, result)


def test_g016_inflection_containing_haeji_is_not_account_termination() -> None:
    assert procedure_type(G016) != "ACCOUNT_TERMINATION"
    for question in ("정해지다", "정해지나요", "정해진", "정해지는", "정해졌나요"):
        assert procedure_type(question) != "ACCOUNT_TERMINATION"


def test_explicit_account_termination_forms_remain_detected() -> None:
    assert procedure_type("IRP를 해지하려면 어떻게 하나요?") == "ACCOUNT_TERMINATION"
    assert procedure_type("퇴직연금 계약 해지 절차 알려줘") == "ACCOUNT_TERMINATION"


def test_g016_does_not_add_termination_procedure_query() -> None:
    assert IntentRouter().classify(G016).intent == "제도"
    assert not any("계약 종료 해지" in query for query, _ in _queries(G016))


def test_g047_adds_narrow_explicit_plan_to_irp_transfer_query() -> None:
    assert ("DB DC 퇴직급여 IRP 이전 수령계좌", "세제") in _queries(G047)
    ordinary = _queries("DB와 DC 급여 차이를 설명해줘")
    assert not any(query.endswith("퇴직급여 IRP 이전 수령계좌") for query, _ in ordinary)


def test_g047_keeps_direct_dc_to_irp_support_internal_and_public() -> None:
    decision = IntentRouter().classify(G047)
    result = ToolRouter(BEvidenceProvider(), BRuleEngine(), BProductCatalog()).run(
        decision.intent,
        SlotManager.extract(G047),
        question=G047,
    )
    assert any(
        item.document_id == "doc51"
        and "DC" in item.excerpt
        and "IRP" in item.excerpt
        and any(marker in item.excerpt for marker in ("이전", "수령"))
        for item in result.evidence
    )
    _, public = _public(G047, "G047")
    assert "[DOC doc51][PAGE 2]" in public.retrieved_context
    assert "DC" in public.retrieved_context and "IRP" in public.retrieved_context
    assert "이전" in public.retrieved_context


def test_g050_uses_existing_retirement_pension_tax_clarification_path() -> None:
    assert tax_intent(G050) == RETIREMENT_PENSION_RECEIPT_TAX
    decision = IntentRouter().classify(G050)
    assert decision.intent == "종합"
    missing = SlotManager().required(decision.intent, {}, G050)
    assert [item.name for item in missing] == ["expected_tax_won"]


def test_g050_tax_intent_negative_regressions() -> None:
    assert tax_intent("연금저축과 IRP 세액공제 한도 알려줘") == TAX_CREDIT
    assert tax_intent("연금저축 600만원 넣으면 세액공제 얼마야?") == TAX_CREDIT
    assert tax_intent("퇴직금을 연금으로 받으면 세금이 어떻게 돼?") == RETIREMENT_PENSION_RECEIPT_TAX
