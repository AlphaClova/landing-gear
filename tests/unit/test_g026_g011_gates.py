"""Generalized G026/G011 gates: tax source contract and evidence-before-limitation."""

from app.agent.canonical import answer_affirms_false_premise, answer_asserts_false_numeric_premise
from app.agent.composer import Draft, GroundedContext
from app.agent.verifier import Verifier
from app.api.schemas import Citation
from app.core.query_normalization import tax_intent
from tests.unit.test_content_p0_policies import grounded


def test_direct_eligibility_threshold_is_kept_in_final_contract() -> None:
    _, _, result, context = grounded("주 14시간 근무자도 퇴직연금 대상인가요?")
    assert any("15시간" in item.excerpt for item in result.evidence)
    hours = next(item for item in context.claim_plan if item["subtask"] == "eligibility_hours")
    assert hours["status"] == "answerable"
    assert hours["claims"][0]["source_type"] == "evidence"
    assert "15시간 이상" in context.fallback_message
    assert "14시간" in context.fallback_message


def test_direct_evidence_is_not_replaced_by_generic_limitation() -> None:
    _, _, _, context = grounded("주 14시간 근무자도 퇴직연금 대상인가요?")
    assert not context.fallback_message.startswith("[한계] 제공된 근거 안에서만")
    draft = Draft(
        message="[한계] 제공된 근거 안에서만 답변할 수 있으며, 확인되지 않은 내용은 단정할 수 없습니다.",
        citations=context.evidence,
        context=context,
    )
    issues = Verifier().check(draft)
    assert issues
    assert Verifier().repair_safe(draft, issues)
    assert "15시간" in draft.message
    assert not draft.message.startswith("[한계] 제공된 근거 안에서만")


def test_partial_supported_answer_keeps_local_limitation() -> None:
    _, _, _, context = grounded("퇴직금을 일시금으로 받으면 세율이 무조건 16.5%인가요?")
    assert "100%" in context.fallback_message
    assert "[한계]" in context.fallback_message
    assert "건강보험" not in context.fallback_message


def test_tax_numeric_without_evidence_or_rule_is_rejected() -> None:
    context = GroundedContext(
        question="퇴직소득세 부담이 어떻게 되나요?",
        intent="세제",
        response_mode="result",
        fallback_message="[한계] 제공된 자료만으로 해당 세율은 확인할 수 없습니다.",
        limitations=["[한계] 제공된 자료만으로 해당 세율은 확인할 수 없습니다."],
        allowed_numbers=[],
    )
    draft = Draft(message="일시금 세율은 22.0%입니다.", context=context)
    issues = Verifier().check(draft)
    assert any("근거 없는 숫자" in item or item == "unsupported factual claim" for item in issues)


def test_tax_factual_claim_without_evidence_is_rejected() -> None:
    context = GroundedContext(
        question="퇴직금을 일시금으로 받으면 어떻게 과세되나요?",
        intent="세제",
        response_mode="result",
        fallback_message="[한계] 제공된 자료만으로 해당 세율은 확인할 수 없습니다.",
        limitations=["[한계] 제공된 자료만으로 해당 세율은 확인할 수 없습니다."],
    )
    draft = Draft(message="일시금은 분리과세로 일괄 종결됩니다.", context=context, citations=[])
    issues = Verifier().check(draft)
    assert issues


def test_wrong_tax_subtype_rate_is_not_claimed() -> None:
    assert tax_intent("퇴직금을 일시금으로 받으면 세율이 무조건 16.5%인가요?") == "RETIREMENT_INCOME_TAX"
    _, _, result, context = grounded("퇴직금을 일시금으로 받으면 세율이 무조건 16.5%인가요?")
    assert context.false_premise
    assert "아닙니다" in context.fallback_message
    draft = Draft(
        message="퇴직금을 일시금으로 수령할 때 적용되는 세율은 기본적으로 16.5%입니다.",
        citations=result.evidence,
        context=context,
    )
    issues = Verifier().check(draft)
    assert "false-premise affirmation" in issues or "unsupported factual claim" in issues or "핵심 grounded contract 변경 또는 일부 누락" in issues
    assert Verifier().repair_safe(draft, issues)
    assert not answer_affirms_false_premise(draft.message)
    assert not answer_asserts_false_numeric_premise(draft.message, "16.5")
    assert "16.5%입니다" not in draft.message.replace(" ", "")


def test_health_insurance_without_question_support_is_removed() -> None:
    citation = Citation(
        id="e1", document_id="doc51", page=1, section="s", source="s",
        excerpt="일시금으로 받으면 퇴직소득세를 100% 즉시 납부해야한다. 건강보험료에 영향을 준다.",
        source_priority=0, score=1.0,
    )
    context = GroundedContext(
        question="퇴직금을 일시금으로 받으면 세율이 무조건 16.5%인가요?",
        intent="세제",
        response_mode="result",
        evidence=[citation],
        fallback_message="아닙니다. 일시금으로 받으면 퇴직소득세를 100% 납부합니다.",
        required_facts=["아닙니다. 일시금으로 받으면 퇴직소득세를 100% 납부합니다."],
        allowed_numbers=["100%"],
        forbidden_behaviors=["핵심 grounded contract 변경 또는 일부 누락"],
        correction_fact="아닙니다. 일시금으로 받으면 퇴직소득세를 100% 납부합니다.",
        false_premise="퇴직금을 일시금으로 받으면 세율이 무조건 16.5%인가요?",
    )
    draft = Draft(
        message="일시금은 100%입니다. 건강보험료가 줄어듭니다.",
        citations=[citation],
        context=context,
    )
    issues = Verifier().check(draft)
    assert "unsupported factual claim" in issues
    assert Verifier().repair_safe(draft, issues)
    assert "건강보험" not in draft.message


def test_hcx_unsupported_percentage_is_stripped_from_final_contract() -> None:
    _, _, result, context = grounded("퇴직금을 일시금으로 받으면 세율이 무조건 16.5%인가요?")
    draft = Draft(
        message="세율은 기본적으로 16.5%입니다. 건강보험료가 부과될 수 있습니다.",
        citations=result.evidence,
        context=context,
    )
    issues = Verifier().check(draft)
    assert issues
    assert Verifier().repair_safe(draft, issues)
    assert "건강보험" not in draft.message
    assert not answer_asserts_false_numeric_premise(draft.message, "16.5")
