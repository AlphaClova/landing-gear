"""Build a human-review pack without changing evaluator decisions."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

REVIEW_FIELDS = [
    "accuracy", "evidence_completeness", "requirement_coverage", "groundedness",
    "reasoning", "safety", "limit_handling", "unsupported_claim_found",
    "unsupported_number_found", "wrong_number_found", "wrong_evidence_found",
    "overconfident_recommendation", "unnecessary_clarification", "overall_pass",
    "reviewer", "comment",
]
CATEGORY_TARGETS = {
    "institution": 3,
    "tax": 2,
    "combined": 2,
    "product_compare": 2,
    "conditional_recommendation": 2,
    "procedure": 2,
    "safety/out_of_scope": 2,
}
PRIORITY_IDS = {"G051", "G076"}


def bucket(category: str) -> str:
    return "safety/out_of_scope" if category in {"safety", "out_of_scope"} else category


def response_type(row: dict) -> str:
    answer = row.get("answer", "")
    if "[필요한 조건]" in answer or answer.rstrip().endswith("?"):
        return "clarification"
    if row.get("category") in {"safety", "out_of_scope"} or answer.startswith(("[한계]", "[거절]")):
        return "limitation"
    return "result"


def compact(row: dict, reason: str) -> dict:
    try:
        trace = json.loads(row.get("think_trace") or "{}")
    except json.JSONDecodeError:
        trace = {}
    evidence = row.get("retrieved_context", [])
    product_facts = [item for item in evidence if str(item).startswith("상품명:")]
    rule_calls = trace.get("rule_results", [])
    if not rule_calls:
        rule_calls = [call for call in trace.get("tool_calls", []) if call.get("tool_name") in {"calculate", "calculate_withdrawal_comparison"}]
    base = {
        "id": row["id"], "category": row["category"], "review_reason": reason,
        "HIGH_PRIORITY_REVIEW": row["id"] in PRIORITY_IDS, "question": row["question"],
        "final_answer": row.get("answer", ""), "response_type": response_type(row),
        "retrieved_evidence": json.dumps(evidence, ensure_ascii=False),
        "document_id_page": json.dumps(row.get("retrieved_provenance", []), ensure_ascii=False),
        "product_fact": json.dumps(trace.get("product_facts", product_facts), ensure_ascii=False),
        "rule_result": json.dumps(rule_calls, ensure_ascii=False),
        "hcx_attempts": row.get("hcx_attempts", 0),
        "safe_repair": bool(row.get("deterministic_repaired")),
        "fallback": bool(row.get("fallback_used")),
        "fallback_reason": row.get("fallback_reason") or "",
    }
    return {**base, **{field: "" for field in REVIEW_FIELDS}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    rows = data["results"]
    chosen: dict[str, str] = {r["id"]: "MANUAL_REVIEW" for r in rows if r["auto_result"] == "MANUAL_REVIEW"}
    for row in rows:
        if row["id"] in PRIORITY_IDS:
            chosen.setdefault(row["id"], "STRATIFIED_PASS_SAMPLE" if row["auto_result"] == "PASS" else "HIGH_PRIORITY_REVIEW")
    for category, target in CATEGORY_TARGETS.items():
        existing = sum(reason == "STRATIFIED_PASS_SAMPLE" and bucket(r["category"]) == category for r in rows for reason in [chosen.get(r["id"])])
        candidates = [r for r in rows if r["auto_result"] == "PASS" and bucket(r["category"]) == category and r["id"] not in chosen]
        needed = max(0, target - existing)
        for _ in range(needed):
            if not candidates:
                break
            if category == "safety/out_of_scope":
                candidates.sort(key=lambda r: (sum(x["category"] == r["category"] and chosen.get(x["id"]) == "STRATIFIED_PASS_SAMPLE" for x in rows), r["id"]))
            row = candidates.pop(0)
            chosen[row["id"]] = "STRATIFIED_PASS_SAMPLE"
    while sum(reason == "STRATIFIED_PASS_SAMPLE" for reason in chosen.values()) < 15:
        counts = {category: sum(reason == "STRATIFIED_PASS_SAMPLE" and bucket(r["category"]) == category for r in rows for reason in [chosen.get(r["id"])]) for category in CATEGORY_TARGETS}
        candidates = [r for r in rows if r["auto_result"] == "PASS" and r["id"] not in chosen]
        if not candidates:
            break
        candidates.sort(key=lambda r: (counts.get(bucket(r["category"]), 0), r["id"]))
        chosen[candidates[0]["id"]] = "STRATIFIED_PASS_SAMPLE"
    packed = [compact(r, chosen[r["id"]]) for r in rows if r["id"] in chosen]
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    fields = list(packed[0]) if packed else []
    with (out / "manual_review.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(packed)
    lines = ["# Full v3 human review pack", "", f"- Total: **{len(packed)}**", f"- MANUAL_REVIEW: **{sum(x['review_reason']=='MANUAL_REVIEW' for x in packed)}**", f"- PASS samples: **{sum(x['review_reason']=='STRATIFIED_PASS_SAMPLE' for x in packed)}**", ""]
    for item in packed:
        lines += [f"## {item['id']}", "", f"- Category: {item['category']}", f"- Review reason: {item['review_reason']}", f"- HIGH_PRIORITY_REVIEW: {str(item['HIGH_PRIORITY_REVIEW']).lower()}", f"- Response type: {item['response_type']}", f"- HCX attempts: {item['hcx_attempts']}", f"- Safe repair: {item['safe_repair']}", f"- Fallback: {item['fallback']}", f"- Fallback reason: {item['fallback_reason'] or '(none)'}", "", "### Question", "", item["question"], "", "### Final answer", "", item["final_answer"], "", "### Retrieved evidence", "", item["retrieved_evidence"], "", "### Document/page", "", item["document_id_page"], "", "### Product Fact", "", item["product_fact"], "", "### Rule Result", "", item["rule_result"], "", "### Human checks", ""]
        lines += [f"- {field}:" for field in REVIEW_FIELDS] + [""]
    (out / "manual_review.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps({"manual_cases": sum(x["review_reason"] == "MANUAL_REVIEW" for x in packed), "pass_samples": sum(x["review_reason"] == "STRATIFIED_PASS_SAMPLE" for x in packed), "total": len(packed)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
