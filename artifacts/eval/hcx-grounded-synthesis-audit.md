# HCX Grounded Synthesis audit

## Historical fallback inventory (before)

Historical `official-v9`, `official-paraphrase-v6`, and `blind-20-v2` traces retained the final fallback reason and answer, but did not retain either HCX draft. The attempt-output columns below are therefore `NOT_CAPTURED`; they are not reconstructed from the final answer.

| id | intent | response | class | attempt 1 | violation 1/2 | attempt 2 | final latency ms |
|---|---|---|---|---|---|---|---:|
| G002 | 세제 | result | A EXTRA_NUMBER | NOT_CAPTURED | extra 300 | NOT_CAPTURED | 11025.010 |
| G004 | 상품 | result | G FORMAT | NOT_CAPTURED | limitation marker omitted | NOT_CAPTURED | 13162.690 |
| P004 | 세제 | result | G FORMAT | NOT_CAPTURED | limitation marker omitted | NOT_CAPTURED | 7338.842 |
| P005 | 세제 | result | A EXTRA_NUMBER | NOT_CAPTURED | extra 118, 148, 300 | NOT_CAPTURED | 9899.423 |
| P006 | 세제 | result | A EXTRA_NUMBER | NOT_CAPTURED | extra 5500 | NOT_CAPTURED | 9001.111 |
| P008 | 세제 | result | G FORMAT | NOT_CAPTURED | limitation marker omitted | NOT_CAPTURED | 11043.185 |
| P009 | 세제 | result | A EXTRA_NUMBER | NOT_CAPTURED | extra 264000, 79200 | NOT_CAPTURED | 13348.383 |
| P010 | 상품 | result | G FORMAT | NOT_CAPTURED | limitation marker omitted | NOT_CAPTURED | 25144.197 |
| P011 | 상품 | result | G FORMAT | NOT_CAPTURED | limitation marker omitted | NOT_CAPTURED | 15137.243 |
| P012 | 상품 | result | G FORMAT | NOT_CAPTURED | limitation marker omitted | NOT_CAPTURED | 15274.849 |
| P015 | 상품 | clarification | E EXTRA_SLOT | NOT_CAPTURED | repeated IRP slot | NOT_CAPTURED | 3725.971 |
| BTX03 | 세제 | result | A EXTRA_NUMBER | NOT_CAPTURED | limitation omitted; extra 118, 148, 3.3 | NOT_CAPTURED | 15241.114 |
| BTX04 | 세제 | result | A EXTRA_NUMBER | NOT_CAPTURED | extra 5500 | NOT_CAPTURED | 9983.681 |
| BTX05 | 세제 | result | A EXTRA_NUMBER | NOT_CAPTURED | extra 118, 148, 5 | NOT_CAPTURED | 11335.924 |
| BTR01 | 세제 | result | G FORMAT | NOT_CAPTURED | limitation marker omitted | NOT_CAPTURED | 15119.251 |
| BTR04 | 세제 | result | G FORMAT | NOT_CAPTURED | limitation marker omitted | NOT_CAPTURED | 14496.235 |
| BTR05 | 세제 | result | G FORMAT | NOT_CAPTURED | limitation marker omitted | NOT_CAPTURED | 15008.710 |
| BPR02 | 상품 | result | G FORMAT | NOT_CAPTURED | limitation marker omitted | NOT_CAPTURED | 14208.812 |
| BPR03 | 상품 | result | G FORMAT | NOT_CAPTURED | limitation marker omitted | NOT_CAPTURED | 14370.002 |

Final fallback answers and full questions are retained case-by-case in the three source `latest.json` files.

### Root-cause totals

- A EXTRA_NUMBER: 7
- B UNSUPPORTED_FACT: 0
- C PRODUCT_UNSUPPORTED_FACT: 0
- D LIMITATION_CONTRADICTION: 0
- E EXTRA_CLARIFICATION_SLOT: 1
- F OVERCONFIDENT_RECOMMENDATION: 0
- G FORMAT_OR_PARSING: 11
- H HCX_TIMEOUT as terminal fallback reason: 0
- I OTHER: 0

The seven numeric cases and the repeated slot are true violations. The eleven format cases are verifier false positives for synthesis quality when the semantic caution is otherwise present; the contract-required marker itself was missing. They can safely be repaired by appending the immutable limitation text without permitting a new fact.

## After instrumentation

New result traces retain, without credentials:

- initial and regeneration output
- violations after each phase
- transport attempt status and duration
- prompt character count
- focused evidence count and character count
- product-fact and rule-result counts

The only after-run fallback was `BTX03`. Its complete two drafts and violations are in `perf-blind-v1/latest.json`. It was a true violation: HCX added income threshold, allocation example, and calculated tax-saving numbers outside the allowed-number set. The grounded fallback removed all unsupported values.

## Prompt and evidence findings

- Aggregate prompt/latency Pearson correlation: approximately 0.55; prompt size is a meaningful but not exclusive latency factor.
- Direct evidence is capped at four focused items.
- DB/DC uses doc10 windows around DB/DC definitions.
- Tax deduction uses doc41/doc55 windows around 600/900/rate statements.
- Teacher retirement uses doc26/doc51 windows around benefit, 60-day and retirement-income statements.
- Product comparison uses matched product facts and at most one prospectus window per compared product.
- English `Solomon` exposed a literal-alias product filtering issue; it is now mapped to the same Korean product family instead of filtering by the English spelling.

## Timeout contract

`HCX_TIMEOUT_SECONDS=8.0`, `FAST_PATH_TIMEOUT_SECONDS=6.0`, and `DEEP_PATH_TIMEOUT_SECONDS=8.0`. The route timeout values are performance targets and are not an enclosing cancellation deadline in the orchestrator. HCX retries can therefore make a request exceed both targets. The after run kept the 8-second HCX timeout unchanged and observed zero HCX timeout retries and zero HTTP errors.
