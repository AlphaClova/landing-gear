from app.api.schemas import (
    Citation,
    InternalAnswer,
    ThinkTrace,
    parse_retrieved_context,
    select_public_citations,
    to_eval_response,
)


def _citation(evidence_id: str, document_id: str, page: int, excerpt: str) -> Citation:
    return Citation(
        id=evidence_id,
        document_id=document_id,
        page=page,
        source="provided",
        excerpt=excerpt,
    )


def _answer(
    citations: list[Citation],
    *,
    claim_plan: list[dict[str, object]],
    product_facts: list[dict[str, object]] | None = None,
    message: str = "검증된 답변 본문",
) -> InternalAnswer:
    return InternalAnswer(
        type="result",
        message=message,
        request_id="req-test",
        citations=citations,
        trace=ThinkTrace(
            intent="제도",
            route="fast_path",
            route_confidence=1.0,
            claim_plan=claim_plan,
            product_facts=product_facts or [],
        ),
    )


def _claim(*evidence_ids: str, product_fact_ids: list[str] | None = None) -> dict[str, object]:
    return {
        "subtask": "test",
        "status": "answerable",
        "claims": [{
            "text": "검증된 사실",
            "evidence_ids": list(evidence_ids),
            "product_fact_ids": product_fact_ids or [],
        }],
    }


def test_public_context_reuses_claim_evidence_mapping_and_preserves_answer() -> None:
    db_dc = _citation("db-dc", "doc10", 1, "DB와 DC의 급여 결정 방식과 운용 주체")
    eligibility = _citation("eligibility", "doc11", 2, "퇴직연금 가입 대상")
    internal = _answer([db_dc, eligibility], claim_plan=[_claim("db-dc")])

    public = to_eval_response(internal, "Q-DB-DC", "DB형과 DC형의 차이는?")

    assert public.answer == internal.message
    assert parse_retrieved_context(public.retrieved_context) == [db_dc.excerpt]


def test_public_context_deduplicates_same_id_and_equivalent_excerpt() -> None:
    first = _citation("tax-limit", "doc41", 1, "연금저축 세액공제 한도는 연 600만원입니다.")
    same_id = first.model_copy(update={"excerpt": "연금저축 세액공제 한도는 연 600만원입니다."})
    equivalent = _citation("tax-limit-copy", "doc41", 2, "연금저축  세액공제 한도는 연 600만원입니다!")
    internal = _answer(
        [first, same_id, equivalent],
        claim_plan=[_claim("tax-limit", "tax-limit-copy")],
    )

    assert select_public_citations(internal, "연금저축과 IRP 세액공제 한도는?") == [first]


def test_similar_evidence_with_different_numbers_is_not_deduplicated() -> None:
    pension = _citation("pension", "doc41", 1, "연금저축 세액공제 한도는 연 600만원으로 적용됩니다.")
    combined = _citation("combined", "doc55", 10, "연금저축 세액공제 한도는 연 900만원으로 적용됩니다.")
    internal = _answer([pension, combined], claim_plan=[_claim("pension", "combined")])

    assert select_public_citations(internal, "연금저축과 IRP 세액공제 한도는?") == [pension, combined]


def test_unresolved_general_recommendation_hides_incidental_product_prospectus() -> None:
    general = _citation("general", "doc-guide", 3, "상품 선택에는 투자기간과 위험성향 확인이 필요합니다.")
    prospectus = _citation("fund", "r2_short", 1, "솔로몬 단기국공채 투자설명서")
    internal = _answer(
        [general, prospectus],
        claim_plan=[_claim("general")],
        product_facts=[{
            "product_id": "short",
            "product_name": "미래에셋솔로몬단기국공채증권자투자신탁",
            "document_id": "r2_short",
            "page": 1,
        }],
        message="투자기간과 위험성향을 먼저 알려주세요.",
    )

    assert select_public_citations(internal, "IRP 상품을 추천해줘") == [general]


def test_confirmed_product_comparison_keeps_each_claimed_prospectus() -> None:
    short = _citation("short-evidence", "r2_short", 1, "솔로몬 단기국공채 위험등급")
    long = _citation("long-evidence", "r2_long", 1, "솔로몬 장기국공채 위험등급")
    facts = [
        {"product_id": "short", "product_name": "솔로몬 단기국공채", "document_id": "r2_short", "page": 1},
        {"product_id": "long", "product_name": "솔로몬 장기국공채", "document_id": "r2_long", "page": 1},
    ]
    internal = _answer(
        [short, long],
        claim_plan=[_claim(product_fact_ids=["short", "long"])],
        product_facts=facts,
        message="솔로몬 단기국공채와 솔로몬 장기국공채를 비교합니다.",
    )

    assert select_public_citations(internal, "솔로몬 단기/장기 상품 비교") == [short, long]


def test_out_of_scope_answer_keeps_empty_public_context_and_answer() -> None:
    internal = _answer([], claim_plan=[], message="해당 질문은 지원 범위를 벗어납니다.")
    internal.type = "limitation"

    public = to_eval_response(internal, "Q-OOS", "오늘 날씨와 야구 결과 알려줘")

    assert public.answer == internal.message
    assert public.retrieved_context == ""
