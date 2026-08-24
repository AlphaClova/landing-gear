# Landing Gear
은퇴 자금의 안전한 착륙을 돕는 연금 의사결정 Agent

## 담당 A (Agent · API · 배포)

FastAPI 기반 Agent 파이프라인: Intent Router → Slot Manager → Tool Router → Composer → Verifier.
B(검색/계산)의 `retrieve_evidence` / `calculate` / `calculate_withdrawal_comparison` /
`query_products`는 `app/agent/tools.py`의 Provider로 연결된다 — `calculate_withdrawal_comparison`은
B의 실제 구현(`app/tools/withdrawal_comparison.py`)에 연결되어 있고, 나머지는 아직 Mock Provider다.
`app/api/dependencies.py`의 `get_tool_router()`에서 주입을 바꾼다.
A·B·C 3자 합의된 필드 매핑·응답 구조는 [`docs/contract.md`](docs/contract.md) 참고.

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

## 담당 B (Data · Retrieval · Rule Engine)

퇴직연금 세제 규칙 계산, 근거 검색(BM25), 상품 조회, claim-evidence 검증을 담당한다.

### 구현 범위

- 퇴직연금 세제(70/60/50%) deterministic rule engine
- topic·account type·effective date 필터를 지원하는 BM25 retriever
- SQLite 기반 상품 조회
- 근거 없는 numeric/factual claim을 차단하는 Claim-Evidence 매핑 가드
- rule 경계값, retrieval 필터링, evidence 매핑 단위 테스트
- 문서 파싱, 인덱스 빌드 검증, 상품 시딩, unsupported claim 평가용 스크립트

### 담당 폴더

- `app/tools/`
- `app/data/`
- `scripts/`
- `tests/unit/rules/`
- `tests/unit/retrieval/`

### 실행

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
PYTHONPATH=. pytest tests/unit/rules tests/unit/retrieval tests/unit/evidence -q
```

### 다음 작업 (담당 B)

1. PDF/DOCX/XLSX 파서를 정식 구현으로 교체하고 표 행을 보존한다.
2. 원본 문서에서 processed chunk 메타데이터(`document_id`, `page`, `effective_from`, `valid_to`)를 채운다.
3. 2025/2026 rule version을 추가하고 버전 혼용을 막는 회귀 테스트를 추가한다.
4. 검증된 소스 수식으로 연금 수령 한도 rule을 구현한다.
5. claim-evidence golden 테스트와 unsupported claim rate 체크를 추가한다.
