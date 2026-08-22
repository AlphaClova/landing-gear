from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Callable

from app.data.schemas.models import RetrievalHit
from app.tools.evidence_builder import (
    build_claim_record,
    build_evidence_card,
    build_internal_tool_result_record,
    validate_claims,
)
from app.tools.rule_engine import (
    MissingInputError,
    RoundingPolicyUndefinedError,
    UnknownRuleVersionError,
    calc_retirement_lump_sum_tax,
    calc_retirement_pension_tax,
    calculate_retirement_tax_scenario,
)
from scripts.build_index import load_chunks


OUTPUT = Path("app/data/processed/withdrawal_comparison_sample.json")
ERROR_OUTPUT = Path("app/data/processed/withdrawal_comparison_error_samples.json")


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def _capture_error(case: str, inputs: dict[str, Any], call: Callable[[], Any]) -> dict[str, Any]:
    try:
        call()
    except (MissingInputError, RoundingPolicyUndefinedError, UnknownRuleVersionError) as error:
        return {
            "case": case,
            "inputs": inputs,
            "error_type": type(error).__name__,
            "message": str(error),
            "api_error_family": "MISSING_INPUT"
            if isinstance(error, MissingInputError)
            else "RULE_ERROR",
        }
    raise AssertionError(f"{case} did not raise")


def main() -> None:
    chunks = load_chunks(Path("app/data/processed/chunks.jsonl"))
    chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    evidence_ids = ["doc51-p001-t004-41a054df8c", "doc51-p002-t016-389a14afe5"]
    evidence = []
    for evidence_id in evidence_ids:
        chunk = chunks_by_id[evidence_id]
        evidence.append(
            build_evidence_card(
                RetrievalHit(chunk.chunk_id, 1.0, chunk.document_id, chunk.page, chunk.text),
                chunk,
            )
        )
    evidence_registry = {card["evidence_id"]: card for card in evidence}

    comparison = calculate_retirement_tax_scenario(300_000_000, 24_000_000)
    calculations = [
        calc_retirement_lump_sum_tax(24_000_000),
        calc_retirement_pension_tax(24_000_000, 10),
        calc_retirement_pension_tax(24_000_000, 21),
    ]
    internal_records = [build_internal_tool_result_record(item) for item in calculations]
    claims = []
    for scenario, calculation, record in zip(
        comparison.scenarios, calculations, internal_records, strict=True
    ):
        claims.append(
            build_claim_record(
                "numeric",
                f"{scenario.scenario}: tax={scenario.tax_value}, rate={scenario.applicable_rate}",
                evidence_ids=calculation.evidence_ids,
                tool_result_ids=[record["tool_result_id"]],
                required_document_id="doc51",
                asserted_value=scenario.tax_value,
                asserted_rate=str(scenario.applicable_rate),
                rule_id=scenario.rule_id,
                rule_version=scenario.rule_version,
            )
        )
    validation = validate_claims(
        claims,
        evidence_registry,
        {record["tool_result_id"]: record for record in internal_records},
    )
    output = {
        "inputs": {"retirement_amount": 300_000_000, "deferred_retirement_tax": 24_000_000},
        "comparison": asdict(comparison),
        "evidence": evidence,
        "applied_rules": [
            {"rule_id": row.rule_id, "rule_version": row.rule_version}
            for row in comparison.scenarios
        ],
        "claim_validation": validation,
    }
    OUTPUT.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )

    errors = [
        _capture_error(
            "missing_deferred_retirement_tax",
            {"retirement_amount": 300_000_000, "deferred_retirement_tax": None},
            lambda: calculate_retirement_tax_scenario(300_000_000, None),
        ),
        _capture_error(
            "missing_actual_pension_year",
            {"deferred_retirement_tax": 24_000_000, "actual_pension_year": None},
            lambda: calc_retirement_pension_tax(24_000_000, None),
        ),
        _capture_error(
            "fractional_won_without_rounding_policy",
            {"deferred_retirement_tax": 1, "actual_pension_year": 10},
            lambda: calc_retirement_pension_tax(1, 10),
        ),
        _capture_error(
            "unknown_explicit_rule_version",
            {"deferred_retirement_tax": 24_000_000, "actual_pension_year": 10,
             "rule_version": "unknown-version"},
            lambda: calc_retirement_pension_tax(24_000_000, 10, "unknown-version"),
        ),
    ]
    ERROR_OUTPUT.write_text(
        json.dumps({"errors": errors}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(output, ensure_ascii=False, indent=2, default=_json_default))


if __name__ == "__main__":
    main()
