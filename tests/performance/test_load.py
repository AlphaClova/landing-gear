"""문서 7장 공통 수치 목표: 연속 호출 오류율 1% 미만, 일반 6초/복합 8초 이내.

Mock HCX(응답 즉시 반환) 기준이라 절대 지연시간은 실제 목표를 그대로 검증하지
않는다 — 오케스트레이션 자체가 안정적으로 100회 연속 호출을 처리하는지,
그리고 회귀로 인한 비정상적 지연이 없는지를 잡아내는 것이 목적이다.
실제 HCX 연동 후에는 별도 스테이징 환경에서 e2e 성능 측정을 추가한다.
"""

import time

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_QUESTIONS = [
    "퇴직연금 해지 신청 서류는 뭐가 필요한가요?",
    "확정급여형 제도는 회사가 운용하나요?",
    "퇴직소득세 세율이 어떻게 되나요?",
    "IRP 상품 중에 어떤 펀드가 있나요?",
]


def test_100_consecutive_calls_stay_under_error_and_latency_budget() -> None:
    n = 100
    errors = 0
    durations: list[float] = []

    for i in range(n):
        question = _QUESTIONS[i % len(_QUESTIONS)]
        start = time.monotonic()
        resp = client.post("/v1/chat", json={"session_id": f"perf-{i}", "question": question})
        durations.append(time.monotonic() - start)
        if resp.status_code >= 500:
            errors += 1

    error_rate = errors / n
    durations.sort()
    p95 = durations[int(n * 0.95) - 1]

    assert error_rate < 0.01, f"오류율 {error_rate:.2%} (목표: 1% 미만)"
    assert p95 < 6.0, f"p95 지연 {p95:.2f}s (일반 응답 목표: 6초 이내)"
    assert max(durations) < 8.0, f"최대 지연 {max(durations):.2f}s (복합 응답 목표: 8초 이내)"
