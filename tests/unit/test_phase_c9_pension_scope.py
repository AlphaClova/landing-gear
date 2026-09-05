from app.agent.composer import Composer, Draft, GroundedContext
from app.agent.hcx_client import HCXClient
from app.agent.router import IntentRouter
from app.agent.slots import SlotManager
from app.agent.tools import BEvidenceProvider, BProductCatalog, BRuleEngine, ToolResult, ToolRouter
from app.agent.verifier import Verifier
from app.api.public_evidence import select_public_citations
from app.api.schemas import Citation, InternalAnswer, ThinkTrace
from app.core.config import Settings
from app.core.query_normalization import (
    evidence_compatible_with_question_scope,
    pension_scope,
    pension_scopes,
)
from app.main import app
from app.tools.retriever import RETRIEVAL_MIN_QUERY_COVERAGE, RETRIEVAL_MIN_SCORE
from fastapi.testclient import TestClient
from tests.contract.test_public_evidence_pruning_gates import C1, C2, C3, C4, C5, _public
from tests.unit.test_content_p0_policies import grounded
from tests.unit.test_missing_direct_evidence_queries import G019, G042
from tests.unit.test_phase_c1_p0_fixes import G047
from tests.unit.test_phase_c2_g072_fee_mapping import G072
from tests.unit.test_phase_c7_g075_product_availability import G075
from tests.unit.test_phase_c6_relation_guards import G099

client = TestClient(app)

A = "연금은 언제부터 받을 수 있나요?"
B = "퇴직연금은 언제부터 받을 수 있나요?"
C = "연금저축은 언제부터 받을 수 있나요?"
D = "IRP는 언제부터 받을 수 있나요?"
E = "국민연금은 언제부터 받을 수 있나요?"
F = "연금은 몇 살부터 받을 수 있나요?"
G = "연금 언제 받아요?"
SAVINGS_IRP = "연금저축과 IRP는 어떻게 다른가요?"
DB_DC = "DB형과 DC형 차이 알려줘"
DC_IRP_TRANSFER = "퇴직 후 DC에서 IRP로 이전하려면?"
NATIONAL_VS_RETIREMENT = "국민연금과 퇴직연금 차이는?"


def _run(question: str):
    decision = IntentRouter().classify(question)
    result = ToolRouter(BEvidenceProvider(), BRuleEngine(), BProductCatalog()).run(
        decision.intent,
        SlotManager.extract(question),
        question=question,
    )
    return decision, result


def _context(question: str):
    decision, result = _run(question)
    missing = SlotManager().required(decision.intent, SlotManager.extract(question), question)
    composer = Composer(HCXClient(Settings(hcx_api_key="")))
    return decision, result, composer.build_context(
        question, decision.intent, result, required_slots=missing or None,
    )


def _citation(excerpt: str, *, document_id: str = "doc10") -> Citation:
    return Citation(id="ev", document_id=document_id, page=1, source="provided", excerpt=excerpt)


def test_specific_scope_beats_generic_substring() -> None:
    assert pension_scope("국민연금은 언제부터 받을 수 있나요?") == "NATIONAL_PENSION"
    assert pension_scopes("국민연금은 언제부터 받을 수 있나요?") == ("NATIONAL_PENSION",)
    assert pension_scope("연금저축은 언제부터 받을 수 있나요?") == "PENSION_SAVINGS"
    assert pension_scopes("연금저축은 언제부터 받을 수 있나요?") == ("PENSION_SAVINGS",)
    assert "GENERIC_PENSION" not in pension_scopes("국민연금")
    assert "GENERIC_PENSION" not in pension_scopes("연금저축")


def test_bare_pension_is_generic_scope() -> None:
    assert pension_scope(A) == "GENERIC_PENSION"
    assert pension_scope(F) == "GENERIC_PENSION"
    assert pension_scope(G) == "GENERIC_PENSION"
    assert pension_scopes(A) == ()
    assert pension_scope("21년차 연금수령 세금은?") == "NONE"
    assert pension_scope("퇴직재원 연금수령 기간별 납부비율") == "NONE"


def test_generic_pension_receiving_does_not_force_doc10() -> None:
    _, result = _run(A)
    assert result.evidence == []
    assert ToolRouter._evidence_queries(A, "제도", ToolResult()) == []


def test_pension_savings_rejects_retirement_evidence() -> None:
    retirement = "퇴직연금은 기업이 근로자의 퇴직금을 적립하고 연금(만 55세 이후 지급)으로 수령할 수 있습니다."
    savings = "연금저축은 누구나 가입할 수 있다. 소득이 없어도 가입이 가능하다."
    assert evidence_compatible_with_question_scope(C, retirement) is False
    assert evidence_compatible_with_question_scope(C, savings) is True
    _, result = _run(C)
    assert all(item.document_id != "doc10" for item in result.evidence)
    assert all("퇴직연금" not in item.excerpt or "연금저축" in item.excerpt for item in result.evidence)


def test_national_pension_rejects_retirement_evidence() -> None:
    retirement = "퇴직연금은 만 55세 이후 지급됩니다."
    assert evidence_compatible_with_question_scope(E, retirement) is False
    _, result, context = _context(E)
    assert result.evidence == []
    assert context.response_mode == "limitation"
    assert "퇴직연금" not in context.fallback_message
    assert "55" not in context.fallback_message
    assert "국민연금" in context.fallback_message


def test_irp_direct_evidence_is_allowed() -> None:
    irp_excerpt = "IRP사업자는 해지(인출) 또는 만 55세 이후 연금수령(연금수령 시 절세 가능)"
    retirement_only = "퇴직연금은 기업이 근로자의 퇴직금을 사외 금융기관에 적립합니다."
    assert evidence_compatible_with_question_scope(D, irp_excerpt) is True
    assert evidence_compatible_with_question_scope(D, retirement_only) is False
    _, result = _run(D)
    assert all(item.document_id != "doc10" for item in result.evidence)
    assert all("IRP" in item.excerpt.upper() or "개인형" in item.excerpt for item in result.evidence)


def test_generic_unqualified_retirement_claim_is_rejected() -> None:
    context = GroundedContext(
        question=A, intent="제도", response_mode="result",
        fallback_message="정확한 답변을 위해 퇴직연금, 연금저축, IRP 중 어떤 연금을 기준으로 안내할까요?",
    )
    draft = Draft(
        message="퇴직연금은 만 55세 이후부터 받을 수 있습니다.",
        citations=[_citation("퇴직연금은 연금(만 55세 이후 지급)으로 수령할 수 있습니다.")],
        context=context,
    )
    issues = Verifier().check(draft)
    assert "pension scope mismatch" in issues
    assert Verifier().repair_safe(draft, issues)
    assert "만 55세 이후부터 받을 수 있습니다" not in draft.message


def test_generic_qualified_retirement_claim_with_direct_support_is_allowed() -> None:
    excerpt = "퇴직연금은 기업이 근로자의 퇴직금을 사외 금융기관에 적립하고, 퇴직 시 근로자가 연금(만 55세 이후 지급) 또는 일시금으로 수령할 수 있는 노후 소득 보장 제도입니다."
    context = GroundedContext(
        question=A, intent="제도", response_mode="result",
        evidence=[_citation(excerpt)],
        required_facts=[excerpt],
        fallback_message="제공된 근거의 퇴직연금 기준으로는 만 55세 이후부터 수령할 수 있습니다.",
    )
    draft = Draft(
        message="제공된 근거의 퇴직연금 기준으로는 만 55세 이후부터 수령할 수 있습니다.",
        citations=[_citation(excerpt)],
        context=context,
    )
    assert "pension scope mismatch" not in Verifier().check(draft)


def test_live_matrix_generic_is_clarification_without_doc10() -> None:
    for question, question_id in ((A, "C9-A"), (F, "C9-F"), (G, "C9-G")):
        decision, result, context = _context(question)
        assert decision.intent == "제도"
        assert context.response_mode == "clarification"
        assert result.evidence == []
        body = client.get("/answer", params={"question_id": question_id, "question": question}).json()
        assert "55" not in body["answer"]
        assert "doc10" not in body["retrieved_context"]
        think = __import__("json").loads(body["think_trace"])
        assert think["intent"] == "제도"


def test_live_matrix_retirement_keeps_doc10() -> None:
    _, result, context = _context(B)
    assert any(item.document_id == "doc10" for item in result.evidence)
    assert any("55세" in item.excerpt for item in result.evidence)
    facts = " ".join(context.required_facts)
    assert "퇴직연금" in facts
    body = client.get("/answer", params={"question_id": "C9-B", "question": B}).json()
    assert "doc10" in body["retrieved_context"] or "55" in body["answer"] or "한계" in body["answer"]


def test_live_matrix_savings_and_national_do_not_substitute_retirement() -> None:
    _, result_c, context_c = _context(C)
    assert all(item.document_id != "doc10" for item in result_c.evidence)
    assert "55세 이후부터 받을 수 있습니다" not in (context_c.fallback_message or "")
    body_c = client.get("/answer", params={"question_id": "C9-C", "question": C}).json()
    assert "doc10" not in body_c["retrieved_context"]
    assert not (body_c["answer"].startswith("퇴직연금은") and "55" in body_c["answer"])

    _, result_e, context_e = _context(E)
    assert result_e.evidence == []
    assert context_e.response_mode == "limitation"
    body_e = client.get("/answer", params={"question_id": "C9-E", "question": E}).json()
    assert body_e["retrieved_context"] == ""
    assert "55" not in body_e["answer"]
    assert "퇴직연금은 만" not in body_e["answer"]


def test_live_matrix_irp_does_not_use_retirement_faq() -> None:
    _, result = _run(D)
    assert all(item.document_id != "doc10" for item in result.evidence)
    body = client.get("/answer", params={"question_id": "C9-D", "question": D}).json()
    assert "doc10" not in body["retrieved_context"]


def test_additional_regression_questions_keep_existing_paths() -> None:
    assert IntentRouter().classify(SAVINGS_IRP).intent == "제도"
    _, savings_irp = _run(SAVINGS_IRP)
    assert not any(item.document_id == "doc10" and "확정급여형" in item.excerpt and "연금저축" not in item.excerpt for item in savings_irp.evidence)

    assert IntentRouter().classify(DB_DC).intent == "제도"
    _, dbdc, ctx = _context(DB_DC)
    assert any(item.document_id == "doc10" for item in dbdc.evidence)
    assert ctx.response_mode != "clarification"

    assert IntentRouter().classify(DC_IRP_TRANSFER).intent == "절차"
    _, _, national_ctx = _context(NATIONAL_VS_RETIREMENT)
    assert national_ctx.response_mode == "limitation"
    assert "국민연금" in national_ctx.fallback_message


def test_generic_clarification_public_context_is_empty() -> None:
    internal = InternalAnswer(
        type="clarification",
        message="정확한 답변을 위해 퇴직연금, 연금저축, IRP 중 어떤 연금을 기준으로 안내할까요?",
        request_id="req-c9",
        citations=[_citation("퇴직연금은 만 55세 이후 지급")],
        required_slots=[],
        trace=ThinkTrace(intent="제도", route="deep_path", route_confidence=0.7),
    )
    assert select_public_citations(internal, A) == []


def test_freeze_c1_c5_and_target_goldens() -> None:
    assert RETRIEVAL_MIN_SCORE == 0.01
    assert RETRIEVAL_MIN_QUERY_COVERAGE == 0.51
    for question, question_id in ((C1, "C1"), (C2, "C2"), (C3, "C3"), (C4, "C4"), (C5, "C5")):
        internal, public = _public(question, question_id)
        assert public.answer == internal.message
    _, _, g019_result, _ = grounded(G019)
    assert any(item.document_id == "doc51" for item in g019_result.evidence)
    _, _, g042_result, _ = grounded(G042)
    blob = " ".join(item.excerpt for item in g042_result.evidence)
    assert "70%" in blob and "60%" in blob and "50%" in blob
    _, _, g047_result, _ = grounded(G047)
    assert any("IRP" in item.excerpt and ("이전" in item.excerpt or "DC" in item.excerpt) for item in g047_result.evidence)
    _, _, g072_result, g072_ctx = grounded(G072)
    assert "0.12" in (g072_ctx.fallback_message or "") or g072_result.products
    _, g075_public = _public(G075, "G075")
    assert g075_public.answer
    _, _, _, g099_ctx = grounded(G099)
    assert g099_ctx.claim_plan or g099_ctx.fallback_message
