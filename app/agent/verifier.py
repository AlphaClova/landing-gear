"""Verifier (A8): 숫자·근거·누락·단정을 검증해 최종 InternalAnswer를 만든다.

근거 없는 숫자, 근거 없는 단정적 추천 문구는 통과시키지 않고
type을 "limitation"으로 낮춘다 (문서 7장 Verifier 기준).
"""

import re
from decimal import Decimal, InvalidOperation

from app.agent.composer import Draft
from app.agent.router import RouteDecision
from app.api.schemas import CalculationResult, Citation, InternalAnswer, RequiredSlot, ThinkTrace, ToolCallTrace
from app.core.query_normalization import is_teacher_retirement_domain

_ASSERTIVE_PHRASES = (
    "무조건",
    "반드시 가입",
    "강력 추천",
    "가장 좋은 선택입니다",
    "최고의 상품",
    "무조건 이득",
)

_UNSUPPORTED_GENERALIZATIONS = ("대기업", "공공기관", "중소기업", "스타트업")
_SOURCE_REQUIRED_TERMS = (
    "듀레이션", "금리 민감도", "변동성", "예금자보호", "원금 보장", "원금보장",
    "중간정산", "더 안전", "더 안정", "절세에 유리", "일반적입니다",
)
_UNREQUESTED_ADVICE = ("전문가의 조언", "전문가와의 상담", "전문가의 상담", "전문가와 상담", "상담을 받아", "전략을 수립", "중요합니다", "신중하게 결정", "장기적 관점")
_LIMIT_MARKERS = ("[주의]", "[한계]", "단정할 수 없습니다", "확정할 수 없습니다", "확인할 수 없습니다", "확인해야", "개인별", "정보가 없습니다", "근거가 없습니다")
_DEFINITIVE_AFTER_LIMIT = (
    "매우 효과적",
    "효과를 누릴 수",
    "더 안정적",
    "가장 안정적",
    "반드시 유리",
    "무조건 유리",
)

_NUMBER_PATTERN = re.compile(r"\d[\d,]*(?:\.\d+)?(?:\s*(?:억|천만|백만|만)\s*원|\s*원|\s*%)?")


class Verifier:
    def repair_safe(self, draft: Draft, issues: list[str]) -> bool:
        """Repair only text whose exact source is the immutable contract."""
        context = draft.context
        if not context:
            return False
        if "안전 거절 확장" in issues or "Rule 밖 금액 계산" in issues or "민감정보 응답 확장" in issues or "반올림 실패 응답 확장" in issues or "상품 한계 응답 확장" in issues or "핵심 grounded contract 변경 또는 일부 누락" in issues:
            draft.message = context.fallback_message
            draft.hcx_audit.append({"phase":"deterministic_repair", "violations":issues, "action":"restore_grounded_contract"})
            return not self.check(draft)
        if issues and all(issue == "필수 limitation 누락" for issue in issues) and context.limitations:
            draft.message = f"{draft.message.rstrip()}\n\n" + "\n".join(context.limitations)
            draft.hcx_audit.append({"phase":"deterministic_repair", "violations":issues, "action":"append_contract_limitation"})
            return not self.check(draft)
        if context.response_mode == "clarification" and issues and all(issue.startswith("요청하지 않은 clarification") for issue in issues):
            allowed = " ".join(slot.prompt for slot in context.required_clarifications)
            forbidden = [marker for marker in ("DB", "DC", "IRP") if marker not in allowed]
            repaired = "\n".join(line for line in draft.message.splitlines() if not any(m in line for m in forbidden)).strip()
            if repaired:
                draft.message = repaired
                draft.hcx_audit.append({"phase":"deterministic_repair", "violations":issues, "action":"remove_extra_slot_line"})
                return not self.check(draft)
        if context.response_mode == "clarification" and issues and all(
            issue.startswith("clarification") or issue.startswith("요청하지 않은 clarification") for issue in issues
        ):
            draft.message = "정확한 답변을 위해 " + "; ".join(slot.prompt for slot in context.required_clarifications)
            draft.hcx_audit.append({"phase":"deterministic_repair", "violations":issues, "action":"restrict_to_required_slots"})
            return not self.check(draft)
        return False

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
            hcx_invoked=bool(draft and draft.hcx_invoked),
            hcx_attempts=draft.hcx_attempts if draft else 0,
            hcx_success=bool(draft and draft.hcx_success),
            hcx_first_pass=bool(draft and draft.hcx_first_pass),
            hcx_regenerated=bool(draft and draft.hcx_regenerated),
            deterministic_repaired=bool(draft and draft.deterministic_repaired),
            hcx_timeout_count=draft.hcx_timeout_count if draft else 0,
            degraded=bool(draft and draft.degraded),
            degraded_reason=draft.degraded_reason if draft else None,
            degraded_fallback=draft.degraded_fallback if draft else None,
            fallback_used=bool(draft and draft.fallback_used),
            hcx_fallback_reason=draft.fallback_reason if draft else None,
            hcx_audit=draft.hcx_audit if draft else [],
            prompt_metrics=draft.prompt_metrics if draft else {},
            rule_results=[
                {"rule_id": item.rule_id, "rule_version": item.rule_version, "label": item.label,
                 "value": item.value, "unit": item.unit, "rate": item.rate, "formula": item.formula}
                for item in (draft.calculation_results if draft else [])
            ],
            product_facts=[
                {key: value for key, value in item.items() if key in {"product_id", "document_id", "page", "product_name", "asset_type", "risk_level", "risk_label", "plan_types"}}
                for item in (draft.context.products if draft and draft.context else [])
            ],
            claim_plan=draft.context.claim_plan if draft and draft.context else [],
            recommendation_constraints=draft.context.recommendation_constraints if draft and draft.context else [],
        )

        if required_slots:
            assert draft is not None
            return InternalAnswer(
                type="clarification",
                message=draft.message,
                request_id=request_id,
                session_id=session_id,
                required_slots=required_slots,
                confidence=1.0,
                trace=trace,
            )

        if out_of_scope:
            assert draft is not None
            return InternalAnswer(
                type="limitation",
                message=draft.message,
                request_id=request_id,
                session_id=session_id,
                confidence=0.9,
                trace=trace,
            )

        assert draft is not None
        issues = self.check(draft)

        if issues:
            if any(issue.startswith("근거 없는 숫자") for issue in issues):
                subject = {
                    "제도": "DB·DC 등 퇴직연금 제도 설명에 포함된",
                    "세제": "요청하신 세액공제·세율 등",
                    "상품": "상품 비교에 포함된",
                    "절차": "퇴직연금 절차 설명에 포함된",
                    "종합": "퇴직연금 비교에 포함된",
                }.get(route_decision.intent, "답변에 포함된")
                message = (
                    f"[한계] 현재 제공된 근거와 계산 결과만으로는 {subject} 수치를 정확히 "
                    "확인할 수 없습니다. 확인되지 않은 숫자는 안내하지 않습니다."
                )
            elif any(issue.startswith("한계와 모순") for issue in issues):
                message = (
                    "[한계] 현재 제공된 근거만으로는 질문의 적용 여부나 우열을 확정할 수 없습니다. "
                    "한계와 모순되는 단정적 결론은 제공하지 않습니다."
                )
            else:
                message = (
                    f"{draft.message}\n\n[한계] 현재 제공된 근거만으로는 일부 내용을 충분히 "
                    f"검증하지 못했습니다 ({', '.join(issues)})."
                )
            return InternalAnswer(
                type="limitation",
                message=message,
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

    def check(self, draft: Draft) -> list[str]:
        issues: list[str] = []

        context = draft.context
        if context and context.response_mode == "clarification":
            allowed = " ".join(slot.prompt for slot in context.required_clarifications)
            for marker in ("DB", "DC", "IRP"):
                if marker in draft.message and marker not in allowed:
                    issues.append(f"요청하지 않은 clarification('{marker}')")
            if "Departmental Retirement Pension" in draft.message:
                issues.append("근거 없는 clarification 설명")
            allowed_numbers = {self._normalize(x) for x in _NUMBER_PATTERN.findall(allowed + " " + context.question)}
            found_numbers = {self._normalize(x) for x in _NUMBER_PATTERN.findall(draft.message)}
            if found_numbers - allowed_numbers:
                issues.append("clarification extra number")
            factual_markers = ("계산됩니다", "부과됩니다", "감면됩니다", "적용됩니다", "유리합니다", "책임입니다", "보장됩니다")
            if any(marker in draft.message for marker in factual_markers):
                issues.append("clarification factual expansion")
            return issues
        if context and context.response_mode == "limitation":
            if not any(x in draft.message for x in ("어렵", "범위를 벗어나", "한계", "제공할 수 없")):
                issues.append("필수 limitation 누락")
            return issues

        if not draft.citations and not draft.calculation_results:
            issues.append("근거·계산 결과 없음")

        for phrase in _ASSERTIVE_PHRASES:
            if phrase in draft.message and not self._negated_assertion(draft.message, phrase):
                issues.append(f"단정적 표현('{phrase}')")

        evidence_text = "\n".join(citation.excerpt for citation in draft.citations)
        support_text = evidence_text
        if context:
            support_text += "\n" + "\n".join(context.required_facts + context.limitations)
            support_text += "\n" + repr(context.products)
        for phrase in _UNSUPPORTED_GENERALIZATIONS:
            if phrase in draft.message and phrase not in evidence_text:
                issues.append(f"근거 없는 일반화('{phrase}')")
        for phrase in _SOURCE_REQUIRED_TERMS:
            if phrase in draft.message and phrase not in support_text:
                issues.append(f"근거 없는 금융 사실('{phrase}')")
        for phrase in _UNREQUESTED_ADVICE:
            if phrase in draft.message and phrase not in support_text:
                issues.append(f"근거 없는 조언('{phrase}')")

        if context and "절세 전략 또는 중간정산 대안 추가" in context.forbidden_behaviors:
            if draft.message.strip() != context.fallback_message.strip():
                issues.append("안전 거절 확장")
        if context and "민감정보 조회 방법 또는 수집 요청 추가" in context.forbidden_behaviors:
            if draft.message.strip() != context.fallback_message.strip():
                issues.append("민감정보 응답 확장")
        if context and "반올림 정책 없는 계산 또는 대체 세율 추가" in context.forbidden_behaviors:
            if draft.message.strip() != context.fallback_message.strip():
                issues.append("반올림 실패 응답 확장")
        if context and "상품 비교 한계 외 사실 추가" in context.forbidden_behaviors:
            if draft.message.strip() != context.fallback_message.strip():
                issues.append("상품 한계 응답 확장")
        if context and "핵심 grounded contract 변경 또는 일부 누락" in context.forbidden_behaviors:
            if draft.message.strip() != context.fallback_message.strip():
                issues.append("핵심 grounded contract 변경 또는 일부 누락")

        if context and is_teacher_retirement_domain(context.question) and any(
            item.document_id == "doc26" for item in context.evidence
        ):
            population_subtasks = {
                "benefit_legal_character", "account_transfer_or_deposit",
                "tax_refund_procedure", "retirement_tax_effect",
            }
            if any(item.get("subtask") in population_subtasks for item in context.claim_plan) and not any(
                marker in draft.message for marker in ("교사", "공무원", "명예퇴직수당", "명퇴수당")
            ):
                issues.append("population-specific evidence 누락")

        if context:
            for constraint in context.recommendation_constraints:
                if constraint.get("applied"):
                    continue
                raw = str(constraint.get("constraint", ""))
                if raw.startswith("investment_horizon="):
                    years = raw.split("=", 1)[1].removesuffix("y")
                    if re.search(rf"{re.escape(years)}년\s*(?:투자\s*)?(?:후보|적합|추천)", draft.message):
                        issues.append("미적용 추천 조건을 적용한 표현")

        if context and context.calculations:
            money_pattern = re.compile(r"\d[\d,]*(?:\.\d+)?\s*(?:억|천만|백만|만)?\s*원")
            found_money = {self._normalize(x) for x in money_pattern.findall(draft.message)}
            rule_money = {self._normalize(str(item.value)) for item in context.calculations}
            if found_money - rule_money:
                issues.append("Rule 밖 금액 계산")

        if self._contradicts_limitation(draft.message):
            issues.append("한계와 모순되는 단정")
        if context and context.limitations and not any(x in draft.message for x in ("[한계]", "[주의]")):
            issues.append("필수 limitation 누락")

        unverified = self._unverified_numbers(draft.message, draft.calculation_results, draft.citations)
        if context:
            found = {self._normalize(x) for x in _NUMBER_PATTERN.findall(re.sub(r"(?m)^\s*\d+\.\s*", "", draft.message))}
            allowed = {self._normalize(x) for x in context.allowed_numbers}
            unverified = sorted(found - allowed)
        if unverified and not draft.calculation_results:
            issues.append(f"근거 없는 숫자({', '.join(unverified[:3])})")

        if context and context.products:
            support = "\n".join(c.excerpt for c in context.evidence) + repr(context.products)
            for field in ("듀레이션", "변동성", "최적", "가장 적합", "더 안정적"):
                if field in draft.message and field not in support and field not in " ".join(context.limitations):
                    issues.append(f"근거 없는 상품 주장('{field}')")

        return issues

    @staticmethod
    def _negated_assertion(message: str, phrase: str) -> bool:
        for match in re.finditer(re.escape(phrase), message):
            before = message[max(0, match.start() - 6):match.start()]
            after = message[match.end():match.end() + 35]
            if any(marker in before for marker in ("아닙", "않")) or any(
                marker in after for marker in ("아닙", "않", "수 없", "단정할 수 없", "결론낼 수 없")
            ):
                return True
        return False

    def _check(self, draft: Draft) -> list[str]:
        return self.check(draft)

    @classmethod
    def _contradicts_limitation(cls, message: str) -> bool:
        positions = [message.find(marker) for marker in _LIMIT_MARKERS if marker in message]
        if not positions:
            return False
        suffix = message[min(positions):]
        return any(claim in suffix and not cls._negated_assertion(suffix, claim) for claim in _DEFINITIVE_AFTER_LIMIT)

    def _unverified_numbers(
        self, message: str, calculations: list[CalculationResult], citations: list[Citation]
    ) -> list[str]:
        known = {self._normalize(str(c.value)) for c in calculations}
        for citation in citations:
            known.update(self._normalize(m) for m in _NUMBER_PATTERN.findall(citation.excerpt))
        without_list_markers = re.sub(r"(?m)^\s*\d+\.\s*", "", message)
        found = {self._normalize(m) for m in _NUMBER_PATTERN.findall(without_list_markers)}
        return sorted(found - known)

    @staticmethod
    def _normalize(value: str) -> str:
        compact = re.sub(r"\s+", "", value).replace(",", "")
        match = re.fullmatch(r"(\d+(?:\.\d+)?)(억|천만|백만|만)?원?%?", compact)
        if not match:
            return compact
        try:
            number = Decimal(match.group(1))
        except InvalidOperation:
            return compact
        scale = {
            "억": Decimal("100000000"),
            "천만": Decimal("10000000"),
            "백만": Decimal("1000000"),
            "만": Decimal("10000"),
        }.get(match.group(2), Decimal(1))
        normalized = number * scale
        return format(normalized.normalize(), "f")
