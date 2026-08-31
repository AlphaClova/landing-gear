import csv

from scripts.evaluate import reports, score

BASE={"id":"G001","category":"institution","difficulty":"low","question":"질문","must_have_evidence":True,"required_document_ids":[],"required_pages":[],"required_numbers":[],"forbidden_numbers":[],"required_phrases_or_concepts":[],"forbidden_claims":[]}

def body(answer="근거 답변",context=None):
 if context is None:
  ctx="[DOC doc1][PAGE 1][EVIDENCE e1]\n문서 근거"
 elif context=="" or context==[]:
  ctx=""
 elif isinstance(context,list):
  ctx="\n\n".join(f"[DOC d][EVIDENCE e]\n{item}" for item in context)
 else:
  ctx=context
 return {"question_id":"G001","question":"질문","retrieved_context":ctx,"think_trace":"{}","answer":answer}


def test_passes_valid_strict_response():
 assert score(BASE,200,body(),1.0,None)["auto_result"]=="PASS"


def test_public_list_context_is_schema_error():
 row=score(BASE,200,{**body(),"retrieved_context":["문서 근거"]},1.0,None)
 assert "SCHEMA_ERROR" in row["fail_reasons"]


def test_detects_missing_evidence_and_number():
 c={**BASE,"required_numbers":["900만원"]}
 row=score(c,200,body(context=""),1.0,None)
 assert {"MISSING_EVIDENCE","WRONG_NUMBER"}<=set(row["fail_reasons"])

def test_detects_schema_and_clarification_failure():
 c={**BASE,"must_ask_clarification":True}
 b=body(); b["extra"]="not strict"
 row=score(c,200,b,1.0,None)
 assert {"SCHEMA_ERROR","MISSED_CLARIFICATION"}<=set(row["fail_reasons"])

def test_detects_service_limitation_phrases_without_broad_false_positive():
 c={**BASE,"must_have_evidence":False,"must_show_limit":True,"expected_response_type":"limitation"}
 assert score(c,200,body("제공된 자료로 확인하기 어렵습니다",""),1.0,None)["fail_reasons"]==[]
 row=score(c,200,body("자세한 확인이 필요합니다",""),1.0,None)
 assert "MISSED_LIMITATION" in row["fail_reasons"]
 assert score(c,200,body("정확한 금액을 말씀드릴 수 없습니다",""),1.0,None)["fail_reasons"]==[]


def test_manual_review_pack_includes_every_auto_fail(tmp_path):
 rows=[]
 for index,result in enumerate(("FAIL","MANUAL_REVIEW","PASS"),1):
  rows.append({
   "id":f"G{index:03d}","category":"institution","difficulty":"low","question":"q",
   "http_status":200,"latency_ms":1.0,"auto_result":result,"fail_reasons":[],"details":[],
   "answer":"a","retrieved_context":[],"retrieved_provenance":[],"think_trace":"{}",
   "hcx_invoked":False,"hcx_attempts":0,"hcx_success":False,"hcx_first_pass":False,
   "hcx_regenerated":False,"deterministic_repaired":False,"hcx_timeout_count":0,
   "hcx_audit":[],"prompt_metrics":{},"fallback_used":False,"fallback_reason":None,
   "manual_review_required":result=="MANUAL_REVIEW","subsets":[],"request_audit":{},
  })
 provider={key:"real" for key in ("hcx_mode","evidence_provider_mode","rule_provider_mode","product_provider_mode")}
 reports(rows,tmp_path,"full",provider,"ORIGINAL_SINGLE_RUN")
 with (tmp_path/"manual_review.csv").open(encoding="utf-8-sig") as stream:
  ids={row["id"] for row in csv.DictReader(stream)}
 assert {"G001","G002"} <= ids


def test_manual_review_pack_includes_p0_candidates_even_if_pass(tmp_path):
 rows=[]
 for item_id, result, category in (("G001","FAIL","tax"),("G102","PASS","safety"),("G089","PASS","conditional_recommendation")):
  rows.append({
   "id":item_id,"category":category,"difficulty":"low","question":"q",
   "http_status":200,"latency_ms":1.0,"auto_result":result,"fail_reasons":[],"details":[],
   "answer":"a","retrieved_context":[],"retrieved_provenance":[],"think_trace":"{}",
   "hcx_invoked":False,"hcx_attempts":0,"hcx_success":False,"hcx_first_pass":False,
   "hcx_regenerated":False,"deterministic_repaired":False,"hcx_timeout_count":0,
   "hcx_audit":[],"prompt_metrics":{},"fallback_used":False,"fallback_reason":None,
   "manual_review_required":False,"subsets":[],"request_audit":{},
  })
 provider={key:"real" for key in ("hcx_mode","evidence_provider_mode","rule_provider_mode","product_provider_mode")}
 reports(rows,tmp_path,"full",provider,"ORIGINAL_SINGLE_RUN")
 with (tmp_path/"manual_review.csv").open(encoding="utf-8-sig") as stream:
  ids={row["id"] for row in csv.DictReader(stream)}
 assert {"G001","G102","G089"} <= ids
