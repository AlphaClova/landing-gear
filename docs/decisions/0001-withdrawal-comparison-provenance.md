# ADR 0001: Separate calculation, evidence, and API trace ownership

Status: accepted

## Decision

Role B returns calculation/comparison values with deterministic evidence
identifiers. Citation rendering is separate, and A owns tool-call trace IDs and
tool names. Rule versions are selected by B at the scenario boundary and are
included in results for auditability.

## Rationale

This avoids duplicate citations and trace identifiers while preserving an
auditable path from every numeric scenario through its rule/version and source
evidence. Nullable pages prevent DOCX sources without reliable rendered page
boundaries from receiving invented locators.

## Compatibility

B's legacy deterministic tool-result wrapper remains internal to claim
validation tests. It is not exported as a shared schema or emitted by the
withdrawal comparison interface.
