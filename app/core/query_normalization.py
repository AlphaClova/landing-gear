"""Shared query aliases and semantic feature extraction.

This module contains reusable vocabulary, never complete evaluation questions.
Entity recognition and legal equivalence are deliberately separate concepts.
"""

from __future__ import annotations

import re


ALIASES: dict[str, tuple[str, ...]] = {
    "irp": ("IRP", "개인형퇴직연금", "개인형 퇴직연금"),
    "db": ("DB", "DB형", "디비", "디비형", "확정급여", "확정급여형", "Defined Benefit"),
    "dc": ("DC", "DC형", "디씨", "디씨형", "확정기여", "확정기여형", "Defined Contribution"),
    "teacher": ("교사", "교직원", "선생님", "교원"),
    "public_employee": ("공무원", "교육공무원"),
    "retirement": ("명퇴", "명예퇴직", "조기퇴직"),
    "legal_retirement_benefit": ("명퇴수당", "명예퇴직수당", "퇴직수당"),
    "comparison": (
        "비교",
        "차이",
        "차이점",
        "다른 점",
        "뭐가 다른",
        "무엇이 다른",
        "대조",
        "vs",
        "각각 특징",
        "서로 어떻게 달라",
        "구분해줘",
        "무엇이 나을",
        "어떤 게 나을",
        "어느 것이",
        "중 어떤",
    ),
    "tax_deduction": ("세액공제", "세액 공제", "세금공제", "공제 한도", "공제한도", "공제 최대"),
    "product_family": ("솔로몬", "Solomon", "국공채"),
    "product_entity": ("채권", "장기채", "단기채", "펀드", "예금형", "ETF"),
    "product_metric": ("수익률", "총보수", "보수", "기준일"),
    "recommendation_context": ("은퇴자", "생활비 목적", "현금흐름", "투자기간", "손실 감내", "위험 선호", "중위험"),
    "institution": ("퇴직연금", "퇴직금제도", "일반 퇴직금", "일반퇴직금", "수령구조", "운용주체"),
    "institution_feature": ("근속", "가입 대상", "가입대상", "공무원", "외국인 근로자", "비자", "부담금"),
    "retirement_benefit": ("명예퇴직금", "명퇴수당", "명예퇴직수당", "법정퇴직금", "법정외퇴직금"),
    "product_feature": ("듀레이션", "금리 민감도", "변동성", "위험등급", "단기형", "중기형", "장기형"),
    "tax_evasion": ("세금을 안 내", "세금 안 내", "탈세", "비밀 방법", "세금 회피"),
    "tax_rule": ("연금수령", "연금 수령", "연차", "21년차", "수령 세금", "세금 부담", "절세액"),
    "procedure_feature": ("중도인출", "증빙", "입금계좌", "계약이전", "개설"),
    "sensitive_data": ("주민번호", "계좌번호", "비밀번호", "인증번호"),
    "principal_protection": ("손실 가능성", "원금 손실", "원금손실", "원금 보장", "원금보장", "예금자보호"),
    "inducement": ("과장", "엄청", "큰 폭", "거의 없어", "무조건"),
}

_DB_DC_CONTEXT = ("퇴직연금", "퇴직금", "퇴직재원", "급여", "운용", "적립금", "제도", "차이", "책임", "성과", "수익률", "보장", "회사", "고용주")


def has_alias(question: str, group: str) -> bool:
    aliases = ALIASES[group]
    for alias in aliases:
        if alias.isascii() and alias.isalpha():
            if re.search(rf"(?<![A-Za-z]){re.escape(alias)}(?![A-Za-z])", question, re.IGNORECASE):
                return True
        elif alias.lower() in question.lower():
            return True
    return False


def is_db_dc_question(question: str) -> bool:
    has_db = has_alias(question, "db")
    has_dc = has_alias(question, "dc")
    if has_db and has_dc:
        return True
    return (has_db or has_dc) and any(context in question for context in _DB_DC_CONTEXT)


def is_comparison_question(question: str) -> bool:
    return has_alias(question, "comparison") or "안정" in question


def is_tax_deduction_question(question: str) -> bool:
    return has_alias(question, "tax_deduction") or any(x in question.replace(" ", "") for x in ("납입한도", "공제대상", "공제상한")) or ("공제" in question and any(x in question for x in ("한도", "최대", "상한", "환급액")))


def is_closed_tax_faq(question: str) -> bool:
    return any(x in question for x in ("세율", "감면율", "과세", "붙나요", "무조건", "연금소득세", "퇴직소득세")) and not any(
        x in question for x in ("내 세금 계산", "절세액 계산", "실수령액 계산")
    )


def is_teacher_retirement_domain(question: str) -> bool:
    occupation = has_alias(question, "teacher") or has_alias(question, "public_employee")
    retirement = has_alias(question, "retirement") or has_alias(question, "legal_retirement_benefit")
    return occupation and retirement


def population_scope(question: str) -> str:
    """Return the narrowest population explicitly named by the user."""
    teacher = has_alias(question, "teacher")
    public_official = has_alias(question, "public_employee")
    if teacher and public_official:
        return "TEACHER_PUBLIC_OFFICIAL"
    if teacher:
        return "TEACHER"
    if public_official:
        return "PUBLIC_OFFICIAL"
    if any(x in question for x in ("임원", "대표이사", "등기이사")):
        return "EXECUTIVE"
    return "GENERAL_EMPLOYEE"


def retirement_benefit_subtasks(question: str) -> tuple[str, ...]:
    """Extract reusable subtasks for population-specific retirement benefits."""
    if not is_teacher_retirement_domain(question):
        return ()
    return (
        "benefit_legal_character",
        "account_transfer_or_deposit",
        "tax_refund_procedure",
        "retirement_tax_effect",
    )


def has_legally_named_retirement_benefit(question: str) -> bool:
    return has_alias(question, "legal_retirement_benefit") or "명퇴금" in question or "명예퇴직금" in question


def needs_retirement_benefit_clarification(question: str) -> bool:
    ambiguous_label = any(marker in question for marker in ("보상금", "지원금", "위로금"))
    generic_amount = any(marker in question for marker in ("수당", "금액")) and not has_legally_named_retirement_benefit(question)
    return is_teacher_retirement_domain(question) and (ambiguous_label or generic_amount)


def tax_intent(question: str) -> str | None:
    """Classify tax semantics without embedding evaluation questions."""
    if is_tax_deduction_question(question):
        return "TAX_CREDIT"
    if any(x in question for x in ("연금수령", "연금 수령", "수령연차", "절세액", "이연퇴직소득세", "10년", "21년")):
        return "PENSION_WITHDRAWAL_TAX"
    if any(x in question for x in ("퇴직소득세", "퇴직금", "세금")):
        return "RETIREMENT_INCOME_TAX"
    return None


def procedure_type(question: str) -> str | None:
    if "중도인출" in question:
        return "EARLY_WITHDRAWAL"
    if "해지" in question or "끝내" in question:
        return "ACCOUNT_TERMINATION"
    if "개설" in question or "처음 만들" in question:
        return "ACCOUNT_OPENING"
    if "연금" in question and any(x in question for x in ("개시", "시작")):
        return "PENSION_START"
    if any(x in question for x in ("계약이전", "계좌 이전", "이전", "이동")):
        return "ACCOUNT_TRANSFER"
    if any(x in question for x in ("퇴직급여", "수령계좌", "입금계좌")):
        return "RETIREMENT_BENEFIT_RECEIPT"
    return None


def tax_source_types(question: str) -> tuple[str, ...]:
    sources = []
    if any(x in question for x in ("개인납입", "개인 납입", "세액공제")):
        sources.extend(("NON_DEDUCTED_CONTRIBUTION", "DEDUCTED_CONTRIBUTION_AND_EARNINGS"))
    if any(x in question for x in ("퇴직금", "이연퇴직소득")):
        sources.append("DEFERRED_RETIREMENT_INCOME")
    return tuple(dict.fromkeys(sources))
