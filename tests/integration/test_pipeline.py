"""대표 통합 질문(문서 8장)이 역질문 -> 슬롯 채움 -> 검색/계산/검증까지 통과하는지 확인."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

QUESTION = "퇴직금 3억원, 예상 퇴직소득세 2,400만원인데 일시금과 연금 중 무엇이 나을까요?"


def test_representative_question_asks_for_missing_plan_type_first() -> None:
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
    assert body["type"] == "clarification"
    assert any(s["name"] == "plan_type" for s in body["required_slots"])
    assert len(body["required_slots"]) <= 3


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


def test_session_retains_slots_across_followup_turns() -> None:
    session_id = "integration-3"
    first = client.post(
        "/v1/chat",
        json={
            "session_id": session_id,
            "question": QUESTION,
            "profile": {"retirement_amount_won": 300_000_000, "expected_tax_won": 24_000_000},
        },
    )
    assert first.json()["type"] == "clarification"

    second = client.post(
        "/v1/chat",
        json={"session_id": session_id, "question": "DC형이에요", "profile": {"plan_type": "DC"}},
    )
    assert second.status_code == 200


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
