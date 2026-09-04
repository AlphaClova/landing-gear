from app.tools.retriever import (
    _PENSION_RECEIVING_EXPANSION,
    _expand_query,
    pension_receiving_normalization_applies,
    retrieve_evidence,
)

APPLIES = (
    "연금은 언제부터 받을 수 있나요?",
    "퇴직연금은 몇 살부터 받을 수 있나요?",
    "퇴직금은 연금으로 받을 수 있나요?",
)

DOES_NOT_APPLY = (
    "지원금은 언제 받을 수 있나요?",
    "주식 배당은 언제 받을 수 있나요?",
    "월급은 언제 받을 수 있나요?",
    "몇 살부터 운전할 수 있나요?",
    "DC와 DB, 퇴직금이 정해지는 방식이랑 운용 주체가 어떻게 다른가요?",
    "연금저축이랑 IRP에 넣으면 세액공제 얼마까지 되나요? 다 합쳐서요.",
    "솔로몬 국공채 단기 중장기 장기 상품의 차이와 안정성을 비교해줘",
)


def test_receiving_normalization_applies_to_pension_start_age_questions() -> None:
    for query in APPLIES:
        assert pension_receiving_normalization_applies(query), query
        search_query, _ = _expand_query(query, "pension_system")
        assert query in search_query
        assert "수령" in search_query
        assert "55세" not in search_query
        assert "만 55세" not in search_query


def test_receiving_normalization_does_not_apply_without_pension_anchor() -> None:
    for query in DOES_NOT_APPLY:
        assert pension_receiving_normalization_applies(query) is False, query
        search_query, _ = _expand_query(query, None)
        assert _PENSION_RECEIVING_EXPANSION not in search_query


def test_query_expansion_does_not_hardcode_answer_values() -> None:
    assert "55세" not in _PENSION_RECEIVING_EXPANSION
    assert "만 55세" not in _PENSION_RECEIVING_EXPANSION
    assert "3.3" not in _PENSION_RECEIVING_EXPANSION
    assert "16.5" not in _PENSION_RECEIVING_EXPANSION


def test_pension_receiving_queries_retrieve_receipt_evidence() -> None:
    q1 = retrieve_evidence("연금은 언제부터 받을 수 있나요?", "pension_system", 5)
    q2 = retrieve_evidence("퇴직연금은 몇 살부터 받을 수 있나요?", "pension_system", 5)
    q3 = retrieve_evidence("퇴직금은 연금으로 받을 수 있나요?", "pension_system", 5)
    assert q1 and any("55세" in item.excerpt or "수령" in item.excerpt for item in q1)
    assert q2 and any("55세" in item.excerpt or "수령" in item.excerpt for item in q2)
    assert q3 and any("연금" in item.excerpt and ("수령" in item.excerpt or "일시금" in item.excerpt) for item in q3)
    assert all(item.document_id != "r2_kr5153450658" for item in q1 + q2 + q3)


def test_non_pension_time_questions_do_not_use_receiving_expansion() -> None:
    for query in (
        "지원금은 언제 받을 수 있나요?",
        "주식 배당은 언제 받을 수 있나요?",
        "몇 살부터 운전할 수 있나요?",
        "오늘 비트코인 가격이 오를까요?",
    ):
        assert pension_receiving_normalization_applies(query) is False
        search_query, kind = _expand_query(query, None)
        assert search_query == query
        assert kind is None
