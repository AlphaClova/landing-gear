# Landing Gear
은퇴 자금의 안전한 착륙을 돕는 연금 의사결정 Agent

## Role B Bootstrap (Data, Retrieval, Rule Engine)

This repository is initialized for the `feature/data-rule` branch workflow.

### Implemented in this bootstrap

- Deterministic rule engine baseline for retirement pension tax (70/60/50).
- BM25 retriever baseline with metadata filters (topic, account type, effective date).
- Product SQL query baseline (SQLite).
- Claim-Evidence mapping guard to block unsupported numeric/factual claims.
- Unit tests for rule boundaries, retrieval filtering, and evidence mapping.
- Utility scripts for parsing, index build validation, product seeding, and unsupported claim evaluation.

### Folder Scope for Role B

- `app/tools/`
- `app/data/`
- `scripts/`
- `tests/unit/rules/`
- `tests/unit/retrieval/`

### Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. pytest tests/unit/rules tests/unit/retrieval tests/unit/evidence -q
```

### Next Required Work (Role B)

1. Replace placeholder parsing with production parsers for PDF/DOCX/XLSX and preserve table rows.
2. Populate processed chunk metadata from source docs (`document_id`, `page`, `effective_from`, `valid_to`).
3. Add rule versions for 2025/2026 and regression tests to prevent mixed-version outputs.
4. Implement pension receipt limit rule from validated source equations.
5. Add claim-evidence golden tests and unsupported claim rate checks.

