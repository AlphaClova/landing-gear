import json
from pathlib import Path

from app.agent.router import IntentRouter
from app.agent.slots import SlotManager
from app.agent.composer import Composer, Draft
from app.agent.tools import ToolResult
from app.agent.verifier import Verifier
from app.api.schemas import Citation
from app.api.schemas import CalculationResult


def _cases():
    return [json.loads(x) for x in Path("tests/golden/official_paraphrase_15.jsonl").read_text(encoding="utf-8").splitlines()]


def test_official_paraphrases_use_generalized_intents():
    router = IntentRouter()
    for case in _cases():
        assert router.classify(case["question"]).intent == case["expected_intent"], case["id"]


def test_closed_questions_skip_unrelated_slots_and_recommendations_ask_three():
    router, slots = IntentRouter(), SlotManager()
    for case in _cases():
        decision = router.classify(case["question"])
        missing = slots.required(decision.intent, {}, case["question"])
        if case["expected_response_type"] == "clarification":
            expected = {"investment_horizon", "risk_tolerance"}
            if "IRP" not in case["question"].upper():
                expected.add("plan_type")
            assert {x.name for x in missing} == expected
        else:
            assert missing == [], case["id"]


def test_recommendation_does_not_ask_for_plan_type_already_in_question():
    missing = SlotManager().required("상품", {}, "내게 맞는 IRP 상품 하나 정해줘. 다른 정보는 아직 없어.")
    assert [slot.name for slot in missing] == ["investment_horizon", "risk_tolerance"]


def test_numeric_grounding_canonicalizes_korean_won_units():
    verifier = Verifier()
    assert verifier._normalize("900만원") == verifier._normalize("9,000,000원")
    assert verifier._normalize("9,000,000원") == verifier._normalize("9000000")
    assert verifier._normalize("901만원") != verifier._normalize("9000000")


def test_withdrawal_answer_rejects_money_not_returned_by_rule():
    draft = Draft(
        message="계산 결과는 300만원입니다.",
        citations=[Citation(id="c1", document_id="doc51", page=1, source="doc51", excerpt="퇴직소득세 안내")],
        calculation_results=[CalculationResult(rule_id="r", label="tax", value=2_400_000, unit="원")],
    )
    # Context-based enforcement is exercised through the real Composer contract.
    class EchoHCX:
        last_attempts = 1
        last_success = True
        def complete(self, *args, **kwargs):
            return "계산 결과는 300만원입니다."
    composed = Composer(EchoHCX()).compose(
        "퇴직금과 세금으로 비교해줘", "종합", ToolResult(
            evidence=draft.citations, calculations=draft.calculation_results
        )
    )
    assert "Rule 밖 금액 계산" in Verifier().check(composed)


def test_unrelated_substring_does_not_turn_institution_question_into_procedure():
    decision = IntentRouter().classify("DC와 DB 퇴직금이 정해지는 방식은?")
    assert decision.intent == "제도"


def test_false_premise_policy_does_not_accept_exaggerated_teacher_tax_claim():
    message = Composer._apply_behavior_policy(
        "퇴직하는 선생님인데 명퇴금 절세가 엄청나다는 말이 맞나요?",
        ToolResult(),
        "절세 효과가 있습니다.",
    )
    assert "[주의]" in message
    assert "단정할 수 없습니다" in message
    assert "법적 성격" in message

    paraphrase = Composer._apply_behavior_policy(
        "명퇴수당의 연금계좌 절세 효과를 과장 없이 설명해 주세요.", ToolResult(), "절세 효과입니다."
    )
    assert "[주의]" in paraphrase


def test_product_period_comparison_discloses_missing_fact_dimensions():
    result = ToolResult(products=[{"product_id": "p1"}])
    message = Composer._apply_behavior_policy(
        "국공채 단기와 장기의 안정성 차이를 비교해줘.", result, "두 상품을 비교했습니다."
    )
    assert "[한계]" in message
    assert "듀레이션" in message
    assert "확정할 수 없습니다" in message

    period_wording = Composer._apply_behavior_policy(
        "국공채 기간별 상품 차이와 위험등급은?", result, "상품 정보입니다."
    )
    assert "[한계]" in period_wording


def test_db_dc_policy_uses_only_documented_core_distinction():
    evidence = Citation(id="doc10-c1", document_id="doc10", page=1, source="doc10", excerpt="DB와 DC 근거")
    assert Composer._is_db_dc_explanation("DB와 DC 차이는?", ToolResult(evidence=[evidence]))


def test_grounded_closed_answer_calls_hcx_with_grounding_contract():
    class RecordingHCX:
        last_attempts = 1
        last_success = True
        called = False
        def complete(self, *args, **kwargs):
            self.called = True
            return "연금저축은 600만원, IRP 포함 합산은 900만원입니다. 세액공제율은 16.5% 또는 13.2%입니다."

    evidence = Citation(
        id="doc41-c1",
        document_id="doc41",
        page=1,
        source="doc41",
        excerpt="연금저축 600만원, IRP 합산 900만원, 16.5% 또는 13.2%",
    )
    hcx = RecordingHCX()
    draft = Composer(hcx).compose(
        "연금저축과 IRP 세액공제 한도는?", "세제", ToolResult(evidence=[evidence])
    )
    assert "600만원" in draft.message and "900만원" in draft.message
    assert hcx.called and draft.hcx_invoked and draft.hcx_success


def test_verifier_detects_claim_that_contradicts_prior_limitation():
    assert Verifier._contradicts_limitation(
        "[한계] 안정성 우열을 확정할 수 없습니다. 따라서 단기 상품이 더 안정적입니다."
    )
    assert Verifier._contradicts_limitation(
        "[주의] 적용 여부를 확인할 수 없습니다. 네, 매우 효과적입니다."
    )
    assert not Verifier._contradicts_limitation("[한계] 안정성 우열을 확정할 수 없습니다.")


def test_verifier_flags_company_size_generalization_without_evidence():
    draft = Draft(
        message="DC는 중소기업과 스타트업에서 선호됩니다.",
        citations=[Citation(id="c1", document_id="doc10", page=1, source="doc10", excerpt="DB와 DC 정의")],
    )
    assert "근거 없는 일반화('중소기업')" in Verifier()._check(draft)
