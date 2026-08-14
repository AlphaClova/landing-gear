from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.data.schemas.models import CalculationResult, Citation, RuleDefinition


class RuleEngineError(Exception):
    """Base error type for deterministic calculation failures."""


class MissingInputError(RuleEngineError):
    """Raised when required inputs are missing or invalid."""


class UnknownRuleVersionError(RuleEngineError):
    """Raised when a requested rule version does not exist."""


@dataclass(frozen=True)
class ComparisonRow:
    scenario: str
    tax_result: CalculationResult


RETIREMENT_TAX_RULES: dict[str, RuleDefinition] = {
    "2026-01-01": RuleDefinition(
        rule_id="RETIRE_TAX_RATE_BY_YEAR",
        version="2026-01-01",
        brackets=[
            (10, Decimal("0.70")),
            (20, Decimal("0.60")),
            (10_000, Decimal("0.50")),
        ],
        source=Citation(document_id="doc51", page=3),
    )
}


def _get_rule(rule_version: str) -> RuleDefinition:
    rule = RETIREMENT_TAX_RULES.get(rule_version)
    if rule is None:
        raise UnknownRuleVersionError(f"Unknown rule_version: {rule_version}")
    return rule


def retirement_tax_rate_by_year(actual_pension_year: int, rule_version: str = "2026-01-01") -> Decimal:
    if actual_pension_year < 1:
        raise MissingInputError("actual_pension_year must be >= 1")

    rule = _get_rule(rule_version)
    for upper_bound, rate in rule.brackets:
        if actual_pension_year <= upper_bound:
            return rate

    # Should never happen because of the fallback bracket.
    raise RuleEngineError("No tax bracket matched for actual_pension_year")


def calc_retirement_pension_tax(
    deferred_retirement_tax: int,
    actual_pension_year: int,
    rule_version: str = "2026-01-01",
) -> CalculationResult:
    if deferred_retirement_tax < 0:
        raise MissingInputError("deferred_retirement_tax must be >= 0")

    rate = retirement_tax_rate_by_year(actual_pension_year, rule_version)
    value = int(Decimal(deferred_retirement_tax) * rate)
    rule = _get_rule(rule_version)

    return CalculationResult(
        value=value,
        rate=rate,
        formula=f"{deferred_retirement_tax} * {rate}",
        rule_id=rule.rule_id,
        rule_version=rule.version,
        citations=[rule.source],
        assumptions=[],
        warnings=[],
        result_type="exact",
        is_exact=True,
    )


def calc_retirement_lump_sum_tax(deferred_retirement_tax: int, rule_version: str = "2026-01-01") -> CalculationResult:
    if deferred_retirement_tax < 0:
        raise MissingInputError("deferred_retirement_tax must be >= 0")

    rule = _get_rule(rule_version)
    return CalculationResult(
        value=deferred_retirement_tax,
        rate=Decimal("1.00"),
        formula=f"{deferred_retirement_tax} * 1.00",
        rule_id=rule.rule_id,
        rule_version=rule.version,
        citations=[rule.source],
        assumptions=[],
        warnings=[],
        result_type="exact",
        is_exact=True,
    )


def compare_lump_sum_vs_pension(
    deferred_retirement_tax: int,
    pension_year_candidates: list[int],
    rule_version: str = "2026-01-01",
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
