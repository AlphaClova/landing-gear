from scripts.evaluate import score

BASE={"id":"G001","category":"institution","difficulty":"low","question":"질문","must_have_evidence":True,"required_document_ids":[],"required_pages":[],"required_numbers":[],"forbidden_numbers":[],"required_phrases_or_concepts":[],"forbidden_claims":[]}

def body(answer="근거 답변",context=None):
 return {"question_id":"G001","question":"질문","retrieved_context":["문서 근거"] if context is None else context,"think_trace":"{}","answer":answer}

def test_passes_valid_strict_response():
 assert score(BASE,200,body(),1.0,None)["auto_result"]=="PASS"

def test_detects_missing_evidence_and_number():
 c={**BASE,"required_numbers":["900만원"]}
 row=score(c,200,body(context=[]),1.0,None)
 assert {"MISSING_EVIDENCE","WRONG_NUMBER"}<=set(row["fail_reasons"])

def test_detects_schema_and_clarification_failure():
 c={**BASE,"must_ask_clarification":True}
 b=body(); b["extra"]="not strict"
 row=score(c,200,b,1.0,None)
 assert {"SCHEMA_ERROR","MISSED_CLARIFICATION"}<=set(row["fail_reasons"])

def test_detects_service_limitation_phrases_without_broad_false_positive():
 c={**BASE,"must_have_evidence":False,"must_show_limit":True,"expected_response_type":"limitation"}
 assert score(c,200,body("제공된 자료로 확인하기 어렵습니다",[]),1.0,None)["fail_reasons"]==[]
 row=score(c,200,body("자세한 확인이 필요합니다",[]),1.0,None)
 assert "MISSED_LIMITATION" in row["fail_reasons"]
 assert score(c,200,body("정확한 금액을 말씀드릴 수 없습니다",[]),1.0,None)["fail_reasons"]==[]
