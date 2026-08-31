"""Intent Router (A4) + Fast/Deep Path 결정.

공식 예시 유형: 제도 / 세제 / 종합 / 절차 / 상품 / 범위 밖.
키워드 기반 최소 구현이다. 정확도가 부족해지면 HCX 분류로 교체하되
intent 문자열 값과 route_confidence/fallback_reason 계약은 유지한다.
"""

from dataclasses import dataclass
import re
from typing import Literal

from app.core.query_normalization import (
    RETIREMENT_PENSION_RECEIPT_TAX,
    has_alias,
    is_comparison_question,
    is_db_dc_question,
    is_tax_deduction_question,
    is_teacher_retirement_domain,
    tax_intent,
)

Intent = Literal["제도", "세제", "종합", "절차", "상품", "범위 밖"]
Route = Literal["fast_path", "deep_path"]

_KEYWORDS: dict[Intent, tuple[str, ...]] = {
    "제도": ("운용 주체", "운용 책임", "제도 설명", "퇴직연금 제도"),
    "세제": ("세금", "세율", "과세", "소득세", "퇴직소득세", "비과세", "절세"),
    "상품": ("상품", "IRP", "펀드", "예금", "ETF", "국공채", "채권형", "솔로몬", "수익률 비교"),
    "절차": ("신청", "절차", "방법", "서류", "이전", "이동", "해지", "끝내", "어떻게 하나요", "어떻게 해야"),
}

_OUT_OF_SCOPE_MARKERS = ("주식 추천", "부동산 투자", "코인", "타로", "날씨", "번역")


@dataclass
class RouteDecision:
    intent: Intent
    route: Route
    route_confidence: float
    fallback_reason: str | None = None


class IntentRouter:
    def classify(self, question: str) -> RouteDecision:
        if any(marker in question for marker in _OUT_OF_SCOPE_MARKERS):
            return RouteDecision(
                intent="범위 밖",
                route="fast_path",
                route_confidence=0.95,
                fallback_reason="out_of_scope_marker_matched",
            )

        scores: dict[Intent, int] = {
            intent: sum(1 for kw in kws if self._matches(question, kw)) for intent, kws in _KEYWORDS.items()
        }
        if is_db_dc_question(question):
            scores["제도"] += 2
        if tax_intent(question) == "TAX_CREDIT" or is_teacher_retirement_domain(question):
            scores["세제"] += 2
        if has_alias(question, "product_family"):
            scores["상품"] += 1
        if has_alias(question, "product_entity"):
            scores["상품"] += 2
        if has_alias(question, "institution"):
            scores["제도"] += 2
        if has_alias(question, "retirement_benefit"):
            scores["세제"] += 2
        if has_alias(question, "product_feature"):
            scores["상품"] += 2
        if has_alias(question, "product_metric"):
            scores["상품"] += 2
        if has_alias(question, "recommendation_context"):
            scores["상품"] += 2
        if has_alias(question, "institution_feature"):
            scores["제도"] += 2
        if has_alias(question, "tax_rule"):
            scores["세제"] += 2
        if has_alias(question, "procedure_feature"):
            scores["절차"] += 2
        matched = {intent: score for intent, score in scores.items() if score > 0}

        # 세액공제 한도는 계좌명이 함께 나와도 상품 추천이 아닌 세제 factual 질의다.
        if scores["세제"] and (tax_intent(question) == "TAX_CREDIT" or is_teacher_retirement_domain(question) or any(marker in question for marker in ("세금", "절세"))):
            matched = {"세제": scores["세제"]}

        # 금액과 세액이 함께 주어지고 수령안 비교/결과를 요구하면 세제 FAQ가
        # 아니라 deterministic withdrawal comparison을 실행할 종합 질의다.
        has_retirement_amount = bool(re.search(r"퇴직(?:급여|금)\s*\d", question))
        has_tax_amount = bool(re.search(r"(?:예상\s*)?(?:퇴직소득)?세(?:금)?\s*\d", question))
        if has_retirement_amount and has_tax_amount and any(
            marker in question for marker in ("비교", "일시금", "연금", "결과", "계산 근거")
        ):
            matched = {"종합": 3}

        if tax_intent(question) == RETIREMENT_PENSION_RECEIPT_TAX and any(
            marker in question for marker in ("비교", "절세액", "10년", "21년", "수령")
        ):
            matched = {"종합": 3}

        # 상품명/자산유형과 비교 표현이 함께 있으면 product compare로 우선한다.
        has_specific_product_signal = has_alias(question, "product_family") or has_alias(question, "product_metric") or any(
            marker in question for marker in ("펀드", "채권", "상품 목록", "상품 후보")
        )
        if scores["상품"] and has_specific_product_signal and is_comparison_question(question) and not (has_retirement_amount or has_tax_amount):
            matched = {"상품": scores["상품"]}

        # 상품 선택 요청은 계좌/제도명이 함께 있어도 상품 intent다. 실제 추천에
        # 필요한 사용자 조건은 Router가 아니라 SlotManager가 판정한다.
        if scores["상품"] and any(marker in question for marker in ("추천", "골라", "정해")):
            if has_retirement_amount and has_tax_amount:
                matched = {"종합": 3}
            else:
                matched = {"상품": scores["상품"]}

        # 신청·이전·해지와 구비서류를 직접 묻는 질문은 제도명이 포함돼도
        # 실행 절차를 묻는 단일 도메인 질의다.
        if scores["절차"] and any(marker in question for marker in ("신청", "서류", "이전", "해지", "절차")):
            multi_procedure = scores["상품"] > 0 and any(marker in question for marker in ("상품 선택", "추천", "연금 개시"))
            multi_tax = scores["세제"] > 0 and any(marker in question for marker in ("세금", "과세", "퇴직소득세"))
            matched = {"종합": max(3, scores["절차"])} if (multi_procedure or multi_tax) else {"절차": scores["절차"]}

        if not matched:
            return RouteDecision(
                intent="범위 밖",
                route="fast_path",
                route_confidence=0.4,
                fallback_reason="no_keyword_match",
            )

        is_comparison = is_comparison_question(question)
        has_numbers = sum(ch.isdigit() for ch in question) >= 4  # 금액 등 복합 조건 신호

        if len(matched) >= 2 or (is_comparison and has_numbers):
            top_score = max(matched.values())
            total = sum(matched.values()) or 1
            confidence = min(0.6, top_score / total)
            return RouteDecision(
                intent="종합",
                route="deep_path",
                route_confidence=confidence,
                fallback_reason="multi_domain_or_comparison_with_numbers",
            )

        intent = max(matched, key=lambda k: matched[k])
        confidence = min(0.95, 0.5 + 0.15 * matched[intent])

        if confidence >= 0.8 and not is_comparison:
            return RouteDecision(intent=intent, route="fast_path", route_confidence=confidence)

        return RouteDecision(
            intent=intent,
            route="deep_path",
            route_confidence=confidence,
            fallback_reason="low_confidence_or_comparison",
        )

    @staticmethod
    def _matches(question: str, keyword: str) -> bool:
        # 두 글자 동사형 keyword가 다른 어절 안에 포함되는 오탐(정해지는→해지)을 막는다.
        if keyword == "해지":
            return any(token.startswith("해지") for token in question.split())
        return keyword in question
