from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready() -> None:
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


def test_chat_missing_question_returns_422() -> None:
    resp = client.post("/v1/chat", json={"session_id": "s1"})
    assert resp.status_code == 422


def test_chat_response_shape() -> None:
    resp = client.post("/v1/chat", json={"session_id": "contract-1", "question": "연금 상품 신청 절차가 어떻게 되나요?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] in {"clarification", "result", "limitation", "error"}
    assert "request_id" in body and body["request_id"]
    assert "citations" in body
    assert "required_slots" in body
    assert resp.headers["x-request-id"] == body["request_id"]


def test_chat_out_of_scope() -> None:
    resp = client.post("/v1/chat", json={"session_id": "contract-2", "question": "오늘 날씨 어때?"})
    assert resp.status_code == 200
    assert resp.json()["type"] == "limitation"


def test_answer_loose_mode_returns_internal_answer() -> None:
    resp = client.post("/answer", json={"question_id": "q-1", "question": "퇴직연금 제도 알려줘"})
    assert resp.status_code == 200
    body = resp.json()
    assert "trace" in body
    assert body["request_id"]


def test_answer_error_response_has_code_and_request_id(monkeypatch) -> None:
    from app.api import dependencies as deps
    from app.core.errors import ErrorCode, ToolError

    class BrokenToolRouter:
        def run(self, *args, **kwargs):
            raise ToolError("retrieve_evidence", "boom", code=ErrorCode.TOOL_UNAVAILABLE)

    deps.get_tool_router.cache_clear()
    monkeypatch.setattr(deps, "get_tool_router", lambda: BrokenToolRouter())
    deps.get_orchestrator.cache_clear()

    resp = client.post(
        "/v1/chat", json={"session_id": "contract-3", "question": "퇴직연금 해지 신청 서류는 뭐가 필요한가요?"}
    )
    assert resp.status_code == 503
    body = resp.json()
    assert body["code"] == "tool_unavailable"
    assert body["request_id"]

    deps.get_orchestrator.cache_clear()
