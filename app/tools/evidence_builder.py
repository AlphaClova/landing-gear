from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
import hashlib
import json
from typing import Any

from app.data.schemas.models import CalculationResult, Chunk, ClaimEvidenceLink, RetrievalHit


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


def _deterministic_id(prefix: str, payload: Any) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def build_evidence_card(hit: RetrievalHit, chunk: Chunk | None = None) -> dict[str, Any]:
    if chunk is not None and chunk.chunk_id != hit.chunk_id:
        raise EvidenceMappingError("retrieval hit and chunk IDs do not match")
    return {
        "evidence_id": hit.chunk_id,
        "chunk_id": hit.chunk_id,
        "document_id": hit.document_id,
        "page": hit.page,
        "section": chunk.section if chunk is not None else None,
        "quote": chunk.text if chunk is not None else hit.quote,
        "source_priority": chunk.source_priority if chunk is not None else None,
        "score": hit.score,
    }


def build_internal_tool_result_record(result: CalculationResult) -> dict[str, Any]:
    """Build a B-internal deterministic record; this is not an A-facing contract."""
    calculation = asdict(result)
    calculation["rate"] = str(result.rate) if result.rate is not None else None
    payload = {
        "value": result.value,
        "rate": calculation["rate"],
        "formula": result.formula,
        "rule_id": result.rule_id,
        "rule_version": result.rule_version,
        "evidence_ids": calculation["evidence_ids"],
    }
    return {
        "tool_result_id": _deterministic_id("tool", payload),
        "tool_name": "calc_retirement_pension_tax",
        "contract_scope": "b_internal_validation",
        "calculation_result": calculation,
    }


def build_claim_record(
    claim_type: str,
    text: str,
    evidence_ids: list[str] | None = None,
    tool_result_ids: list[str] | None = None,
    **validation_metadata: Any,
) -> dict[str, Any]:
    evidence_ids = evidence_ids or []
    tool_result_ids = tool_result_ids or []
    identity = {"claim_type": claim_type, "text": text}
    return {
        "claim_id": _deterministic_id("claim", identity),
        "claim_type": claim_type,
        "text": text,
        "evidence_ids": evidence_ids,
        "tool_result_ids": tool_result_ids,
        **validation_metadata,
    }


def validate_claim(
    claim: dict[str, Any],
    evidence_registry: dict[str, dict[str, Any]],
    tool_result_registry: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    reasons: list[str] = []
    evidence_ids = claim.get("evidence_ids", [])
    tool_result_ids = claim.get("tool_result_ids", [])
    claim_type = claim.get("claim_type")

    valid_evidence = [evidence_registry[eid] for eid in evidence_ids if eid in evidence_registry]
    valid_tools = [tool_result_registry[tid] for tid in tool_result_ids if tid in tool_result_registry]
    if len(valid_evidence) != len(evidence_ids):
        reasons.append("invalid_evidence_id")
    if len(valid_tools) != len(tool_result_ids):
        reasons.append("invalid_tool_result_id")

    if claim_type == "factual" and not valid_evidence:
        reasons.append("factual_claim_requires_evidence")
    if claim_type == "numeric" and not valid_tools:
        reasons.append("numeric_claim_requires_tool_result")
    if claim_type == "conditional" and not valid_evidence and not valid_tools:
        reasons.append("conditional_claim_requires_support")

    required_document_id = claim.get("required_document_id")
    if required_document_id and valid_evidence:
        if not any(card["document_id"] == required_document_id for card in valid_evidence):
            reasons.append("irrelevant_evidence")

    expected_evidence = claim.get("expected_evidence")
    if expected_evidence and valid_evidence:
        expected_fields = (
            "evidence_id",
            "chunk_id",
            "document_id",
            "page",
            "section",
            "source_priority",
        )
        if not any(
            all(
                card.get(field) == expected_evidence[field]
                for field in expected_fields
                if field in expected_evidence
            )
            for card in valid_evidence
        ):
            reasons.append("expected_evidence_mismatch")

    required_terms = claim.get("required_evidence_terms", [])
    if required_terms and valid_evidence:
        if not any(all(term in card["quote"] for term in required_terms) for card in valid_evidence):
            reasons.append("irrelevant_evidence")

    for tool in valid_tools:
        calculation = tool["calculation_result"]
        if "asserted_value" in claim and calculation["value"] != claim["asserted_value"]:
            reasons.append("numeric_value_mismatch")
        if "asserted_rate" in claim and Decimal(calculation["rate"]) != Decimal(
            str(claim["asserted_rate"])
        ):
            reasons.append("numeric_rate_mismatch")
        if claim.get("rule_id") and calculation["rule_id"] != claim["rule_id"]:
            reasons.append("rule_id_mismatch")
        if claim.get("rule_version") and calculation["rule_version"] != claim["rule_version"]:
            reasons.append("rule_version_mismatch")
        calculation_evidence_ids = calculation.get("evidence_ids", [])
        calculation_evidence = [
            evidence_registry[eid]
            for eid in calculation_evidence_ids
            if eid in evidence_registry
        ]
        if len(calculation_evidence) != len(calculation_evidence_ids):
            reasons.append("invalid_calculation_evidence_id")
        if required_document_id and calculation_evidence and not any(
            card["document_id"] == required_document_id for card in calculation_evidence
        ):
            reasons.append("tool_evidence_mismatch")
        expected_citation = claim.get("expected_citation")
        if expected_citation and calculation_evidence and not any(
            card.get("document_id") == expected_citation.get("document_id")
            and card.get("page") == expected_citation.get("page")
            for card in calculation_evidence
        ):
            reasons.append("tool_evidence_mismatch")

    return {
        "claim_id": claim["claim_id"],
        "supported": not reasons,
        "reasons": sorted(set(reasons)),
    }


def validate_claims(
    claims: list[dict[str, Any]],
    evidence_registry: dict[str, dict[str, Any]],
    tool_result_registry: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    validations = [
        validate_claim(claim, evidence_registry, tool_result_registry) for claim in claims
    ]
    unsupported_count = sum(not result["supported"] for result in validations)
    validated_count = len(validations)
    return {
        "validations": validations,
        "unsupported_claim_count": unsupported_count,
        "validated_claim_count": validated_count,
        "unsupported_claim_rate": unsupported_count / validated_count if validated_count else 0.0,
    }
