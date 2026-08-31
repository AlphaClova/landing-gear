from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """A(Agent/API) 담당 소유 설정. 값 추가 시 .env.example도 함께 수정한다."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # HyperCLOVA X
    hcx_api_key: str = ""
    hcx_api_base_url: str = "https://clovastudio.stream.ntruss.com"
    hcx_model: str = "HCX-005"
    hcx_prompt_version: str = "v1"
    hcx_timeout_seconds: float = 8.0
    hcx_max_retries: int = 2
    hcx_total_budget_seconds: float = 10.0

    # 평가 계약
    eval_schema_mode: str = "loose"  # "strict"면 5필드로 직렬화

    # 세션
    session_ttl_seconds: int = 1800

    # 성능 목표 (문서 7장 공통 수치 목표)
    fast_path_timeout_seconds: float = 6.0
    deep_path_timeout_seconds: float = 8.0

    # 로깅
    log_level: str = "INFO"

    # CORS (C 프론트 개발 서버용, 배포 시 실제 origin으로 제한)
    cors_allow_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
