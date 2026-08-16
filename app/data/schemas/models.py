from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal


ResultType = Literal["exact", "scenario", "conditional"]
ClaimType = Literal["numeric", "factual", "conditional"]


@dataclass(frozen=True)
class Citation:
    document_id: str
    page: int
    quote: str | None = None


@dataclass(frozen=True)
class CalculationResult:
    value: int | None
    rate: Decimal | None
    formula: str
    rule_id: str
    rule_version: str
    citations: list[Citation] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    result_type: ResultType = "exact"
    is_exact: bool = True


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
class ClaimEvidenceLink:
    claim_id: str
    claim_type: ClaimType
    evidence_ids: list[str] = field(default_factory=list)
    tool_result_ids: list[str] = field(default_factory=list)
