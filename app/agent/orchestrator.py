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
        if session_id:
            self._sessions.merge(session_id, slots)

        if route_decision.intent == "범위 밖":
            return self._verifier.finalize(
                draft=None,
                request_id=request_id,
                session_id=session_id,
                route_decision=route_decision,
                tool_traces=[],
                out_of_scope=True,
            )

        missing = self._slots.required(route_decision.intent, slots)
        if missing:
            return self._verifier.finalize(
                draft=None,
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
            draft = self._composer.compose(question, route_decision.intent, tool_result)
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
