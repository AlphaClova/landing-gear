# Landing Gear

> 은퇴 자금의 안전한 착륙을 돕는 연금 의사결정 AI Agent

Landing Gear는 연금 상품·제도·세제 정보를 기반으로 사용자의 자연어 질문을 이해하고,
관련 근거를 검색·계산한 뒤 근거 기반 답변을 제공하는 연금 의사결정 Agent입니다.

단순 문서 검색에 그치지 않고 질문 유형에 따라
제도·세제·상품·절차를 구분하고,
필요한 경우 Rule Engine과 Product DB를 함께 활용합니다.

답변에 필요한 정보가 부족한 경우 임의로 추정하지 않고
한계를 명시하거나 추가 조건을 질문합니다.

---

## 주요 기능

- DB / DC / IRP / 연금저축 등 연금 제도 질의
- 세액공제 및 퇴직소득세 관련 세제 질의
- 복합적인 연금 제도·세제 질의
- 연금 수령 및 퇴직급여 관련 절차 안내
- 연금 상품 설명 및 비교
- 사용자 조건 기반 상품 추천
- BM25 기반 근거 문서 검색
- SQLite 기반 Product Fact 조회
- deterministic Rule Engine 기반 계산
- Claim-Evidence 검증을 통한 hallucination 방지
- 정보 부족 시 clarification / limitation 응답
- 평가용 Public API 제공

---

## 시스템 구조

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
Intent Router
→ Slot Manager
→ Tool Router
→ Composer
→ Verifier
```

Tool Router는 `app/agent/tools.py`의 Provider 인터페이스를 통해
검색·계산·상품 조회 구현과 연결됩니다.

주요 Tool:

- `retrieve_evidence`
- `calculate`
- `calculate_withdrawal_comparison`
- `query_products`

필드 매핑 및 내부 응답 계약은
[`docs/contract.md`](docs/contract.md)를 참고합니다.

---

## 기술 스택

### Backend

- Python
- FastAPI
- Pydantic
- Uvicorn

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

## 프로젝트 구조

```text
landing-gear/
├── app/
│   ├── agent/
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
├── scripts/
├── tests/
├── docs/
│   ├── contract.md
│   └── deploy.md
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

---

# 실행 환경

## 권장 환경

- Python 3.x
- pip
- Docker (선택)

---

## 1. Repository Clone

```bash
git clone <REPOSITORY_URL>
cd landing-gear
```

---

## 2. Python 가상환경 구성

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows:

```bash
.venv\Scripts\activate
```

---

## 3. Dependency 설치

애플리케이션 실행에 필요한 dependency를 설치합니다.

```bash
pip install -r requirements.txt
```

테스트까지 실행하려면 개발·테스트 dependency를 설치합니다.

```bash
pip install -r requirements-dev.txt
```

`requirements-dev.txt`는 `requirements.txt`를 포함하며 `pytest` 등 테스트용 dependency를 추가로 설치합니다.

---

## 4. 환경변수 설정

환경변수 예시 파일을 복사합니다.

```bash
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

평가 환경에서는 `/answer`가 공식 5개 필드로 응답하도록 다음 설정을 사용합니다.

```env
EVAL_SCHEMA_MODE=strict
```

`HCX_API_KEY`와 같은 민감한 인증 정보는 Repository에 포함하지 않습니다.

---
## 5. Backend 실행

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

개발 환경에서는:

```bash
uvicorn app.main:app --reload
```

실행 후:

```text
http://localhost:8000
```
## 6. Frontend 실행

Frontend 디렉터리로 이동합니다.

```bash
cd frontend
```

dependency를 설치합니다.

```bash
npm install
```

환경변수를 설정합니다.

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_CHAT_API_MODE=http
VITE_USE_MOCK_API=false
```

개발 서버를 실행합니다.

```bash
npm run dev
```

기본 개발 환경에서는 다음 주소에서 접속할 수 있습니다.

```text
http://localhost:5173
```

---

# 주요 API

## 1. 평가용 API

```http
GET /answer
```

### Query Parameters

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `question_id` | string | 평가 질문 ID |
| `question` | string | 평가 질의 원문 |

### cURL 예시

```bash
curl -G "http://localhost:8000/answer" \
  --data-urlencode "question_id=Q-001" \
  --data-urlencode "question=DB형과 DC형의 차이는 무엇인가요?"
```

### Response

평가 API는 다음 5개 필드를 반환합니다.

```json
{
  "question_id": "Q-001",
  "question": "DB형과 DC형의 차이는 무엇인가요?",
  "retrieved_context": "답변 생성에 사용된 검색 근거",
  "think_trace": "질의 분류 및 도구 사용 결과",
  "answer": "최종 답변"
}
```

각 top-level 필드는 문자열로 반환됩니다.

---

## 2. Chat API

```http
POST /v1/chat
```

프론트엔드에서 세션 기반 질의를 처리하기 위해 사용하는 API입니다.

---

## 3. Health Check

```http
GET /health
```

애플리케이션 liveness를 확인합니다.

---

## 4. Readiness Check

```http
GET /ready
```

서비스가 실제 요청을 처리할 준비가 되었는지 확인합니다.

---

# Agent 동작 방식

## 1. Intent Routing

사용자 질문을 다음과 같은 유형으로 분류합니다.

- 제도
- 세제
- 상품
- 절차
- 종합 질의
- 범위 밖 질문

예를 들어 `연금`이라는 일반 표현과 다음 구체적인 연금 유형을 구분합니다.

- 퇴직연금
- IRP
- 연금저축
- 국민연금

질문의 범위가 불명확하면 특정 연금 제도로 임의 해석하지 않고
추가 조건을 질문합니다.

---

## 2. Evidence Retrieval

BM25 기반 검색으로 질문과 관련된 문서를 조회합니다.

검색 시 다음 메타데이터를 활용합니다.

- `document_id`
- `page`
- topic
- account type
- effective date

질문 범위와 다른 문서는 최종 공개 근거에서 제거합니다.

---

## 3. Rule Engine

문서 검색만으로 안정적으로 계산하기 어려운 규칙성 수치는
deterministic Rule Engine에서 처리합니다.

예:

- 연금 수령 연차별 퇴직소득세 적용 비율
- 세제 관련 계산
- 인출 방식 비교

Rule 결과는 LLM이 임의 계산하지 않고
Tool 결과를 기반으로 답변에 반영합니다.

---

## 4. Product Search

Product Fact DB를 통해 상품 정보를 조회합니다.

주요 속성:

- 상품명
- 자산유형
- 위험등급
- 가입 가능 계좌
- 투자전략
- 판매 클래스
- 비용·보수
- 기타 확인 가능한 상품 Fact

Product Fact에 없는 값은 임의 생성하지 않습니다.

---

## 5. Composer

질문과 Tool 결과를 기반으로 답변 구조를 생성합니다.

직접 근거가 확인된 claim은
해당 evidence와 연결해 구성합니다.

근거가 부족한 경우 임의 사실을 추가하지 않고
limitation 또는 clarification을 생성합니다.

---

## 6. Verifier

최종 답변 전에 다음 항목을 검증합니다.

- 숫자와 근거 일치 여부
- factual claim의 근거 존재 여부
- 질문과 evidence의 scope 일치 여부
- 세금 관계의 근거 일치 여부
- 상품명 / 비용 / 위험등급 등 상품 Fact 일치 여부
- 근거 없는 확정적 추천 여부

검증에 실패하면 안전한 답변으로 repair 또는 fallback합니다.

---

# Grounding 원칙

Landing Gear는 다음 원칙으로 답변을 생성합니다.

### 1. 근거 문서 우선

답변의 사실·숫자·비교는 검색된 근거 또는 deterministic Tool 결과를 사용합니다.

### 2. 근거 없는 단정 금지

Context에서 확인할 수 없는 정보는 사실처럼 생성하지 않습니다.

### 3. 조건 없는 상품 추천 금지

계좌 유형, 투자기간, 감내 가능한 위험 등 필요한 조건을 먼저 확인합니다.

### 4. 질문 범위와 다른 근거 제거

예를 들어 연금저축 질문에
퇴직연금 근거를 임의로 대체해 사용하지 않습니다.

### 5. 정보 부족 시 한계 안내

직접 근거가 없는 경우:

```text
[한계] 제공된 근거만으로 해당 내용을 확정할 수 없습니다.
```

와 같은 방식으로 정보 한계를 명시합니다.

---

# 테스트

전체 테스트:

```bash
pytest -q
```

주요 테스트 범위:

- Agent routing
- Pension scope
- API contract
- Retrieval
- Rule Engine
- Product search
- Claim-Evidence mapping
- Tax relation grounding
- Product comparison
- Safety / limitation
- Regression

특정 Rule / Retrieval 테스트:

```bash
PYTHONPATH=. pytest \
  tests/unit/rules \
  tests/unit/retrieval \
  tests/unit/evidence \
  -q
```

---

# Docker

## 이미지 빌드

```bash
docker build -t landing-gear-agent .
```

## 실행

```bash
docker run --rm \
  -p 8000:8000 \
  --env-file .env \
  landing-gear-agent
```

실행 확인:

```bash
curl http://localhost:8000/health
```

평가 API 확인:

```bash
curl -G "http://localhost:8000/answer" \
  --data-urlencode "question_id=Q-001" \
  --data-urlencode "question=DB형과 DC형의 차이는 무엇인가요?"
```

---

# CI

Pull Request 생성 시 GitHub Actions를 통해 다음 항목을 검증합니다.

- Python test
- API contract
- Docker build

CI 설정:

```text
.github/workflows/ci.yml
```

---

# 배포

평가 서버는 Public Network에서 접근 가능한 API 형태로 배포합니다.

배포 환경에서는 `/answer` endpoint가 항상 활성화되어 있어야 합니다.

상세 배포 및 장애 대응 절차는 다음 문서를 참고합니다.

[`docs/deploy.md`](docs/deploy.md)

---

# 평가 API Contract

평가 서버는 다음 형식을 따릅니다.

### Request

```http
GET /answer?question_id={id}&question={question}
```

### Response

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

# 팀 역할

### Agent / API / Deployment

- Agent orchestration
- FastAPI
- HyperCLOVA X 연동
- API contract
- deployment

### Data / Retrieval / Rule Engine

- document preprocessing
- BM25 retrieval
- Rule Engine
- Product Fact DB
- evidence validation

### Frontend / UX

- 사용자 질의 UI
- 근거 문서 표시
- 상품 및 의사결정 결과 시각화
- API 연동

---

# License / Data

본 프로젝트는 2026 미래에셋증권 AI Festival 연금 Agent 과제를 위해 개발되었습니다.

제공 데이터는 대회 과제 수행 목적에 맞게 사용합니다.
