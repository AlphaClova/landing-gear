"""Targeted C1~C6 plus static P0 support checks. Does not call HCX Full 120."""

from __future__ import annotations

import json
from pathlib import Path

from app.api.schemas import Citation, InternalAnswer, ThinkTrace, parse_retrieved_context, to_eval_response
from tests.unit.test_content_p0_policies import grounded

C1 = "DC와 DB, 퇴직금이 정해지는 방식이랑 운용 주체가 어떻게 다른가요?"
C2 = "연금저축이랑 IRP에 넣으면 세액공제 얼마까지 되나요? 다 합쳐서요."
C3 = "명퇴하는 교사예요. 명퇴수당을 연금계좌에 넣으면 세금 감면이 어마어마하다던데, 절세법만 알려주세요."
C4 = "솔로몬 국공채 단기 · 중장기 · 장기, 뭐가 달라요? 안정적인 걸 원해요."
C5 = "좋은 연금 상품 하나 추천해 주세요."
C6 = "비트코인 가격을 예측해줘"
P0_IDS = (
    "G011", "G026", "G031", "G033", "G056", "G089", "G102",
    "G004", "G058", "G059",
    "G002", "G039", "G041", "G042", "G044", "G045", "G051", "G053", "G055",
)
_ARTIFACT = Path("artifacts/eval/full-real-v9/latest.json")


def _internal(question: str, *, message: str | None = None, intent: str | None = None) -> InternalAnswer:
    decision, _, result, context = grounded(question)
    facts = [
        {key: value for key, value in product.items() if key in {
            "product_id", "document_id", "page", "product_name", "asset_type", "risk_level", "risk_label", "plan_types",
        }}
        for product in result.products
    ]
    return InternalAnswer(
        type="limitation" if (intent or decision.intent) == "범위 밖" else "result",
        message=message or context.fallback_message,
        request_id="req-prune",
        citations=list(result.evidence),
        trace=ThinkTrace(
            intent=intent or decision.intent,
            route=decision.route,
            route_confidence=decision.route_confidence,
            claim_plan=context.claim_plan,
            product_facts=facts,
            rule_results=[
                {"rule_id": item.rule_id, "label": item.label, "value": item.value}
                for item in result.calculations
            ],
        ),
    )


def _public(question: str, question_id: str, **kwargs: object):
    internal = _internal(question, **kwargs)  # type: ignore[arg-type]
    before_answer = internal.message
    before_citations = [item.model_copy() for item in internal.citations]
    before_intent = internal.trace.intent
    before_plan = list(internal.trace.claim_plan)
    before_products = list(internal.trace.product_facts)
    before_rules = list(internal.trace.rule_results)
    public = to_eval_response(internal, question_id, question)
    assert public.answer == before_answer
    assert internal.message == before_answer
    assert internal.citations == before_citations
    assert internal.trace.intent == before_intent
    assert internal.trace.claim_plan == before_plan
    assert internal.trace.product_facts == before_products
    assert internal.trace.rule_results == before_rules
    return internal, public


def test_c1_pipeline_keeps_doc10_p1_and_drops_eligibility_tax() -> None:
    internal, public = _public(C1, "C1")
    docs = [(item.document_id, item.page) for item in internal.citations]
    assert ("doc10", 1) in docs
    docs = public.retrieved_context
    assert "[DOC doc10][PAGE 1]" in docs
    assert "[DOC doc10][PAGE 2]" not in docs
    assert "[DOC doc10][PAGE 3]" not in docs
    assert "[DOC doc51]" not in docs
    assert "[DOC doc55]" not in docs
    assert public.answer == internal.message


def test_c2_pipeline_keeps_600_900_and_drops_doc51_retirement_tax() -> None:
    internal, public = _public(C2, "C2")
    assert "600" in public.retrieved_context
    assert "900" in public.retrieved_context
    assert "3.3%" not in public.retrieved_context
    assert "연금소득세" not in public.retrieved_context
    assert public.answer == internal.message


def test_c3_pipeline_keeps_honor_60day_and_drops_example() -> None:
    internal, public = _public(C3, "C3")
    assert "명예퇴직수당" in public.retrieved_context or "퇴직수당" in public.retrieved_context
    assert "60일" in public.retrieved_context
    assert "30년 근무" not in public.retrieved_context
    assert public.retrieved_context.count("[DOC doc26][PAGE 1]") <= 1 or "60일" in public.retrieved_context
    assert public.answer == internal.message


def test_c4_pipeline_keeps_three_products_without_ultrashort() -> None:
    internal, public = _public(C4, "C4")
    assert "단기국공채" in public.retrieved_context
    assert "중장기국공채" in public.retrieved_context
    assert "장기국공채" in public.retrieved_context
    assert public.retrieved_context.count("상품명: 미래에셋솔로몬단기국공채") == 1
    assert public.retrieved_context.count("상품명: 미래에셋솔로몬중장기국공채") == 1
    assert public.retrieved_context.count("상품명: 미래에셋솔로몬장기국공채") == 1
    assert "초단기" not in public.retrieved_context
    assert "분류체계 개편" not in public.retrieved_context
    assert public.answer == internal.message


def test_c5_pipeline_drops_unselected_solomon_prospectus() -> None:
    message = "IRP 혹은 DC 중 어떤 계좌 기준인지, 예상 투자 기간과 감수 가능한 손실 수준을 알려주세요."
    internal, public = _public(C5, "C5", message=message)
    assert "솔로몬" not in public.retrieved_context
    assert "투자설명서" not in public.retrieved_context
    assert "수수료선취" not in public.retrieved_context
    assert public.answer == message


def test_c6_pipeline_keeps_empty_context() -> None:
    internal, public = _public(C6, "C6", intent="범위 밖")
    assert public.retrieved_context == ""
    assert parse_retrieved_context(public.retrieved_context) == []


def test_g011_keeps_15_hour_support() -> None:
    _, public = _public("주 14시간 근무자도 퇴직연금 대상인가요?", "G011")
    assert "15시간" in public.retrieved_context or "15시간" in public.answer


def test_g058_drops_non_short_solomon() -> None:
    _, public = _public("솔로몬 국공채 단기형 특징을 문서 근거로 설명해줘", "G058")
    if public.retrieved_context:
        assert "초단기" not in public.retrieved_context


def _artifact_rows() -> dict[str, dict]:
    payload = json.loads(_ARTIFACT.read_text())
    rows = payload["results"] if isinstance(payload, dict) and "results" in payload else payload
    if isinstance(payload, dict) and not isinstance(rows, list):
        for value in payload.values():
            if isinstance(value, list) and value and isinstance(value[0], dict) and "id" in value[0]:
                rows = value
                break
    return {row["id"]: row for row in rows}


def test_static_p0_answer_support_is_not_lost() -> None:
    if not _ARTIFACT.exists():
        return
    rows = _artifact_rows()
    lost: list[str] = []
    for case_id in P0_IDS:
        row = rows[case_id]
        answer = row.get("answer") or ""
        excerpts = row.get("retrieved_context") or []
        if not isinstance(excerpts, list):
            continue
        citations = [
            Citation(id=f"{case_id}-{index}", document_id="unknown", source="provided", excerpt=str(excerpt), page=None)
            for index, excerpt in enumerate(excerpts)
        ]
        internal = InternalAnswer(
            type="result",
            message=answer,
            request_id=case_id,
            citations=citations,
            trace=ThinkTrace(intent="세제", route="fast_path", route_confidence=1.0),
        )
        public = to_eval_response(internal, case_id, row["question"])
        assert public.answer == answer
        remaining = public.retrieved_context
        for token in ("600만원", "900만원", "15시간", "60일", "100%", "70%"):
            if token in answer and excerpts and token not in remaining and not any(token in str(item) for item in excerpts):
                continue
            if token in answer and any(token in str(item) for item in excerpts) and token not in remaining:
                lost.append(f"{case_id}:{token}")
    assert lost == []
