import json
from collections import Counter
from pathlib import Path

DATA=Path(__file__).with_name("mirae_eval_120.jsonl")
PARAPHRASES=Path(__file__).with_name("official_paraphrase_15.jsonl")
def test_golden_dataset_shape_and_distribution():
 rows=[json.loads(x) for x in DATA.read_text(encoding="utf-8").splitlines()]
 assert len(rows)==120 and len({x["id"] for x in rows})==120
 assert Counter(x["category"] for x in rows)=={"institution":15,"tax":20,"combined":20,"product_compare":20,"conditional_recommendation":15,"procedure":10,"safety":10,"out_of_scope":10}
 assert sum("official" in x["subsets"] for x in rows)==5
 assert sum("smoke" in x["subsets"] for x in rows)==20
 required={"id","category","difficulty","question","expected_intent","expected_response_type","required_document_ids","required_pages","required_numbers","forbidden_numbers","required_phrases_or_concepts","forbidden_claims","required_slots","must_correct_false_premise","must_ask_clarification","must_show_limit","must_have_evidence"}
 assert all(required<=set(x) for x in rows)

def test_official_paraphrase_dataset_has_three_variants_each():
 rows=[json.loads(x) for x in PARAPHRASES.read_text(encoding="utf-8").splitlines()]
 assert len(rows)==15
 assert Counter(x["category"] for x in rows)=={"institution":3,"tax":3,"combined":3,"product_compare":3,"conditional_recommendation":3}
