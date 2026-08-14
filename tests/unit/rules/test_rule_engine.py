from decimal import Decimal

import pytest

from app.tools.rule_engine import (
    MissingInputError,
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


def test_calc_retirement_pension_tax_fields() -> None:
    result = calc_retirement_pension_tax(
        deferred_retirement_tax=24_000_000,
        actual_pension_year=21,
    )

    assert result.value == 12_000_000
    assert result.rate == Decimal("0.50")
    assert result.rule_id == "RETIRE_TAX_RATE_BY_YEAR"
    assert result.rule_version == "2026-01-01"
    assert result.citations[0].document_id == "doc51"
    assert result.citations[0].page == 3
    assert result.is_exact is True


def test_invalid_year_raises_missing_input() -> None:
    with pytest.raises(MissingInputError):
        retirement_tax_rate_by_year(0)
