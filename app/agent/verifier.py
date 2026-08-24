"""Verifier (A8): 숫자·근거·누락·단정을 검증해 최종 InternalAnswer를 만든다.

근거 없는 숫자, 근거 없는 단정적 추천 문구는 통과시키지 않고
type을 "limitation"으로 낮춘다 (문서 7장 Verifier 기준).
"""

import re

from app.agent.composer import Draft
from app.agent.router import RouteDecision
from app.api.schemas import CalculationResult, InternalAnswer, RequiredSlot, ThinkTrace, ToolCallTrace

_ASSERTIVE_PHRASES = (
    "무조건",
    "반드시 가입",
    "강력 추천",
    "가장 좋은 선택입니다",
    "최고의 상품",
    "무조건 이득",
)

_NUMBER_PATTERN = re.compile(r"\d[\d,]*\.?\d*")


class Verifier:
    def finalize(
        self,
        *,
        draft: Draft | None,
        request_id: str,
        session_id: str | None,
        route_decision: RouteDecision,
        tool_traces: list[ToolCallTrace],
        required_slots: list[RequiredSlot] | None = None,
        out_of_scope: bool = False,
    ) -> InternalAnswer:
        trace = ThinkTrace(
            intent=route_decision.intent,
            route=route_decision.route,
            route_confidence=route_decision.route_confidence,
            fallback_reason=route_decision.fallback_reason,
            tool_calls=tool_traces,
        )

        if required_slots:
            prompts = "; ".join(s.prompt for s in required_slots)
            return InternalAnswer(
                type="clarification",
                message=f"정확한 답변을 위해 아래 내용을 확인해 주세요: {prompts}",
                request_id=request_id,
                session_id=session_id,
                required_slots=required_slots,
                confidence=1.0,
                trace=trace,
            )

        if out_of_scope:
            return InternalAnswer(
                type="limitation",
                message="이 질문은 은퇴 자금(퇴직연금) 의사결정 범위를 벗어나 답변드리기 어렵습니다.",
                request_id=request_id,
                session_id=session_id,
                confidence=0.9,
                trace=trace,
            )

        assert draft is not None
        issues = self._check(draft)

        if issues:
            return InternalAnswer(
                type="limitation",
                message=(
                    f"{draft.message}\n\n[한계] 현재 제공된 근거만으로는 일부 내용을 충분히 "
                    f"검증하지 못했습니다 ({', '.join(issues)})."
                ),
                request_id=request_id,
                session_id=session_id,
                comparison=draft.comparison,
                withdrawal_result=draft.withdrawal_result,
                calculation_results=draft.calculation_results,
                citations=draft.citations,
                confidence=0.4,
                trace=trace,
            )

        confidence = 0.85 if (draft.calculation_results or draft.citations) else 0.6
        return InternalAnswer(
            type="result",
            message=draft.message,
            request_id=request_id,
            session_id=session_id,
            comparison=draft.comparison,
            withdrawal_result=draft.withdrawal_result,
            calculation_results=draft.calculation_results,
            citations=draft.citations,
            confidence=confidence,
            trace=trace,
        )

    def _check(self, draft: Draft) -> list[str]:
        issues: list[str] = []

        if not draft.citations and not draft.calculation_results:
            issues.append("근거·계산 결과 없음")

        for phrase in _ASSERTIVE_PHRASES:
            if phrase in draft.message:
                issues.append(f"단정적 표현('{phrase}')")

        unverified = self._unverified_numbers(draft.message, draft.calculation_results)
        if unverified and not draft.calculation_results:
            issues.append(f"근거 없는 숫자({', '.join(unverified[:3])})")

        return issues

    def _unverified_numbers(self, message: str, calculations: list[CalculationResult]) -> list[str]:
        known = {self._normalize(str(c.value)) for c in calculations}
        found = {self._normalize(m) for m in _NUMBER_PATTERN.findall(message)}
        return sorted(found - known)

    @staticmethod
    def _normalize(value: str) -> str:
        v = value.replace(",", "")
        if v.endswith(".0"):
            v = v[:-2]
        return v
