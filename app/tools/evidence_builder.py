from __future__ import annotations

from app.data.schemas.models import ClaimEvidenceLink, RetrievalHit


class EvidenceMappingError(ValueError):
    """Raised when claims cannot be mapped to evidence/tool outputs."""


def build_claim_evidence_link(
    claim_id: str,
    claim_type: str,
    evidence_ids: list[str],
    tool_result_ids: list[str],
) -> ClaimEvidenceLink:
    if claim_type in {"numeric", "factual"} and not evidence_ids and not tool_result_ids:
        raise EvidenceMappingError(
            "numeric/factual claims must include evidence_ids or tool_result_ids"
        )

    return ClaimEvidenceLink(
        claim_id=claim_id,
        claim_type=claim_type,  # type: ignore[arg-type]
        evidence_ids=evidence_ids,
        tool_result_ids=tool_result_ids,
    )


def build_evidence_card(hit: RetrievalHit) -> dict[str, str | int]:
    return {
        "evidence_id": hit.chunk_id,
        "document_id": hit.document_id,
        "page": hit.page,
        "quote": hit.quote,
    }
