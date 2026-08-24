from dataclasses import asdict
from decimal import Decimal

from app.data.schemas.models import CalculationResult, Citation, ComparisonScenario


def test_citation_page_accepts_integer_and_null_without_coercion() -> None:
    assert Citation("doc-pdf", 3).page == 3
    citation = Citation("doc-docx", None)
    assert citation.page is None
    assert asdict(citation)["page"] is None


def test_empty_lists_are_not_null() -> None:
    calculation = CalculationResult(None, None, "", "RULE", "1.0.0")
    scenario = ComparisonScenario(
        "lump_sum", 0, Decimal("1.0"), 0, "0 * 1.0",
        "RULE", "1.0.0", ["evidence-1"]
    )
    assert calculation.assumptions == calculation.warnings == []
    assert scenario.assumptions == scenario.warnings == []
    assert not hasattr(calculation, "citations")
