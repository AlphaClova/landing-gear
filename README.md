# Landing Gear

> 은퇴 자금의 안전한 착륙을 돕는 연금 의사결정 AI Agent — 2026 미래에셋증권 AI Festival 제출작

## 1. 프로젝트 소개

Landing Gear는 연금 상품·제도·세제 정보를 기반으로 사용자의 자연어 질문을 이해하고,
관련 근거를 검색·계산한 뒤 근거 기반 답변을 제공하는 연금 의사결정 Agent입니다.

단순 문서 검색에 그치지 않고 질문 유형에 따라 제도·세제·상품·절차를 구분하고,
필요한 경우 deterministic Rule Engine과 Product DB를 함께 활용해 답변을 구성합니다.
답변에 필요한 정보가 부족한 경우 임의로 추정하지 않고 한계를 명시하거나 추가 조건을 질문합니다.

대표 기능인 **인출 의사결정**은 사용자가 입력한 퇴직급여 예상액과 감면 전 기준 퇴직소득세를 바탕으로,
일시금·10년 연금·21년 이상 연금 등 수령 방식별 세액 차이를 Rule Engine으로 계산해 비교합니다.

- 백엔드: FastAPI (Render 배포)
- 프론트엔드: React + TypeScript + Vite (Vercel 배포)
- 생성형 AI 모델: HyperCLOVA X 단독 사용

---

## 2. 배포 및 평가 Endpoint

| 구분 | URL |
| --- | --- |
| **평가 서버 호출용 Endpoint** | **`https://landing-gear.onrender.com/answer`** |
| 프론트엔드 (데모 화면) | `https://landing-gear-nine.vercel.app` |
| Liveness | `https://landing-gear.onrender.com/health` |
| Readiness | `https://landing-gear.onrender.com/ready` |

실제 운영 환경은 **Vercel(프론트엔드) + Render(백엔드, FastAPI)** 구조이며,
평가 클라이언트는 공개된 `/answer` Endpoint를 직접 호출합니다.

평가 서버는 `GET https://landing-gear.onrender.com/answer`를 `question_id`, `question` 쿼리 파라미터로 호출합니다.

```http
GET /answer?question_id={질의 ID}&question={평가 질의}
```

`EVAL_SCHEMA_MODE=strict` 배포 환경에서 응답은 다음 공식 5개 문자열 필드로 고정됩니다.

```json
{
  "question_id": "string",
  "question": "string",
  "retrieved_context": "string",
  "think_trace": "string",
  "answer": "string"
}
```

---

## 3. 주요 기능

- DB / DC / IRP / 연금저축 등 연금 제도 질의
- 세액공제 및 퇴직소득세 관련 세제 질의
- 복합적인 연금 제도·세제 질의
- 연금 수령 및 퇴직급여 관련 절차 안내
- 연금 상품 설명 및 비교
- 사용자 조건 기반 상품 추천
- 퇴직급여 인출 방식(일시금 / 10년 연금 / 21년 이상 연금)별 세액 비교
- BM25 기반 근거 문서 검색
- SQLite 기반 Product Fact 조회
- deterministic Rule Engine 기반 계산
- Claim-Evidence 검증을 통한 hallucination 방지
- 정보 부족 시 clarification / limitation 응답
- 평가용 Public API 제공

---

## 4. 시스템 구조

```text
User Question
     │
     ▼
Intent Router
     │
     ▼
Slot Manager
     │
     ▼
Tool Router
     │
     ├── retrieve_evidence
     │      └── BM25 Retriever
     │
     ├── calculate
     │      └── Rule Engine
     │
     ├── calculate_withdrawal_comparison
     │      └── Withdrawal Comparison
     │
     └── query_products
            └── Product DB
     │
     ▼
Composer
     │
     ▼
HyperCLOVA X
     │
     ▼
Verifier
     │
     ▼
Grounded Answer
```

Agent 파이프라인은 다음과 같이 구성됩니다.

```text
Intent Router → Slot Manager → Tool Router → Composer → Verifier
```

Tool Router는 `app/agent/tools.py`의 Provider 인터페이스를 통해
검색·계산·상품 조회 구현과 연결되며, 아래 네 가지 Tool은 모두 실제 구현으로 연결되어 있습니다.

- `retrieve_evidence` — BM25 근거 문서 검색
- `calculate` — 퇴직소득세 Rule Engine 계산
- `calculate_withdrawal_comparison` — 인출 방식별 세액 비교
- `query_products` — Product Fact DB 조회

프론트엔드는 평가용 `GET /answer`와 화면 대화용 `POST /v1/chat` 두 경로로 동일한 백엔드에 요청하며,
두 경로 모두 위 파이프라인을 공유합니다.

필드 매핑 및 내부 응답 계약은 [`docs/contract.md`](docs/contract.md)를 참고합니다.

---

## 5. 기술 스택

### Backend

- Python
- FastAPI
- Pydantic
- Uvicorn

### Frontend

- React
- TypeScript
- Vite

### AI

- HyperCLOVA X
- Grounded Generation
- Claim-Evidence Verification

> 본 프로젝트의 생성형 AI 모델은 HyperCLOVA X만 사용합니다.

### Data / Retrieval

- BM25 Retrieval
- SQLite
- Structured Product Fact
- Rule Engine

### Document Processing

- PDF: `pdfplumber`
- DOCX: `python-docx`
- XLSX: `openpyxl`
- PPTX: `python-pptx`

---

## 6. 프로젝트 구조

```text
landing-gear/
├── app/
│   ├── agent/
│   │   ├── orchestrator.py
│   │   ├── router.py
│   │   ├── tools.py
│   │   ├── composer.py
│   │   ├── verifier.py
│   │   └── ...
│   │
│   ├── api/
│   │   ├── dependencies.py
│   │   ├── schemas.py
│   │   └── ...
│   │
│   ├── tools/
│   │   ├── retriever.py
│   │   ├── withdrawal_comparison.py
│   │   └── ...
│   │
│   ├── data/
│   └── main.py
│
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   └── features/
│   └── package.json
│
├── scripts/
├── tests/
├── docs/
│   ├── contract.md
│   ├── deploy.md
│   └── submission/
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

---

## 7. 로컬 실행 방법

### 7.1 Backend

```bash
git clone <REPOSITORY_URL>
cd landing-gear

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements-dev.txt   # 테스트까지 포함, requirements.txt를 포함함

cp .env.example .env
```

주요 환경변수는 다음과 같습니다.

| 변수 | 설명 | 기본값 / 예시 |
| --- | --- | --- |
| `HCX_API_KEY` | HyperCLOVA X API 인증 Key | 직접 설정 |
| `HCX_API_BASE_URL` | HyperCLOVA X API Base URL | `https://clovastudio.stream.ntruss.com` |
| `HCX_MODEL` | 사용할 HyperCLOVA X 모델 | `HCX-005` |
| `HCX_PROMPT_VERSION` | Prompt 버전 | `v1` |
| `HCX_TIMEOUT_SECONDS` | HCX 요청 timeout | `8.0` |
| `HCX_MAX_RETRIES` | HCX 최대 재시도 횟수 | `2` |
| `EVAL_SCHEMA_MODE` | 평가 API 응답 스키마 모드 | `strict` |
| `SESSION_TTL_SECONDS` | 세션 유지 시간(초) | `1800` |
| `FAST_PATH_TIMEOUT_SECONDS` | Fast Path 제한 시간(초) | `6.0` |
| `DEEP_PATH_TIMEOUT_SECONDS` | Deep Path 제한 시간(초) | `8.0` |
| `LOG_LEVEL` | 로그 레벨 | `INFO` |
| `CORS_ALLOW_ORIGINS` | 허용할 Frontend Origin 목록 | `["*"]` |

`HCX_API_KEY`와 같은 민감한 인증 정보는 Repository에 포함하지 않으며, 비워두면 mock 모드로 동작합니다.

```bash
uvicorn app.main:app --reload
```

실행 후 `http://localhost:8000`에서 확인할 수 있습니다.

### 7.2 Frontend

```bash
cd frontend
npm install
cp .env.example .env.local   # VITE_API_BASE_URL을 백엔드 주소로 설정
npm run dev
```

기본 개발 환경에서는 `http://localhost:5173`에서 접속할 수 있습니다.

---

## 8. 주요 API

### 8.1 평가용 API

```http
GET /answer
```

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `question_id` | string | 평가 질문 ID |
| `question` | string | 평가 질의 원문 |

```bash
curl -G "https://landing-gear.onrender.com/answer" \
  --data-urlencode "question_id=Q-001" \
  --data-urlencode "question=DB형과 DC형의 차이는 무엇인가요?"
```

평가 API는 다음 5개 필드를 문자열로 반환합니다.

```json
{
  "question_id": "Q-001",
  "question": "DB형과 DC형의 차이는 무엇인가요?",
  "retrieved_context": "답변 생성에 사용된 검색 근거",
  "think_trace": "질의 분류 및 도구 사용 결과",
  "answer": "최종 답변"
}
```

### 8.2 Chat API

```http
POST /v1/chat
```

프론트엔드에서 세션 기반 질의(연금 상담, 인출 의사결정)를 처리하기 위해 사용하는 API입니다.

### 8.3 Health / Readiness

```http
GET /health   # liveness
GET /ready    # readiness — 실제 요청 처리 준비 상태 확인
```

---

## 9. Grounding 및 안전 원칙

### 9.1 Grounding 원칙

1. **근거 문서 우선** — 답변의 사실·숫자·비교는 검색된 근거 또는 deterministic Tool 결과를 사용합니다.
2. **근거 없는 단정 금지** — Context에서 확인할 수 없는 정보는 사실처럼 생성하지 않습니다.
3. **조건 없는 상품 추천 금지** — 계좌 유형, 투자기간, 감내 가능한 위험 등 필요한 조건을 먼저 확인합니다.
4. **질문 범위와 다른 근거 제거** — 예를 들어 연금저축 질문에 퇴직연금 근거를 임의로 대체해 사용하지 않습니다.
5. **정보 부족 시 한계 안내** — 직접 근거가 없는 경우 `[한계] 제공된 근거만으로 해당 내용을 확정할 수 없습니다.`와 같은 방식으로 한계를 명시합니다.

### 9.2 Verifier 검증 항목

최종 답변 반환 전 Verifier가 다음 항목을 검증하며, 실패 시 안전한 답변으로 repair 또는 fallback합니다.

- 숫자와 근거 일치 여부
- factual claim의 근거 존재 여부
- 질문과 evidence의 scope 일치 여부
- 세금 관계의 근거 일치 여부
- 상품명 / 비용 / 위험등급 등 상품 Fact 일치 여부
- 근거 없는 확정적 추천 여부(예: "무조건", "최고의" 등 단정 표현 차단)

---

## 10. 테스트

### 10.1 Backend

```bash
pytest -q
```

특정 Rule / Retrieval 단위 테스트만 실행:

```bash
PYTHONPATH=. pytest tests/unit/rules tests/unit/retrieval tests/unit/evidence -q
```

주요 테스트 범위: Agent routing, Pension scope, API contract, Retrieval, Rule Engine, Product search,
Claim-Evidence mapping, Tax relation grounding, Product comparison, Safety / limitation, Regression.

### 10.2 Frontend

```bash
cd frontend
npm run lint
npx vitest run
npm run build
```

---

## 11. Docker 및 배포

### 11.1 이미지 빌드 및 실행

```bash
docker build -t landing-gear-agent .
docker run --rm -p 8000:8000 --env-file .env landing-gear-agent
```

```bash
curl http://localhost:8000/health

curl -G "http://localhost:8000/answer" \
  --data-urlencode "question_id=Q-001" \
  --data-urlencode "question=DB형과 DC형의 차이는 무엇인가요?"
```

### 11.2 배포 구조

평가 서버는 Public Network에서 접근 가능한 API 형태로 배포되어 있으며, `/answer` Endpoint는 항상 활성화되어 있습니다.

- 백엔드: **Render**에 Docker 컨테이너로 배포 (`https://landing-gear.onrender.com`)
- 프론트엔드: **Vercel**에 배포 (`https://landing-gear-nine.vercel.app`)
- 프론트엔드의 실제 배포 오리진은 백엔드 `CORS_ALLOW_ORIGINS` 허용 목록에 등록되어 있습니다.

상세 배포 및 장애 대응 절차는 [`docs/deploy.md`](docs/deploy.md)를 참고합니다.

---

## 12. 기술제안서

본 프로젝트의 상세 기술 제안 내용은 다음 문서에 정리되어 있습니다.

[Landing Gear 기술제안서](docs/submission/Landing_Gear_기술제안서.pdf)

---

## License / Data

본 프로젝트는 2026 미래에셋증권 AI Festival 연금 Agent 과제를 위해 개발되었습니다.
제공 데이터는 대회 과제 수행 목적에 맞게 사용합니다.
