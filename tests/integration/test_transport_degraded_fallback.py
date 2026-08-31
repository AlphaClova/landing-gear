import json

import pytest

from app.agent.composer import Composer
from app.agent.tools import ToolResult
from app.agent.verifier import Verifier
from app.api.schemas import CalculationResult, Citation
from app.api.schemas import serialize_retrieved_context
from app.core.errors import ErrorCode, HCXError


class FailingHCX:
    def __init__(self, *, code=ErrorCode.UPSTREAM_ERROR, status=429):
        self.last_attempts = 3
        self.last_success = False
        self.last_timeout_count = int(code == ErrorCode.UPSTREAM_TIMEOUT)
        self.last_attempt_details = [{
            "attempt": 3, "success": False, "upstream_http_status": status,
            "timeout": code == ErrorCode.UPSTREAM_TIMEOUT, "final_exhausted": True,
        }]
        self.code = code

    def complete(self, *_args, **_kwargs):
        raise HCXError("unavailable", code=self.code, attempt_details=self.last_attempt_details)


def evidence_result() -> ToolResult:
    return ToolResult(evidence=[Citation(
        id="doc51-p2", document_id="doc51", page=2, source="provided",
        excerpt="퇴직금 연금수령 시 실제수령연차에 따라 이연퇴직소득세의 70%, 60%, 50%를 납부한다.",
    )])


def test_all_429_with_grounded_plan_returns_deterministic_answer() -> None:
    draft = Composer(FailingHCX()).compose("퇴직금 연금수령 세금을 알려줘", "세제", evidence_result())
    assert draft.degraded is True
    assert draft.degraded_reason == "HCX_RATE_LIMIT"
    assert draft.degraded_fallback == "deterministic_grounded"
    assert draft.message == draft.context.fallback_message
    assert Verifier().check(draft) == []


def test_timeout_with_grounded_plan_falls_back_without_another_hcx_call() -> None:
    draft = Composer(FailingHCX(code=ErrorCode.UPSTREAM_TIMEOUT, status=None)).compose(
        "퇴직금 연금수령 세금을 알려줘", "세제", evidence_result()
    )
    assert draft.degraded_reason == "HCX_TIMEOUT"
    assert draft.hcx_attempts == 3
    assert draft.hcx_success is False


def test_hcx_unavailable_without_grounded_answer_returns_only_limitation() -> None:
    draft = Composer(FailingHCX()).compose("확인되지 않은 사실을 알려줘", "세제", ToolResult())
    assert draft.context.response_mode == "limitation"
    assert draft.message.startswith("[한계]")
    assert "확인되지 않은 내용은 단정할 수 없습니다" in draft.message


def test_degraded_trace_can_preserve_strict_five_field_contract() -> None:
    draft = Composer(FailingHCX()).compose("퇴직금 연금수령 세금을 알려줘", "세제", evidence_result())
    payload = {
        "question_id": "T1", "question": draft.context.question,
        "retrieved_context": serialize_retrieved_context(draft.citations),
        "think_trace": json.dumps({"degraded": draft.degraded, "degraded_reason": draft.degraded_reason}),
        "answer": draft.message,
    }
    assert set(payload) == {"question_id", "question", "retrieved_context", "think_trace", "answer"}
    assert all(isinstance(value, str) for value in payload.values())


def test_degraded_calculation_keeps_matching_rule_result() -> None:
    result = evidence_result()
    result.calculations = [CalculationResult(
        rule_id="RETIRE_TAX_RATE_BY_YEAR", label="annuity_10_years",
        value=7000000, unit="원", formula="10000000 * 0.70",
    )]
    draft = Composer(FailingHCX()).compose("예상 퇴직소득세 1000만원의 연금수령 세금", "세제", result)
    assert draft.calculation_results[0].rule_id == "RETIRE_TAX_RATE_BY_YEAR"
    assert draft.context.claim_plan
    assert Verifier().check(draft) == []
