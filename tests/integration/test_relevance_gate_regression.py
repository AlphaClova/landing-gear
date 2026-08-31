import json
from pathlib import Path

import pytest

from app.agent.router import IntentRouter
from app.agent.tools import BEvidenceProvider, BProductCatalog, BRuleEngine, ToolRouter


TARGET_IDS = {"G003", "G008", "G021", "G041", "G042", "G046", "G051", "G055", "G059", "G082"}


def _target_cases() -> list[dict[str, object]]:
    rows = [json.loads(line) for line in Path("tests/golden/mirae_eval_120.jsonl").read_text(encoding="utf-8").splitlines()]
    return [row for row in rows if row["id"] in TARGET_IDS]


@pytest.mark.parametrize("case", _target_cases(), ids=lambda case: str(case["id"]))
def test_content_p0_target_retrieval_survives_relevance_gate(case: dict[str, object]) -> None:
    question = str(case["question"])
    intent = IntentRouter().classify(question).intent
    result = ToolRouter(BEvidenceProvider(), BRuleEngine(), BProductCatalog()).run(
        intent, {}, question=question
    )

    assert result.evidence, case["id"]
