import logging
import sys
from typing import Any


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if root.handlers:
        return  # 중복 설정 방지 (uvicorn --reload 등)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":%(message)r}',
        )
    )
    root.addHandler(handler)
    root.setLevel(level.upper())


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_context(logger: logging.Logger, event: str, **fields: Any) -> None:
    """request_id 등 구조화 필드를 포함한 단일 라인 로그."""
    payload = " ".join(f"{k}={v!r}" for k, v in fields.items())
    logger.info("%s %s", event, payload)
