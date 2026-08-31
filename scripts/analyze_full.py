"""Create a read-only diagnostic report from a completed Full evaluation."""
import json, math, statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("artifacts/eval/full-real-v1")
data = json.loads((ROOT / "latest.json").read_text(encoding="utf-8"))
rows = data["results"]

def trace(row):
    try: return json.loads(row.get("think_trace") or "{}")
    except json.JSONDecodeError: return {}

def response_type(row):
    a=row["answer"]
    if "[필요한 조건]" in a: return "clarification"
    if "범위를 벗어나" in a or a.startswith("[한계]"): return "limitation"
    return "result"

def root_cause(row):
    a=row["answer"]; cat=row["category"]
    if row["id"] in {"G103","G105","G106","G107","G108"}: return ["EVALUATOR_FALSE_NEGATIVE"]
    if "FALSE_PREMISE_ACCEPTED" in row["fail_reasons"]: return ["RETRIEVAL","HCX_GROUNDEDNESS"]
    if "범위를 벗어나" in a and cat not in {"out_of_scope","safety"}: return ["ROUTER"]
    if cat=="conditional_recommendation" and response_type(row)=="clarification": return ["EVALUATOR_FALSE_NEGATIVE"]
    if response_type(row)=="clarification": return ["SLOT_POLICY"]
    if not row["retrieved_context"]: return ["RETRIEVAL","HCX_GROUNDEDNESS"]
    return ["VERIFIER"]

def priority(row, roots):
    if any(x in row["fail_reasons"] for x in ("HTTP_ERROR","TIMEOUT","SCHEMA_ERROR","WRONG_NUMBER","FALSE_PREMISE_ACCEPTED","MISSED_CLARIFICATION","MISSED_LIMITATION")): return "P0"
    if "ROUTER" in roots or "HCX_GROUNDEDNESS" in roots: return "P0"
    if "SLOT_POLICY" in roots or "EVALUATOR_FALSE_NEGATIVE" in roots: return "P1"
    return "P1"

fails=[]
for r in rows:
    if r["auto_result"]!="FAIL": continue
    t=trace(r); roots=root_cause(r)
    fails.append({"id":r["id"],"category":r["category"],"question":r["question"],"actual_intent":t.get("intent"),
      "route":t.get("route"),"response_type":response_type(r),"requested_slots":r["answer"].split("[필요한 조건]",1)[1].strip() if "[필요한 조건]" in r["answer"] else "",
      "documents":r["retrieved_provenance"],"tool_calls":t.get("tool_calls",[]),"answer":r["answer"],"fail_reasons":r["fail_reasons"],
      "root_cause":roots,"bug_type":"evaluator bug" if roots==["EVALUATOR_FALSE_NEGATIVE"] else "service bug","priority":priority(r,roots),"latency_ms":r["latency_ms"]})
(ROOT/"fail-root-causes.json").write_text(json.dumps(fails,ensure_ascii=False,indent=2),encoding="utf-8")

cats=defaultdict(list)
for r in rows: cats[r["category"]].append(r)
md=["# Full Real v1 diagnostic report","",f"- PASS: {sum(r['auto_result']=='PASS' for r in rows)}",f"- FAIL: {len(fails)}",f"- MANUAL_REVIEW: {sum(r['auto_result']=='MANUAL_REVIEW' for r in rows)}","","## Category summary","","| category | total | PASS | FAIL | MANUAL | HCX | safe repair | fallback | p50 | p95 |","|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
for cat,rs in sorted(cats.items()):
    l=sorted(x["latency_ms"] for x in rs); q=lambda z:l[max(0,math.ceil(len(l)*z)-1)]
    md.append(f"| {cat} | {len(rs)} | {sum(x['auto_result']=='PASS' for x in rs)} | {sum(x['auto_result']=='FAIL' for x in rs)} | {sum(x['auto_result']=='MANUAL_REVIEW' for x in rs)} | {sum(x['hcx_invoked'] for x in rs)} | {sum(x.get('deterministic_repaired',False) for x in rs)} | {sum(x['fallback_used'] for x in rs)} | {q(.5):.1f} | {q(.95):.1f} |")
md += ["","## Root causes",""]
for k,v in Counter(x for f in fails for x in f["root_cause"]).most_common(): md.append(f"- {k}: {v}")
md += ["","## All failures",""]
for f in fails:
    md += [f"### {f['id']} — {f['priority']}","",f"- Category: {f['category']}",f"- Question: {f['question']}",f"- Actual intent/path: {f['actual_intent']} / {f['route']}",f"- Response type: {f['response_type']}",f"- Requested slots: {f['requested_slots'] or '(none)'}",f"- Evidence: {f['documents'] or '(none)'}",f"- Fail reason: {', '.join(f['fail_reasons'])}",f"- Root cause: {', '.join(f['root_cause'])}",f"- Classification: {f['bug_type']}",f"- Latency: {f['latency_ms']} ms","","Answer:","",f["answer"],""]
(ROOT/"full-diagnostic.md").write_text("\n".join(md),encoding="utf-8")
print(json.dumps({"failures":len(fails),"root_causes":Counter(x for f in fails for x in f["root_cause"])},ensure_ascii=False,default=dict))
