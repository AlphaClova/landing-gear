import pytest

from app.agent.composer import Composer
from app.agent.hcx_client import HCXClient
from app.agent.router import IntentRouter
from app.agent.slots import SlotManager
from app.agent.tools import BEvidenceProvider, BProductCatalog, BRuleEngine, ToolRouter
from app.agent.verifier import Verifier
from app.agent.composer import Draft, GroundedContext
from app.core.config import Settings
from app.core.query_normalization import procedure_type, tax_intent


RULE_IDS = {"세제": "retirement_income_tax", "종합": "lump_sum_vs_pension"}


def grounded(question: str):
    decision = IntentRouter().classify(question)
    slots = SlotManager.extract(question)
    tools = ToolRouter(BEvidenceProvider(), BRuleEngine(), BProductCatalog())
    result = tools.run(decision.intent, slots, question=question, rule_id=RULE_IDS.get(decision.intent))
    composer = Composer(HCXClient(Settings(hcx_api_key="")))
    return decision, slots, result, composer.build_context(question, decision.intent, result)


def test_false_premise_dc_responsibility_is_corrected() -> None:
    _, _, _, context = grounded("DC형 운용 결과를 회사가 보장하고 책임지나요?")
    assert context.false_premise
    assert "아닙니다" in context.fallback_message
    assert "근로자가 직접 운용" in context.fallback_message


def test_db_dc_direct_question_preserves_comparison_contract() -> None:
    _, _, result, context = grounded("DB형과 DC형은 퇴직급여가 정해지는 방식과 운용 주체가 어떻게 다른가요?")
    assert result.procedure_type is None
    assert any(item["subtask"] == "db_dc_difference" for item in context.claim_plan)
    assert "확정급여형(DB)" in context.fallback_message
    assert "확정기여형(DC)" in context.fallback_message
    assert "해지 절차" not in context.fallback_message


def test_db_dc_fact_inversion_is_rejected_and_repaired() -> None:
    _, _, result, context = grounded("DB와 DC의 퇴직급여 결정 방식과 운용 주체를 비교해 주세요")
    draft = Draft(
        message="DB는 가입자가 직접 운용하고 DC는 회사가 직접 운용합니다.",
        citations=result.evidence,
        context=context,
    )
    verifier = Verifier()
    issues = verifier.check(draft)
    assert "DB/DC fact inversion" in issues
    assert verifier.repair_safe(draft, issues)
    assert draft.message == context.fallback_message


def test_irp_only_nine_million_tax_credit_limit_semantics() -> None:
    _, _, _, context = grounded("연금저축 없이 IRP에만 900만원을 납입하면 공제 대상 한도는 어떻게 되나요?")
    assert "900만원은 세액공제 대상 납입액 한도 안" in context.fallback_message
    assert "900만원만큼 세금이 줄어든다는 뜻이 아닙니다" in context.fallback_message


def test_combined_withdrawal_comparison_preserves_answerable_rate_subtask() -> None:
    decision, _, _, context = grounded("DC 퇴직급여를 IRP로 이전한 뒤 10년과 21년 수령 조건을 비교해 주세요")
    assert decision.intent == "종합"
    assert "70%" in context.fallback_message and "50%" in context.fallback_message
    assert "예상 퇴직소득세가 필요" in context.fallback_message
    assert "IRP로 이전" in context.fallback_message


def test_tax_sources_are_separated() -> None:
    _, _, result, context = grounded("퇴직금과 개인 납입금이 함께 있는 IRP의 과세 재원을 구분해 주세요")
    assert set(result.tax_source_types) == {"NON_DEDUCTED_CONTRIBUTION", "DEDUCTED_CONTRIBUTION_AND_EARNINGS", "DEFERRED_RETIREMENT_INCOME"}
    assert "같은 세율로 취급하지 않습니다" in context.fallback_message
    assert "3.3~5.5%는 퇴직금 재원 자체의 세율" in context.fallback_message


def test_zero_deferred_tax_is_valid_rule_input() -> None:
    _, slots, result, context = grounded("퇴직금 3억원, 예상 퇴직소득세 0원인 IRP의 일시금과 연금을 비교해 주세요")
    assert slots["expected_tax_won"] == 0
    assert result.withdrawal_result is not None
    assert {x.tax_value for x in result.withdrawal_result.comparison.scenarios} == {0}
    assert "퇴직소득세 0KRW" in context.fallback_message


def test_retirement_withdrawal_tax_does_not_route_to_tax_credit() -> None:
    question = "예상 퇴직소득세를 기준으로 10년과 21년 연금수령 부담을 비교하고 싶어요"
    assert tax_intent(question) == "PENSION_WITHDRAWAL_TAX"
    assert IntentRouter().classify(question).intent == "종합"


def test_teacher_scope_is_not_applied_to_general_employee() -> None:
    _, _, result, context = grounded("일반 근로자의 명예퇴직금과 법정퇴직금을 다른 계좌로 받을 수 있나요?")
    assert all(item.document_id != "doc26" for item in result.evidence)
    assert "교사·공무원 전용 자료" in context.fallback_message


@pytest.mark.parametrize("question", [
    "명퇴 예정인 교사인데 명퇴수당 절세 방법 알려줘",
    "교직원 명예퇴직수당을 연금계좌에 넣을 수 있나요?",
    "공무원 명퇴수당을 받은 뒤 세금 환급 절차가 있나요?",
])
def test_population_specific_retirement_claims_are_preserved(question: str) -> None:
    _, _, result, context = grounded(question)
    assert result.evidence[0].document_id == "doc26"
    assert {item["subtask"] for item in context.claim_plan} >= {
        "benefit_legal_character", "account_transfer_or_deposit",
        "tax_refund_procedure", "retirement_tax_effect",
    }
    assert "60일" in context.fallback_message
    assert "퇴직소득세 환급" in context.fallback_message


def test_general_employee_does_not_receive_teacher_public_official_rule() -> None:
    _, _, result, context = grounded("일반 회사원 명예퇴직금 절세 알려줘")
    assert all(item.document_id != "doc26" for item in result.evidence)
    assert "공무원연금공단" not in context.fallback_message


def test_executive_does_not_receive_teacher_public_official_rule() -> None:
    _, _, result, context = grounded("임원 퇴직금 IRP 절세 알려줘")
    assert all(item.document_id != "doc26" for item in result.evidence)
    assert "공무원연금공단" not in context.fallback_message


def test_termination_is_not_early_withdrawal() -> None:
    _, _, _, context = grounded("퇴직연금 계약 해지 절차를 확인하고 싶습니다")
    assert procedure_type(context.question) == "ACCOUNT_TERMINATION"
    assert "개인회생·파산 서류를 일반 해지 절차로 적용하지 않습니다" in context.fallback_message


def test_irp_opening_does_not_reuse_benefit_receipt_documents() -> None:
    _, _, _, context = grounded("신규 IRP 계좌 개설 서류 목록을 알려주세요")
    assert "신규 계좌 개설에 필요한 서류 목록을 직접 확인할 수 없습니다" in context.fallback_message
    assert "퇴직급여신청서와 IRP가입확인서" in context.fallback_message


def test_dc_to_pension_saving_uses_irp_transfer_path() -> None:
    _, _, _, context = grounded("DC 적립금을 퇴직 뒤 연금저축으로 이전해 운용할 수 있나요?")
    assert "먼저 IRP로 이전" in context.fallback_message
    assert "연금저축으로 계약이전" in context.fallback_message


def test_product_fact_does_not_manufacture_fee_fields() -> None:
    _, _, result, _ = grounded("솔로몬 단기 국공채 상품의 위험과 비용을 문서 기준으로 설명해 주세요")
    assert result.products
    assert all("sales_fee" not in item and "total_cost" not in item for item in result.products)


def test_complete_recommendation_slots_query_products() -> None:
    _, slots, result, context = grounded("IRP에서 3년 운용할 낮은 위험 상품 후보를 보여주세요")
    assert slots["investment_horizon"] == 3 and slots["risk_tolerance"] == "stable"
    assert 1 <= len(result.products) <= 5
    assert all(item["risk_level"] >= 5 and "IRP" in item["plan_types"] for item in result.products)
    assert "제공된 Product Fact" in context.fallback_message


def test_future_return_refusal_has_no_generic_advice() -> None:
    _, _, _, context = grounded("자료에 없는 미래 수익률을 숫자로 만들어 주세요")
    assert "예측할 수 없습니다" in context.fallback_message
    assert "전문가" not in context.fallback_message and "신중" not in context.fallback_message


def test_tax_saving_needs_tax_but_not_retirement_amount() -> None:
    missing = SlotManager().required("종합", {}, "퇴직소득세만 알고 퇴직금은 몰라요. 연금 절세액 계산해줘")
    assert [item.name for item in missing] == ["expected_tax_won"]


def test_receipt_account_and_tax_both_survive() -> None:
    _, _, _, context = grounded("55세 DB 가입자의 퇴직금 수령계좌와 세금 차이를 같이 설명해줘")
    assert "수령 가능 계좌" in context.fallback_message
    assert "70%·60%·50%" in context.fallback_message


def test_liquidity_is_not_invented_from_tax_schedule() -> None:
    _, _, _, context = grounded("연금 10년 수령과 21년 수령의 세금 및 유동성 차이를 비교해줘")
    assert "실제 유동성 차이" in context.fallback_message
    assert "수령 일정을 정하기 전에는 단정할 수 없습니다" in context.fallback_message


def test_zero_tax_does_not_imply_annuity_always_wins() -> None:
    _, _, _, context = grounded("퇴직금 3억, 세금 0원, IRP인데 연금이 무조건 유리한가요?")
    assert "모두 0원" in context.fallback_message
    assert "무조건 유리하다고 결론낼 수 없습니다" in context.fallback_message


def test_single_metric_product_selection_is_refused() -> None:
    _, _, _, context = grounded("보수보다 과거수익률만 보고 하나 골라줘")
    assert "과거수익률 한 항목만으로" in context.fallback_message


def test_answerable_subtasks_survive_deterministic_fallback() -> None:
    _, _, _, context = grounded("55세 DB 가입자의 퇴직금 수령계좌와 세금 차이를 같이 설명해줘")
    answerable = [item for item in context.claim_plan if item["status"] == "answerable"]
    assert {item["subtask"] for item in answerable} >= {"account_receipt", "retirement_tax"}
    assert all(claim["text"] in context.fallback_message for item in answerable for claim in item["claims"])


def test_multi_intent_keeps_transfer_when_tax_detail_is_limited() -> None:
    _, _, _, context = grounded("DC 가입자가 퇴직 후 연금저축에서 운용하려면 절차와 세금은?")
    assert "먼저 IRP로 이전" in context.fallback_message
    assert "실제 세액 계산에는 예상 퇴직소득세" in context.fallback_message


def test_three_tax_sources_are_present_in_claim_plan() -> None:
    _, _, result, context = grounded("퇴직금과 개인납입금이 섞인 IRP의 과세를 구분해줘")
    assert len(result.tax_source_types) == 3
    assert any(item["subtask"] == "tax_source_separation" for item in context.claim_plan)
    assert "3.3~5.5%는 퇴직금 재원 자체의 세율로 적용하지 않습니다" in context.fallback_message


def test_zero_rule_results_are_rendered_not_treated_as_missing() -> None:
    _, _, result, context = grounded("퇴직금 3억, 세금 0원, IRP인데 연금이 무조건 유리한가요?")
    assert result.withdrawal_result is not None
    assert [item.tax_value for item in result.withdrawal_result.comparison.scenarios] == [0, 0, 0]
    assert context.fallback_message.count("퇴직소득세 0KRW") == 3
    assert "퇴직소득세 절감액도 0원" in context.fallback_message


def test_requested_product_cost_is_value_or_explicit_limitation() -> None:
    _, _, _, context = grounded("솔로몬 국공채 중장기형의 위험과 비용을 알려줘")
    cost = next(item for item in context.claim_plan if item["subtask"] == "product_cost")
    assert cost["status"] in {"answerable", "unsupported"}
    assert (cost.get("claims") and "총보수" in cost["claims"][0]["text"]) or "확인하지 못했습니다" in cost.get("limitation", "")


def test_unapplied_horizon_constraint_is_disclosed() -> None:
    _, _, result, context = grounded("IRP에서 3년 투자할 안정형 상품 후보를 보여줘")
    horizon = next(item for item in result.recommendation_constraints if str(item["constraint"]).startswith("investment_horizon="))
    assert horizon["applied"] is False
    assert "3y 투자기간 적합성을 직접 판정할 공식 field가 없어" in context.fallback_message
    assert "3년 투자할 안정형 상품 후보" not in context.fallback_message


def test_grounded_fallback_does_not_add_generic_advice() -> None:
    _, _, _, context = grounded("IRP에서 3년 투자할 안정형 상품 후보를 보여줘")
    assert not any(marker in context.fallback_message for marker in ("전문가", "신중하게", "장기적 관점"))


def test_product_fact_contract_preserves_risk_scale_direction() -> None:
    _, _, _, context = grounded("솔로몬 국공채 단기 중장기 장기의 차이를 알려줘")
    assert "핵심 grounded contract 변경 또는 일부 누락" in context.forbidden_behaviors
    assert "1등급이 매우 높은 위험" in context.fallback_message
    assert "6등급이 매우 낮은 위험" in context.fallback_message
    assert "숫자가 작을수록 위험이 낮" not in context.fallback_message


def test_three_explicit_product_entities_are_resolved() -> None:
    _, _, result, context = grounded("솔로몬 국공채 단기형과 중장기형, 장기형은 어떤 차이가 있나요?")
    assert [item["entity"] for item in result.product_resolutions] == ["단기", "중장기", "장기"]
    assert all(item["status"] == "RESOLVED" for item in result.product_resolutions)
    names = [item["product_name"] for item in result.products]
    assert len(names) == 3
    assert any("단기국공채" in name and "초단기" not in name for name in names)
    assert any("중장기국공채" in name for name in names)
    assert any("장기국공채" in name and "중장기" not in name for name in names)
    assert all(name in context.fallback_message for name in names)


def test_missing_explicit_product_keeps_resolved_products_and_local_limitation() -> None:
    class MissingLongCatalog(BProductCatalog):
        def query_products(self, *, plan_type=None, category=None):
            return [item for item in super().query_products(plan_type=plan_type, category=category)
                    if "장기국공채" not in item["product_name"] or "중장기" in item["product_name"]]

    question = "솔로몬 국공채 단기형과 중장기형, 장기형을 비교해 주세요"
    decision = IntentRouter().classify(question)
    result = ToolRouter(BEvidenceProvider(), BRuleEngine(), MissingLongCatalog()).run(
        decision.intent, SlotManager.extract(question), question=question
    )
    context = Composer(HCXClient(Settings(hcx_api_key=""))).build_context(question, decision.intent, result)
    assert len(result.products) == 2
    assert {item["status"] for item in result.product_resolutions} == {"RESOLVED", "NOT_FOUND"}
    assert "장기 상품은 현재 Product Fact에서 확인되지 않습니다" in context.fallback_message


def test_tax_credit_intent_does_not_change_to_retirement_tax() -> None:
    _, _, result, context = grounded("IRP는 1년에 1,800만원 전부 세액공제되죠?")
    assert result.tax_intent == "TAX_CREDIT"
    assert "600만원" in context.fallback_message and "900만원" in context.fallback_message
    assert "이연퇴직소득세" not in context.fallback_message


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("확정기여형 성과는 고용주가 보장하는 구조인가요?", "근로자가 직접 운용"),
        ("DC 계좌 수익률 책임이 전부 회사에 있나요?", "아닙니다"),
        ("확정기여 제도에서 회사가 운용을 책임지나요?", "최종 퇴직급여"),
        ("개인연금 없이 IRP만 연 900만원 넣을 때 납입한도는?", "합산 한도"),
        ("IRP 공제대상 납입액과 실제 환급액은 같은 뜻인가요?", "실제 세액공제 금액"),
        ("연금계좌 공제 상한과 줄어드는 세금을 나눠 설명해 주세요", "납부할 세액"),
        ("DC 자금을 IRP로 넘긴 뒤 장기 연금수령 세율 구조도 알려주세요", "IRP로 이전"),
        ("DB와 DC의 급여 결정 방식 및 퇴직 후 이전을 함께 설명해 주세요", "확정급여형"),
        ("수령계좌 안내와 퇴직소득 과세 차이를 같이 보고 싶습니다", "수령 가능 계좌"),
        ("퇴직재원 연금수령 기간별 납부비율과 유동성 한계를 구분해 주세요", "70%"),
        ("IRP 이동, 상품 선택, 연금 시작 단계를 나눠 주세요", "별도 단계"),
        ("솔로몬 중장기 국공채의 확인 가능한 사실만 알려주세요", "Product Fact"),
        ("IRP에서 손실위험이 낮은 채권 후보를 3년 조건으로 찾고 싶습니다", "Product Fact"),
        ("근거 없는 장래 펀드 수익률 수치를 요구하면 어떻게 답하나요?", "예측할 수 없습니다"),
        ("솔로몬 장기 국공채 상품들을 문서 사실로 비교해 주세요", "위험등급"),
        ("국공채 펀드 비용 값이 없으면 추정해서 채워도 되나요?", "한계"),
        ("연금계좌 계약을 끝내는 절차가 궁금합니다", "계약 유형"),
        ("IRP를 처음 만들 때 필요한 서류가 자료에 있나요?", "직접 확인할 수 없습니다"),
        ("DC 퇴직재원을 연금저축으로 이동하는 순서를 알려주세요", "먼저 IRP"),
        ("IRP 일부 중도인출과 계좌 전체 해지를 구분해 주세요", "구분해야 합니다"),
        ("연금 지급을 시작하는 단계와 계좌 이전을 따로 설명해 주세요", "연금 개시"),
    ],
)
def test_blind_content_generalization(question: str, expected: str) -> None:
    _, _, _, context = grounded(question)
    assert expected in context.fallback_message
