from app.agent.router import IntentRouter
from app.agent.slots import SlotManager
from app.agent.tools import BEvidenceProvider, BProductCatalog, BRuleEngine, ToolResult, ToolRouter
from app.core.query_normalization import tax_intent, tax_source_types
from tests.contract.test_public_evidence_pruning_gates import _public


G019 = "IRP와 DC는 같은 제도인가요?"
G042 = "퇴직금과 개인납입금이 섞인 IRP의 과세를 구분해줘"


def _queries(question: str) -> list[tuple[str, str]]:
    decision = IntentRouter().classify(question)
    result = ToolResult(
        tax_intent=tax_intent(question),
        tax_source_types=tax_source_types(question),
    )
    return ToolRouter._evidence_queries(question, decision.intent, result)


def _retrieve(question: str):
    decision = IntentRouter().classify(question)
    return ToolRouter(BEvidenceProvider(), BRuleEngine(), BProductCatalog()).run(
        decision.intent,
        SlotManager.extract(question),
        question=question,
    )


def test_g019_adds_only_relationship_withdrawal_tax_query() -> None:
    queries = _queries(G019)
    assert ("DC 퇴직급여 IRP 이전 수령계좌 제도 관계", "세제") in queries
    assert not any(
        topic == "세제"
        for _, topic in _queries("DB형과 DC형의 운용 주체와 퇴직급여 차이는 무엇인가요?")
    )


def test_g019_retrieves_direct_irp_dc_relationship_support() -> None:
    result = _retrieve(G019)
    assert any(
        item.document_id != "doc10" and "DC" in item.excerpt and "IRP" in item.excerpt
        and any(marker in item.excerpt for marker in ("이전", "수령"))
        for item in result.evidence
    )


def test_g042_adds_two_number_free_mixed_source_tax_queries() -> None:
    supplemental = [
        query for query, topic in _queries(G042)
        if topic == "세제" and query.startswith("연금계좌")
    ]
    assert supplemental == [
        "연금계좌 퇴직소득 실제수령연차 이연퇴직소득세",
        "연금계좌 세액공제 납입금 운용수익 연금소득세",
    ]
    assert not any(number in " ".join(supplemental) for number in ("70", "60", "50", "3.3", "5.5"))


def test_g042_retrieves_both_direct_tax_supports() -> None:
    result = _retrieve(G042)
    excerpts = [item.excerpt for item in result.evidence]
    assert any(
        "이연퇴직소득세" in excerpt
        and all(rate in excerpt for rate in ("70%", "60%", "50%"))
        for excerpt in excerpts
    )
    assert any(
        "세액공제" in excerpt and "운용수익" in excerpt and "연금소득세" in excerpt
        for excerpt in excerpts
    )


def test_unrelated_questions_do_not_add_targeted_tax_queries() -> None:
    tax_credit = _queries("연금저축이랑 IRP에 넣으면 세액공제 얼마까지 되나요? 다 합쳐서요.")
    product = _queries("IRP에서 살 수 있는 펀드 상품을 알려줘")
    targeted = {
        "DC 퇴직급여 IRP 이전 수령계좌 제도 관계",
        "연금계좌 퇴직소득 실제수령연차 이연퇴직소득세",
        "연금계좌 세액공제 납입금 운용수익 연금소득세",
    }
    assert targeted.isdisjoint(query for query, _ in tax_credit)
    assert targeted.isdisjoint(query for query, _ in product)


def test_g019_public_context_keeps_direct_support_not_eligibility() -> None:
    _, public = _public(G019, "G019")
    assert public.retrieved_context
    assert "DC" in public.retrieved_context and "IRP" in public.retrieved_context
    assert "이전" in public.retrieved_context
    assert "[DOC doc10][PAGE 2]" not in public.retrieved_context
    assert "[DOC doc10][PAGE 3]" not in public.retrieved_context


def test_g042_public_context_keeps_both_direct_supports_not_ops() -> None:
    _, public = _public(G042, "G042")
    context = public.retrieved_context
    assert context
    assert all(rate in context for rate in ("70%", "60%", "50%"))
    assert "이연퇴직소득세" in context
    assert all(rate in context for rate in ("3.3%", "5.5%"))
    assert "세액공제" in context and "운용수익" in context and "연금소득세" in context
    assert "명예퇴직금과 잔여부담금" not in context
    assert "IRP의무이전 예외사유" not in context
