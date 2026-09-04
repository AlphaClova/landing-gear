"""Public retrieved_context pruning.

Runs only at the /answer serializer boundary. Retrieval, tool selection,
composition, verification, Rule Result, Product Result, and final answer
text are left unchanged. InternalAnswer.citations is never mutated.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from app.core.query_normalization import (
    is_db_dc_question,
    is_generic_risk_grade_meaning_question,
    is_tax_deduction_question,
    is_teacher_retirement_domain,
    tax_intent,
    TAX_CREDIT,
)

_PRODUCT_SUPPORT = (
    "투자전략",
    "투자위험등급",
    "위험등급:",
    "수수료선취-오프라인",
    "자산유형",
    "상품명:",
)
_TAX_CREDIT_MARKERS = (
    "600만원",
    "600만 원",
    "연600",
    "연 600",
    "900만원",
    "900만 원",
    "연900",
    "연 900",
    "세액공제 한도",
    "세액공제율",
    "납입한도",
    "세액공제 대상",
    "세액공제혜택",
    "세액공제 혜택",
)
_RETIREMENT_TAX_MARKERS = (
    "퇴직소득세",
    "연금소득세",
    "이연퇴직소득세",
    "실제수령연차",
)
_DB_DC_MARKERS = ("확정급여형", "확정기여형", "Defined Benefit", "Defined Contribution")
_ELIGIBILITY_MARKERS = ("가입대상", "가입 대상", "가입 불가", "가입 가능", "개인사업", "근로시간")
_EXAMPLE_MARKERS = ("예를 들어", "30년 근무", "퇴직수당 1억원")
_SUPPORT_PHRASES = (
    "확정급여형",
    "확정기여형",
    "세액공제",
    "납입한도",
    "세액공제율",
    "명예퇴직수당",
    "명퇴수당",
    "퇴직수당",
    "60일",
    "과세이연",
    "환급",
    "퇴직소득",
    "15시간",
    "중도인출",
    "일시금",
    "이연퇴직소득세",
    "가입 대상",
    "가입대상",
)
_DIRECT_TAX_SUPPORT = (
    "퇴직소득세",
    "과세 체계",
    "과세체계",
    "이연퇴직소득",
    "연금소득세",
    "과세이연",
)
_DIRECT_IRP_TRANSFER_SUPPORT = (
    "의무 이전",
    "의무이전",
    "IRP로 이전",
    "IRP(개인형",
    "개인형 퇴직연금계좌",
    "개인형퇴직연금계좌",
)
_UNRELATED_IRP_TAX_OPS = (
    "승진",
    "고객등록",
    "계좌번호",
    "가입자정보",
    "입금계좌는",
    "DC가입자",
    "확정된 퇴직금을 지급",
)
_PII_OR_ACCOUNT_NOISE = (
    "개인정보",
    "고객등록",
    "계좌번호",
    "가입자부담금",
)


def public_answer_text(internal: Any) -> str:
    """Same answer string emitted by the public /answer serializer."""
    if internal.type == "clarification":
        parts = [internal.message]
        if internal.required_slots:
            needed = ", ".join(slot.prompt for slot in internal.required_slots)
            parts.append("[한계] 아래 정보가 없어 확정적으로 답변할 수 없습니다.")
            parts.append(f"[필요한 조건] {needed}")
        return "\n".join(parts)
    return internal.message


def select_public_citations(internal: Any, question: str) -> list[Any]:
    """Prune public evidence without changing the production pipeline."""
    citations = list(internal.citations)
    if not citations:
        return []
    if internal.trace.intent == "범위 밖":
        return []

    answer = public_answer_text(internal)
    public_text = f"{question}\n{answer}"
    used_ids, used_product_ids, product_facts = _claim_mapping(internal)
    eligibility_ids = {
        str(evidence_id)
        for subtask in internal.trace.claim_plan
        if subtask.get("subtask") == "eligibility_relation"
        for claim in (subtask.get("claims") or [])
        if isinstance(claim, dict)
        for evidence_id in (claim.get("evidence_ids") or [])
    }
    original_index = {item.id: index for index, item in enumerate(citations)}

    selected = [
        item for item in citations
        if item.id in eligibility_ids
        or not _drop_reason(item, question, answer, public_text, product_facts, used_product_ids)
    ]
    if _has_extractable_claims(answer):
        selected = [
            item for item in selected
            if item.id in eligibility_ids or _directly_supports(item.excerpt, answer) or _is_selected_product_evidence(item, public_text, product_facts)
        ]
    elif used_ids:
        selected = [item for item in selected if item.id in used_ids or item.id in eligibility_ids or _is_selected_product_evidence(item, public_text, product_facts)]

    selected = _drop_heading_only(selected)
    selected = _deduplicate(selected)
    selected = _keep_bound_eligibility(selected, eligibility_ids)
    selected = _drop_redundant_mixed_tax_credit(selected, question, answer)
    selected = _restore_claim_support(
        selected, citations, question, answer, public_text, product_facts, used_product_ids, original_index,
    )
    selected = _keep_bound_eligibility(selected, eligibility_ids)
    selected.sort(key=lambda item: original_index.get(item.id, 10_000))
    return selected


def _keep_bound_eligibility(items: list[Any], eligibility_ids: set[str]) -> list[Any]:
    if not eligibility_ids or not any(item.id in eligibility_ids for item in items):
        return items
    return [item for item in items if item.id in eligibility_ids or _is_product_citation(item)]


def _drop_redundant_mixed_tax_credit(items: list[Any], question: str, answer: str) -> list[Any]:
    if not (is_tax_deduction_question(question) or tax_intent(question) == TAX_CREDIT):
        return items
    clean_support_exists = any(
        any(marker in item.excerpt for marker in ("600만원", "600만 원", "연600", "연 600"))
        and any(marker in item.excerpt for marker in ("900만원", "900만 원", "연900", "연 900"))
        and not any(marker in item.excerpt for marker in ("중도인출", "기타소득세", "계좌를 해지"))
        for item in items
    )
    if not clean_support_exists:
        return items
    return [
        item for item in items
        if not (
            any(marker in item.excerpt for marker in ("중도인출", "기타소득세", "계좌를 해지"))
            and any(marker in item.excerpt for marker in ("세액공제", "900만원", "900만 원"))
            and not any(marker in answer for marker in ("중도인출", "기타소득세", "계좌를 해지"))
        )
    ]


def _claim_mapping(internal: Any) -> tuple[set[str], set[str], list[dict[str, object]]]:
    used_ids: set[str] = set()
    used_product_ids: set[str] = set()
    for subtask in internal.trace.claim_plan:
        for claim in subtask.get("claims", []) or []:
            if not isinstance(claim, dict):
                continue
            used_ids.update(str(value) for value in claim.get("evidence_ids", []) or [])
            used_product_ids.update(str(value) for value in claim.get("product_fact_ids", []) or [])
    if internal.withdrawal_result is not None:
        for scenario in internal.withdrawal_result.comparison.scenarios:
            used_ids.update(scenario.evidence_ids)
    return used_ids, used_product_ids, list(internal.trace.product_facts)


def _drop_reason(
    item: Any,
    question: str,
    answer: str,
    public_text: str,
    product_facts: list[dict[str, object]],
    used_product_ids: set[str],
) -> str | None:
    excerpt = item.excerpt
    if is_generic_risk_grade_meaning_question(question) and (
        _is_product_citation(item) or "상품명:" in excerpt or "한국투자" in excerpt
    ):
        return "UNSELECTED_PRODUCT_EVIDENCE"
    if _is_product_citation(item):
        if not _product_selected_in_answer(public_text, product_facts, used_product_ids):
            return "UNSELECTED_PRODUCT_EVIDENCE"
        if _is_wrong_product(item, public_text, product_facts):
            return "WRONG_PRODUCT_EVIDENCE"
        if not _product_page_supports_answer(item, answer, public_text):
            return "UNUSED_EVIDENCE"
        return None

    if _is_unused_numeric_example(excerpt, answer):
        return "UNUSED_EVIDENCE"
    if _is_unrelated_irp_retirement_tax(excerpt, question):
        return "IRRELEVANT_EVIDENCE"
    if _is_wrong_honor_benefit_evidence(item, excerpt, question):
        return "WRONG_SCOPE_EVIDENCE"
    if _is_operational_irp_account_noise(excerpt, question):
        return "IRRELEVANT_EVIDENCE"
    if _is_wrong_tax_scope(excerpt, question, answer):
        return "WRONG_SCOPE_EVIDENCE"
    if _is_excess_eligibility(excerpt, question, answer):
        return "IRRELEVANT_EVIDENCE"
    if _is_unused_pension_income_tax(excerpt, answer):
        return "WRONG_SCOPE_EVIDENCE"
    return None


def _is_product_citation(item: Any) -> bool:
    return str(item.document_id).startswith("r2_") or str(item.id).startswith("product-")


def _product_selected_in_answer(
    public_text: str,
    product_facts: list[dict[str, object]],
    used_product_ids: set[str],
) -> bool:
    named = [str(item.get("product_name") or "") for item in product_facts if item.get("product_name")]
    if any(name and name in public_text for name in named):
        return True
    if used_product_ids and any(
        str(item.get("product_id") or "") in used_product_ids and str(item.get("product_name") or "") in public_text
        for item in product_facts
    ):
        return True
    return bool(_horizon_tokens(public_text) and named)


def _is_selected_product_evidence(
    item: Any,
    public_text: str,
    product_facts: list[dict[str, object]],
) -> bool:
    if not _is_product_citation(item):
        return False
    return not _is_wrong_product(item, public_text, product_facts) and _product_selected_in_answer(public_text, product_facts, set())


def _is_wrong_product(item: Any, public_text: str, product_facts: list[dict[str, object]]) -> bool:
    allowed_horizons = _horizon_tokens(public_text)
    excerpt_horizons = _horizon_tokens(item.excerpt)
    if "초단기" in excerpt_horizons and "초단기" not in allowed_horizons:
        return True
    allowed_names = {
        str(product.get("product_name") or "")
        for product in product_facts
        if product.get("product_name") and (
            str(product.get("product_name")) in public_text
            or _horizon_tokens(str(product.get("product_name") or "")).issubset(allowed_horizons)
        )
    }
    allowed_docs = {
        str(product.get("document_id") or "")
        for product in product_facts
        if str(product.get("product_name") or "") in allowed_names
    }
    if allowed_names:
        name_hit = any(name and name in item.excerpt for name in allowed_names)
        doc_hit = item.document_id in allowed_docs
        if not name_hit and not doc_hit:
            return True
        foreign = [
            str(product.get("product_name") or "")
            for product in product_facts
            if product.get("product_name") and str(product.get("product_name")) not in allowed_names
        ]
        if any(name and name in item.excerpt for name in foreign) and not name_hit:
            return True
    elif allowed_horizons and excerpt_horizons and excerpt_horizons.isdisjoint(allowed_horizons):
        return True
    return False


def _product_page_supports_answer(item: Any, answer: str, public_text: str) -> bool:
    if str(item.id).startswith("product-"):
        return True
    excerpt = item.excerpt
    if any(marker in excerpt for marker in _PRODUCT_SUPPORT):
        if "분류체계 개편" in excerpt and "투자전략" not in excerpt and "수수료선취-오프라인" not in excerpt:
            return False
        return True
    return _directly_supports(excerpt, answer)


def _is_irp_retirement_tax_question(question: str) -> bool:
    if is_tax_deduction_question(question):
        return False
    compact = question.replace(" ", "").upper()
    return "퇴직금" in question and "IRP" in compact and "세금" in question


def _is_generic_honor_benefit_question(question: str) -> bool:
    if is_teacher_retirement_domain(question):
        return False
    return any(marker in question for marker in ("명퇴수당", "명예퇴직수당", "명퇴"))


def _is_irp_account_definition_question(question: str) -> bool:
    compact = question.replace(" ", "")
    return "IRP" in compact.upper() and any(marker in question for marker in ("계좌인가요", "어떤 계좌", "무슨 계좌"))


def _is_unrelated_irp_retirement_tax(excerpt: str, question: str) -> bool:
    if not _is_irp_retirement_tax_question(question):
        return False
    if any(marker in excerpt for marker in _UNRELATED_IRP_TAX_OPS):
        return True
    tax_support = any(marker in excerpt for marker in _DIRECT_TAX_SUPPORT)
    transfer_support = any(marker in excerpt for marker in _DIRECT_IRP_TRANSFER_SUPPORT)
    return not (tax_support or transfer_support)


def _is_wrong_honor_benefit_evidence(item: Any, excerpt: str, question: str) -> bool:
    if not _is_generic_honor_benefit_question(question):
        return False
    if str(getattr(item, "document_id", "")) == "doc26":
        return True
    if any(marker in excerpt for marker in _PII_OR_ACCOUNT_NOISE):
        return True
    if any(marker in excerpt for marker in ("교사", "공무원", "교직원", "사립학교")):
        return True
    return not any(marker in excerpt for marker in ("명퇴수당", "명예퇴직수당"))


def _is_operational_irp_account_noise(excerpt: str, question: str) -> bool:
    if not _is_irp_account_definition_question(question):
        return False
    return any(marker in excerpt for marker in _PII_OR_ACCOUNT_NOISE)


def _is_unused_numeric_example(excerpt: str, answer: str) -> bool:
    if not any(marker in excerpt for marker in _EXAMPLE_MARKERS):
        return False
    return "30년" not in answer and "1억" not in answer


def _is_wrong_tax_scope(excerpt: str, question: str, answer: str) -> bool:
    credit_question = is_tax_deduction_question(question) or tax_intent(question) == TAX_CREDIT
    if not credit_question:
        return False
    if any(marker in excerpt for marker in _TAX_CREDIT_MARKERS):
        return False
    if any(marker in excerpt for marker in _RETIREMENT_TAX_MARKERS):
        answer_needs_retirement = any(marker in answer for marker in ("퇴직소득세", "이연퇴직소득세", "연금소득세"))
        return not answer_needs_retirement
    return False


def _is_excess_eligibility(excerpt: str, question: str, answer: str) -> bool:
    if not is_db_dc_question(question):
        return False
    if any(marker in answer for marker in ("가입 대상", "가입대상", "근로시간", "15시간")):
        return False
    if any(marker in excerpt for marker in _DB_DC_MARKERS):
        return False
    return any(marker in excerpt for marker in _ELIGIBILITY_MARKERS)


def _is_unused_pension_income_tax(excerpt: str, answer: str) -> bool:
    if "연금소득세" not in excerpt:
        return False
    if "연금소득세" in answer or "3.3" in answer:
        return False
    return "3.3" in excerpt or "5.5" in excerpt


def _directly_supports(excerpt: str, answer: str) -> bool:
    if any(token in excerpt for token in _support_tokens(answer)):
        return True
    answer_numbers = _claim_numbers(answer)
    excerpt_numbers = _claim_numbers(excerpt)
    if answer_numbers and answer_numbers & excerpt_numbers:
        return True
    return any(phrase in answer and phrase in excerpt for phrase in _SUPPORT_PHRASES)


def _has_extractable_claims(answer: str) -> bool:
    if any(phrase in answer for phrase in _SUPPORT_PHRASES):
        return True
    if any(marker in answer for marker in _DB_DC_MARKERS):
        return True
    if "솔로몬" in answer or "투자신탁" in answer:
        return True
    return bool(_claim_numbers(answer))


def _support_tokens(answer: str) -> list[str]:
    cleaned = re.sub(r"위험등급은 1등급이 매우 높은 위험[^\n]*", " ", answer)
    tokens: list[str] = []
    for match in re.finditer(r"\d+(?:\.\d+)?\s*(?:만원|만\s*원|%|일|시간|년|등급)", cleaned):
        tokens.append(re.sub(r"\s+", "", match.group(0)))
    for phrase in _SUPPORT_PHRASES:
        if phrase in cleaned:
            tokens.append(phrase)
    for marker in _DB_DC_MARKERS:
        if marker in cleaned:
            tokens.append(marker)
    return tokens


def _claim_numbers(text: str) -> set[str]:
    compact = text.replace(",", "").replace(" ", "")
    found: set[str] = set()
    for match in re.finditer(r"\d+(?:\.\d+)?", compact):
        value = match.group(0)
        if value.startswith("20") and len(value) == 4:
            continue
        if value in {"1", "2", "3", "4", "6"}:
            continue
        found.add(value)
    return found


def _horizon_tokens(text: str) -> set[str]:
    found: set[str] = set()
    if "초단기" in text:
        found.add("초단기")
    if "중장기" in text:
        found.add("중장기")
    remainder = text.replace("초단기", " ").replace("중장기", " ")
    if "단기" in remainder:
        found.add("단기")
    if "장기" in remainder:
        found.add("장기")
    return found


def _normalized_evidence_text(value: str) -> str:
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "", value).casefold()


def _is_duplicate_evidence(normalized: str, seen: set[str]) -> bool:
    if not normalized:
        return False
    if normalized in seen:
        return True
    return any(
        min(len(normalized), len(previous)) >= 40
        and re.findall(r"\d+(?:\.\d+)?", normalized) == re.findall(r"\d+(?:\.\d+)?", previous)
        and SequenceMatcher(None, normalized, previous).ratio() >= 0.92
        for previous in seen
    )


def _drop_heading_only(items: list[Any]) -> list[Any]:
    docs_with_body = {item.document_id for item in items if len(item.excerpt.strip()) >= 80}
    kept: list[Any] = []
    for item in items:
        excerpt = item.excerpt.strip()
        if len(excerpt) < 50 and item.document_id in docs_with_body and not re.search(r"\d", excerpt):
            continue
        kept.append(item)
    return kept


def _deduplicate(items: list[Any]) -> list[Any]:
    deduplicated: list[Any] = []
    seen_ids: set[str] = set()
    seen_text_by_page: dict[tuple[str, int | None], set[str]] = {}
    seen_pages: set[tuple[str, int | None, str]] = set()
    for item in items:
        normalized = _normalized_evidence_text(item.excerpt)
        page_key = (item.document_id, item.page, normalized[:80])
        same_page_text = seen_text_by_page.setdefault((item.document_id, item.page), set())
        if item.id in seen_ids or page_key in seen_pages or _is_duplicate_evidence(normalized, same_page_text):
            continue
        deduplicated.append(item)
        seen_ids.add(item.id)
        seen_pages.add(page_key)
        if normalized:
            same_page_text.add(normalized)
    return deduplicated


_HARD_DROP_REASONS = frozenset({
    "WRONG_PRODUCT_EVIDENCE",
    "WRONG_SCOPE_EVIDENCE",
    "IRRELEVANT_EVIDENCE",
})
_DIRECT_PHRASE_CLAIMS = (
    "IRP로 이전",
    "법정퇴직금",
    "이연퇴직소득세",
    "3.3%",
    "5.5%",
)


def _restore_claim_support(
    selected: list[Any],
    original: list[Any],
    question: str,
    answer: str,
    public_text: str,
    product_facts: list[dict[str, object]],
    used_product_ids: set[str],
    original_index: dict[str, int],
) -> list[Any]:
    kept_ids = {item.id for item in selected}
    restored = list(selected)
    remaining = [item for item in original if item.id not in kept_ids]
    tokens = [token for token in _direct_claim_tokens(answer) if token not in {"0%", "0.0%", "0"}]

    def _unmatched() -> list[str]:
        return [
            token for token in tokens
            if not any(_excerpt_supports_claim(item.excerpt, token) for item in restored)
        ]

    while True:
        unmatched = _unmatched()
        if not unmatched:
            break
        best = None
        best_cover: list[str] = []
        for item in remaining:
            cover = [
                token for token in unmatched
                if _excerpt_supports_claim(item.excerpt, token)
                and _is_safe_support_restore(
                    item, question, answer, public_text, product_facts, used_product_ids, token,
                )
            ]
            if len(cover) > len(best_cover):
                best = item
                best_cover = cover
        if best is None or not best_cover:
            break
        restored.append(best)
        remaining = [item for item in remaining if item.id != best.id]

    for product in product_facts:
        name = str(product.get("product_name") or "")
        if not name or name not in public_text:
            continue
        document_id = str(product.get("document_id") or "")
        if any(name in item.excerpt or item.document_id == document_id for item in restored):
            continue
        match = next(
            (
                item for item in remaining
                if (name in item.excerpt or item.document_id == document_id)
                and _is_safe_support_restore(
                    item, question, answer, public_text, product_facts, used_product_ids, name,
                )
            ),
            None,
        )
        if match is not None:
            restored.append(match)
            remaining = [item for item in remaining if item.id != match.id]
    restored.sort(key=lambda item: original_index.get(item.id, 10_000))
    return _deduplicate(restored)


def _direct_claim_tokens(answer: str) -> list[str]:
    tokens = [token for token in _support_tokens(answer) if token not in {"0%", "0.0%", "0"}]
    compact = re.sub(r"\s+", "", answer)
    for phrase in _DIRECT_PHRASE_CLAIMS:
        if phrase.replace(" ", "") in compact:
            tokens.append(phrase)
    for match in re.finditer(r"\d+(?:\.\d+)?%", compact):
        token = match.group(0)
        if token not in {"0%", "0.0%"}:
            tokens.append(token)
    if re.search(r"3\.3\s*[~～\-]\s*5\.5", compact):
        tokens.extend(["3.3%", "5.5%"])
    return list(dict.fromkeys(tokens))


def _excerpt_supports_claim(excerpt: str, claim: str) -> bool:
    if not claim or claim in {"0%", "0.0%"}:
        return False
    if claim in excerpt:
        return True
    compact_excerpt = _normalized_evidence_text(excerpt)
    compact_claim = re.sub(r"\s+", "", claim)
    if compact_claim in {"가입대상"} and compact_claim in compact_excerpt:
        return True
    if compact_claim and compact_claim in compact_excerpt:
        return True
    if claim.endswith("%"):
        stem = claim[:-1]
        if stem in {"0", "0.0"}:
            return False
        pattern = rf"(?<![\d.]){re.escape(stem)}(?![\d.])"
        return bool(re.search(pattern, excerpt.replace(",", ""))) or (
            _normalized_evidence_text(stem) in compact_excerpt if len(_normalized_evidence_text(stem)) >= 2 else False
        )
    return False


def _is_safe_support_restore(
    item: Any,
    question: str,
    answer: str,
    public_text: str,
    product_facts: list[dict[str, object]],
    used_product_ids: set[str],
    claim: str,
) -> bool:
    if is_generic_risk_grade_meaning_question(question):
        return False
    if _is_generic_honor_benefit_question(question):
        return False
    if _is_clarification_without_claims(question, answer):
        return False
    if "초단기" in item.excerpt and "초단기" not in answer:
        return False
    reason = _drop_reason(item, question, answer, public_text, product_facts, used_product_ids)
    if reason in _HARD_DROP_REASONS:
        return False
    if reason == "UNUSED_EVIDENCE" and _is_unused_numeric_example(item.excerpt, answer):
        return False
    if not _excerpt_supports_claim(item.excerpt, claim):
        return False
    if reason == "UNSELECTED_PRODUCT_EVIDENCE":
        return _product_excerpt_supports_fee_claim(item.excerpt, claim)
    return True


def _is_clarification_without_claims(question: str, answer: str) -> bool:
    if "좋은 연금 상품" in question and "추천" in question:
        return True
    asks = any(marker in answer for marker in ("알려주세요", "알려주시면", "필요한 조건"))
    return asks and not _direct_claim_tokens(answer)


def _product_excerpt_supports_fee_claim(excerpt: str, claim: str) -> bool:
    if "%" not in claim and not re.search(r"\d+\.\d+", claim):
        return False
    if not any(marker in excerpt for marker in ("집합투자업자", "판매회사 보수", "판매회사\n보수", "총 보수", "총보수", "지급비용")):
        return False
    return _excerpt_supports_claim(excerpt, claim)
