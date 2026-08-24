import uuid
from functools import lru_cache

from fastapi import Request

from app.agent.composer import Composer
from app.agent.hcx_client import HCXClient
from app.agent.orchestrator import Orchestrator
from app.agent.router import IntentRouter
from app.agent.slots import SlotManager
from app.agent.tools import BRuleEngine, ToolRouter
from app.agent.verifier import Verifier
from app.core.config import Settings, get_settings
from app.core.session import SessionStore, get_session_store


def new_request_id() -> str:
    return f"req_{uuid.uuid4().hex[:20]}"


def get_request_id(request: Request) -> str:
    """미들웨어(app.main)가 request.state.request_id를 채워둔다."""
    return getattr(request.state, "request_id", None) or new_request_id()


@lru_cache
def get_hcx_client() -> HCXClient:
    return HCXClient(get_settings())


@lru_cache
def get_tool_router() -> ToolRouter:
    # retrieve_evidence/query_products는 B 구현이 아직 없어 Mock 유지.
    return ToolRouter(rule_engine=BRuleEngine())


@lru_cache
def get_orchestrator() -> Orchestrator:
    settings: Settings = get_settings()
    session_store: SessionStore = get_session_store(settings.session_ttl_seconds)
    return Orchestrator(
        router=IntentRouter(),
        slot_manager=SlotManager(),
        tool_router=get_tool_router(),
        composer=Composer(get_hcx_client()),
        verifier=Verifier(),
        session_store=session_store,
    )
