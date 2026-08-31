"""HyperCLOVA X client (A3): timeout·retry·모델/프롬프트 버전 관리.

hcx_api_key가 없으면 mock 모드로 동작해 API 키 없이도 파이프라인 전체를
개발·테스트할 수 있게 한다. 실 배포 전에는 반드시 키를 설정해야 한다.
"""

import time
from datetime import datetime, timezone

import httpx

from app.core.config import Settings
from app.core.errors import ErrorCode, HCXError
from app.core.logging import get_logger, log_context

logger = get_logger(__name__)


class HCXClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.Client(
            base_url=settings.hcx_api_base_url,
            timeout=settings.hcx_timeout_seconds,
        )
        self.last_attempts = 0
        self.last_success = False
        self.last_timeout_count = 0
        self.last_attempt_details: list[dict[str, object]] = []

    @property
    def is_mock(self) -> bool:
        return not self._settings.hcx_api_key

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 512,
        request_id: str | None = None,
        case_id: str | None = None,
    ) -> str:
        self.last_attempts = 0
        self.last_success = False
        self.last_timeout_count = 0
        self.last_attempt_details = []
        if self.is_mock:
            self.last_attempts = 1
            self.last_success = True
            return self._mock_complete(user_prompt)

        last_error: Exception | None = None
        budget_started = time.monotonic()
        for attempt in range(1, self._settings.hcx_max_retries + 2):
            remaining = self._settings.hcx_total_budget_seconds - (time.monotonic() - budget_started)
            if remaining <= 0.05:
                break
            self.last_attempts = attempt
            started = time.monotonic()
            started_at = datetime.now(timezone.utc).isoformat()
            try:
                result = self._call(system_prompt, user_prompt, max_tokens, timeout=min(self._settings.hcx_timeout_seconds, remaining))
                self.last_success = True
                detail = {
                    "request_id": request_id,
                    "case_id": case_id,
                    "attempt": attempt,
                    "started_at": started_at,
                    "duration_ms": round((time.monotonic() - started) * 1000, 3),
                    "success": True,
                    "exception_class": None,
                    "transport_error_type": None,
                    "upstream_http_status": 200,
                    "retry_after": None,
                    "timeout": False,
                    "retry": attempt > 1,
                    "final_exhausted": False,
                    "status": "ok",
                }
                self.last_attempt_details.append(detail)
                log_context(logger, "hcx_transport_attempt", **detail)
                return result
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_error = exc
                status = "timeout" if isinstance(exc, httpx.TimeoutException) else "error"
                self.last_timeout_count += status == "timeout"
                response = exc.response if isinstance(exc, httpx.HTTPStatusError) else None
                detail = {
                    "request_id": request_id,
                    "case_id": case_id,
                    "attempt": attempt,
                    "started_at": started_at,
                    "duration_ms": round((time.monotonic() - started) * 1000, 3),
                    "success": False,
                    "exception_class": type(exc).__name__,
                    "transport_error_type": "timeout" if isinstance(exc, httpx.TimeoutException) else ("http_status" if response is not None else "transport"),
                    "upstream_http_status": response.status_code if response is not None else None,
                    "retry_after": response.headers.get("Retry-After") if response is not None else None,
                    "timeout": isinstance(exc, httpx.TimeoutException),
                    "retry": attempt > 1,
                    "final_exhausted": attempt == self._settings.hcx_max_retries + 1,
                    "status": status,
                }
                self.last_attempt_details.append(detail)
                log_context(logger, "hcx_transport_attempt", **detail)
                remaining = self._settings.hcx_total_budget_seconds - (time.monotonic() - budget_started)
                if remaining <= 0.05:
                    break
                time.sleep(min(0.5 * attempt, 2.0, max(0.0, remaining - 0.05)))

        code = ErrorCode.UPSTREAM_TIMEOUT if isinstance(last_error, httpx.TimeoutException) else ErrorCode.UPSTREAM_ERROR
        log_context(
            logger,
            "API_502_FROM_HCX_EXHAUSTED_RETRY" if code == ErrorCode.UPSTREAM_ERROR else "API_504_FROM_HCX_EXHAUSTED_RETRY",
            request_id=request_id,
            case_id=case_id,
            attempts=self.last_attempts,
            exception_class=type(last_error).__name__ if last_error else None,
            final_exhausted=True,
        )
        raise HCXError(
            f"HCX 호출 실패 (bounded attempts 종료): {last_error}",
            code=code,
            attempt_details=list(self.last_attempt_details),
        )

    def _call(self, system_prompt: str, user_prompt: str, max_tokens: int, *, timeout: float | None = None) -> str:
        response = self._client.post(
            f"/testapp/v3/chat-completions/{self._settings.hcx_model}",
            headers={
                "Authorization": f"Bearer {self._settings.hcx_api_key}",
                "Content-Type": "application/json",
            },
            json={
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "maxTokens": max_tokens,
                "temperature": 0.2,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
        return data["result"]["message"]["content"]

    def _mock_complete(self, user_prompt: str) -> str:
        # 사용자 질문·근거 원문을 echo하면 "3억원"처럼 단위 붙은 숫자가 그대로 섞여
        # Verifier의 근거 없는 숫자 검사에 걸린다 (calculation_results 값과 형식이 달라
        # 근거 없는 숫자로 오인됨). mock 응답은 아무 사용자 입력도 echo하지 않는다.
        logger.info(
            "hcx_mock_complete model=%s prompt_version=%s prompt_len=%s",
            self._settings.hcx_model,
            self._settings.hcx_prompt_version,
            len(user_prompt),
        )
        return "[MOCK 응답] 제공된 근거와 계산 결과를 참고해 주세요. (실 HCX 연결 전 mock 모드)"

    def close(self) -> None:
        self._client.close()
