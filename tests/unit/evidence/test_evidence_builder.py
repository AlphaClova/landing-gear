import pytest

from app.tools.evidence_builder import EvidenceMappingError, build_claim_evidence_link


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
