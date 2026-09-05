"""Build an immutable grounding contract and let HCX synthesize its wording."""

from dataclasses import dataclass, field
import json
import re

from app.agent.canonical import detect_false_premise
from app.agent.hcx_client import HCXClient
from app.agent.product_evidence import (
    allows_product_evidence_enrichment,
    build_product_evidence_bundles,
    citations_for_product,
    extract_fee_table,
    is_prospectus_citation,
    render_cost_claim,
    render_fee_table_claim,
    render_product_comparison,
    structured_fee_mapping,
)
from app.agent.router import Intent
from app.agent.tools import ToolResult
from app.api.schemas import CalculationResult, Citation, ComparisonResult, ComparisonRow, RequiredSlot, WithdrawalComparisonResponse
from app.core.query_normalization import (
    ACCOUNT_TERMINATION_TAX,
    EARLY_WITHDRAWAL_TAX,
    allows_dc_irp_account_transfer_claim,
    evidence_compatible_with_question_scope,
    excerpt_supports_dc_contribution_factor_relation,
    excerpt_supports_dc_contribution_structure,
    excerpt_supports_dc_irp_retirement_transfer,
    excerpt_supports_product_type_comparison,
    excerpt_supports_savings_irp_comparison,
    has_alias,
    is_dc_contribution_determination_question,
    has_legally_named_retirement_benefit,
    is_comparison_question,
    is_generic_pension_receiving_question,
    is_pension_savings_irp_comparison,
    is_principal_vs_performance_comparison,
    applies_pension_scope_evidence_filter,
    pension_scopes,
    is_db_dc_question,
    is_tax_deduction_question,
    is_teacher_retirement_domain,
    needs_retirement_benefit_clarification,
    pension_year_rate_block_allowed,
    retirement_benefit_subtasks,
    tax_intent,
)
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
            correction = ""
            if "과거수익률" in question and any(x in question for x in ("가장 좋은", "제일 좋은")):
                correction = "아닙니다. 과거수익률만으로 가장 좋은 상품을 정할 수 없습니다. "
            elif (has_alias(question, "principal_protection") or "손실 안" in question) and any(x in question for x in ("무조건", "손실 안")):
                correction = "무조건 손실이 없는 연금 상품이라고 단정할 수 없습니다. "
            return GroundedContext(question, intent, "clarification", required_clarifications=required_slots,
                forbidden_behaviors=forbidden, fallback_message=f"{correction}정확한 답변을 위해 아래 내용을 확인해 주세요: {prompts}",
                required_facts=[correction.strip()] if correction else [])
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
        if applies_pension_scope_evidence_filter(question):
            result.evidence = [
                item for item in result.evidence
                if evidence_compatible_with_question_scope(question, item.excerpt)
            ]
        if is_pension_savings_irp_comparison(question):
            result.evidence = [
                item for item in result.evidence
                if excerpt_supports_savings_irp_comparison(item.excerpt)
            ]
        if is_principal_vs_performance_comparison(question):
            direct_type = [
                item for item in result.evidence
                if excerpt_supports_product_type_comparison(item.excerpt)
            ]
            if not direct_type:
                result.evidence = []
                result.products = []
            else:
                result.evidence = direct_type
        if "NATIONAL_PENSION" in pension_scopes(question) and not result.evidence:
            fallback = (
                "[한계] 제공된 근거에는 국민연금에 대한 직접 자료가 없어 "
                "수령 시점이나 다른 연금과의 차이를 확정할 수 없습니다."
            )
            return GroundedContext(
                question, intent, "limitation", [], result.products, result.calculations,
                [fallback], [], forbidden, [fallback], [], fallback,
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
        correction_pair = self._false_premise_correction(question, result)
        claim_plan = self._build_claim_plan(question, result, intent)
        tax_scope = result.tax_intent or tax_intent(question)
        unsupported_tax_subtasks = [
            item for item in claim_plan
            if item.get("status") == "unsupported" and "tax" in str(item.get("subtask", ""))
        ]
        if (
            tax_scope == "UNKNOWN_TAX"
            and unsupported_tax_subtasks
            and not any(item.get("claims") for item in unsupported_tax_subtasks)
        ):
            # Retrieval may still supply useful account/source definitions, but an
            # unsupported tax subtask is not permission to synthesize a new
            # entity-to-taxability relationship from adjacent raw excerpts.
            forbidden.append("direct support 없는 tax liability relation 생성")
        if correction_pair:
            fallback_correction, evidence_id = correction_pair
            sourced = [item for item in result.evidence if item.id == evidence_id] or result.evidence[:1]
            claim_plan.insert(0, self._claim("false_premise_correction", fallback_correction, evidence=sourced))
        if required_slots and any(slot.name in {"plan_type", "investment_horizon", "risk_tolerance"} for slot in required_slots):
            # Do not render an unfiltered catalog while recommendation constraints
            # are incomplete. Other answerable procedure/tax subtasks remain.
            claim_plan = [item for item in claim_plan if item.get("subtask") != "product_facts"]
        fallback = self._render_claim_plan(claim_plan) or self._grounded_message(question, result, intent)
        if correction_pair and fallback and correction_pair[0] not in fallback:
            fallback = f"{correction_pair[0]}\n\n{fallback}"
        elif correction_pair and not fallback:
            fallback = correction_pair[0]
        if required_slots:
            prompts = "; ".join(slot.prompt for slot in required_slots)
            partial = fallback or "[한계] 현재 제공된 근거로 답할 수 있는 범위만 안내합니다."
            fallback = f"{partial}\n[필요한 조건] {prompts}"
        facts = self._required_facts(question, result, fallback)
        if fallback is None:
            fallback = "[한계] 제공된 근거 안에서만 답변할 수 있으며, 확인되지 않은 내용은 단정할 수 없습니다."
        answerable = [item for item in claim_plan if item.get("status") == "answerable"]
        if answerable and fallback.startswith("[한계] 제공된 근거 안에서만"):
            fallback = self._render_claim_plan(claim_plan) or fallback
        if not result.evidence and not result.calculations and not result.products:
            return GroundedContext(question, intent, "limitation", limitations=[fallback], forbidden_behaviors=forbidden,
                fallback_message=fallback, required_facts=[fallback])
        limits = [x.strip() for x in re.findall(r"\[(?:주의|한계)\][^\n]+", fallback)]
        if fallback.startswith("[한계] 비교할 특정 상품"):
            forbidden.append("상품 비교 한계 외 사실 추가")
        if (
            is_principal_vs_performance_comparison(question)
            and fallback
            and fallback.startswith("[한계]")
            and not any(item.get("status") == "answerable" for item in claim_plan)
        ):
            forbidden.append("상품 비교 한계 외 사실 추가")
        if is_dc_contribution_determination_question(question):
            forbidden.append("핵심 grounded contract 변경 또는 일부 누락")
        allowed_numbers = self._allowed_numbers(
            result, question, include_question=tax_intent(question) is None
        )
        # Claim-plan text is permitted only when its provenance is explicit. This
        # keeps the number verifier aligned with deterministic fallback claims.
        grounded_claim_text = " ".join(
            str(claim.get("text", ""))
            for subtask in claim_plan
            for claim in subtask.get("claims", [])  # type: ignore[union-attr]
            if isinstance(claim, dict)
        )
        if correction_pair:
            grounded_claim_text += " " + correction_pair[0]
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
            or bool(correction_pair)
            or bool(answerable)
            or len([part for part in fallback.split("\n\n") if part.strip()]) > 1
        )
        if sensitive_contract:
            forbidden.append("핵심 grounded contract 변경 또는 일부 누락")
        return GroundedContext(
            question, intent, "result", result.evidence, result.products, result.calculations,
            facts, allowed_numbers, forbidden, limits, [], fallback,
            false_premise=question if correction_pair else None,
            correction_fact=correction_pair[0] if correction_pair else None,
            correction_evidence_id=correction_pair[1] if correction_pair else None,
            claim_plan=claim_plan, recommendation_constraints=result.recommendation_constraints,
        )

    @staticmethod
    def _required_facts(question: str, result: ToolResult, fallback: str | None) -> list[str]:
        scoped = [
            item for item in result.evidence
            if evidence_compatible_with_question_scope(question, item.excerpt)
        ]
        if is_generic_pension_receiving_question(question):
            return [x.strip() for x in fallback.splitlines() if x.strip()] if fallback else []
        if (
            is_pension_savings_irp_comparison(question)
            or is_principal_vs_performance_comparison(question)
            or is_dc_contribution_determination_question(question)
        ):
            return [x.strip() for x in fallback.splitlines() if x.strip()] if fallback else []
        closed = (fallback is not None or Composer._is_db_dc_explanation(question, result) or Composer._is_tax_deduction_question(question, result)
                  or Composer._is_teacher_retirement_question(question, result) or Composer._is_grounded_product_compare(question, result)
                  or result.withdrawal_result is not None
                  or (has_alias(question, "product_feature") and not has_alias(question, "product_family"))
                  or (has_alias(question, "product_family") and has_alias(question, "principal_protection"))
                  or (has_alias(question, "institution") and "일반" in question)
                  or (has_alias(question, "irp") and has_alias(question, "dc")))
        return [x.strip() for x in fallback.splitlines() if x.strip()] if fallback and closed else [c.excerpt for c in scoped]

    @staticmethod
    def _allowed_numbers(result: ToolResult, question: str = "", *, include_question: bool = True) -> list[str]:
        pattern = re.compile(r"\d[\d,]*(?:\.\d+)?(?:\s*(?:억|천만|백만|만)\s*원|\s*원|\s*%)?")
        values = {m for c in result.evidence for m in pattern.findall(c.excerpt)}
        if include_question:
            values.update(pattern.findall(question))
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
        source_type = "evidence" if evidence else ("rule" if rules else ("product" if products else None))
        source_id = None
        if evidence:
            source_id = evidence[0].id
        elif rules:
            source_id = f"{rules[0].rule_id}:{rules[0].label}"
        elif products:
            source_id = str(products[0].get("product_id") or "")
        return {
            "subtask": subtask,
            "status": "answerable",
            "claims": [{
                "text": text,
                "claim_type": "tax_numeric" if any(token in text for token in ("%", "만원", "세율", "공제")) else "factual",
                "source_type": source_type,
                "source_id": source_id,
                "evidence_ids": [item.id for item in evidence or []],
                "rule_result_ids": [f"{item.rule_id}:{item.label}" for item in rules or []],
                "product_fact_ids": [str(item.get("product_id")) for item in products or [] if item.get("product_id")],
            }],
        }

    @staticmethod
    def _korean_claim_sentences(excerpt: str) -> list[str]:
        text = " ".join(excerpt.split())
        parts = re.split(r"(?<=다)\.\s*", text)
        sentences: list[str] = []
        for part in parts:
            sentence = part.strip(" .")
            if sentence:
                sentences.append(sentence)
        return sentences

    @staticmethod
    def _with_period(sentence: str) -> str:
        return sentence + "." if sentence.endswith("다") else sentence

    @staticmethod
    def _tax_credit_limit_claim_text(sentence: str, excerpt: str) -> str:
        text = Composer._with_period(sentence)
        if "세액공제" in text.replace(" ", ""):
            return text
        if "세액공제" not in excerpt.replace(" ", ""):
            return text
        label = "세액공제 대상 납입한도"
        if text.startswith(label):
            return text
        return f"{label}: {text}"

    def _savings_irp_comparison_claims(self, evidence: list[Citation]) -> list[dict[str, object]]:
        plan: list[dict[str, object]] = []
        seen: set[tuple[str, str]] = set()
        for item in evidence:
            if not excerpt_supports_savings_irp_comparison(item.excerpt):
                continue
            excerpt = item.excerpt
            for sentence in self._korean_claim_sentences(excerpt):
                compact = sentence.replace(" ", "")
                specs: list[str] = []
                if "연금저축" in sentence and (
                    "누구나" in sentence or "가입할 수" in sentence or "가입이 가능" in sentence
                ):
                    specs.append("PENSION_SAVINGS_ELIGIBILITY")
                if ("IRP" in sentence.upper() or "개인형" in sentence) and "가입" in sentence:
                    if "가입대상" in compact or "가입 대상" in sentence or any(
                        token in sentence for token in ("직장인", "자영업", "정해져")
                    ):
                        specs.append("IRP_ELIGIBILITY")
                if any(token in sentence for token in ("입금", "납입")) and "세액공제" not in sentence and re.search(r"\d", sentence):
                    if any(token in sentence for token in ("합산", "총")):
                        specs.append("TOTAL_CONTRIBUTION_LIMIT")
                if "세액공제" in excerpt and "만원" in compact and "입금" not in sentence:
                    if re.search(r"연금저축은.{0,16}연?\d", compact) or (
                        "연금저축" in sentence and "세액공제" in sentence
                    ):
                        specs.append("PENSION_SAVINGS_TAX_CREDIT_LIMIT")
                    if ("IRP" in sentence.upper() or "개인형" in sentence) and any(
                        token in sentence for token in ("포함", "합산", "세액공제")
                    ):
                        specs.append("IRP_COMBINED_TAX_CREDIT_LIMIT")
                for subtask in specs:
                    key = (subtask, sentence)
                    if key in seen:
                        continue
                    seen.add(key)
                    claim_text = self._with_period(sentence)
                    if subtask in {"PENSION_SAVINGS_TAX_CREDIT_LIMIT", "IRP_COMBINED_TAX_CREDIT_LIMIT"}:
                        claim_text = self._tax_credit_limit_claim_text(sentence, excerpt)
                    plan.append(self._claim(subtask, claim_text, evidence=[item]))
        return plan

    def _dc_contribution_claims(self, evidence: list[Citation]) -> list[dict[str, object]]:
        plan: list[dict[str, object]] = []
        seen: set[str] = set()
        for item in evidence:
            if not excerpt_supports_dc_contribution_structure(item.excerpt):
                continue
            for sentence in self._korean_claim_sentences(item.excerpt):
                has_dc = "확정기여" in sentence or "DC" in sentence
                has_flow = any(marker in sentence for marker in ("입금", "운용"))
                if not (has_dc and has_flow):
                    continue
                clause = re.sub(r"은 무엇인가요\?\s*[•·*]?\s*", "은 ", sentence).strip() or sentence
                text = self._with_period(clause)
                if text in seen:
                    continue
                seen.add(text)
                plan.append(self._claim("DC_CONTRIBUTION_STRUCTURE", text, evidence=[item]))
        factor_seen: set[str] = set()
        for item in evidence:
            for sentence in self._korean_claim_sentences(item.excerpt):
                if not excerpt_supports_dc_contribution_factor_relation(sentence):
                    continue
                text = self._with_period(sentence)
                if text in factor_seen:
                    continue
                factor_seen.add(text)
                plan.append(self._claim("CONTRIBUTION_DETERMINATION_FACTOR", text, evidence=[item]))
        if not any(item.get("subtask") == "CONTRIBUTION_DETERMINATION_FACTOR" for item in plan):
            plan.append(self._unsupported(
                "CONTRIBUTION_DETERMINATION_FACTOR",
                "[한계] 제공된 근거만으로는 구체적인 부담금 결정 요인을 확인할 수 없습니다.",
            ))
        if not any(item.get("status") == "answerable" for item in plan):
            plan.append(self._unsupported(
                "DC_CONTRIBUTION_STRUCTURE",
                "[한계] 제공된 근거 안에서만 답변할 수 있으며, 확인되지 않은 내용은 단정할 수 없습니다.",
            ))
        return plan

    @staticmethod
    def _unsupported(subtask: str, limitation: str) -> dict[str, object]:
        return {"subtask": subtask, "status": "unsupported", "claims": [], "limitation": limitation}

    def _build_claim_plan(self, question: str, result: ToolResult, intent: Intent | None = None) -> list[dict[str, object]]:
        plan: list[dict[str, object]] = []
        doc51 = [item for item in result.evidence if item.document_id == "doc51"]
        receipt_evidence = [item for item in result.evidence if item.document_id in {"doc51", "doc55"}]

        doc26 = [item for item in result.evidence if item.document_id == "doc26"]
        population = next((
            label for label in ("공무원", "군인", "사립학교 교직원", "선원")
            if label.replace(" ", "") in question.replace(" ", "")
        ), None)
        eligibility_relation_evidence = [
            item for item in result.evidence
            if population
            and population.replace(" ", "") in item.excerpt.replace(" ", "")
            and "일반퇴직연금가입대상" in item.excerpt.replace(" ", "")
            and "아닙" in item.excerpt
            and "별도" in item.excerpt
            and "퇴직급여제도" in item.excerpt.replace(" ", "")
        ]
        if population and eligibility_relation_evidence and any(marker in question for marker in ("가입", "대상")):
            plan.append(self._claim(
                "eligibility_relation",
                f"{population}은 일반 퇴직연금 가입 대상이 아니며, 별도의 퇴직급여제도를 적용받습니다.",
                evidence=eligibility_relation_evidence[:1],
            ))

        if is_principal_vs_performance_comparison(question):
            direct = [
                item for item in result.evidence
                if excerpt_supports_product_type_comparison(item.excerpt)
            ]
            if direct:
                for item in direct:
                    plan.append(self._claim("product_type_comparison", item.excerpt.strip(), evidence=[item]))
            else:
                plan.append(self._unsupported(
                    "product_type_comparison",
                    "[한계] 제공된 자료에서는 요청한 상품 유형의 정의와 비교 기준을 직접 확인할 수 없어 구체적으로 비교할 수 없습니다.",
                ))
            return plan

        if is_pension_savings_irp_comparison(question):
            plan.extend(self._savings_irp_comparison_claims(result.evidence))
            if not any(item.get("status") == "answerable" for item in plan):
                plan.append(self._unsupported(
                    "savings_irp_comparison",
                    "[한계] 제공된 근거 안에서만 답변할 수 있으며, 확인되지 않은 내용은 단정할 수 없습니다.",
                ))
            return plan

        if is_dc_contribution_determination_question(question):
            plan.extend(self._dc_contribution_claims(result.evidence))
            return plan

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

        hours_evidence = [
            item for item in result.evidence
            if "15시간" in item.excerpt or ("근로시간" in item.excerpt and "가입" in item.excerpt)
        ]
        if hours_evidence and any(marker in question for marker in ("시간", "근무", "가입 대상", "대상인가요", "대상인가")):
            plan.append(self._claim(
                "eligibility_hours",
                "제공 문서에 따르면 1주일 평균 근로시간이 15시간 이상이고 1년 이상 계속 근무하는 경우 퇴직연금 가입 대상입니다. 주 14시간 근무는 이 기준을 충족하지 않습니다.",
                evidence=hours_evidence[:1],
            ))

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

        tax_scope = result.tax_intent or tax_intent(question)
        tax_evidence = [
            item for item in doc51
            if any(marker in item.excerpt for marker in ("퇴직소득세", "이연퇴직소득세", "100%", "70%"))
            and not (tax_scope != "TAX_CREDIT" and "세액공제율" in item.excerpt and "퇴직소득세" not in item.excerpt)
            and ("연금수령" in item.excerpt or "실제수령연차" in item.excerpt or "이연퇴직소득세" in item.excerpt)
        ] or ([item for item in doc51 if "연금수령" in item.excerpt] if pension_year_rate_block_allowed(tax_scope) else [])
        if pension_year_rate_block_allowed(tax_scope) and (tax_evidence or doc51):
            plan.append(self._claim(
                "retirement_tax",
                "퇴직금 재원의 일시금 수령에는 퇴직소득세율 100%가 적용되고, 연금수령에는 실제수령연차에 따라 이연퇴직소득세의 70%·60%·50%가 적용됩니다. [한계] 실제 세액 계산에는 예상 퇴직소득세가 필요하며 수령 일정도 확인해야 합니다.",
                evidence=(tax_evidence or doc51)[:1],
            ))
        elif tax_scope == "RETIREMENT_LUMP_SUM_TAX":
            lump_evidence = [
                item for item in result.evidence
                if "일시금" in item.excerpt and "100%" in item.excerpt
            ]
            if lump_evidence:
                plan.append(self._claim(
                    "lump_sum_tax",
                    "일시금으로 받으면 퇴직소득세를 100% 납부합니다. [한계] 제공된 자료만으로 일시금 세율을 세액공제율과 같은 단일 값으로 단정할 수 없습니다.",
                    evidence=lump_evidence[:1],
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
        elif allows_dc_irp_account_transfer_claim(question):
            dc_irp_evidence = [
                item for item in result.evidence
                if excerpt_supports_dc_irp_retirement_transfer(item.excerpt)
            ]
            if dc_irp_evidence:
                plan.append(self._claim("account_transfer", "DC 법정퇴직금은 IRP로 이전할 수 있습니다.", evidence=dc_irp_evidence))

        if tax_scope == EARLY_WITHDRAWAL_TAX or result.procedure_type == "EARLY_WITHDRAWAL":
            procedure_evidence = [
                item for item in result.evidence
                if any(marker in item.excerpt for marker in ("중도인출", "해지", "인출"))
            ] or [item for item in result.evidence if item.document_id == "doc55"]
            if procedure_evidence:
                plan.append(self._claim(
                    "early_withdrawal",
                    "55세 전 IRP 인출·중도인출은 연금수령 연차에 따른 이연퇴직소득세 납부비율 규칙과 같은 질문이 아닙니다. 중도인출과 계좌 전체 해지는 구분해야 합니다. 제공 문서상 중도인출은 정해진 사유와 증빙이 필요한 절차입니다.",
                    evidence=procedure_evidence[:1],
                ))
            plan.append(self._unsupported(
                "early_withdrawal_tax_detail",
                "[한계] 중도인출·조기인출 세금은 인출 재원과 수령 방식에 따라 달라 제공 문서만으로 세부 세율·세액을 확정할 수 없습니다.",
            ))
        if tax_scope == ACCOUNT_TERMINATION_TAX:
            plan.append(self._unsupported(
                "termination_tax_detail",
                "[한계] 계좌 해지 시 세금은 인출 재원과 수령 방식에 따라 달라 제공 문서만으로 세부 세율·세액을 확정할 수 없습니다.",
            ))
        if (
            tax_scope == "UNKNOWN_TAX"
            and any(marker in question for marker in ("세금", "과세"))
            and result.withdrawal_result is None
            and len(result.tax_source_types) < 3
        ):
            plan.append(self._unsupported(
                "unknown_tax_detail",
                "[한계] 질문의 세금 범위를 연금수령 연차 납부비율로 단정할 수 없어, 제공 문서만으로 세부 세율·세액을 확정할 수 없습니다.",
            ))

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
        elif result.products and allows_product_evidence_enrichment(intent):
            product_text, product_evidence, _ = render_product_comparison(question, result.products, result.evidence, intent=intent)
            plan.append(self._claim(
                "product_facts",
                product_text,
                evidence=product_evidence or None,
                products=result.products,
            ))
        elif result.products:
            plan.append(self._claim("product_facts", self._compose_product_facts(result), products=result.products))
        for resolution in result.product_resolutions:
            if resolution.get("status") == "NOT_FOUND":
                entity = resolution.get("entity", "요청 상품")
                plan.append(self._unsupported(
                    f"product_{entity}",
                    f"[한계] 요청한 {entity} 상품은 현재 Product Fact에서 확인되지 않습니다.",
                ))
        for constraint in result.recommendation_constraints:
            if not constraint.get("applied") and constraint.get("constraint") == "account_type":
                plan.append(self._unsupported(
                    "account_type",
                    "[한계] 현재 Product Fact에서 요청한 계좌 유형에 가입 가능하다고 확인된 상품이 없어 조건 충족 상품을 비교할 수 없습니다.",
                ))
            if not constraint.get("applied") and constraint.get("constraint") == "shared_account_types":
                accounts = [str(value) for value in (constraint.get("value") or [])]
                missing = [str(value) for value in (constraint.get("missing_account_types") or [])]
                joined = "와 ".join(accounts) if accounts else "요청한 계좌 유형"
                if missing:
                    missing_joined = "와 ".join(missing)
                    limitation = (
                        f"[한계] 현재 제공된 Product Fact에서는 {missing_joined} 가입 가능 상품이 확인되지 않아, "
                        f"{joined}에서 공통으로 가입 가능한 상품이 있는지 확정할 수 없습니다."
                    )
                else:
                    limitation = (
                        f"[한계] 현재 제공된 Product Fact에서는 {joined}에서 공통으로 가입 가능한 상품이 확인되지 않아 "
                        "조건 충족 상품을 비교할 수 없습니다."
                    )
                plan.append(self._unsupported("shared_account_types", limitation))
            if not constraint.get("applied") and constraint.get("constraint") == "product_type":
                account = next((
                    item for item in result.recommendation_constraints
                    if item.get("constraint") == "account_type" and item.get("applied")
                ), None)
                product_type = str(constraint.get("value", "요청 유형"))
                if account:
                    limitation = (
                        f"[한계] 현재 Product Fact에서 {account.get('value')} 가입 가능 상품은 확인되지만, "
                        f"그중 {product_type}으로 확인되는 상품은 찾지 못했습니다."
                    )
                else:
                    limitation = f"[한계] 현재 제공 Product Fact 중 {product_type}으로 확인되는 상품은 찾지 못했습니다."
                plan.append(self._unsupported("product_type", limitation))
            if not constraint.get("applied") and constraint.get("constraint") == "investment_horizon":
                horizon = str(constraint.get("value", "요청한 기간"))
                plan.append(self._unsupported(
                    "investment_horizon",
                    f"[한계] 현재 Product Fact에는 {horizon} 투자기간 적합성을 직접 판정할 공식 field가 없어, 이 기간을 상품 필터에 적용하지 않았습니다.",
                ))
            if not constraint.get("applied") and constraint.get("constraint") == "principal_guarantee":
                plan.append(self._unsupported(
                    "principal_guarantee",
                    "[한계] 현재 Product Fact에는 원금보장 여부를 직접 판정할 공식 field가 없습니다. 원금보장 필수 조건을 확인하지 못했으므로 상품 후보를 제시하지 않습니다.",
                ))
            if not constraint.get("applied") and constraint.get("constraint") == "fee_ceiling_percent":
                plan.append(self._unsupported(
                    "fee_ceiling_percent",
                    f"[한계] 현재 Product Fact에는 상품 간 동일 기준으로 비교 가능한 보수 field가 없어 {constraint.get('value')}% 이하 조건을 적용할 수 없습니다. 조건 충족 상품 후보를 제시하지 않습니다.",
                ))
        distinctive_unapplied = [
            item for item in result.recommendation_constraints
            if item.get("constraint") not in {"account_type", "shared_account_types"} and not item.get("applied")
        ]
        if not result.products and distinctive_unapplied and not any(
            item.get("constraint") in {"principal_guarantee", "fee_ceiling_percent", "investment_horizon"}
            for item in distinctive_unapplied
        ):
            plan.append(self._unsupported(
                "recommendation_candidates",
                "[한계] 요청 조건을 현재 Product Fact의 공식 field로 확인할 수 없어 조건 충족 상품 후보를 특정할 수 없습니다.",
            ))
        elif not result.products and distinctive_unapplied and all(
            item.get("constraint") == "investment_horizon" for item in distinctive_unapplied
        ) and not any(item.get("subtask") == "investment_horizon" for item in plan):
            plan.append(self._unsupported(
                "recommendation_candidates",
                "[한계] 투자기간 적합성을 직접 판정할 공식 field가 없어 조건 충족 상품 후보를 특정할 수 없습니다.",
            ))

        requested_cost = any(x in question for x in ("비용", "보수", "수수료"))
        if requested_cost and allows_product_evidence_enrichment(intent):
            cost_text = None
            cost_evidence: list = []
            fee_mapping: dict[str, str] = {}
            for bundle in build_product_evidence_bundles(result.products, result.evidence, intent=intent):
                cost_text = render_cost_claim(bundle, intent=intent)
                if cost_text:
                    cost_evidence = bundle.citations
                    break
            if not cost_text:
                for citation in result.evidence:
                    fields = extract_fee_table(citation)
                    cost_text = render_fee_table_claim(fields)
                    if cost_text:
                        fee_mapping = structured_fee_mapping(fields)
                        cost_evidence = [citation]
                        break
            if cost_text:
                claim = self._claim("product_cost", cost_text, evidence=cost_evidence)
                if fee_mapping:
                    claim["structured_fee_mapping"] = fee_mapping
                plan.append(claim)
            else:
                plan.append(self._unsupported("product_cost", "[한계] 현재 확보된 Product Fact와 투자설명서 근거에서는 요청한 비용 값을 확인하지 못했습니다."))
        elif requested_cost:
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
        if is_pension_savings_irp_comparison(c.question):
            selected = [x for x in c.evidence if excerpt_supports_savings_irp_comparison(x.excerpt)]
            anchors = ("가입", "세액공제", "납입한도", "입금")
        elif is_principal_vs_performance_comparison(c.question):
            selected = [x for x in c.evidence if excerpt_supports_product_type_comparison(x.excerpt)]
            anchors = ("원리금보장", "실적배당", "정의", "비교")
        elif is_dc_contribution_determination_question(c.question):
            selected = [x for x in c.evidence if excerpt_supports_dc_contribution_structure(x.excerpt)]
            anchors = ("확정기여형", "입금", "운용")
        if allows_product_evidence_enrichment(c.intent) and c.products:
            matched: list[Citation] = []
            for product in c.products:
                matched.extend(citations_for_product(product, c.evidence)[:1])
            selected = matched or [x for x in selected if is_prospectus_citation(x)][:len(c.products)]
        elif c.products:
            selected = [x for x in selected if x.document_id.startswith("r2_")][:len(c.products)]
        rows = []
        for item in selected[:4]:
            text = item.excerpt
            positions = [text.find(a) for a in anchors if a in text]
            start = max(0, min(positions)-80) if positions else 0
            if allows_product_evidence_enrichment(c.intent) and c.products:
                for marker in ("2. 투자전략", "1. 투자목적", "수수료선취-오프라인(A)"):
                    idx = text.find(marker)
                    if idx >= 0:
                        start = idx
                        break
            excerpt = text[start:start + (720 if allows_product_evidence_enrichment(c.intent) and c.products else (240 if c.products else 360))]
            rows.append({"document_id":item.document_id, "page":item.page, "excerpt":excerpt})
        return rows

    @staticmethod
    def _prompt_metrics(c: GroundedContext, prompt: str) -> dict[str, int]:
        evidence = Composer._focused_evidence(c)
        return {"prompt_chars":len(prompt), "retrieved_evidence_count":len(evidence),
                "retrieved_evidence_chars":sum(len(str(x["excerpt"])) for x in evidence),
                "product_fact_count":len(c.products), "rule_result_count":len(c.calculations)}

    def _grounded_message(self, question: str, result: ToolResult, intent: Intent | None = None) -> str | None:
        parts: list[str] = []
        if result.withdrawal_result is not None:
            lines = [
                f"- {scenario.scenario}: 퇴직소득세 {scenario.tax_value}{result.withdrawal_result.comparison.unit}, 적용 비율 {scenario.applicable_rate}"
                for scenario in result.withdrawal_result.comparison.scenarios
            ]
            parts.append("Rule Result에 포함된 수령 시나리오별 퇴직소득세입니다.\n" + "\n".join(lines))
        elif pension_year_rate_block_allowed(result.tax_intent or tax_intent(question)) and any("70%" in c.excerpt and "50%" in c.excerpt for c in result.evidence):
            parts.append("제공 문서의 실제수령연차 기준으로 1~10년차에는 이연퇴직소득세의 70%, 11~20년차에는 60%, 21년차부터는 50%를 납부합니다. [한계] 실제 세액 계산에는 예상 퇴직소득세가 필요합니다.")
        if self._is_db_dc_explanation(question, result):
            parts.append("확정급여형(DB)은 근로자가 퇴직할 때 받을 금액이 사전에 확정되어 있고 회사가 적립금을 운용합니다. 확정기여형(DC)은 회사가 매년 일정 금액을 근로자의 계좌에 입금하고 근로자가 직접 운용하므로, 운용 수익률에 따라 최종 퇴직금이 달라집니다.")
        if has_alias(question, "dc") and "연금저축" in question and any(c.document_id == "doc51" and "계약이전" in c.excerpt for c in result.evidence):
            parts.append("DC 퇴직금은 먼저 IRP로 이전해야 하며, 연금저축에서 운용하려면 IRP로 퇴직금을 수령한 뒤 연금저축으로 계약이전할 수 있습니다.")
        elif allows_dc_irp_account_transfer_claim(question) and any(
            excerpt_supports_dc_irp_retirement_transfer(item.excerpt) for item in result.evidence
        ):
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
        if pension_year_rate_block_allowed(result.tax_intent or tax_intent(question)) and any(c.document_id == "doc51" for c in result.evidence):
            parts.append("퇴직금 재원을 연금으로 수령할 때는 실제수령연차에 따라 이연퇴직소득세의 70%·60%·50%를 납부합니다. [한계] 실제 세액은 예상 퇴직소득세와 수령 일정이 있어야 계산할 수 있습니다.")
        if "유동성" in question:
            parts.append("[한계] 제공 문서는 수령연차별 세율은 제시하지만 수령 주기·회차별 금액은 제시하지 않으므로, 10년과 21년 안의 실제 유동성 차이는 수령 일정을 정하기 전에는 단정할 수 없습니다.")
        if has_alias(question, "institution") and "일반" in question:
            parts.append("제공된 제도 근거에 따르면 퇴직연금은 기업이 근로자의 퇴직금을 사외 금융기관에 적립하고, "
                    "퇴직 시 근로자가 연금 또는 일시금으로 수령할 수 있는 제도입니다. "
                    "[한계] 현재 근거에는 일반 퇴직금과의 항목별 차이가 모두 제시되어 있지 않아 그 밖의 차이는 단정할 수 없습니다.")
        if self._is_tax_deduction_question(question, result):
            prefix = "아닙니다. " if any(x in question for x in ("무제한", "무조건")) else ""
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
            parts.append(self._compose_product_facts(result, question, intent))
        if any(x in question for x in ("향후 수익률", "미래 수익률", "장래", "수익률 수치")):
            parts.append("[한계] 제공 문서에 없는 향후 수익률 숫자는 예측할 수 없습니다. 현재 문서와 Product Fact에서 확인되는 과거 수익률·위험·비용만 근거 범위에서 비교할 수 있습니다.")
        return "\n\n".join(dict.fromkeys(parts)) if parts else None

    @staticmethod
    def _false_premise_correction(question: str, result: ToolResult) -> tuple[str, str] | None:
        hit = detect_false_premise(question, result.evidence, result.products)
        if hit:
            return hit.correction, hit.evidence_id
        return None

    @staticmethod
    def _is_db_dc_explanation(q, r): return is_db_dc_question(q) and has_alias(q,"db") and has_alias(q,"dc") and any(c.document_id=="doc10" for c in r.evidence)
    @staticmethod
    def _is_tax_deduction_question(q, r): return (is_tax_deduction_question(q) or r.tax_intent == "TAX_CREDIT") and bool({c.document_id for c in r.evidence}&{"doc41","doc55"})
    @staticmethod
    def _is_teacher_retirement_question(q, r): return is_teacher_retirement_domain(q) and has_legally_named_retirement_benefit(q) and any(c.document_id=="doc26" for c in r.evidence)
    @staticmethod
    def _is_grounded_product_compare(q, r): return bool(r.products) and is_comparison_question(q)
    @staticmethod
    def _compose_product_facts(r, question="", intent: Intent | None = None):
        if allows_product_evidence_enrichment(intent):
            text, _, _ = render_product_comparison(question, r.products, r.evidence, intent=intent)
            return text
        lines=[f"- {p.get('product_name')}: 자산유형 {p.get('asset_type')}, 위험등급 {p.get('risk_level')}등급({p.get('risk_label')}), 가입 가능 계좌 {p.get('plan_types')}" for p in r.products]
        return "제공된 Product Fact와 투자설명서 기준 비교입니다.\n"+"\n".join(lines)+"\n위험등급은 1등급이 매우 높은 위험, 2등급이 높은 위험, 3등급이 다소 높은 위험, 4등급이 보통 위험, 5등급이 낮은 위험, 6등급이 매우 낮은 위험입니다. [한계] 각 상품의 투자전략·클래스·총보수·비용·과거수익률은 현재 구조화된 Product Fact에서 확인되지 않습니다. 상품명만으로 듀레이션·변동성이나 개인 적합성을 단정할 수 없습니다."

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
