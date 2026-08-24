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
        result = client.complete("sys", "질문")
        assert result == "ok"
        assert calls["n"] == 2
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
        return httpx.Response(500, json={"error": "boom"})

    client = HCXClient(_settings(hcx_max_retries=0))
    client._client = httpx.Client(base_url="https://mock", transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(HCXError) as exc_info:
            client.complete("sys", "질문")
        assert exc_info.value.code == ErrorCode.UPSTREAM_ERROR
    finally:
        client.close()
