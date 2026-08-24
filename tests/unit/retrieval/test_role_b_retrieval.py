from __future__ import annotations

from pathlib import Path

from app.data.schemas.models import Chunk
from app.tools.retriever import BM25Retriever
from scripts.parse_documents import build_inventory, parse_document, parse_targets


RAW_DIR = Path("app/data/raw")


def _to_chunk(record: dict[str, object]) -> Chunk:
    return Chunk(
        chunk_id=record["chunk_id"],
        document_id=record["document_id"],
        title=record["title"],
        page=record.get("page"),
        section=record["section"],
        text=record.get("content", record.get("text", "")),
        effective_from=record.get("effective_from"),
        valid_to=record.get("valid_to"),
        topics=record.get("topics", [record.get("topic", "")]),
        account_types=record.get("account_types", [record.get("account_type", "")]),
        source_type=record.get("source_type", "provided"),
        source_priority=record.get("source_priority", 0),
    )


def _doc_chunks() -> list[dict[str, object]]:
    inventory = build_inventory(RAW_DIR)
    _, chunks, failed = parse_targets(RAW_DIR, inventory, {"doc10", "doc51"})
    assert not failed
    return chunks


def _mixed_chunks() -> list[Chunk]:
    return [_to_chunk(chunk) for chunk in _doc_chunks()]


def test_db_dc_query_returns_doc10_top_hit() -> None:
    retriever = BM25Retriever(_mixed_chunks())
    hits = retriever.search(
        "DB형 퇴직연금과 DC형 퇴직연금은 무엇이 다르고 누가 적립금을 운용하나요?",
        top_k=5,
        topics=["pension_system"],
        account_types=["DB_DC"],
    )

    assert hits
    assert hits[0].document_id == "doc10"
    assert hits[0].page == 1
    assert any(hit.document_id == "doc10" for hit in hits)
    assert all(hit.document_id != "r2_kr5153450209" for hit in hits)


def test_withdrawal_query_returns_doc51_top_hit() -> None:
    retriever = BM25Retriever(_mixed_chunks())
    hits = retriever.search(
        "퇴직금을 일시금으로 받는 것과 연금으로 오래 나눠 받는 것의 세금 차이를 비교하려면 어떤 규칙을 확인해야 하나요?",
        top_k=5,
        topics=["withdrawal_tax"],
        account_types=["IRP"],
    )

    assert hits
    assert hits[0].document_id == "doc51"
    assert isinstance(hits[0].page, int)
    assert any(hit.document_id == "doc51" for hit in hits)


def test_metadata_filter_excludes_non_matching_account_type() -> None:
    retriever = BM25Retriever(_mixed_chunks())
    hits = retriever.search(
        "DB형 퇴직연금과 DC형 퇴직연금은 무엇이 다르고 누가 적립금을 운용하나요?",
        top_k=5,
        topics=["pension_system"],
        account_types=["NON_EXISTENT"],
    )

    assert hits == []


def test_deterministic_results_for_same_query_and_index() -> None:
    retriever_first = BM25Retriever(_mixed_chunks())
    retriever_second = BM25Retriever(_mixed_chunks())

    query = "퇴직금을 일시금으로 받는 것과 연금으로 오래 나눠 받는 것의 세금 차이를 비교하려면 어떤 규칙을 확인해야 하나요?"
    first = [hit.chunk_id for hit in retriever_first.search(query, top_k=5)]
    second = [hit.chunk_id for hit in retriever_second.search(query, top_k=5)]

    assert first == second


def test_document_id_and_page_policy_preserved_in_hits() -> None:
    retriever = BM25Retriever(_mixed_chunks())
    hits = retriever.search(
        "퇴직금을 일시금으로 받는 것과 연금으로 오래 나눠 받는 것의 세금 차이를 비교하려면 어떤 규칙을 확인해야 하나요?",
        top_k=5,
    )

    assert hits
    assert all(hit.document_id for hit in hits)
    assert all(isinstance(hit.page, int) for hit in hits if hit.document_id == "doc51")


def test_processed_index_scope_excludes_products() -> None:
    document_ids = {chunk["document_id"] for chunk in _doc_chunks()}
    assert document_ids == {"doc10", "doc51"}


def test_null_dates_remain_null_in_chunk_contract() -> None:
    chunks = [_to_chunk(chunk) for chunk in _doc_chunks()]
    doc51 = [chunk for chunk in chunks if chunk.document_id == "doc51"]
    assert doc51
    assert all(chunk.effective_from is None for chunk in doc51)
    assert all(chunk.valid_to is None for chunk in doc51)
