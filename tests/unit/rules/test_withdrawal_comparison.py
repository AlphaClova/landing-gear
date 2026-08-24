from decimal import Decimal

import pytest

from app.tools.rule_engine import MissingInputError, RoundingPolicyUndefinedError
from app.tools.withdrawal_comparison import calculate_withdrawal_comparison


def test_production_withdrawal_comparison_uses_rule_results_and_provenance() -> None:
    result = calculate_withdrawal_comparison(300_000_000, 24_000_000)

    assert [scenario.scenario for scenario in result.comparison.scenarios] == [
        "lump_sum",
        "annuity_10_years",
        "annuity_21_plus_years",
    ]
    assert [scenario.tax_value for scenario in result.comparison.scenarios] == [
        24_000_000,
        16_800_000,
        12_000_000,
    ]
    assert [scenario.applicable_rate for scenario in result.comparison.scenarios] == [
        Decimal("1.00"),
        Decimal("0.70"),
        Decimal("0.50"),
    ]
    assert [scenario.difference_vs_lump_sum for scenario in result.comparison.scenarios] == [
        0,
        7_200_000,
        12_000_000,
    ]
    assert [card["evidence_id"] for card in result.evidence] == list(
        dict.fromkeys(
            evidence_id
            for scenario in result.comparison.scenarios
            for evidence_id in scenario.evidence_ids
        )
    )
    assert [(rule.rule_id, rule.rule_version) for rule in result.applied_rules] == [
        ("RETIRE_TAX_RATE_BY_YEAR", "1.0.0")
    ]
    assert result.claim_validation["validated_claim_count"] == 3
    assert result.claim_validation["unsupported_claim_count"] == 0
    assert all(item["supported"] for item in result.claim_validation["validations"])


def test_production_withdrawal_comparison_preserves_missing_input_errors() -> None:
    with pytest.raises(MissingInputError, match="retirement_amount is required"):
        calculate_withdrawal_comparison(None, 24_000_000)
    with pytest.raises(MissingInputError, match="deferred_retirement_tax is required"):
        calculate_withdrawal_comparison(300_000_000, None)


def test_production_withdrawal_comparison_preserves_rounding_error() -> None:
    with pytest.raises(RoundingPolicyUndefinedError, match="fractional-won"):
        calculate_withdrawal_comparison(300_000_000, 1)
