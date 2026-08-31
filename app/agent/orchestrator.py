"""전체 파이프라인: Router -> Slot -> Tool -> Composer -> Verifier."""

from app.agent.composer import Composer
from app.agent.router import IntentRouter
from app.agent.slots import SlotManager
from app.agent.tools import ToolRouter
from app.agent.verifier import Verifier
from app.api.schemas import InternalAnswer, UserProfile
from app.core.errors import AppError
from app.core.logging import get_logger, log_context
from app.core.session import SessionStore

logger = get_logger(__name__)

# 세제/종합 intent에서 사용할 기본 Rule Engine id. B가 실제 rule 목록을 정하면 교체한다.
_RULE_ID_BY_INTENT = {
    "세제": "retirement_income_tax",
    "종합": "lump_sum_vs_pension",
}


class Orchestrator:
    def __init__(
        self,
        router: IntentRouter,
        slot_manager: SlotManager,
        tool_router: ToolRouter,
        composer: Composer,
        verifier: Verifier,
        session_store: SessionStore,
    ) -> None:
        self._router = router
        self._slots = slot_manager
        self._tools = tool_router
        self._composer = composer
        self._verifier = verifier
        self._sessions = session_store

    def handle(
        self,
        *,
        question: str,
        request_id: str,
        session_id: str | None,
        profile: UserProfile,
        evaluation_question_id: str | None = None,
    ) -> InternalAnswer:
        route_decision = self._router.classify(question)
        log_context(
            logger,
            "route_decided",
            request_id=request_id,
            intent=route_decision.intent,
            route=route_decision.route,
            confidence=route_decision.route_confidence,
        )

        session_slots = self._sessions.get(session_id) if session_id else {}
        slots = self._slots.merge(profile, session_slots)
        slots.update(self._slots.extract(question))
        if session_id:
            self._sessions.merge(session_id, slots)

        if route_decision.intent == "범위 밖":
            draft = self._verify_and_retry(self._composer.compose(question, route_decision.intent, out_of_scope=True, request_id=request_id, case_id=evaluation_question_id))
            return self._verifier.finalize(
                draft=draft,
                request_id=request_id,
                session_id=session_id,
                route_decision=route_decision,
                tool_traces=[],
                out_of_scope=True,
            )

        missing = self._slots.required(route_decision.intent, slots, question)
        if missing:
            if route_decision.intent in {"종합", "상품"}:
                tool_result = self._tools.run(
                    route_decision.intent,
                    slots,
                    question=question,
                    rule_id=_RULE_ID_BY_INTENT.get(route_decision.intent),
                )
                draft = self._verify_and_retry(self._composer.compose(
                    question, route_decision.intent, tool_result, required_slots=missing,
                    request_id=request_id, case_id=evaluation_question_id,
                ))
                return self._verifier.finalize(
                    draft=draft,
                    request_id=request_id,
                    session_id=session_id,
                    route_decision=route_decision,
                    tool_traces=tool_result.traces,
                )
            draft = self._verify_and_retry(self._composer.compose(question, route_decision.intent, required_slots=missing, request_id=request_id, case_id=evaluation_question_id))
            return self._verifier.finalize(
                draft=draft,
                request_id=request_id,
                session_id=session_id,
                route_decision=route_decision,
                tool_traces=[],
                required_slots=missing,
            )

        try:
            tool_result = self._tools.run(
                route_decision.intent,
                slots,
                question=question,
                rule_id=_RULE_ID_BY_INTENT.get(route_decision.intent),
            )
            draft = self._composer.compose(question, route_decision.intent, tool_result, request_id=request_id, case_id=evaluation_question_id)
            draft = self._verify_and_retry(draft)
        except AppError as exc:
            log_context(logger, "pipeline_error", request_id=request_id, code=exc.code, message=exc.message)
            raise

        return self._verifier.finalize(
            draft=draft,
            request_id=request_id,
            session_id=session_id,
            route_decision=route_decision,
            tool_traces=tool_result.traces,
        )

    def _verify_and_retry(self, draft):
        issues = self._verifier.check(draft)
        if not issues:
            draft.hcx_first_pass = True
            return draft
        logger.warning("hcx_draft_rejected issues=%s", issues)
        draft.hcx_audit[0]["violations"] = issues
        if self._verifier.repair_safe(draft, issues):
            draft.deterministic_repaired = True
            return draft
        if draft.degraded:
            return self._composer.use_fallback(draft, draft.degraded_reason or "; ".join(issues))
        draft = self._composer.regenerate(draft, issues)
        issues = self._verifier.check(draft)
        draft.hcx_audit[-1]["violations"] = issues
        if issues:
            logger.warning("hcx_regeneration_rejected issues=%s", issues)
            return self._composer.use_fallback(draft, "; ".join(issues))
        return draft
