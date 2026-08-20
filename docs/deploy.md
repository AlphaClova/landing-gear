# 배포 / 운영 (A10)

## 실행 명령

```bash
docker build -t landing-gear-agent:latest .
docker run -d --name landing-gear-agent -p 8000:8000 --env-file .env landing-gear-agent:latest
```

## 필수 환경변수

`.env.example` 참고. 배포 전 반드시 확인할 것:

| 변수 | 비워두면 |
| --- | --- |
| `HCX_API_KEY` | mock 모드로 동작 (실 서비스 응답 아님) — 운영 배포 전 필수 설정 |
| `EVAL_SCHEMA_MODE` | `loose` (내부 InternalAnswer 그대로 반환). 평가 서버 연동 시 `strict`로 설정 |
| `CORS_ALLOW_ORIGINS` | `["*"]` — C 프론트 도메인이 확정되면 그 origin으로 제한 |

## NCP 배포 (Container Registry + Server/Container 기준)

1. NCP Container Registry에 로그인 후 이미지 푸시
   ```bash
   docker tag landing-gear-agent:latest <registry>/landing-gear-agent:<tag>
   docker push <registry>/landing-gear-agent:<tag>
   ```
2. 대상 서버(또는 NKS)에서 `.env`를 배포 환경 값으로 채운 뒤 동일한 `docker run` 커맨드로 기동한다.
3. 헬스체크: 로드밸런서/오케스트레이터의 liveness는 `GET /health`, readiness는 `GET /ready`로 연결한다.
4. 배포 직후 `curl <base_url>/health`와 `curl <base_url>/ready` 200 확인 후 트래픽을 전환한다.

## 대표 테스트와 정상 결과

배포 후 아래로 스모크 테스트한다 (문서 8장 대표 통합 질문):

```bash
curl -s -X POST <base_url>/v1/chat -H 'Content-Type: application/json' -d '{
  "session_id": "smoke-1",
  "question": "퇴직금 3억원, 예상 퇴직소득세 2,400만원인데 일시금과 연금 중 무엇이 나을까요?",
  "profile": {"retirement_amount_won": 300000000, "expected_tax_won": 24000000, "plan_type": "DC"}
}'
```

정상 결과: HTTP 200, `type`이 `result` 또는 `limitation`, `request_id`와 `citations`가 채워짐.
(`plan_type`을 빼고 호출하면 `type: "clarification"`이 나오는 것도 정상이다 — 역질문 경로.)

## 장애 발생 시 확인할 로그/파일

- 컨테이너 stdout 구조화 로그: `event=http_request`, `event=app_error`, `event=unhandled_error` 라인의 `request_id`로 추적.
- `GET /ready`의 `hcx_mock_mode`가 `true`인데 운영 환경이면 `HCX_API_KEY` 누락을 의심한다.
- 5xx 응답의 `code` 필드(`app/core/errors.py`의 `ErrorCode`)로 원인 분류: `tool_unavailable`/`tool_argument_error`는 B의 Tool 연동 문제, `upstream_timeout`/`upstream_error`는 HCX 문제.

## 마지막 안정 버전과 되돌리는 방법

이전 태그로 재기동하면 된다 (상태를 갖지 않는 서비스이므로 롤백에 별도 마이그레이션이 없음):

```bash
docker stop landing-gear-agent && docker rm landing-gear-agent
docker run -d --name landing-gear-agent -p 8000:8000 --env-file .env <registry>/landing-gear-agent:<previous-tag>
```

세션 슬롯은 프로세스 메모리에만 있으므로(app/core/session.py) 재기동 시 진행 중이던 역질문 세션은 초기화된다 — 이는 알려진 제약이며, 영속화가 필요해지면 Redis 등으로 `SessionStore` 구현체만 교체한다.
