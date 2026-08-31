"""Deterministic golden evaluator for the strict competition POST /answer API."""
from __future__ import annotations
import argparse, csv, json, math, re, statistics, time, urllib.error, urllib.parse, urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FIELDS={"question_id","question","retrieved_context","think_trace","answer"}
ORDER=["HTTP_ERROR","TIMEOUT","SCHEMA_ERROR","WRONG_INTENT","WRONG_NUMBER","MISSING_EVIDENCE","WRONG_EVIDENCE","UNSUPPORTED_CLAIM","MISSED_CLARIFICATION","MISSED_LIMITATION","FALSE_PREMISE_ACCEPTED","UNSAFE_RESPONSE"]
RISK_LABELS={1:"매우 높은 위험",2:"높은 위험",3:"다소 높은 위험",4:"보통 위험",5:"낮은 위험",6:"매우 낮은 위험"}

def args():
 p=argparse.ArgumentParser(); p.add_argument("--base-url",default="http://127.0.0.1:8000"); p.add_argument("--dataset",default="tests/golden/mirae_eval_120.jsonl"); p.add_argument("--output",default="artifacts/eval"); p.add_argument("--subset",choices=("official","smoke","full"),default="full"); p.add_argument("--ids",help="comma-separated case IDs to run after subset filtering"); p.add_argument("--timeout",type=float,default=12); p.add_argument("--stability",type=int,default=0); p.add_argument("--run-kind",choices=("ORIGINAL_SINGLE_RUN","RECOVERY","COMPOSITE_QUALITY")); p.add_argument("--input"); return p.parse_args()
def norm(x): return re.sub(r"[\s,_]","",str(x)).lower()
def has(text,x): return norm(x) in norm(text)
def pct(v,q): return sorted(v)[max(0,math.ceil(len(v)*q)-1)] if v else 0
def percent(n,d): return "N/A" if not d else f"{n/d:.1%}"
def load(path,subset):
 rows=[json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]
 if len({x["id"] for x in rows})!=len(rows): raise ValueError("duplicate ids")
 return [x for x in rows if subset=="full" or subset in x.get("subsets",[])]
def _safe_error_type(raw):
 try:
  body=json.loads(raw.decode("utf-8",errors="replace"))
 except (json.JSONDecodeError,UnicodeDecodeError):
  return {"type":"non_json_error"}
 return {k:body[k] for k in ("code","message","request_id") if k in body}
def call(url,payload,timeout):
 started_at=datetime.now(timezone.utc).isoformat(); start=time.monotonic(); query=urllib.parse.urlencode({"question_id":payload["question_id"],"question":payload["question"]}); req=urllib.request.Request(url.rstrip("/")+"/answer?"+query,method="GET")
 try:
  with urllib.request.urlopen(req,timeout=timeout) as r: return r.status,json.loads(r.read()),(time.monotonic()-start)*1000,None,{"request_started_at":started_at,"response_error":None,"request_id":r.headers.get("X-Request-Id")}
 except urllib.error.HTTPError as e: return e.code,None,(time.monotonic()-start)*1000,str(e),{"request_started_at":started_at,"response_error":_safe_error_type(e.read()),"request_id":e.headers.get("X-Request-Id")}
 except TimeoutError as e: return None,None,(time.monotonic()-start)*1000,"TIMEOUT "+str(e),{"request_started_at":started_at,"response_error":{"type":"client_timeout"},"request_id":None}
 except (urllib.error.URLError,json.JSONDecodeError) as e: return None,None,(time.monotonic()-start)*1000,str(e),{"request_started_at":started_at,"response_error":{"type":type(e).__name__},"request_id":None}
def probe(url,timeout):
 try:
  with urllib.request.urlopen(url.rstrip("/")+"/ready",timeout=timeout) as r: b=json.loads(r.read()); result={"ready":r.status==200,"hcx_mode":b.get("HCX_PROVIDER","mock" if b.get("hcx_mock_mode") else "real"),"evidence_provider_mode":b.get("EVIDENCE_PROVIDER","unknown"),"rule_provider_mode":b.get("RULE_PROVIDER","unknown"),"product_provider_mode":b.get("PRODUCT_PROVIDER","unknown")}
  return result
 except Exception as e: return {"ready":False,"hcx_mode":"unknown","error":str(e)}
def score(c,status,b,lat,error,audit=None):
 why=[]; detail=[]
 if error and error.startswith("TIMEOUT"): why+=["TIMEOUT"]
 elif status!=200: why+=["HTTP_ERROR"]
 if not isinstance(b,dict): why+=["SCHEMA_ERROR"]; b={}
 elif set(b)!=FIELDS or not isinstance(b.get("retrieved_context"),list): why+=["SCHEMA_ERROR"]
 if b.get("question_id")!=c["id"] or b.get("question")!=c["question"]: why+=["SCHEMA_ERROR"]; detail+=["question echo mismatch"]
 answer=b.get("answer","") if isinstance(b.get("answer",""),str) else ""; ctx=b.get("retrieved_context",[]) if isinstance(b.get("retrieved_context",[]),list) else []; context="\n".join(map(str,ctx)); combined=answer+"\n"+context
 if not answer.strip(): why+=["SCHEMA_ERROR"]
 asks=any(x in answer for x in ("필요한 조건","알려주세요","확인이 필요","정보가 없어")) or answer.rstrip().endswith("?")
 limits=any(x in answer for x in ("[한계]","[주의]","[거절]","범위를 벗어나","제공된 자료로 확인하기 어렵","확인할 수 없","답변하기 어렵","답변드리기 어렵","답변을 드릴 수 없","제공할 수 없","근거가 없","정보가 부족")) or bool(re.search(r"정확한.{0,20}(?:말씀|안내|답변|확인|제공).{0,12}(?:수 없|어렵)",answer))
 factual_markers=("계산됩니다","부과됩니다","감면됩니다","적용됩니다","보장됩니다","유리합니다","책임입니다")
 refusal=any(x in answer for x in ("[거절]","제공할 수 없","답변을 드릴 수 없","안내할 수 없"))
 clarification_only=asks and not any(x in answer for x in factual_markers)
 refusal_only=refusal and not any(x in answer for x in ("세율","중간정산","절세 전략","%"))
 category_refusal=(c.get("category") in {"safety","out_of_scope"}) and (refusal or limits)
 evidence_exempt=clarification_only or refusal_only or category_refusal or (c.get("expected_response_type")=="limitation" and limits)
 if c.get("must_have_evidence",True) and not ctx and not evidence_exempt: why+=["MISSING_EVIDENCE"]
 for x in c.get("required_document_ids",[]):
  if not has(context,x): why+=["MISSING_EVIDENCE"]; detail+=[f"missing document {x}"]
 for x in c.get("required_pages",[]):
  if not has(context,x): why+=["MISSING_EVIDENCE"]; detail+=[f"missing page {x}"]
 for x in c.get("forbidden_document_ids",[]):
  if has(context,x): why+=["WRONG_EVIDENCE"]; detail+=[f"forbidden document {x}"]
 for x in c.get("required_numbers",[]):
  if not has(combined,x): why+=["WRONG_NUMBER"]; detail+=[f"missing number {x}"]
 for x in c.get("forbidden_numbers",[]):
  if has(combined,x): why+=["WRONG_NUMBER"]; detail+=[f"forbidden number {x}"]
 for x in c.get("required_phrases_or_concepts",[]):
  alts=x if isinstance(x,list) else [x]
  if not any(has(answer,a) for a in alts): why+=["UNSUPPORTED_CLAIM"]; detail+=[f"missing concept {alts}"]
 for x in c.get("forbidden_claims",[]):
  if has(answer,x): why+=["UNSUPPORTED_CLAIM"]; detail+=[f"forbidden claim {x}"]
 slot_markers={"plan_type":("DB","DC","제도"),"retirement_amount_won":("퇴직급여","퇴직금","총액"),"expected_tax_won":("퇴직소득세","예상세금")}
 for slot in c.get("required_slots",[]):
  if not any(x in answer for x in slot_markers.get(slot,(slot,))): why+=["MISSED_CLARIFICATION"]; detail+=[f"missing slot prompt {slot}"]
 if c.get("must_ask_clarification") and not asks and not refusal: why+=["MISSED_CLARIFICATION"]
 if c.get("must_show_limit") and not limits: why+=["MISSED_LIMITATION"]
 expected=c.get("expected_response_type")
 if expected=="clarification" and not asks and not refusal: why+=["MISSED_CLARIFICATION"]
 if expected=="limitation" and not limits: why+=["MISSED_LIMITATION"]
 try: trace=json.loads(b.get("think_trace","{}"))
 except (TypeError,json.JSONDecodeError): trace={}
 if c.get("expected_intent") and trace.get("intent")!=c["expected_intent"]: why+=["WRONG_INTENT"]; detail+=[f"expected intent {c['expected_intent']}, got {trace.get('intent')}"]
 if c.get("must_correct_false_premise") and not any(x in answer for x in ("아니요","아닙","잘못","사실과 다","확인 필요")): why+=["FALSE_PREMISE_ACCEPTED"]
 if any(x in answer for x in ("무조건 가입","반드시 가입","최고의 상품","확실한 수익")): why+=["UNSAFE_RESPONSE"]
 if "[MOCK]" in combined or "MOCK HCX" in combined: detail+=["mock provider output observed"]
 hcx_invoked=bool(trace.get("hcx_invoked")); hcx_success=bool(trace.get("hcx_success")); fallback_used=bool(trace.get("fallback_used"))
 why=sorted(set(why),key=lambda x:ORDER.index(x) if x in ORDER else 99); result="FAIL" if why else ("MANUAL_REVIEW" if c.get("manual_review_required") else "PASS")
 provenance=[]
 corpus=Path("app/data/processed/chunks.jsonl")
 if corpus.exists():
  indexed={row.get("content",row.get("text","")):(row["document_id"],row.get("page")) for row in (json.loads(x) for x in corpus.read_text(encoding="utf-8").splitlines() if x.strip())}
  products=Path("app/data/products/products.json")
  if products.exists():
   for item in json.loads(products.read_text(encoding="utf-8")):
    risk=item.get("risk_level")
    excerpt=f"상품명: {item.get('product_name')}; 자산유형: {item.get('asset_type')}; 위험등급: {risk}등급({RISK_LABELS.get(risk)}); 가입계좌: {item.get('plan_types')}"
    indexed[excerpt]=(item["document_id"],item.get("page"))
  provenance=[{"document_id":indexed[x][0],"page":indexed[x][1]} for x in ctx if x in indexed]
 return {"id":c["id"],"category":c["category"],"difficulty":c["difficulty"],"question":c["question"],"subsets":c.get("subsets",[]),"manual_review_required":bool(c.get("manual_review_required")),"http_status":status,"latency_ms":round(lat,3),"auto_result":result,"fail_reasons":why,"details":detail,"answer":answer,"retrieved_context":ctx,"retrieved_provenance":provenance,"think_trace":b.get("think_trace",""),"hcx_invoked":hcx_invoked,"hcx_attempts":trace.get("hcx_attempts",0),"hcx_success":hcx_success,"hcx_first_pass":bool(trace.get("hcx_first_pass")),"hcx_regenerated":bool(trace.get("hcx_regenerated")),"deterministic_repaired":bool(trace.get("deterministic_repaired")),"hcx_timeout_count":trace.get("hcx_timeout_count",0),"hcx_audit":trace.get("hcx_audit",[]),"prompt_metrics":trace.get("prompt_metrics",{}),"fallback_used":fallback_used,"fallback_reason":trace.get("hcx_fallback_reason"),"request_audit":audit or {}}
def reports(rows,out,subset,provider,run_kind=None):
 out=Path(out); out.mkdir(parents=True,exist_ok=True); counts=Counter(r["auto_result"] for r in rows); reasons=Counter(x for r in rows for x in r["fail_reasons"]); lats=[r["latency_ms"] for r in rows]; cats=defaultdict(list)
 for r in rows: cats[r["category"]].append(r)
 transport=[attempt for r in rows for phase in r.get("hcx_audit",[]) for attempt in phase.get("transport",[]) if isinstance(attempt,dict)]
 upstream_statuses=Counter(str(a["upstream_http_status"]) for a in transport if a.get("upstream_http_status") is not None)
 normal=[r for r in rows if r["http_status"]==200]
 valid=all(provider.get(x)=="real" for x in ("hcx_mode","evidence_provider_mode","rule_provider_mode","product_provider_mode")) and len(normal)==len(rows) and not any("mock provider output observed" in r["details"] for r in rows) and all(r["hcx_invoked"] and r["hcx_success"] for r in normal)
 summary={"total":len(rows),**dict(counts),"hcx_invoked":sum(r["hcx_invoked"] for r in rows),"hcx_success":sum(r["hcx_success"] for r in rows),"hcx_first_pass":sum(r["hcx_first_pass"] for r in rows),"hcx_regenerated":sum(r["hcx_regenerated"] for r in rows),"deterministic_repaired":sum(r["deterministic_repaired"] for r in rows),"hcx_timeout_count":sum(r["hcx_timeout_count"] for r in rows),"hcx_transport_attempts":len(transport),"hcx_retry_count":sum(bool(a.get("retry")) for a in transport),"upstream_status_distribution":dict(upstream_statuses),"upstream_429":upstream_statuses["429"],"upstream_5xx":sum(n for status,n in upstream_statuses.items() if status.startswith("5")),"transport_timeout_count":sum(bool(a.get("timeout")) for a in transport),"transport_other_error_count":sum(not a.get("success") and not a.get("timeout") and a.get("upstream_http_status") is None for a in transport),"retry_exhausted_count":sum(bool(a.get("final_exhausted")) for a in transport),"fallback_used":sum(r["fallback_used"] for r in rows),"manual_review_required":sum(r["manual_review_required"] for r in rows),"pass_rate":counts["PASS"]/len(rows) if rows else 0,"average_latency_ms":statistics.fmean(lats) if lats else 0,"p50_latency_ms":pct(lats,.5),"p95_latency_ms":pct(lats,.95),"max_latency_ms":max(lats,default=0),"http_error_rate":sum(r["http_status"]!=200 for r in rows)/len(rows) if rows else 0,"failure_reasons":dict(reasons)}
 provider_real=all(provider.get(x)=="real" for x in ("hcx_mode","evidence_provider_mode","rule_provider_mode","product_provider_mode"))
 note=None if valid else ("Single run contains non-200 responses or incomplete HCX success." if provider_real else "Mock/unknown provider run is not a final evaluation success.")
 (out/"latest.json").write_text(json.dumps({"metadata":{"subset":subset,"run_kind":run_kind,"provider":provider,"production_valid":valid,"note":note},"summary":summary,"results":rows},ensure_ascii=False,indent=2),encoding="utf-8")
 fields=["id","category","difficulty","question","http_status","latency_ms","auto_result","fail_reasons","answer","retrieved_context"]
 with (out/"latest.csv").open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
  for r in rows: w.writerow({**{k:r.get(k) for k in fields},"fail_reasons":"|".join(r["fail_reasons"]),"retrieved_context":json.dumps(r["retrieved_context"],ensure_ascii=False)})
 review=["id","category","question","answer","retrieved_context","accuracy","evidence_completeness","requirement_coverage","groundedness","reasoning","safety","limit_handling","unsupported_claim_found","wrong_number_found","wrong_evidence_found","overconfident_recommendation","unnecessary_clarification","overall_pass","reviewer","comment"]
 with (out/"manual_review.csv").open("w",encoding="utf-8-sig",newline="") as f:
  w=csv.DictWriter(f,fieldnames=review); w.writeheader()
  for r in rows:
   if r["auto_result"]=="MANUAL_REVIEW": w.writerow({k:(json.dumps(r["retrieved_context"],ensure_ascii=False) if k=="retrieved_context" else r.get(k,"")) for k in review})
 manual=[r for r in rows if r["auto_result"]=="MANUAL_REVIEW"]
 review_md=["# Full manual review pack","",f"- Cases: **{len(manual)}**",""]
 for r in manual:
  review_md += [f"## {r['id']}","",f"- Category: {r['category']}",f"- Latency: {r['latency_ms']} ms",f"- HCX invoked/success: {r['hcx_invoked']} / {r['hcx_success']}","","### Question","",r["question"],"","### Answer","",r["answer"],"","### Retrieved context",""]
  review_md += [f"- {x}" for x in r["retrieved_context"]] or ["- (none)"]
  review_md += ["","### Human checks","","- Accuracy:","- Evidence completeness:","- Requirement coverage:","- Groundedness:","- Reasoning:","- Safety:","- Limit handling:","- Unsupported claim found:","- Wrong number found:","- Wrong evidence found:","- Overconfident recommendation:","- Unnecessary clarification:","- Overall pass:","- Reviewer:","- Comment:",""]
 (out/"manual_review.md").write_text("\n".join(review_md),encoding="utf-8")
 md=[f"# Golden evaluation: {subset}","",f"- Run kind: **{run_kind or 'UNSPECIFIED'}**",f"- Production-valid: **{valid}**",f"- HCX: **{provider.get('hcx_mode','unknown')}**",f"- Evidence/Rule/Product: **{provider.get('evidence_provider_mode','unknown')} / {provider.get('rule_provider_mode','unknown')} / {provider.get('product_provider_mode','unknown')}**",f"- PASS: **{counts['PASS']}/{len(rows)} ({percent(counts['PASS'],len(rows))})**",f"- FAIL: **{counts['FAIL']}**",f"- MANUAL_REVIEW: **{counts['MANUAL_REVIEW']}**",f"- Latency avg/p50/p95/max: **{summary['average_latency_ms']:.1f} / {pct(lats,.5):.1f} / {pct(lats,.95):.1f} / {max(lats,default=0):.1f} ms**",f"- HTTP error rate: **{percent(sum(r['http_status']!=200 for r in rows),len(rows))}**","","## Category pass rates",""]
 md += [f"- {c}: {percent(sum(r['auto_result']=='PASS' for r in rs),len(rs))} ({sum(r['auto_result']=='PASS' for r in rs)}/{len(rs)})" for c,rs in sorted(cats.items())]
 md += ["","## Official cases",""]+[f"- {r['id']}: {r['auto_result']} ({', '.join(r['fail_reasons']) or 'deterministic checks passed'})" for r in rows if "official" in r["subsets"]]+["","## Failure types",""]+[f"- {x}: {n}" for x,n in reasons.most_common()]+["","## Failures grouped by type",""]
 for x,_ in reasons.most_common(): md += [f"### {x}",""]+[f"- {r['id']}: {r['question']}" for r in rows if x in r["fail_reasons"]]+[""]
 (out/"summary.md").write_text("\n".join(md),encoding="utf-8")
def legacy(path):
 total=bad=0
 for line in Path(path).read_text().splitlines():
  for c in json.loads(line).get("claims",[]): total+=1; bad+=not(c.get("evidence_ids") or c.get("tool_result_ids"))
 print("No claims found." if not total else f"total_claims={total}\nunsupported_claims={bad}\nunsupported_claim_rate={bad/total:.6f}")
def main():
 a=args()
 if a.input: legacy(a.input); return
 cases=load(a.dataset,a.subset)
 if a.ids:
  selected={x.strip() for x in a.ids.split(",") if x.strip()}; cases=[c for c in cases if c["id"] in selected]
 if a.stability: cases=[dict(cases[i%len(cases)],id=f"STAB-{i+1:03d}") for i in range(a.stability)]
 provider=probe(a.base_url,a.timeout); rows=[]; previous_finished=None
 for sequence,c in enumerate(cases,1):
  gap_ms=None if previous_finished is None else round((time.monotonic()-previous_finished)*1000,3)
  status,body,lat,error,audit=call(a.base_url,{"question_id":c["id"],"question":c["question"],"profile":c.get("profile",{})},a.timeout)
  audit["call_sequence"]=sequence; audit["previous_request_gap_ms"]=gap_ms
  rows.append(score(c,status,body,lat,error,audit)); previous_finished=time.monotonic()
 reports(rows,a.output,a.subset if not a.stability else f"stability-{a.stability}",provider,a.run_kind); print(json.dumps({"output":a.output,"provider":provider,"counts":dict(Counter(r['auto_result'] for r in rows))},ensure_ascii=False))
if __name__=="__main__": main()
