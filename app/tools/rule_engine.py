from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import json
from pathlib import Path
from typing import Any

from app.data.schemas.models import CalculationResult, ComparisonResult, ComparisonScenario


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


def _load_retirement_tax_rules() -> dict[str, dict[str, Any]]:
    rule_path = RULES_DIR / "retirement_tax_rate_by_year.json"
    rule = json.loads(rule_path.read_text(encoding="utf-8"))
    return {rule["version"]: rule}


RETIREMENT_TAX_RULES = _load_retirement_tax_rules()


def select_retirement_tax_rule_version() -> str:
    """Select the sole currently valid verified version deterministically."""
    valid = [
        version
        for version, rule in RETIREMENT_TAX_RULES.items()
        if rule.get("effective_from") is None and rule.get("valid_to") is None
    ]
    if len(valid) != 1:
        raise RuleEngineError(f"Expected one current retirement-tax rule, found {len(valid)}")
    return valid[0]


DEFAULT_RETIREMENT_TAX_RULE_VERSION = select_retirement_tax_rule_version()


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
    return CalculationResult(
        value=value,
        rate=rate,
        formula=f"{deferred_retirement_tax} * {rate}",
        rule_id=rule["rule_id"],
        rule_version=rule["version"],
        evidence_ids=[rule["source"]["evidence_id"]],
        assumptions=[],
        warnings=[],
        result_type="exact",
        is_exact=True,
    )


def calc_retirement_lump_sum_tax(
    deferred_retirement_tax: int | None,
    rule_version: str = DEFAULT_RETIREMENT_TAX_RULE_VERSION,
) -> CalculationResult:
    if deferred_retirement_tax is None:
        raise MissingInputError("deferred_retirement_tax is required")
    if not isinstance(deferred_retirement_tax, int) or isinstance(deferred_retirement_tax, bool):
        raise MissingInputError("deferred_retirement_tax must be an integer")
    if deferred_retirement_tax < 0:
        raise MissingInputError("deferred_retirement_tax must be >= 0")

    rule = _get_rule(rule_version)
    return CalculationResult(
        value=deferred_retirement_tax,
        rate=Decimal("1.00"),
        formula=f"{deferred_retirement_tax} * 1.00",
        rule_id=rule["rule_id"],
        rule_version=rule["version"],
        evidence_ids=[rule["lump_sum_source"]["evidence_id"]],
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


def calculate_retirement_tax_scenario(
    retirement_amount: int | None,
    deferred_retirement_tax: int | None,
) -> ComparisonResult:
    """Build the A/C withdrawal comparison without accepting a rule version."""
    if retirement_amount is None:
        raise MissingInputError("retirement_amount is required")
    if not isinstance(retirement_amount, int) or isinstance(retirement_amount, bool):
        raise MissingInputError("retirement_amount must be an integer")
    if retirement_amount < 0:
        raise MissingInputError("retirement_amount must be >= 0")

    rule_version = select_retirement_tax_rule_version()
    lump_sum = calc_retirement_lump_sum_tax(deferred_retirement_tax, rule_version)
    year_10 = calc_retirement_pension_tax(deferred_retirement_tax, 10, rule_version)
    year_21 = calc_retirement_pension_tax(deferred_retirement_tax, 21, rule_version)
    assert lump_sum.value is not None and year_10.value is not None and year_21.value is not None

    def scenario(scenario_id: str, result: CalculationResult) -> ComparisonScenario:
        assert result.value is not None and result.rate is not None
        return ComparisonScenario(
            scenario=scenario_id,  # type: ignore[arg-type]
            tax_value=result.value,
            applicable_rate=result.rate,
            difference_vs_lump_sum=lump_sum.value - result.value,
            formula=result.formula,
            rule_id=result.rule_id,
            rule_version=result.rule_version,
            evidence_ids=result.evidence_ids,
            assumptions=result.assumptions,
            warnings=result.warnings,
        )

    return ComparisonResult(
        scenarios=[
            scenario("lump_sum", lump_sum),
            scenario("annuity_10_years", year_10),
            scenario("annuity_21_plus_years", year_21),
        ]
    )
