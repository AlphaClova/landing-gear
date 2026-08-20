"""Intent Router (A4) + Fast/Deep Path 결정.

공식 예시 유형: 제도 / 세제 / 종합 / 절차 / 상품 / 범위 밖.
키워드 기반 최소 구현이다. 정확도가 부족해지면 HCX 분류로 교체하되
intent 문자열 값과 route_confidence/fallback_reason 계약은 유지한다.
"""

from dataclasses import dataclass
from typing import Literal

Intent = Literal["제도", "세제", "종합", "절차", "상품", "범위 밖"]
Route = Literal["fast_path", "deep_path"]

_KEYWORDS: dict[Intent, tuple[str, ...]] = {
    "제도": ("확정급여", "확정기여", "DB형", "DC형", "운용 주체", "제도 설명", "퇴직연금 제도"),
    "세제": ("세금", "세율", "과세", "소득세", "퇴직소득세", "비과세", "세액공제"),
    "상품": ("상품", "IRP", "펀드", "예금", "ETF", "수익률 비교"),
    "절차": ("신청", "절차", "방법", "서류", "이전", "해지", "어떻게 하나요", "어떻게 해야"),
}

_COMPARISON_MARKERS = ("비교", "무엇이 나을까", "어느 것이", "vs", " 중 ")

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
            intent: sum(1 for kw in kws if kw in question) for intent, kws in _KEYWORDS.items()
        }
        matched = {intent: score for intent, score in scores.items() if score > 0}

        if not matched:
            return RouteDecision(
                intent="범위 밖",
                route="fast_path",
                route_confidence=0.4,
                fallback_reason="no_keyword_match",
            )

        is_comparison = any(marker in question for marker in _COMPARISON_MARKERS)
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
