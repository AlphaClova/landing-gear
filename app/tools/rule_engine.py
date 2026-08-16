from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import json
from pathlib import Path
from typing import Any

from app.data.schemas.models import CalculationResult, Citation


class RuleEngineError(Exception):
    """Base error type for deterministic calculation failures."""


class MissingInputError(RuleEngineError):
    """Raised when required inputs are missing or invalid."""


class UnknownRuleVersionError(RuleEngineError):
    """Raised when a requested rule version does not exist."""


class RoundingPolicyUndefinedError(RuleEngineError):
    """Raised when a fractional-won result has no source-backed rounding policy."""


@dataclass(frozen=True)
class ComparisonRow:
    scenario: str
    tax_result: CalculationResult


RULES_DIR = Path(__file__).resolve().parents[1] / "data" / "rules"
DEFAULT_RETIREMENT_TAX_RULE_VERSION = "1.0.0"


def _load_retirement_tax_rules() -> dict[str, dict[str, Any]]:
    rule_path = RULES_DIR / "retirement_tax_rate_by_year.json"
    rule = json.loads(rule_path.read_text(encoding="utf-8"))
    return {rule["version"]: rule}


RETIREMENT_TAX_RULES = _load_retirement_tax_rules()


def _get_rule(rule_version: str) -> dict[str, Any]:
    rule = RETIREMENT_TAX_RULES.get(rule_version)
    if rule is None:
        raise UnknownRuleVersionError(f"Unknown rule_version: {rule_version}")
    return rule


def retirement_tax_rate_by_year(
    actual_pension_year: int | None,
    rule_version: str = DEFAULT_RETIREMENT_TAX_RULE_VERSION,
) -> Decimal:
    if actual_pension_year is None:
        raise MissingInputError("actual_pension_year is required")
    if not isinstance(actual_pension_year, int) or isinstance(actual_pension_year, bool):
        raise MissingInputError("actual_pension_year must be an integer")
    if actual_pension_year < 1:
        raise MissingInputError("actual_pension_year must be >= 1")

    rule = _get_rule(rule_version)
    for bracket in rule["parameters"]["brackets"]:
        lower_bound = bracket["min_year"]
        upper_bound = bracket["max_year"]
        if actual_pension_year >= lower_bound and (
            upper_bound is None or actual_pension_year <= upper_bound
        ):
            return Decimal(bracket["rate"])

    # Should never happen because of the fallback bracket.
    raise RuleEngineError("No tax bracket matched for actual_pension_year")


def calc_retirement_pension_tax(
    deferred_retirement_tax: int | None,
    actual_pension_year: int | None,
    rule_version: str = DEFAULT_RETIREMENT_TAX_RULE_VERSION,
) -> CalculationResult:
    if deferred_retirement_tax is None:
        raise MissingInputError("deferred_retirement_tax is required")
    if not isinstance(deferred_retirement_tax, int) or isinstance(deferred_retirement_tax, bool):
        raise MissingInputError("deferred_retirement_tax must be an integer")
    if deferred_retirement_tax < 0:
        raise MissingInputError("deferred_retirement_tax must be >= 0")

    rate = retirement_tax_rate_by_year(actual_pension_year, rule_version)
    decimal_value = Decimal(deferred_retirement_tax) * rate
    if decimal_value != decimal_value.to_integral_value():
        raise RoundingPolicyUndefinedError(
            "fractional-won result cannot be converted without a documented rounding policy"
        )
    value = int(decimal_value)
    rule = _get_rule(rule_version)
    source = rule["source"]

    return CalculationResult(
        value=value,
        rate=rate,
        formula=f"{deferred_retirement_tax} * {rate}",
        rule_id=rule["rule_id"],
        rule_version=rule["version"],
        citations=[
            Citation(
                document_id=source["document_id"],
                page=source["page"],
                quote=f"{source['section']}: {source['quote']}",
            )
        ],
        assumptions=[],
        warnings=[],
        result_type="exact",
        is_exact=True,
    )


def calc_retirement_lump_sum_tax(
    deferred_retirement_tax: int,
    rule_version: str = DEFAULT_RETIREMENT_TAX_RULE_VERSION,
) -> CalculationResult:
    if deferred_retirement_tax < 0:
        raise MissingInputError("deferred_retirement_tax must be >= 0")

    rule = _get_rule(rule_version)
    return CalculationResult(
        value=deferred_retirement_tax,
        rate=Decimal("1.00"),
        formula=f"{deferred_retirement_tax} * 1.00",
        rule_id=rule["rule_id"],
        rule_version=rule["version"],
        citations=[
            Citation(
                document_id=rule["source"]["document_id"],
                page=rule["source"]["page"],
                quote=f"{rule['source']['section']}: {rule['source']['quote']}",
            )
        ],
        assumptions=[],
        warnings=[],
        result_type="exact",
        is_exact=True,
    )


def compare_lump_sum_vs_pension(
    deferred_retirement_tax: int,
    pension_year_candidates: list[int],
    rule_version: str = DEFAULT_RETIREMENT_TAX_RULE_VERSION,
) -> list[ComparisonRow]:
    if not pension_year_candidates:
        raise MissingInputError("pension_year_candidates must not be empty")

    rows: list[ComparisonRow] = [
        ComparisonRow(
            scenario="lump_sum",
            tax_result=calc_retirement_lump_sum_tax(deferred_retirement_tax, rule_version),
        )
    ]

    for pension_year in pension_year_candidates:
        rows.append(
            ComparisonRow(
                scenario=f"pension_year_{pension_year}",
                tax_result=calc_retirement_pension_tax(
                    deferred_retirement_tax=deferred_retirement_tax,
                    actual_pension_year=pension_year,
                    rule_version=rule_version,
                ),
            )
        )
    return rows
