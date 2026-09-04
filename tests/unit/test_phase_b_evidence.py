from app.agent.router import IntentRouter
from app.api.schemas import to_eval_response
from tests.contract.test_public_evidence_pruning_gates import _public
from tests.unit.test_content_p0_policies import grounded

R06 = "IRP는 어떤 계좌인가요?"
R07 = "연금저축과 IRP는 뭐가 다른가요?"
R14 = "퇴직한 뒤 IRP로 옮길 수 있나요?"
R11 = "퇴직금을 IRP에 넣으면 세금은 어떻게 되나요?"
R15 = "명퇴수당을 받은 뒤 연금계좌에 넣을 수 있나요?"
R16 = "위험등급 5등급은 어떤 의미인가요?"


def test_phase_b_router_intents_stay_frozen() -> None:
    router = IntentRouter()
    assert router.classify("DC형에서는 제가 직접 투자하나요?").intent == "제도"
    assert router.classify(R06).intent == "제도"
    assert router.classify(R07).intent == "제도"
    assert router.classify(R14).intent == "절차"


def test_r06_relevant_irp_institution_evidence() -> None:
    _, public = _public(R06, "R06")
    assert public.answer
    assert "[DOC" in public.retrieved_context
    assert "IRP" in public.retrieved_context.upper()
    assert "계좌" in public.retrieved_context or "개인형" in public.retrieved_context
    assert "계좌번호" not in public.retrieved_context
    assert "고객등록" not in public.retrieved_context


def test_r07_institution_comparison_evidence() -> None:
    _, public = _public(R07, "R07")
    assert "[DOC" in public.retrieved_context
    assert "연금저축" in public.retrieved_context
    assert "IRP" in public.retrieved_context.upper()


def test_r14_transfer_procedure_evidence() -> None:
    _, public = _public(R14, "R14")
    assert "[DOC" in public.retrieved_context
    assert "IRP" in public.retrieved_context.upper()
    assert any(term in public.retrieved_context for term in ("이전", "입금", "이동"))


def test_r11_unrelated_doc55_public_evidence_removed() -> None:
    _, public = _public(R11, "R11")
    ctx = public.retrieved_context
    assert "승진" not in ctx
    assert "고객등록" not in ctx
    assert "계좌번호" not in ctx
    assert "가입자정보" not in ctx
    if ctx:
        assert any(term in ctx for term in ("퇴직소득세", "과세", "의무이전", "의무 이전", "IRP"))


def test_r15_teacher_only_and_pii_evidence_removed() -> None:
    _, public = _public(R15, "R15")
    ctx = public.retrieved_context
    assert "교사" not in ctx
    assert "공무원" not in ctx
    assert "개인정보" not in ctx
    assert "고객등록" not in ctx
    assert "계좌번호" not in ctx
    assert "doc26" not in ctx


def test_r16_generic_risk_question_has_no_arbitrary_named_product() -> None:
    decision, _, result, context = grounded(R16)
    assert decision.intent == "상품"
    assert result.products == []
    assert "한국투자" not in context.fallback_message
    assert "골드플랜" not in context.fallback_message
    _, public = _public(R16, "R16")
    assert "한국투자" not in public.answer
    assert "골드플랜" not in public.answer
    assert "한국투자" not in public.retrieved_context
    assert "상품명:" not in public.retrieved_context
    assert "1등급이 매우 높은 위험" not in public.answer
    assert "5등급이 낮은 위험" not in public.answer
