from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal


ResultType = Literal["exact", "scenario", "conditional"]
ClaimType = Literal["numeric", "factual", "conditional"]


@dataclass(frozen=True)
class Citation:
    document_id: str
    page: int | None
    quote: str | None = None


@dataclass(frozen=True)
class CalculationResult:
    value: int | None
    rate: Decimal | None
    formula: str
    rule_id: str
    rule_version: str
    evidence_ids: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    result_type: ResultType = "exact"
    is_exact: bool = True


ScenarioId = Literal["lump_sum", "annuity_10_years", "annuity_21_plus_years"]


@dataclass(frozen=True)
class ComparisonScenario:
    scenario: ScenarioId
    tax_value: int
    applicable_rate: Decimal
    difference_vs_lump_sum: int
    formula: str
    rule_id: str
    rule_version: str
    evidence_ids: list[str]
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ComparisonResult:
    scenarios: list[ComparisonScenario]
    result_type: Literal["exact"] = "exact"
    unit: Literal["KRW"] = "KRW"


@dataclass(frozen=True)
class AppliedRule:
    rule_id: str
    rule_version: str


@dataclass(frozen=True)
class WithdrawalComparisonResult:
    """B-owned result that an A/C adapter can map to its response schema."""

    comparison: ComparisonResult
    evidence: list[dict[str, Any]]
    applied_rules: list[AppliedRule]
    claim_validation: dict[str, Any]


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    document_id: str
    title: str
    page: int | None
    section: str
    text: str
    effective_from: str
    valid_to: str | None
    topics: list[str] = field(default_factory=list)
    account_types: list[str] = field(default_factory=list)
    source_type: str = "provided"
    source_priority: int = 0


@dataclass(frozen=True)
class RuleDefinition:
    rule_id: str
    version: str
    brackets: list[tuple[int, Decimal]]
    source: Citation


@dataclass(frozen=True)
class RetrievalHit:
    chunk_id: str
    score: float
    document_id: str
    page: int | None
    quote: str


@dataclass(frozen=True)
class EvidenceResult:
    """B-owned retrieval result with source provenance preserved."""

    evidence_id: str
    chunk_id: str
    document_id: str
    page: int | None
    section: str
    excerpt: str
    source: str
    source_priority: int
    score: float


@dataclass(frozen=True)
class ClaimEvidenceLink:
    claim_id: str
    claim_type: ClaimType
    evidence_ids: list[str] = field(default_factory=list)
    tool_result_ids: list[str] = field(default_factory=list)
