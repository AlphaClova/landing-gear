"""HCX client(A3)의 mock 모드·timeout·retry 계약을 검증."""

import httpx
import pytest

from app.agent.hcx_client import HCXClient
from app.core.config import Settings
from app.core.errors import ErrorCode, HCXError


def _settings(**overrides) -> Settings:
    base = {"hcx_api_key": "test-key", "hcx_max_retries": 2, "hcx_timeout_seconds": 1.0}
    base.update(overrides)
    return Settings(**base)


def test_mock_mode_when_no_api_key() -> None:
    client = HCXClient(Settings(hcx_api_key=""))
    try:
        assert client.is_mock
        result = client.complete("sys", "안녕하세요")
        assert "[MOCK 응답]" in result
    finally:
        client.close()


def test_retries_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            raise httpx.TimeoutException("boom", request=request)
        return httpx.Response(200, json={"result": {"message": {"content": "ok"}}})

    client = HCXClient(_settings())
    client._client = httpx.Client(base_url="https://mock", transport=httpx.MockTransport(handler))
    try:
        result = client.complete("sys", "질문", request_id="req-test", case_id="G001")
        assert result == "ok"
        assert calls["n"] == 2
        assert client.last_attempt_details[0]["timeout"] is True
        assert client.last_attempt_details[1] == {
            "request_id": "req-test",
            "case_id": "G001",
            "attempt": 2,
            "started_at": client.last_attempt_details[1]["started_at"],
            "duration_ms": client.last_attempt_details[1]["duration_ms"],
            "success": True,
            "exception_class": None,
            "transport_error_type": None,
            "upstream_http_status": 200,
            "retry_after": None,
            "timeout": False,
            "retry": True,
            "final_exhausted": False,
            "status": "ok",
        }
    finally:
        client.close()


def test_exhausts_retries_and_raises_hcx_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("boom", request=request)

    client = HCXClient(_settings(hcx_max_retries=1))
    client._client = httpx.Client(base_url="https://mock", transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(HCXError) as exc_info:
            client.complete("sys", "질문")
        assert exc_info.value.code == ErrorCode.UPSTREAM_TIMEOUT
        assert exc_info.value.status_code == 504
    finally:
        client.close()


def test_upstream_http_error_raises_upstream_error_code(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "2"}, json={"error": "boom"})

    client = HCXClient(_settings(hcx_max_retries=0))
    client._client = httpx.Client(base_url="https://mock", transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(HCXError) as exc_info:
            client.complete("sys", "질문", request_id="req-rate", case_id="G120")
        assert exc_info.value.code == ErrorCode.UPSTREAM_ERROR
        assert client.last_attempt_details[0]["upstream_http_status"] == 429
        assert client.last_attempt_details[0]["retry_after"] == "2"
        assert client.last_attempt_details[0]["final_exhausted"] is True
    finally:
        client.close()


def test_429_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json={"result": {"message": {"content": "ok"}}})

    client = HCXClient(_settings())
    client._client = httpx.Client(base_url="https://mock", transport=httpx.MockTransport(handler))
    try:
        assert client.complete("sys", "질문") == "ok"
        assert [item["upstream_http_status"] for item in client.last_attempt_details] == [429, 200]
    finally:
        client.close()


def test_timeout_attempt_uses_remaining_total_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    client = HCXClient(_settings(hcx_timeout_seconds=8.0, hcx_total_budget_seconds=10.0))
    observed: list[float] = []

    def fail(_system, _user, _tokens, *, timeout=None):
        observed.append(timeout)
        raise httpx.TimeoutException("boom")

    monkeypatch.setattr(client, "_call", fail)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    try:
        with pytest.raises(HCXError):
            client.complete("sys", "질문")
        assert observed
        assert all(value <= 10.0 for value in observed)
    finally:
        client.close()
