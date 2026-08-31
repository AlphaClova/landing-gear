# Full v2 upstream audit

## Measurement separation

- `ORIGINAL_SINGLE_RUN`: 120 calls, 109 successful responses, 4 client timeouts, 7 HTTP 502 responses.
- `RECOVERY`: only the 11 failed IDs, executed separately in `full-real-v2-recovery`.
- `COMPOSITE_QUALITY`: 109 original successful responses plus 11 recovery responses, stored separately in `full-real-v2-composite`.
- Recovery responses were not merged into the original run artifact.

## Original failure observations

The original evaluator did not retain request timestamps, response bodies, response headers, or server-side HCX attempt telemetry for failed requests. Those fields are therefore reported as `NOT_OBSERVED`; they must not be reconstructed as facts.

| call | case | category | result | request start | HCX attempts / latency | safe error type | retry | previous normal gap |
|---:|---|---|---|---|---|---|---|---|
| 21 | G021 | tax | client timeout, 12002.240 ms | NOT_OBSERVED | NOT_OBSERVED | client timeout | NOT_OBSERVED | NOT_OBSERVED |
| 51 | G051 | combined | client timeout, 12002.018 ms | NOT_OBSERVED | NOT_OBSERVED | client timeout | NOT_OBSERVED | NOT_OBSERVED |
| 58 | G058 | product_compare | client timeout, 12002.299 ms | NOT_OBSERVED | NOT_OBSERVED | client timeout | NOT_OBSERVED | NOT_OBSERVED |
| 63 | G063 | product_compare | client timeout, 12002.043 ms | NOT_OBSERVED | NOT_OBSERVED | client timeout | NOT_OBSERVED | NOT_OBSERVED |
| 76 | G076 | product_compare | HTTP 502, 6649.881 ms | NOT_OBSERVED | NOT_OBSERVED | body not retained | NOT_OBSERVED | NOT_OBSERVED |
| 78 | G078 | conditional_recommendation | HTTP 502, 3588.585 ms | NOT_OBSERVED | NOT_OBSERVED | body not retained | NOT_OBSERVED | NOT_OBSERVED |
| 80 | G080 | conditional_recommendation | HTTP 502, 3733.780 ms | NOT_OBSERVED | NOT_OBSERVED | body not retained | NOT_OBSERVED | NOT_OBSERVED |
| 81 | G081 | conditional_recommendation | HTTP 502, 3581.902 ms | NOT_OBSERVED | NOT_OBSERVED | body not retained | NOT_OBSERVED | NOT_OBSERVED |
| 82 | G082 | conditional_recommendation | HTTP 502, 3590.727 ms | NOT_OBSERVED | NOT_OBSERVED | body not retained | NOT_OBSERVED | NOT_OBSERVED |
| 83 | G083 | conditional_recommendation | HTTP 502, 3512.113 ms | NOT_OBSERVED | NOT_OBSERVED | body not retained | NOT_OBSERVED | NOT_OBSERVED |
| 84 | G084 | conditional_recommendation | HTTP 502, 3484.356 ms | NOT_OBSERVED | NOT_OBSERVED | body not retained | NOT_OBSERVED | NOT_OBSERVED |

The seven 502s were not literally seven consecutive API calls: G077 and G079 returned HTTP 200 between them. G080–G084 were five consecutive 502 responses. This distinction matters when evaluating a persistent connection failure hypothesis.

## 502 provenance

The original artifact alone cannot prove the provenance because its evaluator discarded the error body. In the current application, an exhausted `HCXClient` HTTP/transport error is raised as `HCXError(code=upstream_error)`, and the API maps that code to HTTP 502. An unrelated unhandled application exception maps to HTTP 500, not 502. Thus the observed pattern is consistent with the application translating an HCX client failure into 502; it is not evidence that HCX itself returned HTTP 502. The exact upstream status (including a possible 429) was not retained.

## Hypothesis assessment

| hypothesis | assessment | evidence |
|---|---|---|
| HCX transient failure | most plausible, not proven | all 11 recovered later; recovery transport attempts were all `ok`; original run returned to 200 at G077, G079, and G085 |
| rate limit / quota | plausible, not distinguishable | failures occurred later in a long run, but original upstream status/body and rate-limit headers were discarded |
| long-run connection issue | plausible but weakened | late clustering exists, but intervening successful calls and successful recovery using the same client design argue against a permanently poisoned pool |
| retry/backoff issue | possible contributor | client retries timeout, all HTTP status errors, and transport errors with only 0.5/1.0/1.5 second sleeps and no `Retry-After` handling or jitter; original attempt telemetry is absent |
| client connection pool issue | no affirmative evidence | recovery completed all calls over the same process/client path; no original transport exception class was retained |
| application exception converted to 502 | ordinary exception unlikely | generic exceptions map to 500; HCX client exhaustion maps to 502. Exact original body is unavailable, so case-level proof is impossible |

## Recovery audit

Recovery ran on 2026-08-28 with real HCX and strict evaluation schema. Every HCX transport attempt succeeded without transport retry. `hcx_attempts=2` for G051 and G076 means one initial synthesis plus one verifier-requested regeneration, not a transport retry.

| seq | case | UTC start | HCX synthesis calls | transport durations (ms) | API | HCX | result | gap from prior response (ms) |
|---:|---|---|---:|---|---|---|---|---:|
| 1 | G021 | 04:36:02.984 | 1 | 5844.742 | 200 | success | PASS | N/A |
| 2 | G051 | 04:36:08.941 | 2 | 5325.548, 5529.744 | 200 | success | MANUAL_REVIEW | 36.104 |
| 3 | G058 | 04:36:19.897 | 1 | 5201.852 | 200 | success | PASS | 34.790 |
| 4 | G063 | 04:36:25.207 | 1 | 1771.665 | 200 | success | PASS | 21.208 |
| 5 | G076 | 04:36:27.074 | 2 | 4418.870, 2973.268 | 200 | success | PASS | 25.490 |
| 6 | G078 | 04:36:34.578 | 1 | 2813.607 | 200 | success | MANUAL_REVIEW | 35.170 |
| 7 | G080 | 04:36:37.507 | 1 | 1088.956 | 200 | success | MANUAL_REVIEW | 32.965 |
| 8 | G081 | 04:36:38.634 | 1 | 1115.172 | 200 | success | MANUAL_REVIEW | 34.006 |
| 9 | G082 | 04:36:39.862 | 1 | 1585.225 | 200 | success | MANUAL_REVIEW | 33.282 |
| 10 | G083 | 04:36:41.560 | 1 | 3792.981 | 200 | success | MANUAL_REVIEW | 33.136 |
| 11 | G084 | 04:36:45.392 | 1 | 1498.366 | 200 | success | MANUAL_REVIEW | 34.180 |

G051 and G076 used deterministic fallback after both generated drafts violated grounding/limitation checks. This is a functional-quality observation, not an upstream failure.

## Composite functional quality

- PASS: 82
- FAIL: 0
- MANUAL_REVIEW: 38
- Automated final-output failures for unsupported numeric/factual claims, wrong number, missing/wrong/irrelevant evidence, false premise, clarification, and safety: 0
- The 38 manual-review cases remain unconfirmed by a human reviewer; the automated result must not be presented as 120 human-verified passes.

## Root-cause buckets

- SLOT_POLICY: 0 automated final failures
- ROUTER: 0 automated final failures
- HCX_GROUNDEDNESS: 0 automated final failures; G051/G076 required fallback after rejected drafts
- EVALUATOR_FALSE_NEGATIVE: not established
- RETRIEVAL: 0 automated final failures

