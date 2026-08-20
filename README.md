# Landing Gear
은퇴 자금의 안전한 착륙을 돕는 연금 의사결정 Agent

## 담당 A (Agent · API · 배포)

FastAPI 기반 Agent 파이프라인: Intent Router → Slot Manager → Tool Router → Composer → Verifier.
B(검색/계산)의 `retrieve_evidence` / `calculate` / `query_products`는 `app/agent/tools.py`의
Mock Provider로 대체되어 있다 — B가 실제 구현을 넘기면 `app/api/dependencies.py`의
`get_tool_router()`에서 주입 교체한다.

### 실행

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env   # HCX_API_KEY 비워두면 mock 모드로 동작
uvicorn app.main:app --reload
```

### 테스트

```bash
pytest                    # contract + integration + qa(40문항) + performance, 총 52개
pytest tests/qa -v        # A 담당 QA 평가셋만: Agent·정보 부족·범위 밖·안전·API 8문항×5영역
pytest tests/performance  # 연속 100회 호출 오류율<1%, p95<6초, max<8초 확인
```

PR을 올리면 `.github/workflows/ci.yml`이 전체 테스트와 Docker 빌드를 자동 실행한다.

### 주요 엔드포인트

| 경로 | 설명 |
| --- | --- |
| `POST /v1/chat` | 세션 유지, C(프론트)가 호출 |
| `POST /answer` | 평가 서버 호출용. `EVAL_SCHEMA_MODE=strict`면 공식 5필드로 응답 |
| `GET /health` | liveness |
| `GET /ready` | readiness |

### Docker

```bash
docker build -t landing-gear-agent .
docker run --rm -p 8000:8000 --env-file .env landing-gear-agent
```

NCP 배포, 장애 대응, 롤백 절차는 [`docs/deploy.md`](docs/deploy.md) 참고.

