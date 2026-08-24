from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Callable

from app.tools.rule_engine import (
    MissingInputError,
    RoundingPolicyUndefinedError,
    UnknownRuleVersionError,
    calc_retirement_pension_tax,
    calculate_retirement_tax_scenario,
)
from app.tools.withdrawal_comparison import calculate_withdrawal_comparison


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
    result = calculate_withdrawal_comparison(300_000_000, 24_000_000)
    output = {
        "inputs": {"retirement_amount": 300_000_000, "deferred_retirement_tax": 24_000_000},
        **asdict(result),
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
