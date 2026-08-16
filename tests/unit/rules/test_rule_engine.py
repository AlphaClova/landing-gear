from decimal import Decimal

import pytest

from app.tools.rule_engine import (
    DEFAULT_RETIREMENT_TAX_RULE_VERSION,
    MissingInputError,
    RETIREMENT_TAX_RULES,
    RoundingPolicyUndefinedError,
    UnknownRuleVersionError,
    calc_retirement_pension_tax,
    retirement_tax_rate_by_year,
)


@pytest.mark.parametrize(
    "year,expected",
    [
        (10, Decimal("0.70")),
        (11, Decimal("0.60")),
        (20, Decimal("0.60")),
        (21, Decimal("0.50")),
    ],
)
def test_retirement_tax_rate_boundaries(year: int, expected: Decimal) -> None:
    assert retirement_tax_rate_by_year(year) == expected


@pytest.mark.parametrize(
    "year,rate,value",
    [
        (10, Decimal("0.70"), 700_000),
        (11, Decimal("0.60"), 600_000),
        (20, Decimal("0.60"), 600_000),
        (21, Decimal("0.50"), 500_000),
    ],
)
def test_retirement_tax_boundary_calculations(year: int, rate: Decimal, value: int) -> None:
    result = calc_retirement_pension_tax(1_000_000, year)
    assert result.rate == rate
    assert result.value == value


def test_retirement_tax_year_10() -> None:
    assert calc_retirement_pension_tax(1_000_000, 10).rate == Decimal("0.70")


def test_retirement_tax_year_11() -> None:
    assert calc_retirement_pension_tax(1_000_000, 11).rate == Decimal("0.60")


def test_retirement_tax_year_20() -> None:
    assert calc_retirement_pension_tax(1_000_000, 20).rate == Decimal("0.60")


def test_retirement_tax_year_21() -> None:
    assert calc_retirement_pension_tax(1_000_000, 21).rate == Decimal("0.50")


def test_calc_retirement_pension_tax_fields() -> None:
    result = calc_retirement_pension_tax(
        deferred_retirement_tax=24_000_000,
        actual_pension_year=21,
    )

    assert result.value == 12_000_000
    assert result.rate == Decimal("0.50")
    assert result.rule_id == "RETIRE_TAX_RATE_BY_YEAR"
    assert result.rule_version == "1.0.0"
    assert result.citations[0].document_id == "doc51"
    assert result.citations[0].page == 2
    assert result.is_exact is True


def test_invalid_year_raises_missing_input() -> None:
    with pytest.raises(MissingInputError):
        retirement_tax_rate_by_year(0)


def test_retirement_tax_rule_source_is_doc51() -> None:
    rule = RETIREMENT_TAX_RULES[DEFAULT_RETIREMENT_TAX_RULE_VERSION]
    assert rule["source"]["document_id"] == "doc51"
    assert rule["source"]["page"] == 2
    assert rule["source"]["section"] == "연금수령시 퇴직소득세 절세혜택"


def test_retirement_tax_rule_source_priority_is_zero() -> None:
    rule = RETIREMENT_TAX_RULES[DEFAULT_RETIREMENT_TAX_RULE_VERSION]
    assert rule["source_priority"] == 0


def test_retirement_tax_missing_tax() -> None:
    with pytest.raises(MissingInputError, match="deferred_retirement_tax is required"):
        calc_retirement_pension_tax(None, 10)


def test_retirement_tax_missing_year() -> None:
    with pytest.raises(MissingInputError, match="actual_pension_year is required"):
        calc_retirement_pension_tax(1_000_000, None)


def test_retirement_tax_negative_tax() -> None:
    with pytest.raises(MissingInputError, match="must be >= 0"):
        calc_retirement_pension_tax(-1, 10)


def test_retirement_tax_invalid_year() -> None:
    with pytest.raises(MissingInputError, match="must be >= 1"):
        calc_retirement_pension_tax(1_000_000, 0)


def test_retirement_tax_unknown_version() -> None:
    with pytest.raises(UnknownRuleVersionError, match="unknown-version"):
        calc_retirement_pension_tax(1_000_000, 10, "unknown-version")


def test_retirement_tax_rule_version_preserved() -> None:
    result = calc_retirement_pension_tax(
        1_000_000, 10, DEFAULT_RETIREMENT_TAX_RULE_VERSION
    )
    rule = RETIREMENT_TAX_RULES[result.rule_version]
    assert result.rule_version == DEFAULT_RETIREMENT_TAX_RULE_VERSION
    assert rule["effective_from"] is None
    assert rule["valid_to"] is None
    assert set(RETIREMENT_TAX_RULES) == {DEFAULT_RETIREMENT_TAX_RULE_VERSION}


def test_retirement_tax_result_has_formula() -> None:
    result = calc_retirement_pension_tax(1_000_000, 10)
    assert result.formula == "1000000 * 0.70"


def test_retirement_tax_result_has_rule_id() -> None:
    result = calc_retirement_pension_tax(1_000_000, 10)
    assert result.rule_id == "RETIRE_TAX_RATE_BY_YEAR"


def test_retirement_tax_result_has_citation() -> None:
    result = calc_retirement_pension_tax(1_000_000, 10)
    assert result.citations
    assert result.citations[0].document_id == "doc51"
    assert result.citations[0].page == 2
    assert "퇴직소득세 절세혜택" in (result.citations[0].quote or "")


def test_retirement_tax_deterministic() -> None:
    first = calc_retirement_pension_tax(12_345_678, 21)
    second = calc_retirement_pension_tax(12_345_678, 21)
    assert first == second


def test_fractional_won_is_not_silently_rounded_down() -> None:
    with pytest.raises(RoundingPolicyUndefinedError, match="fractional-won"):
        calc_retirement_pension_tax(1, 10)


def test_integral_won_result_remains_exact() -> None:
    result = calc_retirement_pension_tax(10_000_000, 21)
    assert result.value == 5_000_000
    assert result.rate == Decimal("0.50")
    assert result.is_exact is True


@pytest.mark.parametrize("year", [1, 9, 19, 100_000])
def test_retirement_tax_additional_valid_years(year: int) -> None:
    result = calc_retirement_pension_tax(1_000_000, year)
    assert result.value in {700_000, 600_000, 500_000}
