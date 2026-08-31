# Full v3 clean single-run report

## Full v3 single run

- HTTP success: 116/120
- terminal client timeout: 2 (G086, G090)
- API 502: 2 (G072, G089)
- evaluator-visible HCX invocation/success: 116/116 successful API responses
- server-observed HCX case invocation: 120/120
- server-observed case transport success: 118/120
- PASS / FAIL / MANUAL_REVIEW: 81 / 4 / 35
- Production-valid: false

No failed case was retried by the evaluator or replaced after the run.

## HCX transport

- Transport attempts: 154
- Retry attempts: 8
- Upstream statuses: 200 = 144, 429 = 6
- Upstream 5xx: 0
- ReadTimeout: 4
- Other transport errors: 0
- Final exhausted attempts: 2
- Retry-After present: 0

G072 and G089 each received three upstream 429 responses. The HCX client exhausted its configured retries and the application translated each terminal `upstream_error` to API 502. G086 recovered on its second HCX transport attempt and G090 on its third, but both exceeded the evaluator's 12-second request timeout. G094 recovered on its second attempt within the evaluator deadline.

## Quality

The four automatic FAIL results are transport failures. Among completed responses, the automatic evaluator found:

- unsupported numeric: 0
- unsupported factual: 0
- wrong number: 0
- wrong evidence: 0
- false premise failure: 0
- clarification failure: 0
- safety failure: 0
- irrelevant evidence: requires human review; no dedicated automatic detector

Fallback was used in 21/120 cases (17.5%): G008, G011, G022, G023, G026, G028, G029, G031, G033, G041, G042, G046, G049, G051, G056, G057, G059, G065, G076, G097, G107.

G051 again failed grounding verification because generated drafts added unsupported advice/numbers and omitted required limitations. G076 again added unsupported advice and omitted the required limitation. Both are marked `HIGH_PRIORITY_REVIEW=true`.

## Manual review

- MANUAL_REVIEW cases: 35
- Stratified automatic-PASS samples: 15
- Total human-review cases: 50

Combined and conditional-recommendation cases had no automatic PASS candidates because all completed cases in those categories were already MANUAL_REVIEW; they are represented through the complete manual set. The PASS sample covers institution, tax, product comparison, procedure, safety, and out-of-scope cases.

## Regression

- Full pytest: 193 passed in 108.13s
- Focused post-report tests: 8 passed
- `git diff --check`: pass
- Artifact secret scan: pass

## Submission values

```text
FULL_V3_HTTP_SUCCESS=116/120
FULL_V3_TIMEOUT=2
FULL_V3_502=2
FULL_V3_PASS=81
FULL_V3_FAIL=4
FULL_V3_MANUAL_REVIEW=35
HCX_INVOCATION=116/120 evaluator-visible; 120/120 server-observed
HCX_SUCCESS=116/120 evaluator-visible; 118/120 server-observed transport success
UNSUPPORTED_NUMERIC=0
UNSUPPORTED_FACTUAL=0
FALLBACK_RATE=17.5%
P50_MS=2730.466
P95_MS=10509.401
MAX_MS=12001.930
PRODUCTION_VALID=false
```
