# Full Real v4 audit

This is the unmodified `ORIGINAL_SINGLE_RUN` of 120 cases. No failed case was recalled or replaced.

## Outcome

- HTTP success/error: 116 / 4
- Automatic PASS/FAIL/MANUAL_REVIEW: 80 / 7 / 33
- Content failures among automatic FAIL: G003
- Evaluator false negatives among automatic FAIL: G002, G005
- Transport failures: G074, G083, G084 (API 502 after upstream 429 retry exhaustion), G104 (client 12-second timeout)
- Schema failures independent of transport: 0; schema flags on the four transport failures are secondary to missing responses.

## Content audit

- Unsupported numeric: 0
- Unsupported factual: 0
- Wrong number/evidence: 0 / 0
- Wrong scope: 1 (G003 ignores the teacher-specific retirement-benefit applicability path)
- Wrong tax source: 0
- Wrong procedure: 0
- Missing subtask: 1 (G003)
- Unsupported recommendation constraint: 0
- Requested field missing: 0 observed in the previous-P0 watch set
- Rule trace violations: 0

G003 is a content P0 candidate: the final answer gives the generic deferred-retirement-tax schedule but omits the teacher retirement-benefit classification, the applicable doc26 path, and the supported 60-day refund procedure. G002 correctly answers the aggregate contribution limit despite the evaluator requiring a limitation marker. G005 asks for plan, horizon, and risk conditions despite the evaluator not recognizing its declarative clarification form.

## HCX and transport

- Case invocation/success: 116 / 116 in returned strict responses
- First pass: 27
- Deterministic safe repair: 68
- Terminal fallback: 19
- Returned-response trace attempts: 139
- Successful upstream HTTP 200 attempts in returned traces: 138
- Returned-trace ReadTimeout: 1
- Upstream 429: 9 known attempts across three exhausted cases
- Upstream 5xx: 0
- API 502: 3
- Retry exhausted: 3 cases
- Client timeout over 12 seconds: 1 (G104, 12003.014 ms)

The three 502 response bodies preserve only a safe error type rather than per-attempt trace. Each says two retries were exhausted after upstream 429, establishing three attempts per case (nine 429 attempts). The G104 client timeout response does not expose its server-side HCX attempt detail. Therefore 139 is the exact attempt count preserved in returned traces; 148 is the minimum total after adding the nine known exhausted 429 attempts, with G104 server-side attempts unavailable from the response artifact.

## Previous content-P0 regression watch

- 26 cases checked
- HTTP success: 26/26
- Content P0 regression: 0
- Stochastic P0 promotion: none
- The seven prior P1 cases (G004, G043, G048, G054, G076, G079, G088) remain P1; none meets P0 promotion criteria.

## Manual review pack

- Total: 55
- Automatic MANUAL_REVIEW: 33
- Automatic FAIL: 7
- Stratified PASS samples: 15
- Human fields: blank

## v3 to v4

| Metric | v3 | v4 | Change |
|---|---:|---:|---:|
| HTTP success | 116 | 116 | 0 |
| HCX case success | 116 | 116 | 0 |
| PASS | 81 | 80 | -1 |
| FAIL | 4 | 7 | +3 |
| MANUAL_REVIEW | 35 | 33 | -2 |
| terminal fallback | 21 | 19 | -2 |
| safe repair | 48 | 68 | +20 |
| first pass | 44 | 27 | -17 |
| upstream 429 attempts | 6 | 9 | +3 |
| client timeout | 2 | 1 | -1 |
| API 502 | 2 | 3 | +1 |
| ReadTimeout | 4 | 1 | -3 |
| average ms | 3770.447 | 3516.599 | -253.848 |
| p50 ms | 2730.466 | 2591.378 | -139.088 |
| p95 ms | 10509.401 | 9532.961 | -976.440 |
| max ms | 12001.930 | 12003.014 | +1.084 |

## Assessment

- CONTENT_VALID: false — G003 content P0 candidate/missing teacher-specific subtask.
- TRANSPORT_VALID: false — three exhausted upstream-429 cases and one client timeout.
- SCHEMA_VALID: true — all 116 returned application responses satisfy strict schema; schema flags occur only because four transport failures returned no strict answer payload.
- PRODUCTION_VALID: false.
