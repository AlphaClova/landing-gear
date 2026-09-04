from app.tools.retriever import (
    _IRP_ACCOUNT_EXPANSION,
    _IRP_COMPARE_EXPANSION,
    _IRP_TRANSFER_EXPANSION,
    _PENSION_RECEIVING_EXPANSION,
    _expand_query,
    irp_lexical_normalization_applies,
    pension_receiving_normalization_applies,
    retrieve_evidence,
)

R06 = "IRP는 어떤 계좌인가요?"
R07 = "연금저축과 IRP는 뭐가 다른가요?"
R14 = "퇴직한 뒤 IRP로 옮길 수 있나요?"


def test_irp_lexical_normalization_applies_to_account_compare_transfer() -> None:
    assert irp_lexical_normalization_applies(R06)
    assert irp_lexical_normalization_applies(R07)
    assert irp_lexical_normalization_applies(R14)


def test_irp_lexical_normalization_does_not_apply_to_frozen_queries() -> None:
    for query in (
        "연금은 언제부터 받을 수 있나요?",
        "퇴직연금은 몇 살부터 받을 수 있나요?",
        "퇴직금은 연금으로 받을 수 있나요?",
        "DC와 DB, 퇴직금이 정해지는 방식이랑 운용 주체가 어떻게 다른가요?",
        "연금저축이랑 IRP에 넣으면 세액공제 얼마까지 되나요? 다 합쳐서요.",
        "솔로몬 국공채 단기 · 중장기 · 장기, 뭐가 달라요? 안정적인 걸 원해요.",
        "IRP 계약이전 방법",
    ):
        assert irp_lexical_normalization_applies(query) is False, query


def test_irp_expansion_does_not_hardcode_answer_values() -> None:
    for blob in (_IRP_ACCOUNT_EXPANSION, _IRP_COMPARE_EXPANSION, _IRP_TRANSFER_EXPANSION):
        assert "55세" not in blob
        assert "60일" not in blob
        assert "3.3" not in blob
        assert "600" not in blob
        assert "900" not in blob


def test_r06_retrieves_irp_account_institution_evidence() -> None:
    search_query, kind = _expand_query(R06, "pension_system")
    assert R06 in search_query
    assert "계좌" in search_query
    assert "개인형퇴직연금" in search_query
    assert kind is None
    hits = retrieve_evidence(R06, "pension_system", 5)
    assert hits
    joined = " ".join(item.excerpt for item in hits)
    assert "IRP" in joined.upper()
    assert "계좌" in joined or "개인형" in joined
    assert all("계좌번호" not in item.excerpt for item in hits) or any("개인형" in item.excerpt or "연금계좌" in item.excerpt for item in hits)


def test_r07_retrieves_institution_comparison_evidence() -> None:
    search_query, _ = _expand_query(R07, "pension_system")
    assert "비교" in search_query or "차이" in search_query
    hits = retrieve_evidence(R07, "pension_system", 5)
    assert hits
    assert any("연금저축" in item.excerpt and "IRP" in item.excerpt.upper() for item in hits)


def test_r14_retrieves_transfer_procedure_evidence() -> None:
    search_query, _ = _expand_query(R14, "withdrawal_tax")
    assert "이전" in search_query
    assert "55세" not in search_query
    hits = retrieve_evidence(R14, "withdrawal_tax", 5)
    assert hits
    assert any(
        "IRP" in item.excerpt.upper() and any(term in item.excerpt for term in ("이전", "입금", "이동"))
        for item in hits
    )


def test_receiving_normalization_is_unchanged_by_irp_lexical_path() -> None:
    query = "연금은 언제부터 받을 수 있나요?"
    assert pension_receiving_normalization_applies(query)
    assert irp_lexical_normalization_applies(query) is False
    search_query, _ = _expand_query(query, "pension_system")
    assert _PENSION_RECEIVING_EXPANSION in search_query
    assert _IRP_ACCOUNT_EXPANSION not in search_query
    assert _IRP_TRANSFER_EXPANSION not in search_query
