from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.data.schemas.models import (
    AppliedRule,
    CalculationResult,
    Chunk,
    RetrievalHit,
    WithdrawalComparisonResult,
)
from app.tools.evidence_builder import (
    EvidenceMappingError,
    build_claim_record,
    build_evidence_card,
    build_internal_tool_result_record,
    validate_claims,
)
from app.tools.rule_engine import (
    calc_retirement_lump_sum_tax,
    calc_retirement_pension_tax,
    calculate_retirement_tax_scenario,
)


DEFAULT_CHUNKS_PATH = Path(__file__).resolve().parents[1] / "data" / "processed" / "chunks.jsonl"


def _load_chunks(path: Path) -> dict[str, Chunk]:
    chunks: dict[str, Chunk] = {}
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            chunk = Chunk(
                chunk_id=row["chunk_id"],
                document_id=row["document_id"],
                title=row["title"],
                page=row.get("page"),
                section=row["section"],
                text=row.get("content", row.get("text", "")),
                effective_from=row.get("effective_from"),
                valid_to=row.get("valid_to"),
                topics=row.get("topics", [row.get("topic", "")]),
                account_types=row.get("account_types", [row.get("account_type", "")]),
                source_type=row.get("source_type", "provided"),
                source_priority=row.get("source_priority", 0),
            )
            chunks[chunk.chunk_id] = chunk
    return chunks


def _resolve_evidence(
    calculations: list[CalculationResult],
    chunks_by_id: dict[str, Chunk],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    evidence_ids = list(
        dict.fromkeys(
            evidence_id
            for calculation in calculations
            for evidence_id in calculation.evidence_ids
        )
    )
    missing_ids = [evidence_id for evidence_id in evidence_ids if evidence_id not in chunks_by_id]
    if missing_ids:
        raise EvidenceMappingError(f"calculation evidence IDs not found: {', '.join(missing_ids)}")

    evidence = []
    for evidence_id in evidence_ids:
        chunk = chunks_by_id[evidence_id]
        hit = RetrievalHit(
            chunk_id=chunk.chunk_id,
            score=1.0,
            document_id=chunk.document_id,
            page=chunk.page,
            quote=chunk.text,
        )
        evidence.append(build_evidence_card(hit, chunk))
    return evidence, {card["evidence_id"]: card for card in evidence}


def calculate_withdrawal_comparison(
    retirement_amount: int | None,
    deferred_retirement_tax: int | None,
) -> WithdrawalComparisonResult:
    """Build B's complete withdrawal comparison from rule and provenance outputs."""
    comparison = calculate_retirement_tax_scenario(
        retirement_amount,
        deferred_retirement_tax,
    )
    calculations = [
        calc_retirement_lump_sum_tax(deferred_retirement_tax),
        calc_retirement_pension_tax(deferred_retirement_tax, 10),
        calc_retirement_pension_tax(deferred_retirement_tax, 21),
    ]
    evidence, evidence_registry = _resolve_evidence(calculations, _load_chunks(DEFAULT_CHUNKS_PATH))

    internal_records = [build_internal_tool_result_record(result) for result in calculations]
    claims = []
    for scenario, calculation, record in zip(
        comparison.scenarios, calculations, internal_records, strict=True
    ):
        calculation_evidence = [evidence_registry[eid] for eid in calculation.evidence_ids]
        document_ids = {card["document_id"] for card in calculation_evidence}
        required_document_id = next(iter(document_ids)) if len(document_ids) == 1 else None
        expected_citation = (
            {
                "document_id": calculation_evidence[0]["document_id"],
                "page": calculation_evidence[0]["page"],
            }
            if len(calculation_evidence) == 1
            else None
        )
        claims.append(
            build_claim_record(
                "numeric",
                f"{scenario.scenario}: tax={scenario.tax_value}, rate={scenario.applicable_rate}",
                evidence_ids=calculation.evidence_ids,
                tool_result_ids=[record["tool_result_id"]],
                required_document_id=required_document_id,
                expected_citation=expected_citation,
                asserted_value=scenario.tax_value,
                asserted_rate=str(scenario.applicable_rate),
                rule_id=scenario.rule_id,
                rule_version=scenario.rule_version,
            )
        )

    claim_validation = validate_claims(
        claims,
        evidence_registry,
        {record["tool_result_id"]: record for record in internal_records},
    )
    applied_rules = [
        AppliedRule(rule_id=rule_id, rule_version=rule_version)
        for rule_id, rule_version in dict.fromkeys(
            (scenario.rule_id, scenario.rule_version) for scenario in comparison.scenarios
        )
    ]
    return WithdrawalComparisonResult(
        comparison=comparison,
        evidence=evidence,
        applied_rules=applied_rules,
        claim_validation=claim_validation,
    )
