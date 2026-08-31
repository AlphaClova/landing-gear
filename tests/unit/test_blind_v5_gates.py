import json
from pathlib import Path

from app.agent.canonical import answer_affirms_false_premise
from tests.unit.test_content_p0_policies import grounded


BLIND_FALSE_PREMISE = Path("tests/golden/blind_false_premise_15.jsonl")
BLIND_CONSTRAINT = Path("tests/golden/blind_constraint_15.jsonl")


def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_blind_false_premise_dataset_has_fifteen_new_sentences() -> None:
    rows = _load(BLIND_FALSE_PREMISE)
    assert len(rows) == 15
    assert len({row["question"] for row in rows}) == 15
    assert all(row["must_correct_false_premise"] for row in rows)


def test_blind_false_premise_forbids_affirmation_and_requires_grounded_correction() -> None:
    for row in _load(BLIND_FALSE_PREMISE):
        _, _, result, context = grounded(row["question"])
        assert not answer_affirms_false_premise(context.fallback_message), row["question"]
        if not result.evidence and not result.products:
            assert "한계" in context.fallback_message or "확인할 수 없" in context.fallback_message, row["question"]
            continue
        assert context.false_premise, row["question"]
        assert context.fallback_message.startswith("아닙니다") or context.fallback_message.startswith("아니요"), row["question"]
        assert context.correction_fact
        assert context.correction_evidence_id


def test_blind_constraint_dataset_has_fifteen_new_sentences() -> None:
    rows = _load(BLIND_CONSTRAINT)
    assert len(rows) == 15
    assert len({row["question"] for row in rows}) == 15


def test_blind_constraint_provenance_and_no_hard_dump() -> None:
    for row in _load(BLIND_CONSTRAINT):
        _, _, result, context = grounded(row["question"])
        constraints = result.recommendation_constraints
        assert constraints, row["question"]
        for item in constraints:
            assert "applied" in item and "constraint" in item, row["question"]
            if item.get("kind") == "hard" and not item.get("applied"):
                assert result.products == [], row["question"]
                assert "미래에셋장기성장" not in context.fallback_message, row["question"]
        if any(item.get("constraint") == "principal_guarantee" for item in constraints):
            guarantee = next(item for item in constraints if item["constraint"] == "principal_guarantee")
            assert guarantee["applied"] is False
            assert result.products == []
            assert "원금보장" in context.fallback_message or "상품 후보를 제시하지 않습니다" in context.fallback_message
        if any(item.get("constraint") == "investment_horizon" for item in constraints):
            horizon = next(item for item in constraints if item["constraint"] == "investment_horizon")
            assert horizon["applied"] is False
            assert "적용하지 않았습니다" in context.fallback_message or "특정할 수 없습니다" in context.fallback_message or "투자기간 적합성" in context.fallback_message
