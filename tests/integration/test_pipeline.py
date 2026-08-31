"""대표 통합 질문이 질문 내 슬롯 재사용 -> 검색/계산/검증까지 통과하는지 확인."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

QUESTION = "퇴직금 3억원, 예상 퇴직소득세 2,400만원인데 일시금과 연금 중 무엇이 나을까요?"


def test_representative_question_does_not_ask_for_unused_plan_type() -> None:
    resp = client.post(
        "/v1/chat",
        json={
            "session_id": "integration-1",
            "question": QUESTION,
            "profile": {"retirement_amount_won": 300_000_000, "expected_tax_won": 24_000_000},
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] in {"result", "limitation"}
    assert body["required_slots"] == []


def test_representative_question_completes_with_full_profile() -> None:
    resp = client.post(
        "/v1/chat",
        json={
            "session_id": "integration-2",
            "question": QUESTION,
            "profile": {
                "retirement_amount_won": 300_000_000,
                "expected_tax_won": 24_000_000,
                "plan_type": "DC",
            },
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] in {"result", "limitation"}
    assert body["request_id"]
    assert len(body["citations"]) >= 1


def test_question_filled_slots_are_reused_without_clarification() -> None:
    session_id = "integration-3"
    first = client.post(
        "/v1/chat",
        json={
            "session_id": session_id,
            "question": QUESTION,
            "profile": {"retirement_amount_won": 300_000_000, "expected_tax_won": 24_000_000},
        },
    )
    assert first.json()["type"] in {"result", "limitation"}
    assert first.json()["required_slots"] == []


def test_eval_endpoint_returns_five_fields_in_strict_mode(monkeypatch) -> None:
    from app.core import config as config_module

    config_module.get_settings.cache_clear()
    monkeypatch.setenv("EVAL_SCHEMA_MODE", "strict")
    config_module.get_settings.cache_clear()

    resp = client.post("/answer", json={"question_id": "q-strict-1", "question": QUESTION})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"question_id", "question", "retrieved_context", "think_trace", "answer"}
    assert body["question_id"] == "q-strict-1"

    config_module.get_settings.cache_clear()
