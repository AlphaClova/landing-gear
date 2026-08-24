"""HyperCLOVA X client (A3): timeout·retry·모델/프롬프트 버전 관리.

hcx_api_key가 없으면 mock 모드로 동작해 API 키 없이도 파이프라인 전체를
개발·테스트할 수 있게 한다. 실 배포 전에는 반드시 키를 설정해야 한다.
"""

import time

import httpx

from app.core.config import Settings
from app.core.errors import ErrorCode, HCXError
from app.core.logging import get_logger

logger = get_logger(__name__)


class HCXClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.Client(
            base_url=settings.hcx_api_base_url,
            timeout=settings.hcx_timeout_seconds,
        )

    @property
    def is_mock(self) -> bool:
        return not self._settings.hcx_api_key

    def complete(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 512) -> str:
        if self.is_mock:
            return self._mock_complete(user_prompt)

        last_error: Exception | None = None
        for attempt in range(1, self._settings.hcx_max_retries + 2):
            try:
                return self._call(system_prompt, user_prompt, max_tokens)
            except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.TransportError) as exc:
                last_error = exc
                logger.warning("hcx_call_retry attempt=%s error=%s", attempt, exc)
                time.sleep(min(0.5 * attempt, 2.0))

        code = ErrorCode.UPSTREAM_TIMEOUT if isinstance(last_error, httpx.TimeoutException) else ErrorCode.UPSTREAM_ERROR
        raise HCXError(f"HCX 호출 실패 (재시도 {self._settings.hcx_max_retries}회 소진): {last_error}", code=code)

    def _call(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
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
