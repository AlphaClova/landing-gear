from datetime import date

from app.data.schemas.models import Chunk
from app.tools.retriever import BM25Retriever


def _chunks() -> list[Chunk]:
    return [
        Chunk(
            chunk_id="doc51-p03-c01",
            document_id="doc51",
            title="연금 세제",
            page=3,
            section="연금수령 세제",
            text="연금수령시 실제 수령연차에 따라 70 60 50 세율이 적용된다",
            effective_from="2026-01-01",
            valid_to=None,
            topics=["tax", "withdrawal"],
            account_types=["IRP"],
            source_priority=0,
        ),
        Chunk(
            chunk_id="doc10-p01-c01",
            document_id="doc10",
            title="DB DC 기초",
            page=1,
            section="제도",
            text="DB와 DC는 운용 주체와 급여 확정 방식이 다르다",
            effective_from="2025-01-01",
            valid_to=None,
            topics=["system"],
            account_types=["DB", "DC"],
            source_priority=0,
        ),
    ]


def test_retriever_returns_relevant_hit() -> None:
    retriever = BM25Retriever(_chunks())
    hits = retriever.search("연금수령 세율", top_k=1)

    assert len(hits) == 1
    assert hits[0].chunk_id == "doc51-p03-c01"


def test_retriever_applies_metadata_filter() -> None:
    retriever = BM25Retriever(_chunks())
    hits = retriever.search(
        "연금수령",
        top_k=3,
        topics=["tax"],
        account_types=["IRP"],
        on_date=date(2026, 1, 1),
    )

    assert len(hits) == 1
    assert hits[0].document_id == "doc51"
