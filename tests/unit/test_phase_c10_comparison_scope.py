from app.agent.composer import Composer, Draft
from app.agent.hcx_client import HCXClient
from app.agent.router import IntentRouter
from app.agent.slots import SlotManager
from app.agent.tools import BEvidenceProvider, BProductCatalog, BRuleEngine, ToolResult, ToolRouter
from app.agent.verifier import Verifier
from app.api.schemas import Citation
from app.core.config import Settings
from app.core.query_normalization import (
    excerpt_supports_product_type_comparison,
    excerpt_supports_savings_irp_comparison,
    is_pension_savings_irp_comparison,
    is_principal_vs_performance_comparison,
)
from app.main import app
from app.tools.retriever import RETRIEVAL_MIN_QUERY_COVERAGE, RETRIEVAL_MIN_SCORE
from fastapi.testclient import TestClient
from tests.contract.test_public_evidence_pruning_gates import C1, C2, C3, C4, C5, _public
from tests.unit.test_content_p0_policies import grounded
from tests.unit.test_missing_direct_evidence_queries import G019, G042
from tests.unit.test_phase_c1_p0_fixes import G047
from tests.unit.test_phase_c2_g072_fee_mapping import G072
from tests.unit.test_phase_c7_g075_product_availability import G075, G081
from tests.unit.test_phase_c6_relation_guards import G099
from tests.unit.test_phase_c9_pension_scope import A, C as SAVINGS_RECEIVING, D, E

client = TestClient(app)

SAVINGS_IRP = "연금저축과 IRP는 어떻게 다른가요?"
PRINCIPAL_VS_PERFORMANCE = "원리금보장형과 실적배당형은 어떻게 비교해야 하나요?"
DB_DC = "DB형과 DC형의 차이는 무엇인가요?"

_ELIGIBILITY = (
    "연금계좌는 연금저축과 IRP, 두 종류다. 연금저축은 누구나 가입할 수 있다. "
    "소득이 없어도 가입이 가능하지만 직장인, 자영업자 등 종합소득이 있어야 세액공제 혜택을 볼 수 있다. "
    "IRP는 직장인, 자영업자, 직역연금가입자 등 가입대상이 정해져 있다."
)
_LIMITS = (
    "연금저축과 IRP는 합산해서 연1,800만원까지 입금이 가능하다. "
    "그러나 납입액이 모두 세액공제 받을 수 있는 것은 아니다. "
    "세액공제 받을 수 있는 납입한도는 따로 정해져 있다. "
    "연금저축은 연600만원, IRP는 연금저축 납입액을 포함해서 연900만원이다. "
    "연금저축만 있다면 IRP를 추가로 가입해야 연900만원을 채울 수 있다."
)
_TRANSFER = (
    "퇴직금을 수령하는 방식은 크게 두 가지다. 퇴직 즉시 전액을 받는 ‘일시금’과 "
    "연금계좌(IRP·연금저축)에 이전한 뒤 만55세 이후 나눠받는 ‘연금’이다."
)
_DC_IRP_TABLE = (
    "| 55세 미만 | 55세 이상\n"
    "DC법정퇴직금 | IRP 의무이전 | IRP·일반계좌 선택가능"
)


def _run(question: str):
    decision = IntentRouter().classify(question)
    result = ToolRouter(BEvidenceProvider(), BRuleEngine(), BProductCatalog()).run(
        decision.intent,
        SlotManager.extract(question),
        question=question,
    )
    return decision, result


def _context(question: str, result: ToolResult | None = None):
    decision = IntentRouter().classify(question)
    if result is None:
        _, result = _run(question)
    missing = SlotManager().required(decision.intent, SlotManager.extract(question), question)
    composer = Composer(HCXClient(Settings(hcx_api_key="")))
    return decision, result, composer.build_context(
        question, decision.intent, result, required_slots=missing or None,
    )


def _citation(excerpt: str, *, document_id: str = "src", citation_id: str = "ev") -> Citation:
    return Citation(id=citation_id, document_id=document_id, page=1, source="provided", excerpt=excerpt)


def test_savings_irp_comparison_builds_direct_claims() -> None:
    assert is_pension_savings_irp_comparison(SAVINGS_IRP) is True
    result = ToolResult(evidence=[
        _citation(_ELIGIBILITY, document_id="cmp-a", citation_id="e1"),
        _citation(_LIMITS, document_id="cmp-b", citation_id="e2"),
        _citation(_TRANSFER, document_id="noise", citation_id="e3"),
        _citation(_DC_IRP_TABLE, document_id="noise2", citation_id="e4"),
    ])
    _, _, context = _context(SAVINGS_IRP, result)
    subtasks = [str(item.get("subtask")) for item in context.claim_plan]
    assert "PENSION_SAVINGS_ELIGIBILITY" in subtasks
    assert "IRP_ELIGIBILITY" in subtasks
    assert "TOTAL_CONTRIBUTION_LIMIT" in subtasks
    assert "PENSION_SAVINGS_TAX_CREDIT_LIMIT" in subtasks
    assert "IRP_COMBINED_TAX_CREDIT_LIMIT" in subtasks
    assert all(item.get("claims") and item["claims"][0].get("evidence_ids") for item in context.claim_plan if item.get("status") == "answerable")
    blob = " ".join(context.required_facts)
    assert "가입" in blob
    assert "300" not in blob.replace("1,800", "").replace("1800", "")
    tax_credit_text = " ".join(
        str(claim.get("text", ""))
        for item in context.claim_plan
        for claim in item.get("claims", []) or []
        if item.get("subtask") in {"PENSION_SAVINGS_TAX_CREDIT_LIMIT", "IRP_COMBINED_TAX_CREDIT_LIMIT"}
        and isinstance(claim, dict)
    )
    assert "세액공제" in tax_credit_text
    assert "납입한도" in tax_credit_text.replace(" ", "") or "세액공제 대상 납입한도" in tax_credit_text
    contribution = " ".join(
        str(claim.get("text", ""))
        for item in context.claim_plan
        for claim in item.get("claims", []) or []
        if item.get("subtask") == "TOTAL_CONTRIBUTION_LIMIT" and isinstance(claim, dict)
    )
    assert "입금" in contribution
    assert "세액공제 대상 납입한도" not in contribution


def test_savings_irp_comparison_does_not_infer_300() -> None:
    result = ToolResult(evidence=[
        _citation(_ELIGIBILITY, citation_id="e1"),
        _citation(_LIMITS, citation_id="e2"),
    ])
    _, _, context = _context(SAVINGS_IRP, result)
    contract = context.fallback_message
    assert "300" not in contract.replace("1,800", "").replace("1800", "")
    dirty = Draft(
        message=(
            context.fallback_message
            + " 따라서 나머지 300만 원을 채워야 합니다. DC 법정퇴직금은 IRP로 의무이전됩니다."
        ),
        citations=list(context.evidence),
        context=context,
    )
    issues = Verifier().check(dirty)
    assert any(issue.startswith("근거 없는 숫자") or issue == "핵심 grounded contract 변경 또는 일부 누락" for issue in issues)
    assert Verifier().repair_safe(dirty, issues)
    assert "300" not in dirty.message.replace("1,800", "").replace("1800", "")
    assert "의무이전" not in dirty.message
    assert "누구나 가입" in dirty.message or "가입대상" in dirty.message


def test_savings_irp_comparison_drops_transfer_from_required_facts() -> None:
    assert excerpt_supports_savings_irp_comparison(_ELIGIBILITY) is True
    assert excerpt_supports_savings_irp_comparison(_LIMITS) is True
    assert excerpt_supports_savings_irp_comparison(_TRANSFER) is False
    assert excerpt_supports_savings_irp_comparison(_DC_IRP_TABLE) is False
    result = ToolResult(evidence=[
        _citation(_ELIGIBILITY, citation_id="e1"),
        _citation(_LIMITS, citation_id="e2"),
        _citation(_TRANSFER, citation_id="e3"),
        _citation(_DC_IRP_TABLE, citation_id="e4"),
    ])
    _, filtered, context = _context(SAVINGS_IRP, result)
    facts = "\n".join(context.required_facts)
    assert "의무이전" not in facts
    assert "일시금" not in facts
    assert "만55세" not in facts.replace(" ", "")
    assert all(excerpt_supports_savings_irp_comparison(item.excerpt) for item in context.evidence)


def test_principal_vs_performance_is_not_oos() -> None:
    assert is_principal_vs_performance_comparison(PRINCIPAL_VS_PERFORMANCE) is True
    decision = IntentRouter().classify(PRINCIPAL_VS_PERFORMANCE)
    assert decision.intent != "범위 밖"
    assert decision.intent == "상품"


def test_principal_vs_performance_without_direct_evidence_is_safe_limitation() -> None:
    procedure = "원리금보장형 상품을 DC에서 퇴직급여지급 신청 시 특별중도해지1)가 적용되고, DC에서 IRP로 현물이전 후 중도해지 시 중도해지이자율이 적용됩니다."
    prospectus = "집합투자증권은 예금자보호법에 따라 보호되지 않는 실적배당상품이며 투자원금의 손실이 발생할 수 있습니다."
    assert excerpt_supports_product_type_comparison(procedure) is False
    assert excerpt_supports_product_type_comparison(prospectus) is False
    result = ToolResult(evidence=[
        _citation(procedure, citation_id="p1"),
        _citation(prospectus, citation_id="p2"),
    ])
    decision, _, context = _context(PRINCIPAL_VS_PERFORMANCE, result)
    assert decision.intent == "상품"
    assert context.response_mode == "limitation"
    assert "범위를 벗어나" not in context.fallback_message
    assert "[한계]" in context.fallback_message
    assert "무조건" not in context.fallback_message
    assert "고위험" not in context.fallback_message


def test_c9_receiving_scope_regression_unchanged() -> None:
    assert IntentRouter().classify(A).intent == "제도"
    _, generic_result, generic_ctx = _context(A)
    assert generic_ctx.response_mode == "clarification"
    assert generic_result.evidence == []
    _, _, national_ctx = _context(E)
    assert national_ctx.response_mode == "limitation"
    assert "국민연금" in national_ctx.fallback_message
    assert "55" not in national_ctx.fallback_message
    _, savings_result = _run(SAVINGS_RECEIVING)
    assert all(item.document_id != "doc10" for item in savings_result.evidence)
    _, irp_result = _run(D)
    assert all("IRP" in item.excerpt.upper() or "개인형" in item.excerpt for item in irp_result.evidence)


def test_live_savings_irp_comparison_keeps_supported_facts() -> None:
    decision, result, context = _context(SAVINGS_IRP)
    assert decision.intent == "제도"
    assert context.response_mode != "clarification"
    subtasks = {str(item.get("subtask")) for item in context.claim_plan}
    assert {"PENSION_SAVINGS_ELIGIBILITY", "IRP_ELIGIBILITY"} & subtasks
    assert "PENSION_SAVINGS_TAX_CREDIT_LIMIT" in subtasks
    assert "IRP_COMBINED_TAX_CREDIT_LIMIT" in subtasks
    body = client.get("/answer", params={"question_id": "C10-A", "question": SAVINGS_IRP}).json()
    answer = body["answer"]
    assert body["question"] == SAVINGS_IRP
    assert "제공된 근거 안에서만 답변할 수 있으며" not in answer or "가입" in answer
    assert "300만" not in answer
    assert "의무이전" not in answer
    assert "확정급여" not in answer
    assert "55세" not in answer
    assert "세액공제" in answer
    assert "600" in answer.replace(",", "")
    assert "900" in answer.replace(",", "")
    think = __import__("json").loads(body["think_trace"])
    assert think["intent"] == "제도"


def test_live_principal_vs_performance_in_scope_limitation() -> None:
    body = client.get("/answer", params={"question_id": "C10-B", "question": PRINCIPAL_VS_PERFORMANCE}).json()
    think = __import__("json").loads(body["think_trace"])
    assert think["intent"] != "범위 밖"
    assert think["intent"] == "상품"
    assert "범위를 벗어나" not in body["answer"]
    assert "[한계]" in body["answer"] or "확인" in body["answer"]
    assert "무조건 안전" not in body["answer"]
    assert "무조건 고위험" not in body["answer"]


def test_freeze_c1_c5_and_target_goldens() -> None:
    assert RETRIEVAL_MIN_SCORE == 0.01
    assert RETRIEVAL_MIN_QUERY_COVERAGE == 0.51
    assert IntentRouter().classify(DB_DC).intent == "제도"
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
    _, g081_public = _public(G081, "G081")
    assert g081_public.answer
    _, _, _, g099_ctx = grounded(G099)
    assert g099_ctx.claim_plan or g099_ctx.fallback_message
