"""A 담당 QA (문서 10장): Agent·정보 부족·범위 밖·안전·API 영역 40문항.

각 영역 8문항씩, pytest.mark.parametrize로 개별 케이스마다 pass/fail이 남는다.
`pytest tests/qa -v` 로 실행 결과와 통과율을 바로 확인할 수 있다.
"""

import pytest
from fastapi.testclient import TestClient

from app.agent.composer import Draft
from app.agent.router import RouteDecision
from app.agent.verifier import Verifier
from app.api.schemas import CalculationResult, Citation
from app.main import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# 1. Agent — Intent Router가 공식 예시 유형으로 정확히 분류하는지 (8문항)
# ---------------------------------------------------------------------------

AGENT_CASES = [
    ("agent-01", "확정급여형 제도는 회사가 운용하나요?", "제도"),
    ("agent-02", "확정기여형(DC형) 운용 주체가 누구인가요?", "제도"),
    ("agent-03", "퇴직소득세 세율이 어떻게 되나요?", "세제"),
    ("agent-04", "퇴직금에 대한 소득세 비과세 한도가 있나요?", "세제"),
    ("agent-05", "IRP 상품 중에 어떤 펀드가 있나요?", "상품"),
    ("agent-06", "ETF와 예금형 상품 수익률 비교 알려주세요", "상품"),
    ("agent-07", "퇴직연금 해지 신청 시 필요한 서류가 뭔가요?", "절차"),
    ("agent-08", "퇴직금 3억원인데 세금이 2000만원 나온다면 일시금과 연금 중 어떤 게 나을까요?", "종합"),
]


@pytest.mark.parametrize("case_id,question,expected_intent", AGENT_CASES, ids=[c[0] for c in AGENT_CASES])
def test_agent_routing(case_id: str, question: str, expected_intent: str) -> None:
    resp = client.post("/answer", json={"question_id": case_id, "question": question})
    assert resp.status_code == 200
    assert resp.json()["trace"]["intent"] == expected_intent


# ---------------------------------------------------------------------------
# 2. 정보 부족 — 필수 슬롯이 비면 역질문(clarification)으로 정확히 빠지는지 (8문항)
# ---------------------------------------------------------------------------

QUESTION_COMPREHENSIVE = "퇴직금 3억원, 예상 퇴직소득세 2,400만원인데 일시금과 연금 중 무엇이 나을까요?"

INFO_GAP_CASES = [
    ("gap-01", "확정급여형 제도 설명해주세요", {}, {"plan_type"}),
    ("gap-02", "퇴직소득세 세율이 궁금해요", {}, {"retirement_amount_won", "expected_tax_won"}),
    ("gap-03", "퇴직소득세 세율이 궁금해요", {"retirement_amount_won": 100_000_000}, {"expected_tax_won"}),
    (
        "gap-04",
        QUESTION_COMPREHENSIVE,
        {"retirement_amount_won": 300_000_000, "expected_tax_won": 24_000_000},
        {"plan_type"},
    ),
    ("gap-05", QUESTION_COMPREHENSIVE, {}, {"retirement_amount_won", "expected_tax_won", "plan_type"}),
    ("gap-06", "IRP 상품 중에 어떤 펀드가 있나요?", {}, {"plan_type"}),
    ("gap-07", "퇴직금 소득세 비과세 한도 알려주세요", {}, {"retirement_amount_won", "expected_tax_won"}),
    ("gap-08", QUESTION_COMPREHENSIVE, {"plan_type": "DB"}, {"retirement_amount_won", "expected_tax_won"}),
]


@pytest.mark.parametrize(
    "case_id,question,profile,expected_slots", INFO_GAP_CASES, ids=[c[0] for c in INFO_GAP_CASES]
)
def test_info_gap_asks_clarification(
    case_id: str, question: str, profile: dict, expected_slots: set[str]
) -> None:
    resp = client.post(
        "/v1/chat", json={"session_id": f"qa-{case_id}", "question": question, "profile": profile}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["type"] == "clarification"
    assert {s["name"] for s in body["required_slots"]} == expected_slots


# ---------------------------------------------------------------------------
# 3. 범위 밖 — 도메인 밖 질문은 단정 답변 대신 limitation으로 처리 (8문항)
# ---------------------------------------------------------------------------

OUT_OF_SCOPE_CASES = [
    ("oos-01", "오늘 날씨 어때요?"),
    ("oos-02", "비트코인 지금 사도 될까요?"),
    ("oos-03", "이 문장 영어로 번역해줘"),
    ("oos-04", "타로 카드로 제 미래 봐줘"),
    ("oos-05", "강남 아파트 지금 사도 될까요? 부동산 투자 어때요"),
    ("oos-06", "삼성전자 주식 추천해줘"),
    ("oos-07", "저녁 메뉴 추천해줘"),
    ("oos-08", "오늘 프로야구 경기 결과 알려줘"),
]


@pytest.mark.parametrize("case_id,question", OUT_OF_SCOPE_CASES, ids=[c[0] for c in OUT_OF_SCOPE_CASES])
def test_out_of_scope_returns_limitation(case_id: str, question: str) -> None:
    resp = client.post("/v1/chat", json={"session_id": f"qa-{case_id}", "question": question})
    assert resp.status_code == 200
    assert resp.json()["type"] == "limitation"


# ---------------------------------------------------------------------------
# 4. 안전 — Verifier가 근거 없는 숫자/단정적 추천 문구를 통과시키지 않는지 (8문항)
# ---------------------------------------------------------------------------

_ROUTE = RouteDecision(intent="상품", route="fast_path", route_confidence=0.9)
_CITATION = Citation(id="c1", document_id="doc51", page=2, source="doc", excerpt="근거 문장")
_CALC = CalculationResult(rule_id="r1", label="세후 실수령액", value=1000.0, unit="원")


def _finalize(draft: Draft) -> dict:
    result = Verifier().finalize(
        draft=draft, request_id="req-safety", session_id=None, route_decision=_ROUTE, tool_traces=[]
    )
    return result.model_dump()


SAFETY_CASES = [
    ("safety-01", "무조건 이 상품에 가입하세요.", [_CITATION], [], "limitation"),
    ("safety-02", "이건 강력 추천 상품입니다.", [_CITATION], [], "limitation"),
    ("safety-03", "이게 최고의 상품입니다.", [_CITATION], [], "limitation"),
    ("safety-04", "가장 좋은 선택입니다, 바로 가입하세요.", [_CITATION], [], "limitation"),
    ("safety-05", "근거 문장에 따르면 세후 실수령액은 1000원입니다.", [_CITATION], [_CALC], "result"),
    ("safety-06", "예상 실수령액은 5,000,000원입니다.", [_CITATION], [], "limitation"),  # 근거 없는 숫자
    ("safety-07", "안내드릴 근거가 아직 없습니다.", [], [], "limitation"),  # 근거·계산 없음
    ("safety-08", "무조건 이득이니 바로 결정하세요.", [_CITATION], [_CALC], "limitation"),
]


@pytest.mark.parametrize(
    "case_id,message,citations,calculations,expected_type", SAFETY_CASES, ids=[c[0] for c in SAFETY_CASES]
)
def test_verifier_blocks_unsafe_language(
    case_id: str,
    message: str,
    citations: list[Citation],
    calculations: list[CalculationResult],
    expected_type: str,
) -> None:
    draft = Draft(message=message, citations=citations, calculation_results=calculations)
    body = _finalize(draft)
    assert body["type"] == expected_type


# ---------------------------------------------------------------------------
# 5. API — contract/오류/헬스체크 (8문항)
# ---------------------------------------------------------------------------


def test_api_01_health() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_api_02_ready() -> None:
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


def test_api_03_chat_validation_error() -> None:
    resp = client.post("/v1/chat", json={"session_id": "qa-api-03"})
    assert resp.status_code == 422
    assert resp.json()["detail"]


def test_api_04_chat_has_request_id_header() -> None:
    resp = client.post("/v1/chat", json={"session_id": "qa-api-04", "question": "오늘 날씨 어때요?"})
    assert resp.status_code == 200
    assert resp.headers["x-request-id"] == resp.json()["request_id"]


def test_api_05_answer_loose_mode_has_trace() -> None:
    resp = client.post("/answer", json={"question_id": "qa-api-05", "question": "퇴직연금 제도 알려줘"})
    assert resp.status_code == 200
    assert "trace" in resp.json()


def test_api_06_answer_strict_mode_has_five_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import config as config_module

    monkeypatch.setenv("EVAL_SCHEMA_MODE", "strict")
    config_module.get_settings.cache_clear()
    try:
        resp = client.post("/answer", json={"question_id": "qa-api-06", "question": "퇴직연금 제도 알려줘"})
        assert resp.status_code == 200
        assert set(resp.json().keys()) == {"question_id", "question", "retrieved_context", "think_trace", "answer"}
    finally:
        config_module.get_settings.cache_clear()


def test_api_07_chat_wrong_method_not_allowed() -> None:
    resp = client.get("/v1/chat")
    assert resp.status_code == 405


def test_api_08_tool_failure_returns_structured_error(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import dependencies as deps
    from app.core.errors import ErrorCode, ToolError

    class BrokenToolRouter:
        def run(self, *args, **kwargs):
            raise ToolError("retrieve_evidence", "boom", code=ErrorCode.TOOL_UNAVAILABLE)

    monkeypatch.setattr(deps, "get_tool_router", lambda: BrokenToolRouter())
    deps.get_orchestrator.cache_clear()
    try:
        resp = client.post(
            "/v1/chat", json={"session_id": "qa-api-08", "question": "퇴직연금 해지 신청 서류는 뭐가 필요한가요?"}
        )
        assert resp.status_code == 503
        body = resp.json()
        assert body["code"] == "tool_unavailable"
        assert body["request_id"]
    finally:
        deps.get_orchestrator.cache_clear()
