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


def test_answer_default_returns_exact_official_contract() -> None:
    resp = client.post("/answer", json={"question_id": "q-1", "question": "퇴직연금 제도 알려줘"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"question_id", "question", "retrieved_context", "think_trace", "answer"}


def test_answer_get_is_backward_compatible_with_strict_contract(monkeypatch) -> None:
    from app.core import config as config_module
    monkeypatch.setenv("EVAL_SCHEMA_MODE", "strict")
    config_module.get_settings.cache_clear()
    try:
        resp = client.get("/answer", params={"question_id": "q-get", "question": "퇴직연금 제도 알려줘"})
        assert resp.status_code == 200
        assert set(resp.json()) == {"question_id", "question", "retrieved_context", "think_trace", "answer"}
        assert resp.json()["question_id"] == "q-get"
    finally:
        config_module.get_settings.cache_clear()


def test_public_think_trace_excludes_internal_diagnostics() -> None:
    import json

    resp = client.get("/answer", params={"question_id": "trace-safe", "question": "DB와 DC 차이"})
    trace_text = resp.json()["think_trace"]
    trace = json.loads(trace_text)
    assert set(trace) == {
        "intent", "route", "retrieval", "tools", "composition", "verification",
        "hcx_invoked", "hcx_success", "degraded", "fallback_used",
    }
    for forbidden in ("hcx_audit", "request_id", "claim_plan", "prompt_metrics", "violations", "output"):
        assert forbidden not in trace_text


def test_ready_reports_production_b_provider_wiring() -> None:
    body = client.get("/ready").json()
    assert body["EVIDENCE_PROVIDER"] == "real"
    assert body["RULE_PROVIDER"] == "real"
    assert body["PRODUCT_PROVIDER"] == "real"


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
