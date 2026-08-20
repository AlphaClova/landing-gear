import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router as api_router
from app.api.schemas import ErrorResponse
from app.core.config import get_settings
from app.core.errors import AppError, ErrorCode
from app.core.logging import configure_logging, get_logger, log_context

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)

app = FastAPI(title="Landing Gear Agent API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request.state.request_id = f"req_{uuid.uuid4().hex[:20]}"
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = (time.monotonic() - start) * 1000
    response.headers["X-Request-Id"] = request.state.request_id
    log_context(
        logger,
        "http_request",
        request_id=request.state.request_id,
        path=request.url.path,
        status=response.status_code,
        duration_ms=round(duration_ms, 1),
    )
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    log_context(logger, "app_error", request_id=request_id, code=exc.code, message=exc.message)
    body = ErrorResponse(code=exc.code, message=exc.message, request_id=request_id)
    return JSONResponse(status_code=exc.status_code, content=body.model_dump(mode="json"))


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    log_context(logger, "unhandled_error", request_id=request_id, error=repr(exc))
    body = ErrorResponse(code=ErrorCode.INTERNAL_ERROR, message="내부 오류가 발생했습니다.", request_id=request_id)
    return JSONResponse(status_code=500, content=body.model_dump(mode="json"))
