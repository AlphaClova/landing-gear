import json
import re

from fastapi.testclient import TestClient

from app.agent.product_evidence import is_prospectus_citation
from app.agent.router import IntentRouter
from app.agent.slots import SlotManager
from app.agent.tools import BEvidenceProvider, BProductCatalog, BRuleEngine, ToolRouter
from app.core.query_normalization import (
    meaningful_query_tokens,
    normalize_product_horizon_terms,
)
from app.main import app
from app.tools.retriever import RETRIEVAL_MIN_QUERY_COVERAGE, RETRIEVAL_MIN_SCORE
from tests.contract.test_public_evidence_pruning_gates import C1, C2, C3, C4, C5, _public
from tests.unit.test_content_p0_policies import grounded
from tests.unit.test_phase_c2_g072_fee_mapping import G072
from tests.unit.test_phase_c3_g081_product_boundary import G081
from tests.unit.test_phase_c7_g075_product_availability import G075


BROWSER_C4 = "솔로몬 국공채 단기형과 중장기형, 장기형은 어떤 차이가 있나요?"
G004 = C4
client = TestClient(app)


def _run(question: str):
    decision = IntentRouter().classify(question)
    result = ToolRouter(BEvidenceProvider(), BRuleEngine(), BProductCatalog()).run(
        decision.intent,
        SlotManager.extract(question),
        question=question,
    )
    return decision, result


def _names(result) -> list[str]:
    return [str(item.get("product_name") or "") for item in result.products]


def test_horizon_normalization_is_product_context_only() -> None:
    assert ToolRouter._requested_product_periods(BROWSER_C4) == ["단기", "중장기", "장기"]
    tokens = meaningful_query_tokens(BROWSER_C4)
    assert "단기형" not in tokens and "중장기형" not in tokens and "장기형" not in tokens
    assert {"단기", "중장기", "장기"}.issubset(set(tokens))
    generic = "단기형 전략과 장기형 전략은 어떻게 다른가요?"
    assert normalize_product_horizon_terms(generic) == generic
    assert "단기형" in meaningful_query_tokens(generic)


def test_browser_c4_attaches_matched_prospectus_without_ultrashort() -> None:
    decision, result = _run(BROWSER_C4)
    assert decision.intent == "상품"
    assert [trace.tool_name for trace in result.traces] == ["query_products", "retrieve_evidence"]
    names = _names(result)
    assert len(names) == 3
    assert any("단기국공채" in name and "초단기" not in name for name in names)
    assert any("중장기국공채" in name for name in names)
    assert any("장기국공채" in name and "중장기" not in name for name in names)
    assert all("초단기" not in name for name in names)
    prospectus = [item for item in result.evidence if is_prospectus_citation(item)]
    assert len(prospectus) >= 3
    assert all("초단기" not in item.excerpt for item in prospectus)
    _, _, _, context = grounded(BROWSER_C4)
    message = context.fallback_message
    assert "0.66" in message and "0.43" in message and "0.36" in message
    assert "투자전략" in message
    assert "90%" in message and "80%" in message
    assert "총보수·비용 비율" in message
    assert not re.search(r"듀레이션이\s", message)
    assert "금리 민감도가" not in message


def test_browser_c4_public_answer_via_get() -> None:
    response = client.get("/answer", params={"question_id": "C8-C4", "question": BROWSER_C4})
    assert response.status_code == 200
    body = response.json()
    think = json.loads(body["think_trace"])
    assert think["intent"] == "상품"
    assert think["tools"] == ["query_products", "retrieve_evidence"]
    answer = body["answer"]
    context = body["retrieved_context"]
    assert "초단기" not in answer and "초단기" not in context
    assert "0.66" in answer and "0.43" in answer and "0.36" in answer
    assert "투자전략" in answer
    assert "총보수·비용 비율" in answer
    assert context.count("[DOC r2_") >= 3
    assert not re.search(r"듀레이션이\s", answer)


def test_g004_golden_comparison_is_unchanged() -> None:
    _, _, result, context = grounded(G004)
    names = _names(result)
    assert len(names) == 3
    assert all("초단기" not in name for name in names)
    message = context.fallback_message
    assert "0.66" in message and "0.43" in message and "0.36" in message
    assert "투자전략" in message
    assert "초단기" not in message
    internal, public = _public(G004, "G004")
    assert "초단기" not in public.retrieved_context
    assert public.answer == internal.message
    assert "0.66" in public.answer


def test_single_horizon_paraphrase_does_not_expand_to_three_products() -> None:
    cases = {
        "솔로몬 단기형 상품 알려줘": "단기국공채",
        "솔로몬 중장기형 상품 알려줘": "중장기국공채",
        "솔로몬 장기형 상품 알려줘": "장기국공채",
    }
    for question, expected in cases.items():
        _, result = _run(question)
        names = _names(result)
        assert len(names) == 1, question
        assert expected in names[0]
        assert "초단기" not in names[0]
        if expected == "장기국공채":
            assert "중장기" not in names[0]
        if expected == "단기국공채":
            assert "초단기" not in names[0]


def test_generic_horizon_question_does_not_attach_solomon_prospectus() -> None:
    question = "단기형과 장기형의 일반적인 차이가 뭐야?"
    _, result = _run(question)
    assert result.products == []
    assert all("r2_kr5153420063" not in item.document_id for item in result.evidence)
    assert all("r2_kr5153420079" not in item.document_id for item in result.evidence)
    assert all("r2_kr5153420105" not in item.document_id for item in result.evidence)
    assert all("솔로몬" not in item.excerpt for item in result.evidence)


def test_c8_does_not_change_retriever_gates() -> None:
    assert RETRIEVAL_MIN_SCORE == 0.01
    assert RETRIEVAL_MIN_QUERY_COVERAGE == 0.51


def test_c1_c2_c3_c5_g072_g075_g081_remain_frozen() -> None:
    _, public_c1 = _public(C1, "C1")
    assert "확정급여형" in public_c1.answer and "확정기여형" in public_c1.answer
    _, public_c2 = _public(C2, "C2")
    assert "600만원" in public_c2.answer and "900만원" in public_c2.answer
    _, public_c3 = _public(C3, "C3")
    assert "명예퇴직수당" in public_c3.answer and "60일" in public_c3.answer
    _, public_c5 = _public(
        C5,
        "C5",
        message="IRP 혹은 DC 중 어떤 계좌 기준인지, 예상 투자 기간과 감수 가능한 손실 수준을 알려주세요.",
    )
    assert "솔로몬" not in public_c5.retrieved_context

    _, _, _, g072 = grounded(G072)
    cost = next(item for item in g072.claim_plan if item["subtask"] == "product_cost")
    assert cost["structured_fee_mapping"]["총 보수"] == "0.35"

    _, g075 = _public(G075, "G075")
    assert "공통으로 가입 가능한 상품이 있는지 확정할 수 없습니다" in g075.answer
    assert "DC 법정퇴직금은 IRP로 이전할 수 있습니다" not in g075.answer

    _, g081 = _run(G081)
    assert g081.products == []
    assert g081.evidence == []
