from __future__ import annotations

import json
from pathlib import Path

from scripts.parse_documents import build_inventory, parse_document, parse_targets


def _raw_dir() -> Path:
    return Path("app/data/raw")


def _target_ids() -> set[str]:
    return {"doc51", "doc10"}


def test_document_inventory_has_required_fields() -> None:
    inventory = build_inventory(_raw_dir())
    assert inventory

    required = {
        "document_id",
        "filename",
        "raw_path",
        "file_type",
        "page_count",
        "sheet_info",
        "title",
        "topic",
        "account_type",
        "source_priority",
        "effective_from",
        "valid_to",
        "parse_status",
    }
    for row in inventory:
        assert required.issubset(row.keys())


def test_parse_targets_preserve_document_id_and_pdf_page() -> None:
    inventory = build_inventory(_raw_dir())
    inventory, chunks, failed = parse_targets(_raw_dir(), inventory, _target_ids())

    assert not failed
    assert chunks

    chunk_doc_ids = {chunk["document_id"] for chunk in chunks}
    assert "doc51" in chunk_doc_ids
    assert "doc10" in chunk_doc_ids

    doc10_rows = [chunk for chunk in chunks if chunk["document_id"] == "doc10"]
    assert doc10_rows
    assert all(isinstance(row["page"], int) and row["page"] >= 1 for row in doc10_rows)

    doc51_rows = [chunk for chunk in chunks if chunk["document_id"] == "doc51"]
    assert doc51_rows
    assert {row["page"] for row in doc51_rows} == {1, 2, 3}
    assert all(row["section"] for row in doc51_rows)


def test_null_metadata_not_coerced_to_zero_or_empty_string() -> None:
    inventory = build_inventory(_raw_dir())
    inventory, chunks, _ = parse_targets(_raw_dir(), inventory, _target_ids())

    by_id = {row["document_id"]: row for row in inventory}
    assert by_id["doc51"]["valid_to"] is None
    assert by_id["doc51"]["effective_from"] is None

    doc51_chunks = [chunk for chunk in chunks if chunk["document_id"] == "doc51"]
    assert doc51_chunks
    assert all(isinstance(chunk["page"], int) for chunk in doc51_chunks)
    assert all(chunk["valid_to"] is None for chunk in doc51_chunks)
    assert all(chunk["effective_from"] is None for chunk in doc51_chunks)
    assert all(chunk["effective_from"] != "" for chunk in doc51_chunks)


def test_table_chunk_preserved() -> None:
    _, chunks = parse_document(Path("app/data/raw/pension/doc29.xlsx"))
    assert chunks
    assert any(chunk["content_type"] == "table" for chunk in chunks)


def test_chunk_id_is_deterministic_for_same_input() -> None:
    inventory = build_inventory(_raw_dir())
    _, chunks_first, _ = parse_targets(_raw_dir(), inventory, _target_ids())

    inventory_again = build_inventory(_raw_dir())
    _, chunks_second, _ = parse_targets(_raw_dir(), inventory_again, _target_ids())

    ids_first = [chunk["chunk_id"] for chunk in chunks_first]
    ids_second = [chunk["chunk_id"] for chunk in chunks_second]
    assert ids_first == ids_second


def test_chunk_output_serializable() -> None:
    inventory = build_inventory(_raw_dir())
    _, chunks, _ = parse_targets(_raw_dir(), inventory, _target_ids())
    for chunk in chunks[:10]:
        json.dumps(chunk, ensure_ascii=True)


def _pptx_chunks() -> tuple[dict[str, object], list[dict[str, object]]]:
    return parse_document(Path("app/data/raw/pension/doc33.pptx"))


def test_pptx_inventory_supported() -> None:
    inventory = build_inventory(_raw_dir())
    doc33 = next(row for row in inventory if row["document_id"] == "doc33")
    assert doc33["file_type"] == "pptx"
    assert doc33["parse_status"] != "unsupported_file_type"


def test_pptx_slide_count_preserved() -> None:
    inventory, _ = _pptx_chunks()
    assert inventory["page_count"] == 7


def test_pptx_document_id_preserved() -> None:
    _, chunks = _pptx_chunks()
    assert chunks
    assert {chunk["document_id"] for chunk in chunks} == {"doc33"}
    assert all(chunk["topics"] == [] for chunk in chunks)
    assert all(chunk["account_types"] == [] for chunk in chunks)


def test_pptx_slide_number_preserved() -> None:
    _, chunks = _pptx_chunks()
    assert {chunk["page"] for chunk in chunks} == set(range(1, 8))


def test_pptx_text_chunk_created() -> None:
    _, chunks = _pptx_chunks()
    text_chunks = [chunk for chunk in chunks if chunk["content_type"] == "text"]
    assert text_chunks
    assert all(chunk["content"].strip() for chunk in text_chunks)


def test_pptx_table_chunk_preserved_if_present() -> None:
    _, chunks = _pptx_chunks()
    table_chunks = [chunk for chunk in chunks if chunk["content_type"] == "table"]
    assert len(table_chunks) == 2
    assert all(chunk["page"] == 6 for chunk in table_chunks)
    assert all("납입액 | ISA전환입금 금액" in chunk["content"] for chunk in table_chunks)


def test_pptx_chunk_id_is_deterministic() -> None:
    _, first = _pptx_chunks()
    _, second = _pptx_chunks()
    assert [chunk["chunk_id"] for chunk in first] == [chunk["chunk_id"] for chunk in second]


def test_pptx_empty_slide_does_not_create_fake_content() -> None:
    _, chunks = _pptx_chunks()
    assert all(chunk["content"].strip() for chunk in chunks)
    assert all(not chunk["content"].startswith("slide-") for chunk in chunks)


def test_four_real_file_types_dispatch_to_parser() -> None:
    sources = {
        "pdf": Path("app/data/raw/pension/doc10.pdf"),
        "docx": Path("app/data/raw/pension/doc51.docx"),
        "xlsx": Path("app/data/raw/pension/doc29.xlsx"),
        "pptx": Path("app/data/raw/pension/doc33.pptx"),
    }
    for file_type, path in sources.items():
        inventory, chunks = parse_document(path)
        assert inventory["file_type"] == file_type
        assert inventory["parse_status"] != "unsupported_file_type"
        assert chunks
