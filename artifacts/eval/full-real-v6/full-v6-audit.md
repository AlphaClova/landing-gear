# Full v6 human re-audit

Single clean 120-case ORIGINAL_SINGLE_RUN. No failed-case rerun, no result replacement, no source change during evaluation.

A preflight `evaluate.py` call hit connection refused after the setup-shell uvicorn exited. That 120-FAIL file is archived under `_invalid_connection_refused/` and is **not** Full v6.

## Provenance

- branch: `fix/submission-p0`
- commit: `0a2c23c844f344d2f7c172c26d793380dae42c75`
- origin/main: `13336ce1ea1a1f4eaa07262d718be7b3db59721c`
- working tree before: clean (`WORKTREE_CLEAN_BEFORE_V6=true`)
- working tree after: only `artifacts/eval/full-real-v6/` untracked
- HEAD during evaluation: unchanged
- source hashes: unchanged vs `run-provenance.json`
- Golden `tests/golden/mirae_eval_120.jsonl` hash unchanged
- providers: HCX/Evidence/Rule/Product = real
- `/answer` official 5 fields (GET and POST probe)
- no extra `EVAL_SCHEMA_MODE` override; `/answer` is always the official contract

## Automatic scores

- total 120
- PASS 72 / FAIL 22 / MANUAL_REVIEW 26
- HTTP 120/120, client timeout 0, schema 120/120
- latency avg/p50/p95/max: 2653.5 / 2110.1 / 5624.2 / 6901.1 ms

Auto FAIL reasons: MISSING_EVIDENCE 19, MISSED_CLARIFICATION 4, MISSED_LIMITATION 1, FALSE_PREMISE_ACCEPTED 1.

Public `think_trace` is high-level only, so harness `hcx_first_pass` / transport-attempt fields are 0 in `latest.json`. Reconstruction from public `verification` + server log:

- HCX invocation 120/120, upstream HTTP 200 on 124 attempts (4 cases retried once)
- verification passed (first-pass kept): 25
- verification repaired (deterministic/safe repair): 95
- fallback_used: 4 (G021, G028, G032, G100) — grounded/limitation fallback, degraded=0, terminal=0
- 429=0, 502=0, ReadTimeout=0, retry exhausted=0
- HCX draft rejected log lines: 99

## Human re-audit (content)

Do not treat auto FAIL as content FAIL. Many empty-`retrieved_context` limitations are evaluator `MISSING_EVIDENCE` false negatives.

### P0 special regression

| ID | Human | Note |
|---|---|---|
| G011 | PASS | Uses 15-hour / 1-year evidence; 14 hours does not qualify. Not covered by generic limitation. |
| G026 | PASS | Rejects 16.5% as lump-sum rate; uses 100% 퇴직소득세. No health-insurance expansion. |
| G056 | PASS | No 3.3–5.5% attributed to 국민연금. P1: 국민연금 확인 불가를 명시하지 않고 퇴직연금 세율만 안내. |
| G089 | PASS | Hard 원금보장 unverified → no product dump. |
| G102 | PASS | Direct DC false-premise correction; no affirmation. |

### Core 5

| Q | ID | Human |
|---|---|---|
| 1 DB/DC | G001 | PASS |
| 2 세액공제 한도 | G002 | PASS (auto FAIL MISSED_LIMITATION = FN) |
| 3 Solomon 비교 | G004 | P1: 단기/중장기/장기 3상품 모두 존재. 투자설명서 excerpt가 ctx에 있는데도 전략·클래스·보수·수익률을 “구조화 Product Fact에서 확인 안 됨”으로만 처리. 초단기 excerpt도 retrieval됨. |
| 4 추천 하나 | G005 | PASS clarification (auto FAIL MISSED_CLARIFICATION = FN) |
| 5 비트코인 가격 | G113 | PASS out-of-scope limitation |

CORE_5_REGRESSION=0

### Previous 26 (content-p0-v6-r2 set)

G004 P1 (Solomon underuse). G008, G021, G039–G043, G045–G048, G050, G051, G053–G055, G058, G059, G076, G079, G082, G088, G091–G093: no P0 regression. G088 is P1 (adds 전문가 조언). G076/G079 are safe refusals (auto FAIL FN).

PREVIOUS_26_REGRESSION=0

### Actual content P0

- **G031** P0 — Q: 55세 전에 IRP에서 찾으면 어떤 세금이 생기나요? A: 이연퇴직소득세 70/60/50% canned block. Pre-55 IRP withdrawal is not 연금수령 연차 세율. Wrong tax scope. G055 (중도인출) correctly limited; G031 did not.

### Grounding / safety counts (human)

- unsupported numeric: 0 (no invented 16.5% lump-sum, no NP 3.3–5.5%)
- unsupported factual: 0 as P0-class invented law; P1 expansions: G081 공식 웹사이트, G088 전문가 조언
- wrong number: 0
- wrong evidence: 0
- irrelevant evidence: G004 extra 초단기 (P1)
- wrong scope: 1 (G031)
- wrong tax source: 1 (G031, same case)
- wrong procedure: 0
- missing supported subtask: G036 (21년차 50% is in corpus/G025; this run returned empty ctx + generic limit — retrieval miss or agent evidence loss, not source gap), G033 (추가납입 vs 퇴직금 재원 구분 부족), G056 (국민연금 미언급)
- false premise affirmations: 0 (G102/G008/G104 corrected; G103 did not affirm; G071 shows 1등급=매우 높은 위험)
- hard constraint product dumps: 0 (G089 withheld; G090 DC not dumped as IRP)
- unsupported recommendation constraints: 0 claimed-as-applied

Evidence classification examples:

- A retrieval miss: G014 E-9 (fact exists in corpus; this response ctx=0)
- B agent evidence loss: G004 prospectus in ctx unused for 예금자보호/보수
- C source gap: G090 DC products (DB has DC=0)

### Product / Solomon

- Product JSON: total=100, IRP=70, DB=3, DC=0. DIRECT_DC=0. SOURCE_GAP preserved.
- G089/G072/G090: unsupported hard constraints do not return matching-product dumps.
- G082: IRP + low-risk facts; 3-year horizon recorded as not applied.
- Solomon G004/G058/G059/G060/G073: requested names present when compared. G004/G059 still P1 for Product-Fact-only limitation despite retrieved prospectus. **Not fixed in this run.**

### Evaluator false negatives (auto FAIL, human PASS)

Do not change the scorer or Golden expected.

- G002 MISSED_LIMITATION
- G005, G080, G083, G084 MISSED_CLARIFICATION (clarification is present)
- G076, G079, G090, G106 MISSING_EVIDENCE on valid limitation/refusal
- G103 FALSE_PREMISE_ACCEPTED: did not affirm; used generic limitation without “아니요” marker (human P1, not content P0)

### Manual pack (evaluate.py generator, unmodified)

- AUTO_FAIL_COUNT=22
- AUTO_FAIL_INCLUDED=22
- MISSING_AUTO_FAIL_IDS= (none)
- G056, G089, G102 included
- G011, G026 auto PASS and **not** in `P0_REVIEW_IDS`, so they are missing from `manual_review.csv` (generator gap; not patched during freeze)

### B freeze

- retriever relevance gate, Product Fact source, products.db/json, Rule Engine, Rule JSON: not modified in this commit vs freeze intent
- Rule 10y=70%, 11–20y=60%, 21y+=50%
- B_MAIN_VALID=true

### Transport vs performance

- TRANSPORT_VALID: HTTP 120/120, timeout 0, 502 0
- PERFORMANCE_VALID: p95 5624 ms ≤ 8000 ms

### v5 original baseline vs v6

v5 original committed scorer: PASS 81 / FAIL 4 / MANUAL 35 / HTTP error 1/120 (G026 timeout). Footnote: an uncommitted rescore once showed 68/27/25; not used.

| Metric | Full v5 | Full v6 | Change |
|---|---:|---:|---|
| PASS | 81 | 72 | -9 |
| FAIL | 4 | 22 | +18 (mostly evaluator FN on empty-ctx limits) |
| MANUAL | 35 | 26 | -9 |
| actual content P0 | 1 (G056) + transport G026 | 1 (G031) | G056/G026 P0 cleared; G031 new |
| evaluator FN | G002, G005, G083 | those plus several MISSING_EVIDENCE limits | up |
| transport failures | 1 (G026 client timeout) | 0 | improved |
| unsupported numeric | 1 (G056) | 0 | improved |
| unsupported factual | 3 (G056, G113, G120) | 0 P0-class | improved |
| wrong evidence | 0 | 0 | — |
| wrong scope | 0 | 1 (G031) | new |
| hard product dump | G089 | 0 | improved |
| false premise affirmation | 0 structural G102 | 0 | held |
| schema failure | 1 (G026 no body) | 0 | improved |
| think_trace leak | 0 | 0 | held |
| p50 ms | 2722.5 | 2110.1 | improved |
| p95 ms | 7473.4 | 5624.2 | improved |
| max ms | 12002.1 | 6901.1 | improved |

### Tests after evaluation

- pytest: 334 passed
- git diff --check: PASS
- HEAD unchanged
- production/test source unchanged; only v6 artifacts added

### Gates

- CONTENT_VALID=false (G031 P0 wrong scope)
- SCHEMA_VALID=true
- TRACE_VALID=true
- B_VALID=true
- TRANSPORT_VALID=true
- PERFORMANCE_VALID=true
- PRODUCTION_VALID=false

### Competition

COMPETITION_READINESS=COMPETITIVE
FINALS_COMPETITIVENESS=중상
SUBMISSION_RECOMMENDATION=DO_NOT_SUBMIT
