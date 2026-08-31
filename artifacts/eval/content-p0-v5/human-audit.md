# content-p0-v5 human audit

Source: `latest.json`. Verdicts below are human content judgments; automatic PASS/MANUAL_REVIEW is not reused as the verdict. Full final answers, retrieved excerpts, document/page provenance, HCX audit, Rule Results, and Product Facts remain in `latest.json`.

| Case | Verdict | Intent / sub-intents | Requested slots | Tools | Evidence / structured result | HCX / final handling | Human finding |
|---|---|---|---|---|---|---|---|
| G004 | P1 | 상품 / 기간별 상품 비교·안정성 | 없음 | retrieve, product query | four Solomon Product Facts; product docs p1 plus supporting pages | 2 attempts; regeneration failed; fallback | Actual risk/account fields are used. Extra 초단기 entry and fallback reduce precision, but no unsupported superiority claim. |
| G008 | PASS | 종합 / DC false premise | 없음 | retrieve | doc10 pp1-3 | 1; first pass | Directly corrects company-responsibility premise with employee-operation fact. |
| G021 | PASS | 세제 / contribution limit vs credit amount | 없음 | retrieve | doc41 pp1-2, doc51 p2, doc55 pp7,10 | 1; safe repair | IRP-only 9M can fit aggregate limit; distinguishes eligible contribution from actual credit. |
| G039 | PASS | 종합 / lump sum vs annuity tax | supplied 300M benefit, 24M tax, DB | retrieve, withdrawal rule | doc51 pp1-2; three RETIRE_TAX_RATE_BY_YEAR results | 1; safe repair | Final 24M/16.8M/12M exactly match Rule Results. |
| G040 | PASS | 종합 / DC transfer + 10/21-year tax | supplied 200M benefit; missing expected tax | retrieve | doc10 pp1-3, doc51 pp1-2, doc55 | 1; safe repair | Gives 70/50% and IRP transfer; does not invent tax amount. |
| G041 | P0 | 세제 / receiving account + tax comparison | age 55, DB | retrieve | doc10 pp1-3, doc51 pp1-2, doc55 pp13,17,20,23 | 2; fallback | Final generic numeric limitation drops both answerable receiving-account and tax subtasks. |
| G042 | P0 | 종합 / deferred retirement source + personal contribution sources | IRP supplied | retrieve | doc55 pp5,7,13,17 | 2; fallback | Final generic numeric limitation does not distinguish tax sources or protect against applying 3.3-5.5% to retirement principal. |
| G043 | P1 | 세제 / applicability scope | 없음 | retrieve | doc51 p1, doc55 p15; doc26 excluded | 1; safe repair | Correct scope limitation, but duplicated verbatim. |
| G045 | PASS | 종합 / tax comparison + conditional product selection | supplied 500M/40M/stable; missing plan and horizon | retrieve, withdrawal rule | doc51; three 40M-based Rule Results | 1; safe repair | Keeps calculated subtask and asks only missing product conditions. |
| G046 | P0 | 종합 / DC→IRP→pension-saving transfer + tax | DC | retrieve | doc10, doc51 p2, doc55 pp5,17,20,32,33 | 2; fallback | Available transfer path and tax evidence are discarded by generic numeric limitation. |
| G047 | PASS | 절차 / DB-DC distinction + IRP transfer | 없음 | retrieve | doc10 pp1-3, doc51 pp1-2, doc55 | 1; safe repair | Both requested subtasks answered from evidence. |
| G048 | P1 | 종합 / 10-vs-21 tax + liquidity | missing expected tax and schedule | retrieve | doc41, doc51 pp1-3 | 1; safe repair | Correct retirement-tax rates and liquidity limitation; repeats tax-rate paragraph. |
| G050 | PASS | 종합 / pension withdrawal tax saving | expected tax value absent | retrieve | doc41 p2, doc51 p2, doc55 p21 | 1; safe repair | Does not route to tax credit; asks only expected retirement tax and notes schedule dependency. |
| G051 | P0 | 종합 / zero deferred tax + non-tax comparison | supplied 300M, tax 0, IRP | retrieve, withdrawal rule | doc51; three zero-valued Rule Results | 2; fallback | Rule accepts zero, but final omits zero saving and only gives generic non-conclusion. |
| G053 | PASS | 종합 / large-number calculation and basis | supplied 10B/2B | retrieve, withdrawal rule | doc51; three RETIRE_TAX_RATE_BY_YEAR results | 1; safe repair | Final 2B/1.4B/1B exactly match Rule Results. |
| G054 | P1 | 종합 / transfer, product selection, pension start | IRP; missing horizon/risk | retrieve, product query | doc51/doc55 and IRP Product Facts | 1; safe repair | Separates three stages and requests product conditions; procedural detail remains limited. |
| G055 | P0 | 세제 / receiving account, early withdrawal, source tax | age under 55, DB | retrieve | doc10, doc51 pp1-2, doc55 pp20,26 | 2; fallback | Final generic numeric limitation drops all three answerable distinctions. |
| G058 | PASS | 상품 / short Solomon facts | 없음 | retrieve, product query | short Solomon Product Fact; product doc p1 and supporting pages | 1; safe repair | Uses risk/account facts, invents no fee or suitability value, states limitation. |
| G059 | P0 | 상품 / medium-long Solomon risk + cost | 없음 | retrieve, product query | one medium-long Product Fact; product doc pp1,3,21 | 1; safe repair | Risk is answered but requested cost is omitted despite document retrieval; no explicit cost-field limitation. |
| G076 | PASS | 상품 / unsupported future return | 없음 | retrieve | product docs supporting limited available facts | 1; safe repair | Refuses numeric prediction and adds no advice. |
| G079 | P1 | 상품 / unconditional single-product recommendation | plan/horizon/risk missing | retrieve | product-document excerpts only; no Product Fact candidates | 2; fallback | No expert advice in final, but duplicated verifier limitation quotes the user's “무조건” as a violation. |
| G082 | P0 | 상품 / IRP + 3-year + stable candidates | all supplied | retrieve, product query | five IRP risk-level-6 Product Facts | 1; safe repair | Query uses IRP and stable filter but not 3-year horizon; final labels them “3년 후보” and adds unsupported expert-consultation advice. |
| G088 | P1 | 상품 / reject return-only selection | plan/horizon/risk missing | retrieve | product-document excerpts; no Product Fact candidates | 2; fallback | Correct refusal without expert advice, but duplicated verifier limitation remains. |
| G091 | PASS | 절차 / termination | plan type missing | retrieve | doc55 procedure pages | 1; safe repair | Does not turn termination into insolvency early withdrawal; scopes limitation. |
| G092 | PASS | 절차 / new IRP opening documents | 없음 | retrieve | doc41 p1, doc51 p2, doc55 pp5,11,13,32 | 1; safe repair | Explicitly refuses to reuse benefit-receipt documents as opening documents. |
| G093 | PASS | 제도 / DC→IRP→pension-saving transfer | DC | retrieve | doc10 pp1-3, doc51 pp1-3, doc55 p17 | 1; first pass | Correct sequence; no invented tax, fee, or advice. |

## Grounding totals

- PASS: 13
- P1: 6
- P0: 7
- Unsupported numeric: 0
- Unsupported factual: 1 (G082: 3-year suitability implication)
- Wrong number: 0
- Wrong scope: 0
- Wrong tax source: 1 (G042: required source distinction absent)
- Wrong procedure type: 0
- Wrong product fact: 0
- Rule trace valid: true; every final calculated tax amount has a matching Rule Result.

## Gate

`CONTENT_P0=7`; Full v4 is not ready and was not run.
