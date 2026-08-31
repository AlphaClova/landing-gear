import json

from fastapi.testclient import TestClient

from app.api.schemas import Citation, parse_retrieved_context, serialize_retrieved_context
from app.main import app

client = TestClient(app)

FIELDS = {"question_id", "question", "retrieved_context", "think_trace", "answer"}


def _citations() -> list[Citation]:
    return [
        Citation(
            id="doc41-p01-c02",
            document_id="doc41",
            page=1,
            source="provided",
            excerpt="연금저축 세액공제 한도는 연 600만원입니다.",
        ),
        Citation(
            id="doc55-p10-c01",
            document_id="doc55",
            page=10,
            source="provided",
            excerpt="IRP를 포함한 합산 한도는 연 900만원입니다.",
        ),
    ]


def test_serialize_multiple_documents_as_single_string() -> None:
    text = serialize_retrieved_context(_citations())
    assert isinstance(text, str)
    assert not isinstance(text, list)
    assert text.startswith("[DOC doc41][PAGE 1][EVIDENCE doc41-p01-c02]\n")
    assert "[DOC doc55][PAGE 10][EVIDENCE doc55-p10-c01]\n" in text
    excerpts = parse_retrieved_context(text)
    assert excerpts == [
        "연금저축 세액공제 한도는 연 600만원입니다.",
        "IRP를 포함한 합산 한도는 연 900만원입니다.",
    ]


def test_serialize_empty_context_is_empty_string() -> None:
    assert serialize_retrieved_context([]) == ""
    assert parse_retrieved_context("") == []


def test_get_answer_exact_five_string_fields() -> None:
    resp = client.get(
        "/answer",
        params={"question_id": "Q-CONTRACT-001", "question": "DB형과 DC형은 어떻게 다른가요?"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    body = resp.json()
    assert set(body) == FIELDS
    assert all(isinstance(value, str) for value in body.values())
    assert body["question_id"] == "Q-CONTRACT-001"
    assert body["question"] == "DB형과 DC형은 어떻게 다른가요?"
    assert isinstance(body["retrieved_context"], str)
    assert isinstance(body["think_trace"], str)
    json.loads(body["think_trace"])


def test_get_answer_requires_no_auth_header() -> None:
    resp = client.get(
        "/answer",
        params={"question_id": "Q-CONTRACT-002", "question": "오늘 비트코인 가격이 오를까요?"},
        headers={},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == FIELDS
    assert all(isinstance(value, str) for value in body.values())
    assert body["retrieved_context"] == "" or isinstance(body["retrieved_context"], str)
    assert not isinstance(body["retrieved_context"], list)


def test_get_answer_oos_empty_context_is_empty_string() -> None:
    resp = client.get(
        "/answer",
        params={"question_id": "Q-CONTRACT-003", "question": "오늘 비트코인 가격이 오를까요?"},
    )
    body = resp.json()
    assert body["retrieved_context"] == ""
    assert parse_retrieved_context(body["retrieved_context"]) == []
