from app.agent.router import IntentRouter
from app.agent.slots import SlotManager
from app.agent.tools import BEvidenceProvider, BProductCatalog, BRuleEngine, ToolRouter
from tests.contract.test_public_evidence_pruning_gates import _public


G081 = "DC 계좌, 위험등급 낮은 상품을 비용과 함께 비교해줘"


def _run(question: str):
    decision = IntentRouter().classify(question)
    result = ToolRouter(BEvidenceProvider(), BRuleEngine(), BProductCatalog()).run(
        decision.intent,
        SlotManager.extract(question),
        question=question,
    )
    return decision, result


def test_g081_is_product_focused_and_exact_dc_filter_returns_nothing() -> None:
    decision, result = _run(G081)
    assert decision.intent == "상품"
    assert decision.route == "deep_path"
    assert result.products == []
    assert [trace.tool_name for trace in result.traces] == ["query_products"]
    assert result.evidence == []


def test_g081_public_context_does_not_expose_unrelated_pension_evidence() -> None:
    _, public = _public(G081, "G081")
    assert public.retrieved_context == ""
    assert "요청한 계좌 유형" in public.answer
    assert all(document_id not in public.retrieved_context for document_id in ("doc10", "doc51", "doc55"))


def test_account_and_procedure_negative_regressions_keep_existing_intents() -> None:
    expected = {
        "DC와 DB 차이 알려줘": "제도",
        "DC 부담금은 어떻게 정해지나요?": "제도",
        "퇴직 후 DC에서 IRP로 이전할 수 있나요?": "절차",
        "IRP 상품 중 위험등급 낮은 상품 비교해줘": "상품",
        "연금 상품 추천해줘": "상품",
    }
    assert {question: IntentRouter().classify(question).intent for question in expected} == expected
