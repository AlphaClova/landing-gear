"""Tax-scope injection: 70/60/50 pension-year rates only for pension receipt."""

from app.agent.verifier import Verifier
from app.agent.composer import Draft
from app.core.query_normalization import (
    ACCOUNT_TERMINATION_TAX,
    EARLY_WITHDRAWAL_TAX,
    RETIREMENT_LUMP_SUM_TAX,
    RETIREMENT_PENSION_RECEIPT_TAX,
    TAX_CREDIT,
    UNKNOWN_TAX,
    pension_year_rate_block_allowed,
    tax_intent,
)
from tests.unit.test_content_p0_policies import grounded

PENSION_YEAR_MARKERS = ("70%", "60%", "50%")


def _has_year_rate_block(text: str) -> bool:
    compact = text.replace(" ", "")
    return all(marker in compact for marker in PENSION_YEAR_MARKERS)


def test_a_early_withdrawal_does_not_inject_pension_year_block() -> None:
    question = "55세 전에 IRP에서 중도인출하면 세금은?"
    assert tax_intent(question) == EARLY_WITHDRAWAL_TAX
    assert not pension_year_rate_block_allowed(tax_intent(question))
    _, _, result, context = grounded(question)
    assert result.tax_intent == EARLY_WITHDRAWAL_TAX
    assert result.procedure_type == "EARLY_WITHDRAWAL"
    assert not _has_year_rate_block(context.fallback_message)
    assert "3.3" not in context.fallback_message
    assert "16.5" not in context.fallback_message
    assert any(item["subtask"] == "early_withdrawal_tax_detail" for item in context.claim_plan)


def test_g031_paraphrase_keeps_early_withdrawal_scope() -> None:
    question = "55세 전에 IRP에서 찾으면 어떤 세금이 생기나요?"
    assert tax_intent(question) == EARLY_WITHDRAWAL_TAX
    _, _, result, context = grounded(question)
    assert result.tax_intent == EARLY_WITHDRAWAL_TAX
    assert result.procedure_type == "EARLY_WITHDRAWAL"
    assert not _has_year_rate_block(context.fallback_message)
    assert "연금수령 연차" in context.fallback_message or "중도인출" in context.fallback_message


def test_b_account_termination_does_not_inject_pension_year_block() -> None:
    question = "IRP 해지하면 세금은?"
    assert tax_intent(question) == ACCOUNT_TERMINATION_TAX
    _, _, result, context = grounded(question)
    assert result.tax_intent == ACCOUNT_TERMINATION_TAX
    assert not _has_year_rate_block(context.fallback_message)


def test_c_lump_sum_does_not_inject_pension_year_block() -> None:
    question = "퇴직금을 일시금으로 받으면 세금?"
    assert tax_intent(question) == RETIREMENT_LUMP_SUM_TAX
    _, _, _, context = grounded(question)
    assert not _has_year_rate_block(context.fallback_message)


def test_d_ten_year_pension_receipt_may_use_70_percent() -> None:
    question = "IRP에서 10년 동안 연금으로 받으면?"
    assert tax_intent(question) == RETIREMENT_PENSION_RECEIPT_TAX
    _, _, result, context = grounded(question)
    assert result.tax_intent == RETIREMENT_PENSION_RECEIPT_TAX
    assert "70%" in context.fallback_message


def test_e_year_21_pension_receipt_may_use_50_percent() -> None:
    question = "21년차 연금수령 세금은?"
    assert tax_intent(question) == RETIREMENT_PENSION_RECEIPT_TAX
    _, _, _, context = grounded(question)
    assert "50%" in context.fallback_message


def test_f_underspecified_irp_tax_does_not_invent_year_block() -> None:
    question = "IRP 세금 알려줘"
    assert tax_intent(question) == UNKNOWN_TAX
    _, _, result, context = grounded(question)
    assert result.tax_intent == UNKNOWN_TAX
    assert not _has_year_rate_block(context.fallback_message)


def test_g_tax_credit_does_not_inject_pension_year_block() -> None:
    question = "연금저축이랑 IRP에 넣으면 세액공제 얼마까지 되나요? 다 합쳐서요."
    assert tax_intent(question) == TAX_CREDIT
    _, _, _, context = grounded(question)
    assert not _has_year_rate_block(context.fallback_message)
    assert "600만원" in context.fallback_message
    assert "900만원" in context.fallback_message


def test_h_mixed_evidence_does_not_use_off_scope_year_rates() -> None:
    question = "55세 전에 IRP에서 중도인출하면 세금은?"
    _, _, result, context = grounded(question)
    assert "retirement_tax" not in {item["subtask"] for item in context.claim_plan}
    assert not _has_year_rate_block(context.fallback_message)
    draft = Draft(
        message="퇴직금 재원의 일시금 수령에는 퇴직소득세율 100%가 적용되고, 연금수령에는 실제수령연차에 따라 이연퇴직소득세의 70%·60%·50%가 적용됩니다.",
        citations=result.evidence,
        context=context,
    )
    issues = Verifier().check(draft)
    assert "wrong tax scope" in issues
    assert Verifier().repair_safe(draft, issues)
    assert not _has_year_rate_block(draft.message)


def test_receipt_account_tax_difference_is_pension_receipt_scope() -> None:
    question = "55세 DB 가입자입니다. 퇴직금 수령계좌와 세금 차이를 같이 설명해줘"
    assert tax_intent(question) == RETIREMENT_PENSION_RECEIPT_TAX
    assert not tax_intent(question) == EARLY_WITHDRAWAL_TAX


def test_g055_matches_g031_early_withdrawal_tax_policy() -> None:
    g031 = "55세 전에 IRP에서 찾으면 어떤 세금이 생기나요?"
    g055 = "55세 미만 DB 퇴직자의 수령계좌와 중도인출 세금을 설명해줘"
    _, _, r31, c31 = grounded(g031)
    _, _, r55, c55 = grounded(g055)
    assert r31.tax_intent == EARLY_WITHDRAWAL_TAX
    assert r55.tax_intent == EARLY_WITHDRAWAL_TAX
    assert not _has_year_rate_block(c31.fallback_message)
    assert not _has_year_rate_block(c55.fallback_message)
    assert any(item["subtask"] == "early_withdrawal_tax_detail" for item in c31.claim_plan)
    assert any(item["subtask"] == "early_withdrawal_tax_detail" for item in c55.claim_plan)
    assert any(item["subtask"] == "account_receipt" for item in c55.claim_plan)
