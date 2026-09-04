"""Shared query aliases and semantic feature extraction.

This module contains reusable vocabulary, never complete evaluation questions.
Entity recognition and legal equivalence are deliberately separate concepts.
"""

from __future__ import annotations

import re


QUERY_TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣]+")
RELEVANCE_STOPWORDS = frozenset(
    {
        "알려줘", "알려주세요", "설명해줘", "설명해주세요", "궁금해", "궁금합니다",
        "뭐야", "무엇", "어떻게", "비교", "비교해줘", "비교해주세요", "추천",
        "추천해줘", "추천해주세요", "특징", "차이", "결과", "관련", "대해", "방법",
        "조건", "기준", "한도", "최대", "금액", "되나요", "넣으면", "합쳐서요",
        "통합해서", "예요", "하는", "얼마", "메뉴",
        "개인", "함께", "있는", "없이", "넣을", "있나요", "실제", "같은",
        "뜻인가요", "나눠", "설명해", "설명해줘", "안내", "같이", "보고",
        "싶습니다", "구분해", "주세요", "한계", "유동성",
    }
)
_KOREAN_PARTICLES = ("이랑", "하고", "하는", "으로", "에서", "까지", "부터", "처럼", "보다", "에게", "한테", "예요", "와", "과", "은", "는", "이", "가", "을", "를", "의", "에", "로", "도", "만")
_RELEVANCE_CANONICAL = {
    "퇴직재원": "퇴직금",
    "연금수령": "연금수령",
    "기간별": "기간",
    "납부비율": "납부",
    "환급액": "환급",
    "공제대상": "공제",
}

# Relevance-only vocabulary. These terms must never be used to manufacture an answer.
DOMAIN_ANCHORS: dict[str, tuple[str, ...]] = {
    "institution": ("db", "dc", "irp", "연금", "퇴직연금", "연금저축", "퇴직금", "확정급여", "확정기여", "퇴직급여", "적립금", "운용", "책임", "산정", "가입", "대상", "근속"),
    "tax": ("세액공제", "공제", "공제율", "퇴직소득세", "연금소득세", "세율", "세금", "과세", "환급", "절세", "감면", "연차", "기간"),
    "product": ("상품", "펀드", "국공채", "위험등급", "보수", "수익률", "솔로몬", "단기", "중장기", "장기", "금리", "위험"),
    "procedure": ("개설", "이전", "계약이전", "해지", "중도인출", "연금개시", "수령", "증빙"),
    "population": ("교사", "교직원", "공무원", "명퇴", "명퇴수당", "명예퇴직", "명예퇴직수당", "퇴직수당"),
}


def normalize_relevance_token(token: str) -> str:
    normalized = token.lower()
    for particle in _KOREAN_PARTICLES:
        if normalized.endswith(particle) and len(normalized) > len(particle) + 1:
            normalized = normalized[: -len(particle)]
            break
    return _RELEVANCE_CANONICAL.get(normalized, normalized)


def meaningful_query_tokens(question: str) -> tuple[str, ...]:
    """Return stable content tokens used only for retrieval applicability."""
    tokens = []
    for raw in QUERY_TOKEN_PATTERN.findall(question):
        token = normalize_relevance_token(raw)
        if len(token) < 2 or token in RELEVANCE_STOPWORDS:
            continue
        tokens.append(token)
    return tuple(dict.fromkeys(tokens))


def query_domain_anchors(question: str) -> tuple[str, ...]:
    compact = question.replace(" ", "").lower()
    matched = []
    for terms in DOMAIN_ANCHORS.values():
        matched.extend(term for term in terms if term.lower() in compact)
    return tuple(dict.fromkeys(matched))


def domain_query_coverage(question: str) -> float:
    meaningful = meaningful_query_tokens(question)
    if not meaningful:
        return 0.0
    anchors = query_domain_anchors(question)
    supported = [
        token for token in meaningful
        if any(token in anchor.lower() or anchor.lower() in token for anchor in anchors)
    ]
    return len(supported) / len(meaningful)


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


_PRODUCT_AVAILABILITY_PHRASES = (
    "같은 상품",
    "동일 상품",
    "살 수 있",
    "가입할 수 있",
    "구매할 수 있",
)
_PRODUCT_AVAILABILITY_ENTITIES = ("상품", "펀드")
_ACCOUNT_TRANSFER_QUESTION_MARKERS = ("이전", "옮기", "이동", "전환", "수령계좌", "현물이전", "넘긴", "넘겨", "넘길")
_IRP_DC_RELATION_MARKERS = ("같은", "차이", "관계", "다르", "제도")


def is_product_availability_question(question: str) -> bool:
    """True when the user asks whether a product can be bought/joined, not whether plans are the same."""
    if not any(entity in question for entity in _PRODUCT_AVAILABILITY_ENTITIES):
        return False
    return any(phrase in question for phrase in _PRODUCT_AVAILABILITY_PHRASES)


def plan_types_from_question(question: str) -> tuple[str, ...]:
    """All retirement account types named in the question, without collapsing to the first hit."""
    found: list[str] = []
    if has_alias(question, "irp"):
        found.append("IRP")
    if has_alias(question, "dc"):
        found.append("DC")
    if has_alias(question, "db"):
        found.append("DB")
    return tuple(found)


def has_account_transfer_intent(question: str) -> bool:
    return any(marker in question for marker in _ACCOUNT_TRANSFER_QUESTION_MARKERS)


def allows_dc_irp_account_transfer_claim(question: str) -> bool:
    """Permit the DC→IRP retirement-transfer claim only for transfer or plan-relation questions."""
    if is_product_availability_question(question):
        return False
    if not (has_alias(question, "dc") and has_alias(question, "irp")):
        return False
    if has_account_transfer_intent(question):
        return True
    return any(marker in question for marker in _IRP_DC_RELATION_MARKERS)


def excerpt_supports_dc_irp_retirement_transfer(excerpt: str) -> bool:
    """True when one excerpt directly links DC retirement funds, a transfer event, and IRP."""
    compact = excerpt.replace(" ", "")
    has_dc = "DC" in excerpt or "확정기여" in excerpt
    has_irp = "IRP" in excerpt
    has_event = any(token in compact for token in ("이전", "옮기", "이동", "전환"))
    has_source = any(token in compact for token in ("법정퇴직금", "DC퇴직금", "DC법정퇴직금", "퇴직금"))
    if "현물이전" in compact and not any(token in compact for token in ("법정퇴직금", "DC퇴직금")):
        return False
    return has_dc and has_irp and has_event and has_source


def is_generic_risk_grade_meaning_question(question: str) -> bool:
    """True when the user asks what a 1-6 risk grade means, not for a product."""
    if not isinstance(question, str) or not question.strip():
        return False
    if "위험등급" not in question:
        return False
    if re.search(r"[1-6]\s*등급", question) is None:
        return False
    if any(marker in question for marker in ("상품", "펀드", "추천", "골라", "목록", "보여", "솔로몬", "비교")):
        return False
    return any(marker in question for marker in ("의미", "뜻", "무엇", "뭐야", "무슨"))


def is_tax_deduction_question(question: str) -> bool:
    return has_alias(question, "tax_deduction") or any(x in question.replace(" ", "") for x in ("납입한도", "공제대상", "공제상한", "세금에서빠")) or ("공제" in question and any(x in question for x in ("한도", "최대", "상한", "환급액")))


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


TAX_CREDIT = "TAX_CREDIT"
RETIREMENT_PENSION_RECEIPT_TAX = "RETIREMENT_PENSION_RECEIPT_TAX"
EARLY_WITHDRAWAL_TAX = "EARLY_WITHDRAWAL_TAX"
ACCOUNT_TERMINATION_TAX = "ACCOUNT_TERMINATION_TAX"
RETIREMENT_LUMP_SUM_TAX = "RETIREMENT_LUMP_SUM_TAX"
UNKNOWN_TAX = "UNKNOWN_TAX"
# Historical alias used by withdrawal-comparison routing.
PENSION_WITHDRAWAL_TAX = RETIREMENT_PENSION_RECEIPT_TAX


def _compact_question(question: str) -> str:
    return question.replace(" ", "")


def is_early_withdrawal_question(question: str) -> bool:
    """Detect mid-term / pre-55 withdrawal without requiring the exact token 중도인출."""
    compact = _compact_question(question)
    if any(marker in question for marker in ("중도인출", "일부 인출", "일부인출")):
        return True
    pre_55 = any(marker in compact for marker in ("55세전", "55세이전", "만55세전", "55세미만", "만55세미만"))
    withdrawal = any(marker in compact for marker in ("찾으면", "찾아도", "인출하면", "인출하", "빼면", "빼고", "에서찾"))
    if pre_55 and withdrawal:
        return True
    account = has_alias(question, "irp") or has_alias(question, "dc") or "퇴직연금" in question
    return bool(account and withdrawal and any(marker in question for marker in ("세금", "과세", "세율")))


def is_account_termination_question(question: str) -> bool:
    if is_db_dc_question(question):
        return False
    compact = _compact_question(question)
    termination = bool(
        re.search(r"(?<!정)해지(?:$|[\s를은는이가의,?]|하|했|되|된|할|하려)", question)
        or any(marker in question for marker in ("해약", "끝내"))
    )
    return termination or "전액일시인출" in compact or "전액 일시 인출" in question


def pension_year_rate_block_allowed(scope: str | None) -> bool:
    """70/60/50 actual-receipt-year rates apply only to pension-receipt tax."""
    return scope == RETIREMENT_PENSION_RECEIPT_TAX


def tax_scope_compatible(original: str | None, repaired: str | None) -> bool:
    """Repair may only keep the original scope or a compatible specialization."""
    if original == repaired:
        return True
    compatible = {
        UNKNOWN_TAX: {
            RETIREMENT_PENSION_RECEIPT_TAX,
            EARLY_WITHDRAWAL_TAX,
            ACCOUNT_TERMINATION_TAX,
            RETIREMENT_LUMP_SUM_TAX,
            TAX_CREDIT,
        },
    }
    return repaired in compatible.get(original, set())


def _is_pension_receipt_tax(question: str) -> bool:
    compact = _compact_question(question)
    if is_early_withdrawal_question(question) or is_account_termination_question(question):
        return False
    if any(marker in question for marker in ("연금수령", "연금 수령", "수령연차", "이연퇴직소득세")):
        return True
    if (
        "퇴직소득세" in question
        and any(marker in question for marker in ("퇴직금", "퇴직급여"))
        and "연금" in question
        and any(marker in question for marker in ("계산", "절세액", "비교"))
    ):
        return True
    if (
        any(marker in question for marker in ("퇴직금", "퇴직급여"))
        and "연금으로" in question
        and any(marker in question for marker in ("받으", "받으면", "수령"))
        and any(marker in question for marker in ("세금", "과세", "세율"))
    ):
        return True
    if re.search(r"\d+\s*년차", question):
        return True
    year_horizon = any(marker in compact for marker in ("10년", "11년", "21년", "20년"))
    receipt_context = any(marker in question for marker in ("수령", "감면", "절세액", "부담", "세율", "세금", "연금으로"))
    if year_horizon and receipt_context and ("연금저축" not in question or "수령" in question or "년차" in question):
        return True
    if "일시금" in question and any(
        marker in question for marker in ("연금수령", "연금으로", "연금 비교", "일시금과 연금")
    ):
        return True
    if "수령계좌" in question and any(marker in question for marker in ("세금", "과세")):
        return True
    return False


def _is_lump_sum_tax(question: str) -> bool:
    if is_early_withdrawal_question(question):
        return False
    if _is_pension_receipt_tax(question):
        return False
    return "일시금" in question or "일시수령" in question or "일시 수령" in question


def tax_intent(question: str) -> str | None:
    """Classify tax semantics without embedding evaluation questions."""
    if is_tax_deduction_question(question):
        return TAX_CREDIT
    compact = _compact_question(question)
    if "연말정산" in question and any(x in question for x in ("인정", "상한", "한도")):
        return TAX_CREDIT
    if has_alias(question, "irp") and "넣" in question and "세금" in question and "줄" in question and "연금수령" not in compact:
        return TAX_CREDIT
    if is_early_withdrawal_question(question):
        return EARLY_WITHDRAWAL_TAX
    if is_account_termination_question(question) and any(marker in question for marker in ("세금", "과세", "세율")):
        return ACCOUNT_TERMINATION_TAX
    if _is_pension_receipt_tax(question):
        return RETIREMENT_PENSION_RECEIPT_TAX
    if _is_lump_sum_tax(question):
        return RETIREMENT_LUMP_SUM_TAX
    if any(x in question for x in ("세금", "과세", "절세", "세율", "공제율", "감면율", "건강보험료", "퇴직소득세")):
        return UNKNOWN_TAX
    return None


def procedure_type(question: str) -> str | None:
    if is_early_withdrawal_question(question):
        return "EARLY_WITHDRAWAL"
    if is_account_termination_question(question):
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
