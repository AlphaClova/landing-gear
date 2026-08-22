# Withdrawal comparison contract

This contract records the latest agreement between roles A, B, and C for the
retirement-tax withdrawal comparison.

- `Citation.page` is nullable. PDF pages and PPTX slide numbers are 1-based;
  DOCX pages are present only when a reliable rendered boundary exists. A
  fabricated page 0 or 1 is prohibited.
- `CalculationResult` contains calculation data and `evidence_ids`, not nested
  citations. Evidence resolves those identifiers to API-level citations.
- Tool call IDs and names belong to A's `ToolCallTrace`. B may keep a clearly
  internal deterministic result record for claim-validation regressions, but it
  is not an A-facing result contract.
- Agent/scenario calls do not accept a rule version. B's registry selects the
  deterministic current valid version and returns the applied `rule_version`.
  Explicit versions remain supported by low-level calculation calls.
- `ComparisonResult.unit` is `KRW`; monetary values are integer won and rates
  are decimals. Stable scenario IDs are `lump_sum`, `annuity_10_years`, and
  `annuity_21_plus_years`.
- Missing assumptions and warnings are represented by empty lists, never null.
- API citations remain top-level. Comparison scenarios connect to them through
  `evidence_ids` and do not duplicate Citation objects.

The comparison is an exact retirement-income-tax comparison only. It does not
model returns, fees, inflation, health insurance, financial income, or net
proceeds.
