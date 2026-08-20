from enum import StrEnum


class ErrorCode(StrEnum):
    """B/C와 공유하는 공식 오류 code. 값 변경 시 공통 계약 문서를 먼저 수정한다."""

    VALIDATION_ERROR = "validation_error"
    OUT_OF_SCOPE = "out_of_scope"
    TOOL_UNAVAILABLE = "tool_unavailable"
    TOOL_ARGUMENT_ERROR = "tool_argument_error"
    UPSTREAM_TIMEOUT = "upstream_timeout"
    UPSTREAM_ERROR = "upstream_error"
    VERIFICATION_FAILED = "verification_failed"
    INTERNAL_ERROR = "internal_error"


_STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.VALIDATION_ERROR: 422,
    ErrorCode.OUT_OF_SCOPE: 200,  # 정상 응답의 type="limitation"으로 처리, HTTP는 200 유지
    ErrorCode.TOOL_UNAVAILABLE: 503,
    ErrorCode.TOOL_ARGUMENT_ERROR: 400,
    ErrorCode.UPSTREAM_TIMEOUT: 504,
    ErrorCode.UPSTREAM_ERROR: 502,
    ErrorCode.VERIFICATION_FAILED: 200,  # limitation 응답으로 축소, 500이 아님
    ErrorCode.INTERNAL_ERROR: 500,
}


class AppError(Exception):
    """Agent 파이프라인 전역에서 사용하는 표준 예외. 항상 code를 가진다."""

    def __init__(self, code: ErrorCode, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.status_code = _STATUS_BY_CODE.get(code, 500)


class ToolError(AppError):
    """B의 Tool 호출 실패(인자 오류, timeout, 예외)를 표준화."""

    def __init__(self, tool_name: str, message: str, *, code: ErrorCode = ErrorCode.TOOL_UNAVAILABLE) -> None:
        super().__init__(code, message, details={"tool_name": tool_name})
        self.tool_name = tool_name


class HCXError(AppError):
    """HyperCLOVA X 호출 실패(timeout/retry 소진/업스트림 오류)를 표준화."""

    def __init__(self, message: str, *, code: ErrorCode = ErrorCode.UPSTREAM_ERROR) -> None:
        super().__init__(code, message)
