# content-p0-v6-r2 human audit

Human verdicts use final answers and `think_trace` Claim Plan, evidence, Rule Results, Product Facts, constraints, and repair records in `latest.json`.

| Case | Verdict | Basis |
|---|---|---|
| G004 | P1 | Four grounded Solomon Product Facts are rendered; HCX additionally suggests considering the official lower-risk grade. Extra 초단기/wording is non-critical. |
| G008 | PASS | DC responsibility false premise directly corrected from doc10. |
| G021 | PASS | IRP-only 9M eligible-contribution limit and actual credit amount are distinguished. |
| G039 | PASS | Final 24M/16.8M/12M values match three Rule Results. |
| G040 | PASS | DC→IRP and 70/50% structure retained; no tax amount invented. |
| G041 | PASS | `account_receipt` and `retirement_tax` answerable claims both survive repair. |
| G042 | PASS | Three tax-source categories are separated; 3.3–5.5% is explicitly barred from retirement principal. |
| G043 | P1 | Correct general-worker scope and no doc26 application; limitation is duplicated. |
| G045 | PASS | Supplied 500M/40M reused, three Rule Results rendered, only missing product constraints requested. |
| G046 | PASS | Tax claim and DC→IRP→pension-saving transfer claim both retained. |
| G047 | PASS | DB/DC difference and DC→IRP transfer both retained. |
| G048 | P1 | Correct retirement-tax rates; liquidity is locally limited because schedule data is absent. |
| G050 | PASS | Withdrawal-tax intent retained; asks only for expected retirement tax and schedule. |
| G051 | PASS | Three zero Rule Results, zero saving, and decision limitation are all explicit. |
| G053 | PASS | Final 2B/1.4B/1B values match three Rule Results. |
| G054 | P1 | Transfer/product-selection/pension-start stages are separated and missing selection constraints requested; procedural detail remains limited. |
| G055 | PASS | Receipt account, early-withdrawal distinction, retirement tax, and local tax limitation all survive repair. |
| G058 | PASS | Only grounded risk/account Product Facts are stated; no fee or suitability value invented. |
| G059 | PASS | Risk Product Fact plus A-class 0.43% total-fee/cost ratio and 1/2/3/5/10-year cost examples from the matching prospectus are rendered with units kept distinct. |
| G076 | P1 | Future numeric return refused without advice; refusal is duplicated. |
| G079 | P1 | Unsupported one-metric recommendation refused without generic advice; limitation is duplicated. |
| G082 | PASS | IRP and low-risk Product Fact filters are reflected; horizon is recorded `applied=false` and explicitly not claimed as applied. |
| G088 | P1 | Return-only selection refused and missing conditions requested; cost limitation is conservative and somewhat redundant. |
| G091 | PASS | Termination is not converted to insolvency early withdrawal. |
| G092 | PASS | Benefit-receipt documents are not presented as new-account documents. |
| G093 | PASS | DC→IRP→pension-saving order is correct with no tax/fee/advice expansion. |

## Totals and invariants

- PASS: 19
- P1: 7
- P0: 0
- Unsupported numeric/factual: 0/0
- Wrong tax source/scope/procedure: 0/0/0
- Missing requested product field: 0
- Unsupported recommendation constraint claim: 0
- Rule trace valid: true
- Deterministic safe repair: 23 cases
- Terminal fallback: 0 cases
- Answerable subtask lost after repair: 0

Full v4 gate is ready, but Full v4 was not run.
