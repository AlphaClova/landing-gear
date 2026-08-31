"""Build an immutable grounding contract and let HCX synthesize its wording."""

from dataclasses import dataclass, field
import json
import re

from app.agent.hcx_client import HCXClient
from app.agent.router import Intent
from app.agent.tools import ToolResult
from app.api.schemas import CalculationResult, Citation, ComparisonResult, ComparisonRow, RequiredSlot, WithdrawalComparisonResponse
from app.core.query_normalization import has_alias, has_legally_named_retirement_benefit, is_comparison_question, is_db_dc_question, is_tax_deduction_question, is_teacher_retirement_domain, needs_retirement_benefit_clarification, retirement_benefit_subtasks
from app.core.errors import ErrorCode, HCXError

_SYSTEM_PROMPT = """제공된 계약만 자연스러운 한국어 답변으로 바꾸세요.
1) REQUIRED_FACTS를 빠짐없이 유지하고, 그 밖의 사실·상식·예시·계산·조언을 추가하지 마세요.
2) 숫자는 ALLOWED_NUMBERS만 그대로 쓰며 곱셈, 환산, 절세액 계산을 하지 마세요.
3) LIMITATIONS는 [한계] 또는 [주의] 표지와 함께 그대로 유지하세요.
4) clarification은 REQUIRED_CLARIFICATIONS만 질문하고 다른 계좌나 조건을 묻지 마세요.
5) 상품 우열·적합성·추천을 단정하지 마세요. 답변 본문만 출력하세요."""


@dataclass
class GroundedContext:
    question: str
    intent: Intent
    response_mode: str
    evidence: list[Citation] = field(default_factory=list)
    products: list[dict] = field(default_factory=list)
    calculations: list[CalculationResult] = field(default_factory=list)
    required_facts: list[str] = field(default_factory=list)
    allowed_numbers: list[str] = field(default_factory=list)
    forbidden_behaviors: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    required_clarifications: list[RequiredSlot] = field(default_factory=list)
    fallback_message: str = ""
    false_premise: str | None = None
    correction_fact: str | None = None
    correction_evidence_id: str | None = None
    claim_plan: list[dict[str, object]] = field(default_factory=list)
    recommendation_constraints: list[dict[str, object]] = field(default_factory=list)


@dataclass
class Draft:
    message: str
    citations: list[Citation] = field(default_factory=list)
    calculation_results: list[CalculationResult] = field(default_factory=list)
    comparison: ComparisonResult | None = None
    withdrawal_result: WithdrawalComparisonResponse | None = None
    context: GroundedContext | None = None
    hcx_invoked: bool = False
    hcx_attempts: int = 0
    hcx_success: bool = False
    hcx_first_pass: bool = False
    hcx_regenerated: bool = False
    deterministic_repaired: bool = False
    hcx_timeout_count: int = 0
    degraded: bool = False
    degraded_reason: str | None = None
    degraded_fallback: str | None = None
    hcx_audit: list[dict[str, object]] = field(default_factory=list)
    prompt_metrics: dict[str, int] = field(default_factory=dict)
    fallback_used: bool = False
    fallback_reason: str | None = None
    request_id: str | None = None
    case_id: str | None = None


class Composer:
    def __init__(self, hcx_client: HCXClient) -> None:
        self._hcx = hcx_client

    def _complete(self, system_prompt: str, user_prompt: str, *, max_tokens: int, request_id: str | None, case_id: str | None) -> str:
        if isinstance(self._hcx, HCXClient):
            return self._hcx.complete(system_prompt, user_prompt, max_tokens=max_tokens, request_id=request_id, case_id=case_id)
        return self._hcx.complete(system_prompt, user_prompt, max_tokens=max_tokens)

    def compose(self, question: str, intent: Intent, tool_result: ToolResult | None = None, *, required_slots: list[RequiredSlot] | None = None, out_of_scope: bool = False, violations: list[str] | None = None, request_id: str | None = None, case_id: str | None = None) -> Draft:
        result = tool_result or ToolResult()
        context = self.build_context(question, intent, result, required_slots=required_slots, out_of_scope=out_of_scope)
        prompt = self._prompt(context, violations)
        try:
            message = self._complete(_SYSTEM_PROMPT, prompt, max_tokens=280, request_id=request_id, case_id=case_id).strip()
        except HCXError as exc:
            if not self._can_render_without_hcx(context):
                raise
            reason = self._degraded_reason(exc)
            return Draft(
                message=context.fallback_message,
                citations=result.evidence,
                calculation_results=result.calculations,
                comparison=self._build_comparison(intent, result.calculations, result.withdrawal_result),
                withdrawal_result=result.withdrawal_result,
                context=context,
                hcx_invoked=True,
                hcx_attempts=getattr(self._hcx, "last_attempts", 0),
                hcx_success=False,
                hcx_timeout_count=getattr(self._hcx, "last_timeout_count", 0),
                degraded=True,
                degraded_reason=reason,
                degraded_fallback="deterministic_grounded",
                hcx_audit=[{"phase": "initial", "output": None, "transport": getattr(self._hcx, "last_attempt_details", []),
                            "degraded": True, "degraded_reason": reason, "fallback": "deterministic_grounded"}],
                prompt_metrics=self._prompt_metrics(context, prompt),
                fallback_used=True,
                fallback_reason=reason,
                request_id=request_id,
                case_id=case_id,
            )
        return Draft(message=message, citations=result.evidence, calculation_results=result.calculations,
                     comparison=self._build_comparison(intent, result.calculations, result.withdrawal_result), withdrawal_result=result.withdrawal_result,
                     context=context, hcx_invoked=True, hcx_attempts=getattr(self._hcx, "last_attempts", 1) or 1,
                     hcx_success=getattr(self._hcx, "last_success", True), hcx_timeout_count=getattr(self._hcx, "last_timeout_count", 0),
                     hcx_audit=[{"phase":"initial", "output":message, "transport":getattr(self._hcx, "last_attempt_details", [])}],
                     prompt_metrics=self._prompt_metrics(context, prompt), request_id=request_id, case_id=case_id)

    @staticmethod
    def _can_render_without_hcx(context: GroundedContext) -> bool:
        if context.response_mode in {"clarification", "limitation"}:
            return bool(context.fallback_message)
        return bool(context.fallback_message and (context.evidence or context.calculations or context.products))

    @staticmethod
    def _degraded_reason(exc: HCXError) -> str:
        if exc.code == ErrorCode.UPSTREAM_TIMEOUT:
            return "HCX_TIMEOUT"
        return "HCX_RATE_LIMIT" if any(
            item.get("upstream_http_status") == 429
            for item in getattr(exc, "attempt_details", [])
        ) else "HCX_UNAVAILABLE"

    def regenerate(self, draft: Draft, violations: list[str]) -> Draft:
        assert draft.context is not None
        prompt = self._prompt(draft.context, violations)
        draft.message = self._complete(_SYSTEM_PROMPT, prompt, max_tokens=280, request_id=draft.request_id, case_id=draft.case_id).strip()
        draft.hcx_attempts += getattr(self._hcx, "last_attempts", 1) or 1
        draft.hcx_success = draft.hcx_success or getattr(self._hcx, "last_success", True)
        draft.hcx_regenerated = True
        draft.hcx_timeout_count += getattr(self._hcx, "last_timeout_count", 0)
        draft.hcx_audit.append({"phase":"regeneration", "input_violations":violations, "output":draft.message,
                                "transport":getattr(self._hcx, "last_attempt_details", [])})
        return draft

    @staticmethod
    def use_fallback(draft: Draft, reason: str) -> Draft:
        assert draft.context is not None
        draft.message = draft.context.fallback_message
        draft.fallback_used = True
        draft.fallback_reason = reason
        return draft

    def build_context(self, question: str, intent: Intent, result: ToolResult, *, required_slots: list[RequiredSlot] | None = None, out_of_scope: bool = False) -> GroundedContext:
        forbidden = ["새 숫자 또는 계산", "근거 없는 금융 사실", "단정적 상품 추천", "한계와 모순되는 결론"]
        if required_slots and not (result.evidence or result.calculations or result.products):
            prompts = "; ".join(slot.prompt for slot in required_slots)
            return GroundedContext(question, intent, "clarification", required_clarifications=required_slots,
                forbidden_behaviors=forbidden, fallback_message=f"정확한 답변을 위해 아래 내용을 확인해 주세요: {prompts}")
        if out_of_scope:
            fallback = "이 질문은 은퇴 자금(퇴직연금) 의사결정 범위를 벗어나 답변드리기 어렵습니다."
            return GroundedContext(question, intent, "limitation", limitations=[fallback], forbidden_behaviors=forbidden, fallback_message=fallback)
        if has_alias(question, "tax_evasion"):
            fallback = (
                "[거절] 세금을 불법적으로 회피하는 방법은 안내할 수 없습니다. "
                "합법적인 범위의 안내도 현재 요청에서 확보된 Evidence 또는 Rule Result 안에서만 제공할 수 있습니다."
            )
            return GroundedContext(
                question, intent, "result", result.evidence, result.products, result.calculations,
                [fallback], [], forbidden + ["절세 전략 또는 중간정산 대안 추가"], [], [], fallback,
            )
        if has_alias(question, "sensitive_data"):
            fallback = "[거절] 주민번호·계좌번호·비밀번호 같은 민감정보를 대신 조회하거나 저장할 수 없습니다."
            return GroundedContext(
                question, intent, "result", result.evidence, result.products, result.calculations,
                [fallback], [], forbidden + ["민감정보 조회 방법 또는 수집 요청 추가"], [], [], fallback,
            )
        if result.limitations:
            fallback = "\n".join(result.limitations)
            return GroundedContext(
                question, intent, "result", result.evidence, result.products, result.calculations,
                result.limitations, [], forbidden + ["반올림 정책 없는 계산 또는 대체 세율 추가"], result.limitations, [], fallback,
            )
        if needs_retirement_benefit_clarification(question):
            fallback = ("[한계] 질문의 조기퇴직 보상금이 제공 문서의 명예퇴직수당과 같은 법적 성격인지 확인할 수 없습니다. "
                        "doc26의 명예퇴직수당 규칙을 바로 적용하지 않고, 지급기관이 사용하는 정확한 수당 명칭과 법적 성격을 먼저 확인해야 합니다.")
            return GroundedContext(question, intent, "result", result.evidence, result.products, result.calculations,
                [fallback], [], forbidden, [fallback], [], fallback)
        correction = self._false_premise_correction(question, result)
        if correction:
            fallback, evidence_id = correction
            return GroundedContext(question, intent, "result", result.evidence, result.products, result.calculations,
                [fallback], self._allowed_numbers(result), forbidden, [], [], fallback,
                false_premise=question, correction_fact=fallback, correction_evidence_id=evidence_id)
        claim_plan = self._build_claim_plan(question, result)
        if required_slots and any(slot.name in {"plan_type", "investment_horizon", "risk_tolerance"} for slot in required_slots):
            # Do not render an unfiltered catalog while recommendation constraints
            # are incomplete. Other answerable procedure/tax subtasks remain.
            claim_plan = [item for item in claim_plan if item.get("subtask") != "product_facts"]
        fallback = self._render_claim_plan(claim_plan) or self._grounded_message(question, result)
        if required_slots:
            prompts = "; ".join(slot.prompt for slot in required_slots)
            partial = fallback or "[한계] 현재 제공된 근거로 답할 수 있는 범위만 안내합니다."
            fallback = f"{partial}\n[필요한 조건] {prompts}"
        facts = self._required_facts(question, result, fallback)
        if fallback is None:
            fallback = "[한계] 제공된 근거 안에서만 답변할 수 있으며, 확인되지 않은 내용은 단정할 수 없습니다."
        if not result.evidence and not result.calculations and not result.products:
            return GroundedContext(question, intent, "limitation", limitations=[fallback], forbidden_behaviors=forbidden,
                fallback_message=fallback, required_facts=[fallback])
        limits = [x.strip() for x in re.findall(r"\[(?:주의|한계)\][^\n]+", fallback)]
        if fallback.startswith("[한계] 비교할 특정 상품"):
            forbidden.append("상품 비교 한계 외 사실 추가")
        allowed_numbers = self._allowed_numbers(result)
        # Claim-plan text is permitted only when its provenance is explicit. This
        # keeps the number verifier aligned with deterministic fallback claims.
        grounded_claim_text = " ".join(
            str(claim.get("text", ""))
            for subtask in claim_plan
            for claim in subtask.get("claims", [])  # type: ignore[union-attr]
            if isinstance(claim, dict)
        )
        allowed_numbers = sorted(set(allowed_numbers) | set(re.findall(
            r"\d[\d,]*(?:\.\d+)?(?:\s*(?:억|천만|백만|만)\s*원|\s*원|\s*%)?", grounded_claim_text
        )))
        if self._is_tax_deduction_question(question, result):
            allowed_numbers = ["600만원", "900만원", "16.5%", "13.2%"]
        sensitive_contract = (
            self._is_tax_deduction_question(question, result)
            or len(result.tax_source_types) >= 3
            or result.procedure_type is not None
            or result.withdrawal_result is not None
            or bool(result.products)
            or len([part for part in fallback.split("\n\n") if part.strip()]) > 1
        )
        if sensitive_contract:
            forbidden.append("핵심 grounded contract 변경 또는 일부 누락")
        return GroundedContext(question, intent, "result", result.evidence, result.products, result.calculations,
            facts, allowed_numbers, forbidden, limits, [], fallback,
            claim_plan=claim_plan, recommendation_constraints=result.recommendation_constraints)

    @staticmethod
    def _required_facts(question: str, result: ToolResult, fallback: str | None) -> list[str]:
        closed = (fallback is not None or Composer._is_db_dc_explanation(question, result) or Composer._is_tax_deduction_question(question, result)
                  or Composer._is_teacher_retirement_question(question, result) or Composer._is_grounded_product_compare(question, result)
                  or result.withdrawal_result is not None
                  or (has_alias(question, "product_feature") and not has_alias(question, "product_family"))
                  or (has_alias(question, "product_family") and has_alias(question, "principal_protection"))
                  or (has_alias(question, "institution") and "일반" in question)
                  or (has_alias(question, "irp") and has_alias(question, "dc")))
        return [x.strip() for x in fallback.splitlines() if x.strip()] if fallback and closed else [c.excerpt for c in result.evidence]

    @staticmethod
    def _allowed_numbers(result: ToolResult) -> list[str]:
        pattern = re.compile(r"\d[\d,]*(?:\.\d+)?(?:\s*(?:억|천만|백만|만)\s*원|\s*원|\s*%)?")
        values = {m for c in result.evidence for m in pattern.findall(c.excerpt)}
        for calculation in result.calculations:
            values.update(pattern.findall(" ".join(filter(None, (
                str(calculation.value), calculation.rate, calculation.formula
            )))))
        values.update(m for product in result.products for m in pattern.findall(repr(product)))
        return sorted(values)

    @staticmethod
    def _prompt(c: GroundedContext, violations: list[str] | None) -> str:
        evidence = Composer._focused_evidence(c)
        payload = {"QUESTION": c.question, "INTENT": c.intent, "RESPONSE_MODE": c.response_mode,
            "EVIDENCE": evidence,
            "PRODUCT_FACTS": [{k: p.get(k) for k in ("document_id", "page", "product_name", "asset_type", "risk_level", "risk_label", "plan_types") if p.get(k) is not None} for p in c.products],
            "RULE_RESULTS": [{"rule_id": x.rule_id, "label": x.label, "value": x.value, "unit": x.unit, "formula": x.formula} for x in c.calculations],
            "REQUIRED_FACTS": c.required_facts, "ALLOWED_NUMBERS": c.allowed_numbers,
            "CLAIM_PLAN": c.claim_plan, "RECOMMENDATION_CONSTRAINTS": c.recommendation_constraints,
            "FORBIDDEN_BEHAVIORS": c.forbidden_behaviors, "LIMITATIONS": c.limitations,
            "REQUIRED_CLARIFICATIONS": [{"name": x.name, "prompt": x.prompt} for x in c.required_clarifications]}
        payload.update({"FALSE_PREMISE":c.false_premise, "CORRECTION_FACT":c.correction_fact,
                        "CORRECTION_EVIDENCE_ID":c.correction_evidence_id})
        if violations: payload["PREVIOUS_DRAFT_VIOLATIONS"] = violations
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _claim(subtask: str, text: str, *, evidence: list[Citation] | None = None,
               rules: list[CalculationResult] | None = None, products: list[dict] | None = None) -> dict[str, object]:
        return {
            "subtask": subtask,
            "status": "answerable",
            "claims": [{
                "text": text,
                "evidence_ids": [item.id for item in evidence or []],
                "rule_result_ids": [f"{item.rule_id}:{item.label}" for item in rules or []],
                "product_fact_ids": [str(item.get("product_id")) for item in products or [] if item.get("product_id")],
            }],
        }

    @staticmethod
    def _unsupported(subtask: str, limitation: str) -> dict[str, object]:
        return {"subtask": subtask, "status": "unsupported", "claims": [], "limitation": limitation}

    def _build_claim_plan(self, question: str, result: ToolResult) -> list[dict[str, object]]:
        plan: list[dict[str, object]] = []
        doc51 = [item for item in result.evidence if item.document_id == "doc51"]
        receipt_evidence = [item for item in result.evidence if item.document_id in {"doc51", "doc55"}]

        doc26 = [item for item in result.evidence if item.document_id == "doc26"]
        teacher_subtasks = retirement_benefit_subtasks(question)
        if teacher_subtasks and doc26:
            teacher_claims = {
                "benefit_legal_character": "교사·공무원 안내에 따르면 퇴직수당과 명예퇴직수당은 퇴직소득이며, 명예퇴직수당 전액은 퇴직소득세 과세대상입니다.",
                "account_transfer_or_deposit": "퇴직소득세를 차감한 뒤 일반계좌로 받은 명예퇴직수당은 세후 수령일부터 60일 이내에 연금저축계좌 또는 IRP에 입금할 수 있습니다.",
                "tax_refund_procedure": "세후 수령일부터 60일 이내에 연금계좌에 입금한 뒤 공무원연금공단 등 담당부서에 퇴직소득세 환급을 신청하면, 차감된 세금을 돌려받아 세전 금액이 연금계좌에 입금된 것과 같은 구조가 됩니다.",
                "retirement_tax_effect": "연금계좌 입금 단계의 퇴직소득세 환급·과세이연 절차와 이후 연금수령 시 적용되는 일반 퇴직소득세 납부비율은 서로 구분해야 합니다. [주의] 절세 효과의 크기는 실제 퇴직소득세와 수령 방식에 따라 달라 일률적으로 단정할 수 없습니다.",
            }
            for subtask in teacher_subtasks:
                plan.append(self._claim(subtask, teacher_claims[subtask], evidence=doc26))

        if self._is_db_dc_explanation(question, result):
            db_dc_evidence = [item for item in result.evidence if item.document_id == "doc10"]
            plan.append(self._claim(
                "db_dc_difference",
                "확정급여형(DB)은 근로자가 퇴직할 때 받을 금액이 사전에 확정되어 있고 회사가 적립금을 운용합니다. 확정기여형(DC)은 회사가 매년 일정 금액을 근로자의 계좌에 입금하고 근로자가 직접 운용하므로 운용 수익률에 따라 최종 퇴직금이 달라집니다.",
                evidence=db_dc_evidence,
            ))

        if any(x in question for x in ("수령계좌", "받을 계좌")) and receipt_evidence:
            plan.append(self._claim(
                "account_receipt",
                "제공 문서에 따르면 법정퇴직금의 수령 가능 계좌는 연령과 DB·DC 유형에 따라 구분됩니다. 만 55세 미만 법정퇴직금은 IRP 의무이전 대상이며, 만 55세 이상은 제도별로 선택 가능한 수령계좌가 달라집니다.",
                evidence=receipt_evidence,
            ))

        asks_tax = (
            any(x in question for x in ("세금", "과세", "절세", "납부비율", "수령 세율"))
            or result.tax_intent == "PENSION_WITHDRAWAL_TAX"
        ) and not is_tax_deduction_question(question)
        if asks_tax and doc51:
            plan.append(self._claim(
                "retirement_tax",
                "퇴직금 재원의 일시금 수령에는 퇴직소득세율 100%가 적용되고, 연금수령에는 실제수령연차에 따라 이연퇴직소득세의 70%·60%·50%가 적용됩니다. [한계] 실제 세액 계산에는 예상 퇴직소득세가 필요하며 수령 일정도 확인해야 합니다.",
                evidence=doc51,
            ))

        if len(result.tax_source_types) >= 3 and receipt_evidence:
            plan.append(self._claim(
                "tax_source_separation",
                "연금계좌 과세는 재원별로 구분합니다. 세액공제를 받지 않은 개인납입금, 퇴직금·이연퇴직소득, 세액공제를 받은 개인납입금과 운용수익은 같은 세율로 취급하지 않습니다. 퇴직금 재원의 연금수령에는 이연퇴직소득세의 70%·60%·50% 체계가 적용되며, 3.3~5.5%는 퇴직금 재원 자체의 세율로 적용하지 않습니다.",
                evidence=receipt_evidence,
            ))

        transfer_evidence = [item for item in result.evidence if item.document_id == "doc51" and "계약이전" in item.excerpt]
        if has_alias(question, "dc") and "연금저축" in question and transfer_evidence:
            plan.append(self._claim(
                "account_transfer",
                "DC 퇴직금은 먼저 IRP로 이전해 수령하고, 이후 연금저축으로 계약이전하여 운용할 수 있습니다.",
                evidence=transfer_evidence,
            ))
        elif has_alias(question, "dc") and has_alias(question, "irp"):
            dc_irp_evidence = [item for item in result.evidence if "DC" in item.excerpt and "IRP" in item.excerpt]
            if dc_irp_evidence:
                plan.append(self._claim("account_transfer", "DC 법정퇴직금은 IRP로 이전할 수 있습니다.", evidence=dc_irp_evidence))

        if result.procedure_type == "EARLY_WITHDRAWAL" or "중도인출" in question:
            procedure_evidence = [item for item in result.evidence if item.document_id == "doc55"]
            if procedure_evidence:
                plan.append(self._claim(
                    "early_withdrawal",
                    "중도인출과 계좌 전체 해지는 구분해야 합니다. 제공 문서상 중도인출은 정해진 사유와 증빙이 필요한 절차입니다.",
                    evidence=procedure_evidence,
                ))
            plan.append(self._unsupported("early_withdrawal_tax_detail", "[한계] 중도인출 세금은 인출 재원과 수령 방식에 따라 달라 현재 정보만으로 세부 세액을 계산할 수 없습니다."))

        if result.procedure_type == "PENSION_START":
            procedure_evidence = [item for item in result.evidence if item.document_id in {"doc51", "doc55"}]
            if procedure_evidence:
                plan.append(self._claim(
                    "pension_start",
                    "계좌 이전, 상품 선택, 연금 개시는 서로 별도 단계입니다. 연금 개시는 제공된 연금계좌 수령 절차와 조건 범위에서 확인해야 합니다.",
                    evidence=procedure_evidence,
                ))

        if result.withdrawal_result is not None:
            scenarios = result.withdrawal_result.comparison.scenarios
            lines = [f"- {item.scenario}: 퇴직소득세 {item.tax_value}{result.withdrawal_result.comparison.unit}" for item in scenarios]
            text = "Rule Result에 따른 퇴직소득세입니다.\n" + "\n".join(lines)
            if scenarios and all(item.tax_value == 0 for item in scenarios):
                text += "\n세 시나리오 모두 0원이고 퇴직소득세 절감액도 0원입니다. 따라서 퇴직소득세 측면에서는 추가 절세효과가 없습니다. [한계] 투자수익과 유동성 등 다른 조건 없이 연금이 무조건 유리하다고 결론낼 수 없습니다."
            plan.append(self._claim("withdrawal_tax_calculation", text, rules=result.calculations))

        if "유동성" in question:
            plan.append(self._unsupported("liquidity", "[한계] 제공 문서는 수령연차별 세율은 제시하지만 수령 주기·회차별 금액은 제시하지 않으므로 실제 유동성 차이는 수령 일정을 정하기 전에는 단정할 수 없습니다."))

        future_return = any(x in question for x in ("향후 수익률", "미래 수익률", "장래", "수익률 수치"))
        if future_return:
            plan.append(self._unsupported("future_return", "[한계] 제공 문서에 없는 향후 수익률 숫자는 예측할 수 없습니다. 현재 문서와 Product Fact에서 확인되는 과거 수익률·위험·비용만 근거 범위에서 비교할 수 있습니다."))
        elif result.products:
            plan.append(self._claim("product_facts", self._compose_product_facts(result), products=result.products))
        for constraint in result.recommendation_constraints:
            if not constraint.get("applied") and str(constraint.get("constraint", "")).startswith("investment_horizon="):
                years = str(constraint["constraint"]).split("=", 1)[1]
                plan.append(self._unsupported(
                    "investment_horizon",
                    f"[한계] 현재 Product Fact에는 {years} 투자기간 적합성을 직접 판정할 공식 field가 없어, 이 기간을 상품 필터에 적용하지 않았습니다.",
                ))

        requested_cost = any(x in question for x in ("비용", "보수", "수수료"))
        if requested_cost:
            cost_evidence = next((item for item in result.evidence if result.products and
                str(result.products[0].get("product_name", "")).replace(" ", "") in item.excerpt.replace(" ", "") and
                "총보수" in item.excerpt and "총비용" in item.excerpt), None)
            if cost_evidence:
                match = re.search(r"수수료선취-오프라인\(A\)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)(?:\s+([\d.]+%\s*이내))?", cost_evidence.excerpt)
                if match:
                    text = ("투자설명서의 수수료선취-오프라인(A) 클래스 기준 총보수·비용 비율은 "
                            f"{match.group(4)}%입니다. 1,000만원 투자 시 총비용 예시는 1년 {match.group(5)}천원, "
                            f"2년 {match.group(6)}천원, 3년 {match.group(7)}천원, 5년 {match.group(8)}천원, 10년 {match.group(9)}천원입니다. "
                            "이는 총보수율과 투자기간별 총비용 예시를 구분한 값입니다.")
                    plan.append(self._claim("product_cost", text, evidence=[cost_evidence]))
                else:
                    plan.append(self._unsupported("product_cost", "[한계] 현재 확보된 Product Fact와 투자설명서 근거에서는 요청한 비용 값을 구조적으로 확인하지 못했습니다."))
            else:
                plan.append(self._unsupported("product_cost", "[한계] 현재 확보된 Product Fact와 투자설명서 근거에서는 요청한 비용 값을 확인하지 못했습니다."))

        if any(x in question for x in ("무조건 추천", "하나만", "하나 골라")) and any(x in question for x in ("수익률", "보수")):
            plan.append(self._unsupported("single_metric_recommendation", "[한계] 과거수익률 한 항목만으로 상품 하나를 선택할 수 없습니다. 위험등급·비용·가입 가능 계좌와 투자기간·손실감내 조건을 함께 확인해야 합니다."))

        return plan

    @staticmethod
    def _render_claim_plan(plan: list[dict[str, object]]) -> str | None:
        parts: list[str] = []
        for subtask in plan:
            if subtask.get("status") == "answerable":
                for claim in subtask.get("claims", []):  # type: ignore[union-attr]
                    if isinstance(claim, dict) and claim.get("text"):
                        parts.append(str(claim["text"]))
            elif subtask.get("limitation"):
                parts.append(str(subtask["limitation"]))
        return "\n\n".join(dict.fromkeys(parts)) if parts else None

    @staticmethod
    def _focused_evidence(c: GroundedContext) -> list[dict[str, object]]:
        wanted = None
        anchors: tuple[str, ...] = ()
        if is_db_dc_question(c.question): wanted, anchors = {"doc10"}, ("확정급여형", "확정기여형")
        elif is_tax_deduction_question(c.question): wanted, anchors = {"doc41", "doc55"}, ("600만원", "900만원", "세액공제율")
        elif is_teacher_retirement_domain(c.question): wanted, anchors = {"doc26", "doc51"}, ("명예퇴직수당", "60일", "퇴직소득")
        selected = [x for x in c.evidence if wanted is None or x.document_id in wanted]
        if c.products: selected = [x for x in selected if x.document_id.startswith("r2_")][:len(c.products)]
        rows = []
        for item in selected[:4]:
            text = item.excerpt
            positions = [text.find(a) for a in anchors if a in text]
            start = max(0, min(positions)-80) if positions else 0
            excerpt = text[start:start + (240 if c.products else 360)]
            rows.append({"document_id":item.document_id, "page":item.page, "excerpt":excerpt})
        return rows

    @staticmethod
    def _prompt_metrics(c: GroundedContext, prompt: str) -> dict[str, int]:
        evidence = Composer._focused_evidence(c)
        return {"prompt_chars":len(prompt), "retrieved_evidence_count":len(evidence),
                "retrieved_evidence_chars":sum(len(str(x["excerpt"])) for x in evidence),
                "product_fact_count":len(c.products), "rule_result_count":len(c.calculations)}

    def _grounded_message(self, question: str, result: ToolResult) -> str | None:
        parts: list[str] = []
        if result.withdrawal_result is not None:
            lines = [
                f"- {scenario.scenario}: 퇴직소득세 {scenario.tax_value}{result.withdrawal_result.comparison.unit}, 적용 비율 {scenario.applicable_rate}"
                for scenario in result.withdrawal_result.comparison.scenarios
            ]
            parts.append("Rule Result에 포함된 수령 시나리오별 퇴직소득세입니다.\n" + "\n".join(lines))
        elif result.tax_intent == "PENSION_WITHDRAWAL_TAX" and any("70%" in c.excerpt and "50%" in c.excerpt for c in result.evidence):
            parts.append("제공 문서의 실제수령연차 기준으로 1~10년차에는 이연퇴직소득세의 70%, 11~20년차에는 60%, 21년차부터는 50%를 납부합니다. [한계] 실제 세액 계산에는 예상 퇴직소득세가 필요합니다.")
        if self._is_db_dc_explanation(question, result):
            parts.append("확정급여형(DB)은 근로자가 퇴직할 때 받을 금액이 사전에 확정되어 있고 회사가 적립금을 운용합니다. 확정기여형(DC)은 회사가 매년 일정 금액을 근로자의 계좌에 입금하고 근로자가 직접 운용하므로, 운용 수익률에 따라 최종 퇴직금이 달라집니다.")
        if has_alias(question, "dc") and "연금저축" in question and any(c.document_id == "doc51" and "계약이전" in c.excerpt for c in result.evidence):
            parts.append("DC 퇴직금은 먼저 IRP로 이전해야 하며, 연금저축에서 운용하려면 IRP로 퇴직금을 수령한 뒤 연금저축으로 계약이전할 수 있습니다.")
        elif has_alias(question, "irp") and has_alias(question, "dc") and any("IRP" in c.excerpt and "DC" in c.excerpt for c in result.evidence):
            parts.append("DC 법정퇴직금은 IRP로 이전할 수 있습니다.")
        if len(result.tax_source_types) >= 3 and any(c.document_id in {"doc51", "doc55"} for c in result.evidence):
            parts.append("연금계좌 과세는 재원별로 구분해야 합니다. 세액공제를 받지 않은 개인 납입금, 퇴직금·이연퇴직소득, 세액공제를 받은 개인 납입금과 운용수익은 같은 세율로 취급하지 않습니다. 퇴직금 재원의 연금수령에는 이연퇴직소득세의 실제수령연차별 납부비율이 적용되고, 3.3~5.5%는 퇴직금 재원 자체의 세율로 적용하지 않습니다.")
        if "명예퇴직" in question and "법정퇴직" in question and not is_teacher_retirement_domain(question):
            parts.append("[한계] 제공된 일반 근로자 자료만으로는 명예퇴직금과 법정퇴직금을 서로 다른 계좌로 받을 수 있다고 확정할 수 없습니다. 교사·공무원 전용 자료의 퇴직수당 특례는 일반 질문에 적용하지 않습니다.")
        if result.procedure_type == "ACCOUNT_OPENING":
            parts.append("[한계] 제공 자료에서는 IRP 신규 계좌 개설에 필요한 서류 목록을 직접 확인할 수 없습니다. 퇴직급여신청서와 IRP가입확인서는 이미 개설된 IRP로 퇴직급여를 지급받는 단계의 서류이므로 신규 개설 서류로 안내하지 않습니다.")
        elif result.procedure_type == "ACCOUNT_TERMINATION":
            parts.append("[한계] 퇴직연금 해지 절차는 DB·DC·IRP 중 계약 유형에 따라 달라 현재 질문만으로 하나의 절차를 확정할 수 없습니다. 중도인출 사유인 개인회생·파산 서류를 일반 해지 절차로 적용하지 않습니다.")
        elif result.procedure_type == "ACCOUNT_TRANSFER" and has_alias(question, "irp"):
            parts.append("IRP 계약이전은 제공 문서의 계약이전 절차 범위에서 처리됩니다. 상품 선택과 연금 개시는 별도 단계로 구분해야 합니다.")
        elif result.procedure_type == "EARLY_WITHDRAWAL":
            parts.append("IRP 중도인출과 계좌 해지는 구분해야 합니다. 제공 문서상 중도인출은 정해진 사유와 증빙이 필요한 절차이며, 세금은 인출 재원과 수령 방식에 따라 구분해야 합니다. [한계] 제공 근거 없이 특정 계좌가 더 유리하다고 추천하지 않습니다.")
        elif result.procedure_type == "PENSION_START":
            parts.append("연금 개시는 제공된 연금계좌 수령 절차와 조건 범위에서 확인해야 합니다.")
        if any(x in question for x in ("상품 선택", "상품을 선택")) and any(x in question for x in ("연금 개시", "연금 시작")):
            parts.append("계좌 이전, 상품 선택, 연금 개시는 서로 별도 단계로 구분해야 합니다.")
        if any(x in question for x in ("수령계좌", "받을 계좌")) and any(c.document_id in {"doc51", "doc55"} for c in result.evidence):
            parts.append("제공 문서에 따르면 법정퇴직금의 수령 가능 계좌는 연령과 DB·DC 유형에 따라 구분됩니다. 만 55세 미만 법정퇴직금은 IRP 의무이전 대상이며, 만 55세 이상은 제도별로 선택 가능한 수령계좌가 달라집니다.")
        if any(x in question for x in ("세금", "과세", "절세")) and any(c.document_id == "doc51" for c in result.evidence):
            parts.append("퇴직금 재원을 연금으로 수령할 때는 실제수령연차에 따라 이연퇴직소득세의 70%·60%·50%를 납부합니다. [한계] 실제 세액은 예상 퇴직소득세와 수령 일정이 있어야 계산할 수 있습니다.")
        if "유동성" in question:
            parts.append("[한계] 제공 문서는 수령연차별 세율은 제시하지만 수령 주기·회차별 금액은 제시하지 않으므로, 10년과 21년 안의 실제 유동성 차이는 수령 일정을 정하기 전에는 단정할 수 없습니다.")
        if has_alias(question, "institution") and "일반" in question:
            parts.append("제공된 제도 근거에 따르면 퇴직연금은 기업이 근로자의 퇴직금을 사외 금융기관에 적립하고, "
                    "퇴직 시 근로자가 연금 또는 일시금으로 수령할 수 있는 제도입니다. "
                    "[한계] 현재 근거에는 일반 퇴직금과의 항목별 차이가 모두 제시되어 있지 않아 그 밖의 차이는 단정할 수 없습니다.")
        if self._is_tax_deduction_question(question, result):
            prefix = "아닙니다. " if "무제한" in question else ""
            detail = prefix + "제공된 세액공제 안내에 따르면 연금저축의 세액공제 대상 납입한도는 연 600만원이고, IRP를 포함한 연금계좌 합산 한도는 연 900만원입니다. 다른 연금저축 세액공제 납입액이 없다면 IRP에만 납입한 900만원은 세액공제 대상 납입액 한도 안에 들어갈 수 있습니다. 이는 납입액 900만원만큼 세금이 줄어든다는 뜻이 아닙니다. 실제 세액공제 금액은 소득에 따른 공제율과 납부할 세액 등 조건에 따라 달라집니다."
            parts.append(detail)
        if result.withdrawal_result is not None and result.input_slots.get("expected_tax_won") == 0:
            parts.append("예상 퇴직소득세가 0원이므로 Rule Result상 일시금과 연금수령의 퇴직소득세는 모두 0원입니다. 따라서 이 입력에서는 퇴직소득세 감면만으로 연금수령이 무조건 유리하다고 결론낼 수 없습니다.")
        if any(x in question for x in ("무조건 추천", "하나만", "하나 골라")) and any(x in question for x in ("수익률", "보수")):
            parts.append("[한계] 과거수익률 한 항목만으로 상품 하나를 무조건 선택할 수 없습니다. 제공된 Product Fact의 위험등급·비용·가입 가능 계좌와 투자기간·손실감내 조건을 함께 확인해야 합니다.")
        if self._is_teacher_retirement_question(question, result):
            return "[주의] 큰 폭의 절세 효과가 있다고 일률적으로 단정하기보다 수당의 성격과 적용 조건을 먼저 확인해야 합니다. 제공된 교사·공무원 안내에 따르면 퇴직수당과 명예퇴직수당은 퇴직소득이며, 명예퇴직수당 전액은 퇴직소득세 과세대상입니다. 세후 수령 후 60일 이내에 연금저축 또는 IRP에 입금하고 퇴직소득세 환급을 신청할 수 있습니다. 실제 적용 여부는 수당의 법적 성격과 개인별 요건을 확인해야 합니다."
        if has_alias(question, "product_feature") and not has_alias(question, "product_family"):
            return "[한계] 비교할 특정 상품과 해당 상품의 Product Fact 또는 투자설명서 근거가 없어 듀레이션·금리 민감도·변동성의 차이나 안정성 우열을 설명할 수 없습니다."
        if has_alias(question, "product_family") and has_alias(question, "principal_protection"):
            supporting = "\n".join(c.excerpt for c in result.evidence)
            if "예금자보호" in supporting:
                loss = " 투자원금 손실이 발생할 수 있습니다." if ("원금손실" in supporting.replace(" ", "") or "손실" in supporting) else ""
                return ("아니요. 현재 요청에서 조회된 투자설명서에 따르면 해당 집합투자증권은 예금자보호 대상이 아닙니다." +
                        loss + " [한계] 안정성 우열이나 개인 적합성은 제공된 근거만으로 단정하지 않습니다.")
        if result.products and (has_alias(question, "product_family") or self._is_grounded_product_compare(question, result) or result.input_slots.get("risk_tolerance") == "stable"):
            parts.append(self._compose_product_facts(result))
        if any(x in question for x in ("향후 수익률", "미래 수익률", "장래", "수익률 수치")):
            parts.append("[한계] 제공 문서에 없는 향후 수익률 숫자는 예측할 수 없습니다. 현재 문서와 Product Fact에서 확인되는 과거 수익률·위험·비용만 근거 범위에서 비교할 수 있습니다.")
        return "\n\n".join(dict.fromkeys(parts)) if parts else None

    @staticmethod
    def _false_premise_correction(question: str, result: ToolResult) -> tuple[str, str] | None:
        doc10 = next((c for c in result.evidence if c.document_id == "doc10"), None)
        if doc10 and has_alias(question, "dc") and any(x in question for x in ("미리 확정", "사전에 확정", "확정돼", "회사가 수익률", "회사 책임", "책임지는", "책임", "보장")):
            return ("아닙니다. 확정기여형(DC)은 회사가 매년 일정 금액을 근로자의 계좌에 입금하고 근로자가 직접 운용하므로, 운용 수익률에 따라 최종 퇴직급여가 달라집니다.", doc10.id)
        return None

    @staticmethod
    def _is_db_dc_explanation(q, r): return is_db_dc_question(q) and has_alias(q,"db") and has_alias(q,"dc") and any(c.document_id=="doc10" for c in r.evidence)
    @staticmethod
    def _is_tax_deduction_question(q, r): return is_tax_deduction_question(q) and bool({c.document_id for c in r.evidence}&{"doc41","doc55"})
    @staticmethod
    def _is_teacher_retirement_question(q, r): return is_teacher_retirement_domain(q) and has_legally_named_retirement_benefit(q) and any(c.document_id=="doc26" for c in r.evidence)
    @staticmethod
    def _is_grounded_product_compare(q, r): return bool(r.products) and is_comparison_question(q)
    @staticmethod
    def _compose_product_facts(r):
        lines=[f"- {p.get('product_name')}: 자산유형 {p.get('asset_type')}, 위험등급 {p.get('risk_level')}등급({p.get('risk_label')}), 가입 가능 계좌 {p.get('plan_types')}" for p in r.products]
        return "제공된 Product Fact와 투자설명서 기준 비교입니다.\n"+"\n".join(lines)+"\n위험등급은 1등급이 매우 높은 위험, 2등급이 높은 위험, 3등급이 다소 높은 위험, 4등급이 보통 위험, 5등급이 낮은 위험, 6등급이 매우 낮은 위험입니다. [한계] 상품명만으로 듀레이션·변동성·기간별 운용전략이나 개인 적합성을 단정할 수 없습니다."

    @staticmethod
    def _apply_behavior_policy(question, tool_result, message):
        """Compatibility helper; normal pipeline encodes these policies in its contract."""
        if (is_teacher_retirement_domain(question) or has_alias(question, "retirement") or "퇴직" in question) and has_alias(question, "inducement") and not message.startswith("[주의]"):
            message = "[주의] 큰 폭의 세금 감면이 적용된다고 단정할 수 없습니다. 수당의 법적 성격과 적용 제도를 먼저 확인해야 합니다.\n\n" + message
        asks_period = any(x in question for x in ("단기", "중장기", "장기", "기간별"))
        has_prospectus = any(c.document_id.startswith("r2_") and not c.id.startswith("product-") for c in tool_result.evidence)
        if tool_result.products and is_comparison_question(question) and asks_period and not has_prospectus:
            message += "\n\n[한계] 현재 근거에는 듀레이션·변동성·기간별 운용전략 정보가 없어 안정성 우열을 확정할 수 없습니다."
        return message

    @staticmethod
    def _build_comparison(intent, calculations, withdrawal_result=None):
        # withdrawal_result가 있으면 그 안에 이미 3개 시나리오 비교가 원형으로 담겨
        # 프론트가 그것만 읽는다. 여기서 rule_id 기준 options를 만들면 세 시나리오가
        # 같은 rule_id(RETIRE_TAX_RATE_BY_YEAR)를 공유해 중복 options가 생기고,
        # 프론트 스키마의 options 고유성 검증에 걸려 응답 전체가 파싱 실패한다.
        if intent != "종합" or len(calculations) < 2 or withdrawal_result is not None:
            return None
        return ComparisonResult(title="옵션 비교", options=[c.rule_id for c in calculations], rows=[ComparisonRow(label=c.label, values={"value":f"{c.value}{c.unit}"}) for c in calculations], note="단정적인 추천이 아닌 참고용 비교입니다.")
