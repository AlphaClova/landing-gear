"""Verifier (A8): 숫자·근거·누락·단정을 검증해 최종 InternalAnswer를 만든다.

근거 없는 숫자, 근거 없는 단정적 추천 문구는 통과시키지 않고
type을 "limitation"으로 낮춘다 (문서 7장 Verifier 기준).
"""

import re
from decimal import Decimal, InvalidOperation

from app.agent.canonical import (
    answer_affirms_false_premise,
    answer_asserts_false_numeric_premise,
    detect_false_premise,
)
from app.agent.composer import Draft
from app.agent.product_evidence import allows_product_evidence_enrichment, answer_fee_mapping
from app.agent.router import RouteDecision
from app.api.schemas import CalculationResult, Citation, InternalAnswer, RequiredSlot, ThinkTrace, ToolCallTrace
from app.core.query_normalization import (
    UNKNOWN_TAX,
    has_retirement_scope_qualifier,
    is_db_dc_question,
    is_generic_pension_question,
    is_pension_receiving_question,
    is_tax_deduction_question,
    is_teacher_retirement_domain,
    pension_scopes,
    pension_year_rate_block_allowed,
    tax_intent,
    tax_source_types,
)

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

# Taxability polarity and tax-treatment claims. Patterns are semantic
# categories (taxability / exemption / rate / reduction), not exact-phrase blocks.
_TAXABILITY_NEGATIVE_RE = re.compile(
    r"(?:과세(?:가|는|를)?\s*(?:발생하지|되지|하지|이루어지지)\s*않|"
    r"비과세|"
    r"세금이\s*(?:없|발생하지\s*않|부과되지\s*않|붙지\s*않)|"
    r"(?:과세|세금)(?:가|이|은)?\s*(?:부과되지|이루어지지)\s*않|"
    r"과세\s*대상이\s*아닙|"
    r"세금을\s*(?:내지|안\s*내|떼지\s*않)|"
    r"세금\s*안\s*붙|"
    r"과세가\s*면제|"
    r"세금\s*부담이\s*없|"
    r"세금\s*없이|"
    r"과세\s*면제)"
)
_TAXABILITY_POSITIVE_RE = re.compile(
    r"(?:과세됩니다|과세가\s*발생(?!하지)|"
    r"과세의?\s*대상|"
    r"세금이\s*발생합니다|"
    r"세금을\s*(?:내야|납부해야)|"
    r"퇴직\s*소득세.{0,24}(?:납부|부과|차감|감면|공제)|"
    r"소득세를?\s*차감|"
    r"감면됩니다|"
    r"과세가\s*이루어)"
)
_TAX_ACCOUNT_TYPES = ("연금저축", "IRP")
_TAX_SOURCE_TYPES = ("법정외퇴직금", "법정퇴직금", "퇴직금재원", "개인납입금", "운용수익", "IRP추가납입", "추가납입")
_TAX_EVENTS = ("중도인출", "해지", "일시금", "연금수령")
_TAX_RATE_OR_REDUCTION_RE = re.compile(
    r"(?:\d+(?:\.\d+)?\s*%|감면|세율|과세이연)"
)
_LIMITATION_SKIP_MARKERS = (
    "[한계]", "[주의]", "확정할 수 없", "단정할 수 없", "확인할 수 없",
    "제공된 문서만으로", "뜻이 아닙니다", "일률적으로", "단정하지 않습니다",
)


class Verifier:
    def repair_safe(self, draft: Draft, issues: list[str]) -> bool:
        """Repair only text whose exact source is the immutable contract."""
        context = draft.context
        if not context:
            return False
        if "안전 거절 확장" in issues or "Rule 밖 금액 계산" in issues or "민감정보 응답 확장" in issues or "반올림 실패 응답 확장" in issues or "상품 한계 응답 확장" in issues or "핵심 grounded contract 변경 또는 일부 누락" in issues or "DB/DC fact inversion" in issues or "false-premise affirmation" in issues or "false-premise correction 누락" in issues or "limitation contract expansion" in issues or "unsupported hard constraint product dump" in issues or "unsupported factual claim" in issues or "future-return inference" in issues or "product unit confusion" in issues or "product fee mapping mismatch" in issues or "unsupported product recommendation" in issues or "pension scope mismatch" in issues or any(issue.startswith("근거 없는 숫자") for issue in issues):
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
        if context.response_mode == "clarification" and "필수 clarification correction 누락" in issues:
            draft.message = context.fallback_message
            draft.hcx_audit.append({"phase":"deterministic_repair", "violations":issues, "action":"restore_clarification_correction"})
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
            if context.required_facts and not all(fact in draft.message for fact in context.required_facts):
                issues.append("필수 clarification correction 누락")
            return issues
        if context and context.response_mode == "limitation":
            if not any(x in draft.message for x in ("어렵", "범위를 벗어나", "한계", "제공할 수 없")):
                issues.append("필수 limitation 누락")
            if draft.message.strip() != context.fallback_message.strip():
                issues.append("limitation contract expansion")
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

        if context and is_db_dc_question(context.question):
            compact = re.sub(r"\s+", "", draft.message)
            inverted_operator = bool(
                re.search(r"(?:DB|확정급여형).{0,35}(?:근로자|가입자).{0,12}(?:직접)?운용", compact)
                or re.search(r"(?:DC|확정기여형).{0,35}회사.{0,12}(?:직접)?운용", compact)
            )
            inverted_benefit = bool(
                re.search(r"(?:DC|확정기여형).{0,35}(?:급여|퇴직금).{0,15}(?:사전|미리).{0,8}확정", compact)
                or re.search(r"(?:DB|확정급여형).{0,35}(?:운용성과|수익률).{0,15}(?:급여|퇴직금).{0,8}(?:달라|변동)", compact)
            )
            if inverted_operator or inverted_benefit:
                issues.append("DB/DC fact inversion")

        if context and self._pension_scope_mismatch(context.question, draft.message, evidence_text):
            issues.append("pension scope mismatch")

        if context:
            support_blob = evidence_text + "\n" + "\n".join(context.required_facts + context.limitations) + repr(context.products)
            for term in ("TDF", "EMP"):
                if term in draft.message and term not in support_blob and term not in context.question:
                    issues.append("unsupported factual claim")
            if re.search(r"국민연금.{0,80}(?:5\.5|3\.3)|(?:5\.5|3\.3).{0,80}국민연금", draft.message) and "국민연금" not in evidence_text:
                issues.append("unsupported factual claim")
            if context.claim_plan:
                sourced = False
                for subtask in context.claim_plan:
                    for claim in subtask.get("claims", []) or []:
                        if not isinstance(claim, dict):
                            continue
                        if claim.get("evidence_ids") or claim.get("rule_result_ids") or claim.get("product_fact_ids"):
                            sourced = True
                if not sourced and any(marker in draft.message for marker in ("적용됩니다", "부과됩니다", "납부하게", "보장됩니다")):
                    if draft.message.strip() != (context.fallback_message or "").strip():
                        issues.append("unsupported factual claim")

        if context:
            hit = detect_false_premise(context.question, context.evidence, context.products)
            if context.false_premise or hit:
                if answer_affirms_false_premise(draft.message):
                    issues.append("false-premise affirmation")
                if hit and answer_asserts_false_numeric_premise(draft.message, hit.user_claim.value):
                    issues.append("false-premise affirmation")
                correction = context.correction_fact or (hit.correction if hit else None)
                if correction and correction not in draft.message:
                    issues.append("false-premise correction 누락")

            if any(marker in draft.message for marker in ("건강보험료", "건강보험")) and not any(
                marker in context.question for marker in ("건강보험료", "건강보험")
            ):
                issues.append("unsupported factual claim")

            if self._ungrounded_tax_liability_claim(draft, context, evidence_text):
                issues.append("unsupported factual claim")
            if self._unsupported_eligibility_relation(draft, context):
                issues.append("unsupported factual claim")

            classified = tax_intent(context.question)
            if classified and classified != "TAX_CREDIT" and not is_tax_deduction_question(context.question):
                support = "\n".join(citation.excerpt for citation in draft.citations)
                support += "\n" + "\n".join(context.required_facts + [context.correction_fact or ""])
                for marker in ("16.5%", "13.2%", "600만원", "900만원"):
                    if marker in draft.message and marker not in support and marker not in (context.correction_fact or ""):
                        issues.append("unsupported factual claim")
                        break
            if not pension_year_rate_block_allowed(classified):
                uses_year_rates = all(marker in draft.message.replace(" ", "") for marker in ("70%", "60%", "50%"))
                mixed_source = len(tax_source_types(context.question)) >= 3 and "재원" in draft.message
                if uses_year_rates and not mixed_source:
                    issues.append("wrong tax scope")

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
                if raw == "investment_horizon":
                    horizon = str(constraint.get("value", ""))
                    if horizon and re.search(rf"{re.escape(horizon)}\s*(?:투자\s*)?(?:후보|적합|추천)", draft.message):
                        issues.append("미적용 추천 조건을 적용한 표현")
                if constraint.get("kind") == "hard" and not constraint.get("applied") and context.products:
                    issues.append("unsupported hard constraint product dump")

        if context and context.calculations:
            money_pattern = re.compile(r"\d[\d,]*(?:\.\d+)?\s*(?:억|천만|백만|만)?\s*원")
            found_money = {self._normalize(x) for x in money_pattern.findall(draft.message)}
            rule_money = {self._normalize(str(item.value)) for item in context.calculations}
            if found_money - rule_money:
                issues.append("Rule 밖 금액 계산")

        if self._contradicts_limitation(draft.message):
            issues.append("한계와 모순되는 단정")
        answerable_plan = [
            item for item in (context.claim_plan if context else [])
            if item.get("status") == "answerable"
        ]
        generic_limit_only = bool(
            context
            and context.limitations
            and all("제공된 근거 안에서만" in item for item in context.limitations)
        )
        if context and context.limitations and not any(x in draft.message for x in ("[한계]", "[주의]")):
            if not (answerable_plan and generic_limit_only):
                issues.append("필수 limitation 누락")

        unverified = self._unverified_numbers(draft.message, draft.calculation_results, draft.citations)
        if context:
            found = {self._normalize(x) for x in _NUMBER_PATTERN.findall(re.sub(r"(?m)^\s*\d+\.\s*", "", draft.message))}
            allowed = {self._normalize(x) for x in context.allowed_numbers}
            unverified = sorted(found - allowed)
        if unverified and not draft.calculation_results:
            issues.append(f"근거 없는 숫자({', '.join(unverified[:3])})")

        if context and allows_product_evidence_enrichment(context.intent):
            expected_fee_mapping: dict[str, str] = {}
            for subtask in context.claim_plan:
                mapping = subtask.get("structured_fee_mapping")
                if isinstance(mapping, dict):
                    expected_fee_mapping.update({str(key): str(value) for key, value in mapping.items()})
            if expected_fee_mapping:
                stated = answer_fee_mapping(draft.message)
                if any(
                    value != expected_fee_mapping.get(label)
                    for label, values in stated.items()
                    for value in values
                ) or re.search(r"수수료\s*선취(?:\s*[-·]?\s*)오프라인.{0,16}\d+(?:\.\d+)?\s*%", draft.message):
                    issues.append("product fee mapping mismatch")

        if context and context.products:
            support = "\n".join(c.excerpt for c in context.evidence) + repr(context.products)
            for field in ("듀레이션", "변동성", "최적", "가장 적합", "더 안정적"):
                if field in draft.message and field not in support and field not in " ".join(context.limitations):
                    issues.append(f"근거 없는 상품 주장('{field}')")
            if allows_product_evidence_enrichment(context.intent):
                compact = re.sub(r"\s+", "", draft.message)
                if re.search(r"(향후|미래|기대)수익률|앞으로더좋", compact) and "미래성과를보장하지않는다" not in compact and "예측할수없습니다" not in compact:
                    issues.append("future-return inference")
                if re.search(r"(?:총비용 예시|투자 시 총비용).{0,40}\d+(?:\.\d+)?\s*%", draft.message):
                    issues.append("product unit confusion")
                if re.search(r"총보수·비용 비율.{0,16}\d+천원", draft.message):
                    issues.append("product unit confusion")
                if any(x in context.question for x in ("안정", "안전한")) and len(context.products) >= 2:
                    if re.search(r"(단기|중장기|장기).{0,24}(가장 안정|더 안정|추천합니다|가입하세요)", draft.message):
                        issues.append("unsupported product recommendation")

        return issues

    @staticmethod
    def _non_limitation_text(message: str) -> str:
        """Remove limitation sentences, not entire paragraphs containing one."""
        kept: list[str] = []
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", message):
            if any(marker in sentence for marker in _LIMITATION_SKIP_MARKERS):
                continue
            kept.append(sentence)
        return "\n".join(kept)

    @classmethod
    def _taxability_polarity(cls, text: str) -> tuple[bool, bool]:
        return bool(_TAXABILITY_POSITIVE_RE.search(text)), bool(_TAXABILITY_NEGATIVE_RE.search(text))

    @classmethod
    def _answerable_tax_contract(cls, context) -> str:
        parts = list(context.required_facts)
        if context.correction_fact:
            parts.append(context.correction_fact)
        for subtask in context.claim_plan:
            if subtask.get("status") != "answerable":
                continue
            for claim in subtask.get("claims") or []:
                if isinstance(claim, dict) and claim.get("text"):
                    parts.append(str(claim["text"]))
        return "\n".join(parts)

    @staticmethod
    def _tax_liability_tuple(text: str) -> tuple[set[str], set[str], set[str]]:
        compact = re.sub(r"\s+", "", text)
        accounts = {marker for marker in _TAX_ACCOUNT_TYPES if marker in compact}
        sources = {marker for marker in _TAX_SOURCE_TYPES if marker in compact}
        events = {marker for marker in _TAX_EVENTS if marker in compact}
        return accounts, sources, events

    @classmethod
    def _is_tuple_sensitive(cls, text: str) -> bool:
        accounts, sources, events = cls._tax_liability_tuple(text)
        return bool(accounts and sources and events)

    @classmethod
    def _directly_supported_tax_relation(
        cls, sentence: str, context, *, require_question_entities: bool = False,
    ) -> bool:
        """Require tax polarity and the claim tuple in one support item."""
        claim_pos, claim_neg = cls._taxability_polarity(sentence)
        if not claim_pos and not claim_neg:
            return True
        accounts, sources, events = cls._tax_liability_tuple(sentence)
        contract_items = [
            str(claim.get("text", ""))
            for subtask in context.claim_plan
            if subtask.get("status") == "answerable"
            for claim in (subtask.get("claims") or [])
            if isinstance(claim, dict) and claim.get("text")
        ]
        question_compact = re.sub(r"\s+", "", context.question)
        claimed = accounts | sources | events
        evidence_relevant = not require_question_entities or (
            bool(claimed) and all(entity in question_compact for entity in claimed)
        )
        support_items = contract_items + (
            [citation.excerpt for citation in context.evidence] if evidence_relevant else []
        )
        for support in support_items:
            support_accounts, support_sources, support_events = cls._tax_liability_tuple(support)
            if accounts - support_accounts or sources - support_sources or events - support_events:
                continue
            support_pos, support_neg = cls._taxability_polarity(support)
            if (claim_pos and support_pos) and (not claim_neg or support_neg):
                return True
            if claim_neg and support_neg and not claim_pos:
                return True
        return False

    def _ungrounded_tax_liability_claim(self, draft: Draft, context, evidence_text: str) -> bool:
        """Require same-scope Evidence/Rule/claim-plan for tax factual claims.

        Covers taxability polarity, exemption, rate, and reduction.
        Tax-liability sentences are checked even when TAX_INTENT is None.
        """
        remaining = self._non_limitation_text(draft.message)
        if not remaining.strip():
            return False
        fallback = (context.fallback_message or "").strip()
        if remaining.strip() == fallback:
            return False
        pos, neg = self._taxability_polarity(remaining)
        rate_or_reduction = bool(_TAX_RATE_OR_REDUCTION_RE.search(remaining))
        classified = tax_intent(context.question)
        unknown = classified == UNKNOWN_TAX
        if not pos and not neg and not (unknown and rate_or_reduction):
            return False
        liability_sentences = [
            sentence for sentence in re.split(r"(?<=[.!?])\s+|\n+", remaining)
            if any(self._taxability_polarity(sentence))
        ]
        if self._is_tuple_sensitive(remaining) and not self._directly_supported_tax_relation(remaining, context):
            return True
        if any(
            self._is_tuple_sensitive(sentence)
            and not self._directly_supported_tax_relation(sentence, context)
            for sentence in liability_sentences
        ):
            return True
        if unknown:
            if liability_sentences:
                return any(
                    not self._directly_supported_tax_relation(
                        sentence, context, require_question_entities=True,
                    )
                    for sentence in liability_sentences
                )
        contract = self._answerable_tax_contract(context)
        if unknown:
            support = contract
        else:
            support = "\n".join([contract, evidence_text, repr(context.calculations)])
        sup_pos, sup_neg = self._taxability_polarity(support)
        if neg and not sup_neg:
            return True
        if pos and not sup_pos:
            return True
        if unknown and rate_or_reduction and not _TAX_RATE_OR_REDUCTION_RE.search(support):
            return True
        return False

    @staticmethod
    def _unsupported_eligibility_relation(draft: Draft, context) -> bool:
        compact = re.sub(r"\s+", "", draft.message)
        negative = bool(re.search(r"(?:가입|적용)대상이?아니|가입대상이아닙", compact))
        separate = "별도" in compact and "제도" in compact and "적용" in compact
        if not negative and not separate:
            return False
        entities = tuple(
            marker for marker in ("공무원", "군인", "사립학교교직원", "선원")
            if marker in compact
        )
        if not entities:
            return False
        for citation in context.evidence:
            support = re.sub(r"\s+", "", citation.excerpt)
            if not all(entity in support for entity in entities):
                continue
            supports_negative = "가입대상" in support and "아닙" in support
            supports_separate = "별도" in support and "퇴직급여제도" in support and "적용" in support
            if (not negative or supports_negative) and (not separate or supports_separate):
                return False
        return True

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

    @staticmethod
    def _pension_scope_mismatch(question: str, message: str, evidence_text: str) -> bool:
        specific = pension_scopes(question)
        compact = re.sub(r"\s+", "", message)
        retirement_in_answer = "퇴직연금" in message
        receiving_fact = any(token in compact for token in ("받을수", "수령", "55세", "만55"))
        qualified = has_retirement_scope_qualifier(message)
        if is_generic_pension_question(question):
            if ("55세" in compact or "만55" in compact) and not qualified:
                return True
            return bool(retirement_in_answer and receiving_fact and not qualified)
        if specific == ("PENSION_SAVINGS",):
            return bool(retirement_in_answer and receiving_fact)
        if "NATIONAL_PENSION" in specific:
            if retirement_in_answer and "국민연금" not in evidence_text:
                return True
            return bool(("55세" in compact or "만55" in compact) and "국민연금" not in evidence_text)
        if specific == ("IRP",) and is_pension_receiving_question(question):
            irp_named = "IRP" in message.upper() or "개인형" in message
            return bool(retirement_in_answer and receiving_fact and not irp_named)
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
