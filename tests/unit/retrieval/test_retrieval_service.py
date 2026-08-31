import json

import pytest

from app.tools import retriever


QUERY = "연금 수령 기간에 따른 퇴직소득세 감면"


def test_retrieve_evidence_returns_actual_doc51_provenance() -> None:
    results = retriever.retrieve_evidence(QUERY, "withdrawal_tax", 3)

    assert 0 < len(results) <= 3
    assert any(result.document_id == "doc51" for result in results)
    assert all(result.evidence_id == result.chunk_id for result in results)
    assert all(result.document_id and result.section and result.excerpt for result in results)
    assert all(result.source_priority == 0 for result in results)
    assert all(result.score > 0 for result in results)


def test_retrieve_evidence_without_topic_filter() -> None:
    results = retriever.retrieve_evidence(QUERY, None, 2)

    assert 0 < len(results) <= 2


def test_retrieve_evidence_applies_topic_filter() -> None:
    results = retriever.retrieve_evidence(QUERY, "pension_system", 5)

    assert results
    assert all(result.document_id == "doc10" for result in results)


def test_retrieve_evidence_respects_top_k() -> None:
    assert len(retriever.retrieve_evidence("퇴직연금", None, 1)) == 1


@pytest.mark.parametrize("top_k", [0, -1, True, 1.5])
def test_retrieve_evidence_rejects_invalid_top_k(top_k: object) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        retriever.retrieve_evidence(QUERY, None, top_k)  # type: ignore[arg-type]


@pytest.mark.parametrize("query", ["", "   "])
def test_retrieve_evidence_rejects_empty_query(query: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        retriever.retrieve_evidence(query, None, 3)


def test_retrieve_evidence_returns_empty_list_without_fallback() -> None:
    assert retriever.retrieve_evidence("존재하지않는검색어", "withdrawal_tax", 3) == []


def test_retrieve_evidence_preserves_nullable_page(monkeypatch, tmp_path) -> None:
    corpus = tmp_path / "chunks.jsonl"
    row = {
        "chunk_id": "unit-docx-section",
        "document_id": "unit-docx",
        "title": "unit fixture",
        "page": None,
        "section": "nullable page contract",
        "text": "고유검색어",
        "effective_from": None,
        "valid_to": None,
        "topics": ["unit_topic"],
        "account_types": [],
        "source_type": "unit_fixture",
        "source_priority": 7,
    }
    corpus.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(retriever, "DEFAULT_CHUNKS_PATH", corpus)

    result = retriever.retrieve_evidence("고유검색어", "unit_topic", 1)[0]

    assert result.page is None
    assert result.section == "nullable page contract"
    assert result.source_priority == 7


@pytest.mark.parametrize(
    "query",
    [
        "연금저축이랑 IRP에 넣으면 세액공제 얼마까지 되나요? 다 합쳐서요.",
        "개인형퇴직연금하고 연금저축 공제 한도를 통합해서 알려줘.",
    ],
)
def test_tax_deduction_queries_cover_both_provided_sources(query: str) -> None:
    document_ids = {result.document_id for result in retriever.retrieve_evidence(query, "withdrawal_tax", 5)}
    assert {"doc41", "doc55"} <= document_ids


@pytest.mark.parametrize(
    "query",
    [
        "명퇴하는 교사예요. 명퇴수당 연금계좌 절세를 알려주세요.",
        "교직원 명예퇴직수당을 IRP에 넣으면 어떻게 되나요?",
    ],
)
def test_teacher_retirement_queries_cover_specific_and_general_sources(query: str) -> None:
    document_ids = {result.document_id for result in retriever.retrieve_evidence(query, "withdrawal_tax", 5)}
    assert {"doc26", "doc51"} <= document_ids


def test_product_compare_covers_all_four_prospectuses() -> None:
    results = retriever.retrieve_evidence(
        "솔로몬 국공채 단기 중장기 장기 상품의 차이와 안정성을 비교해줘", "product", 5
    )
    assert {
        "r2_kr5153420063",
        "r2_kr5153420079",
        "r2_kr5153420105",
        "r2_kr5153450658",
    } <= {result.document_id for result in results}
