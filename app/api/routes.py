from fastapi import APIRouter, Depends, Query

from app.agent.orchestrator import Orchestrator
from app.api.dependencies import get_orchestrator, get_request_id, get_tool_router
from app.api.schemas import (
    AnswerRequest,
    ChatRequest,
    ChatResponse,
    EvalResponse,
    InternalAnswer,
    to_chat_response,
    to_eval_response,
)
from app.core.config import Settings, get_settings

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """liveness: 프로세스가 떠 있는지만 확인."""
    return {"status": "ok"}


@router.get("/ready")
def ready(settings: Settings = Depends(get_settings)) -> dict[str, str | bool]:
    """readiness: 하위 의존성이 응답 가능한 상태인지 확인."""
    providers = get_tool_router().provider_status()
    return {
        "status": "ready",
        "hcx_mock_mode": not bool(settings.hcx_api_key),
        "HCX_PROVIDER": "real" if settings.hcx_api_key else "mock",
        **providers,
    }


@router.post("/v1/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
    request_id: str = Depends(get_request_id),
) -> ChatResponse:
    internal = orchestrator.handle(
        question=request.question,
        request_id=request_id,
        session_id=request.session_id,
        profile=request.profile,
    )
    return to_chat_response(internal)


def _answer(
    request: AnswerRequest,
    orchestrator: Orchestrator,
    settings: Settings,
    request_id: str,
) -> EvalResponse | InternalAnswer:
    internal = orchestrator.handle(
        question=request.question,
        request_id=request_id,
        session_id=None,
        profile=request.profile,
        evaluation_question_id=request.question_id,
    )

    # /answer is the competition endpoint and always has the official contract.
    # /v1/chat remains the internal/frontend contract.
    return to_eval_response(internal, question_id=request.question_id, question=request.question)


@router.post("/answer", response_model=None)
def answer_post(
    request: AnswerRequest,
    orchestrator: Orchestrator = Depends(get_orchestrator),
    settings: Settings = Depends(get_settings),
    request_id: str = Depends(get_request_id),
) -> EvalResponse | InternalAnswer:
    return _answer(request, orchestrator, settings, request_id)


@router.get("/answer", response_model=None)
def answer_get(
    question_id: str = Query(...),
    question: str = Query(...),
    orchestrator: Orchestrator = Depends(get_orchestrator),
    settings: Settings = Depends(get_settings),
    request_id: str = Depends(get_request_id),
) -> EvalResponse | InternalAnswer:
    return _answer(AnswerRequest(question_id=question_id, question=question), orchestrator, settings, request_id)
