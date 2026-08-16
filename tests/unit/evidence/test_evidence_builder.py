import pytest
from pathlib import Path

from app.tools.evidence_builder import (
    EvidenceMappingError,
    build_claim_evidence_link,
    build_claim_record,
    build_evidence_card,
    build_tool_result_record,
    validate_claim,
    validate_claims,
)
from app.tools.retriever import BM25Retriever
from app.tools.rule_engine import calc_retirement_pension_tax
from scripts.build_index import load_chunks


def test_numeric_claim_requires_mapping() -> None:
    with pytest.raises(EvidenceMappingError):
        build_claim_evidence_link(
            claim_id="C01",
            claim_type="numeric",
            evidence_ids=[],
            tool_result_ids=[],
        )


def test_conditional_claim_can_have_empty_mapping() -> None:
    link = build_claim_evidence_link(
        claim_id="C02",
        claim_type="conditional",
        evidence_ids=[],
        tool_result_ids=[],
    )
    assert link.claim_id == "C02"


def _actual_records() -> tuple[dict, dict, dict]:
    chunks = load_chunks(Path("app/data/processed/chunks.jsonl"))
    chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    hits = BM25Retriever(chunks).search(
        "퇴직금을 연금으로 21년째 받고 있다면 퇴직소득세는 어떻게 달라지나요?",
        top_k=20,
        topics=["withdrawal_tax"],
        account_types=["IRP"],
    )
    hit = next(
        hit
        for hit in hits
        if hit.document_id == "doc51"
        and hit.page == 2
        and "1 ~ 10년차" in chunks_by_id[hit.chunk_id].text
    )
    evidence = build_evidence_card(hit, chunks_by_id[hit.chunk_id])
    tool = build_tool_result_record(calc_retirement_pension_tax(10_000_000, 21, "1.0.0"))
    return evidence, tool, chunks_by_id


def _factual_claim(evidence_id: str, expected_evidence: dict | None = None) -> dict:
    return build_claim_record(
        "factual",
        "퇴직소득세의 연금수령 적용 비율은 실제 연금 수령연차에 따라 달라진다.",
        evidence_ids=[evidence_id],
        required_document_id="doc51",
        required_evidence_terms=["수령하는 기간", "감면율"],
        **({"expected_evidence": expected_evidence} if expected_evidence else {}),
    )


def _numeric_claim(tool_result_id: str, **overrides: object) -> dict:
    text = str(
        overrides.pop(
            "text",
            "이연퇴직소득세 10,000,000원을 21년차 기준으로 계산하면 적용 비율은 0.50이고 계산값은 5,000,000원이다.",
        )
    )
    metadata = {
        "required_document_id": "doc51",
        "asserted_value": 5_000_000,
        "asserted_rate": "0.50",
        "rule_id": "RETIRE_TAX_RATE_BY_YEAR",
        "rule_version": "1.0.0",
        "expected_citation": {"document_id": "doc51", "page": 2},
    }
    metadata.update(overrides)
    return build_claim_record(
        "numeric",
        text,
        tool_result_ids=[tool_result_id] if tool_result_id else [],
        **metadata,
    )


def test_factual_claim_with_valid_evidence_is_supported() -> None:
    evidence, _, _ = _actual_records()
    result = validate_claim(
        _factual_claim(evidence["evidence_id"], evidence),
        {evidence["evidence_id"]: evidence},
        {},
    )
    assert result["supported"] is True


def test_numeric_claim_with_valid_tool_result_is_supported() -> None:
    _, tool, _ = _actual_records()
    result = validate_claim(
        _numeric_claim(tool["tool_result_id"]), {}, {tool["tool_result_id"]: tool}
    )
    assert result["supported"] is True


def test_claim_without_evidence_is_unsupported() -> None:
    result = validate_claim(_factual_claim(""), {}, {})
    assert result["supported"] is False
    assert "factual_claim_requires_evidence" in result["reasons"]


def test_numeric_claim_without_tool_result_is_unsupported() -> None:
    result = validate_claim(_numeric_claim(""), {}, {})
    assert result["supported"] is False
    assert "numeric_claim_requires_tool_result" in result["reasons"]


def test_invalid_evidence_id_is_detected() -> None:
    result = validate_claim(_factual_claim("missing-evidence"), {}, {})
    assert result["supported"] is False
    assert "invalid_evidence_id" in result["reasons"]


def test_invalid_tool_result_id_is_detected() -> None:
    result = validate_claim(_numeric_claim("missing-tool"), {}, {})
    assert result["supported"] is False
    assert "invalid_tool_result_id" in result["reasons"]


def test_wrong_document_evidence_fails_expected_support() -> None:
    evidence, _, chunks_by_id = _actual_records()
    doc10_hit = BM25Retriever(list(chunks_by_id.values())).search(
        "DB DC 적립금 운용", top_k=1, topics=["pension_system"]
    )[0]
    irrelevant = build_evidence_card(doc10_hit, chunks_by_id[doc10_hit.chunk_id])
    result = validate_claim(
        _factual_claim(irrelevant["evidence_id"], evidence),
        {irrelevant["evidence_id"]: irrelevant},
        {},
    )
    assert evidence["document_id"] == "doc51"
    assert result["supported"] is False
    assert "irrelevant_evidence" in result["reasons"]
    assert "expected_evidence_mismatch" in result["reasons"]


def test_numeric_claim_value_mismatch_is_detected() -> None:
    _, tool, _ = _actual_records()
    claim = _numeric_claim(
        tool["tool_result_id"],
        text="이연퇴직소득세 계산값은 6,000,000원이다.",
        asserted_value=6_000_000,
    )
    result = validate_claim(claim, {}, {tool["tool_result_id"]: tool})
    assert result["supported"] is False
    assert "numeric_value_mismatch" in result["reasons"]


def test_numeric_rate_mismatch_is_detected() -> None:
    _, tool, _ = _actual_records()
    claim = _numeric_claim(tool["tool_result_id"], asserted_rate="0.60")
    result = validate_claim(claim, {}, {tool["tool_result_id"]: tool})
    assert result["supported"] is False
    assert "numeric_rate_mismatch" in result["reasons"]


def test_rule_id_mismatch_is_detected() -> None:
    _, tool, _ = _actual_records()
    claim = _numeric_claim(tool["tool_result_id"], rule_id="OTHER_RULE")
    result = validate_claim(claim, {}, {tool["tool_result_id"]: tool})
    assert result["supported"] is False
    assert "rule_id_mismatch" in result["reasons"]


def test_rule_version_mismatch_is_detected() -> None:
    _, tool, _ = _actual_records()
    claim = _numeric_claim(tool["tool_result_id"], rule_version="other-version")
    result = validate_claim(claim, {}, {tool["tool_result_id"]: tool})
    assert result["supported"] is False
    assert "rule_version_mismatch" in result["reasons"]


def test_rule_citation_document_page_matches_evidence() -> None:
    evidence, tool, _ = _actual_records()
    claim = _numeric_claim(
        tool["tool_result_id"],
        expected_citation={"document_id": evidence["document_id"], "page": evidence["page"]},
    )
    result = validate_claim(claim, {}, {tool["tool_result_id"]: tool})
    assert result["supported"] is True


def test_rule_citation_document_page_mismatch_is_detected() -> None:
    _, tool, _ = _actual_records()
    claim = _numeric_claim(
        tool["tool_result_id"],
        expected_citation={"document_id": "doc51", "page": 3},
    )
    result = validate_claim(claim, {}, {tool["tool_result_id"]: tool})
    assert result["supported"] is False
    assert "tool_citation_mismatch" in result["reasons"]


def test_unsupported_claim_rate_zero_for_valid_case() -> None:
    evidence, tool, _ = _actual_records()
    result = validate_claims(
        [_factual_claim(evidence["evidence_id"]), _numeric_claim(tool["tool_result_id"])],
        {evidence["evidence_id"]: evidence},
        {tool["tool_result_id"]: tool},
    )
    assert result["unsupported_claim_count"] == 0
    assert result["validated_claim_count"] == 2
    assert result["unsupported_claim_rate"] == 0.0


def test_evidence_link_ids_are_deterministic() -> None:
    evidence_first, tool_first, _ = _actual_records()
    evidence_second, tool_second, _ = _actual_records()
    claim_first = _numeric_claim(tool_first["tool_result_id"])
    claim_second = _numeric_claim(tool_second["tool_result_id"])
    assert evidence_first["evidence_id"] == evidence_second["evidence_id"]
    assert tool_first["tool_result_id"] == tool_second["tool_result_id"]
    assert claim_first["claim_id"] == claim_second["claim_id"]
