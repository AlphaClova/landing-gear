# Full v5 audit

## Run integrity

- Run kind: ORIGINAL_SINGLE_RUN
- Total: 120, executed once; no recovery, failed-case rerun, or result replacement
- HTTP success: 119/120
- Automatic: PASS 81 / FAIL 4 / MANUAL_REVIEW 35
- Real providers: HCX / Evidence / Rule / Product
- Strict five-field response: valid for all 119 returned responses

## Content

- G003: PASS. doc26 page 1 is primary evidence; legal character, account deposit, 60-day refund procedure, and retirement-tax effect are preserved in Claim Plan and final answer.
- Evaluator false negatives: G002, G005, G083.
- Content P0: G056. The answer attributes a 5.5%–3.3% pension-income-tax range to National Pension without supporting National Pension evidence; the retrieved rate concerns pension-account funds. This is an unsupported numeric/factual claim and wrong tax source.
- Additional P1 grounding expansion: G113 adds generic cryptocurrency/investment advice; G120 expands the refusal with unsupported legal/medical assertions. G029 adds unrequested expert-advice wording.
- Unsupported numeric: 1 case (G056)
- Unsupported factual: 3 cases (G056, G113, G120)
- Wrong scope: 0
- Wrong tax source: 1 case (G056)
- Wrong procedure: 0
- Missing subtask: 0

## Rule trace

- Calculated-tax cases: G024, G030, G034, G039, G045, G051, G053
- Each case contains three matching RETIRE_TAX_RATE_BY_YEAR results.
- RULE_TRACE_VALID: true

## HCX and transport

- HCX invocation observable from returned artifacts: 119/120
- HCX success: 117
- First pass: 30
- Safe repair: 75
- Terminal fallback: 15
- Degraded grounded/limitation fallback: 2 (G068, G087)
- Returned transport attempts: 140
- Upstream 429 attempts: 7
- 429 exhausted: 2; both converted to strict HTTP 200 degraded responses
- 502: 0
- Returned ReadTimeout attempts: 1 (G096, subsequently recovered)
- Client timeout: 1 (G026); server-side trace is unavailable in the client artifact
- Latency avg / p50 / p95 / max: 3329.210 / 2722.451 / 7473.385 / 12002.144 ms

## v4 to v5

| Metric | v4 | v5 |
|---|---:|---:|
| HTTP success | 116 | 119 |
| PASS | 80 | 81 |
| FAIL | 7 | 4 |
| MANUAL | 33 | 35 |
| 429 exhausted cases | 3 known | 2 |
| API 502 | 3 | 0 |
| Client timeout | 1 | 1 |
| Safe repair | 68 | 75 |
| Terminal fallback | 19 | 15 |
| Average ms | 3516.599 | 3329.210 |
| p95 ms | 9532.961 | 7473.385 |

## Regression and assessment

- Previous content P0 26: HTTP 26/26; P0 0; one real HCX timeout exhaustion (G088) returned strict HTTP 200 deterministic grounded fallback.
- pytest: 252 passed
- git diff --check: PASS
- Source and Golden dataset hashes matched pre-run provenance after evaluation.
- CONTENT_VALID=false
- TRANSPORT_VALID=false
- SCHEMA_VALID=false for the complete 120-case run (119 returned strict responses; G026 had no response)
- PRODUCTION_VALID=false
