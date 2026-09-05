import re

from app.agent.composer import Composer, Draft
from app.agent.hcx_client import HCXClient
from app.agent.router import IntentRouter
from app.agent.slots import SlotManager
from app.agent.tools import BEvidenceProvider, BProductCatalog, BRuleEngine, ToolResult, ToolRouter
from app.agent.verifier import Verifier
from app.api.schemas import Citation
from app.core.config import Settings
from app.core.query_normalization import (
    excerpt_supports_dc_contribution_factor_relation,
    is_dc_contribution_determination_question,
    procedure_type,
)
from tests.unit.test_content_p0_policies import grounded
from tests.unit.test_phase_c1_p0_fixes import G016


G016_CRITERIA = "DC 부담금 결정 기준은 무엇인가요?"
G016_COMPANY = "DC 회사 부담금은 무엇에 따라 결정되나요?"
G016_TENURE_PROBE = "DC 회사 부담금은 근속기간에 따라 달라지나요?"
IRP_TERMINATION = "IRP를 해지하면 어떻게 되나요?"
PENSION_TERMINATION = "연금계좌 해지 시 어떻게 되나요?"

_DC_STRUCTURE = (
    "확정기여형(DC, Defined Contribution)은 무엇인가요? "
    "회사가 매년 일정 금액을 근로자의 계좌에 입금하고, 근로자가 직접 운용하여 "
    "수익률에 따라 최종 퇴직금이 달라집니다."
)
_ELIGIBILITY_NOISE = (
    "1주일 평균 근로시간이 15시간 이상이고 1년 이상 계속 근무하는 경우 "
    "퇴직연금 가입 대상입니다."
)
_FACTOR_SENTENCE = (
    "확정기여형(DC) 부담금은 근속기간과 연령에 따라 책정됩니다."
)

_ASSERTIVE_FACTOR = re.compile(
    r"(근속|연령|나이|직급|임금|호봉).{0,32}(?:따라|달라지|책정|결정)|"
    r"(?:따라|달라지|책정|결정).{0,32}(근속|연령|나이|직급|임금|호봉)"
)
_LIMIT_SKIP = ("단정할 수 없", "확인할 수 없", "확정할 수 없", "[한계]")


def _context(question: str, result: ToolResult | None = None):
    decision = IntentRouter().classify(question)
    if result is None:
        result = ToolRouter(BEvidenceProvider(), BRuleEngine(), BProductCatalog()).run(
            decision.intent,
            SlotManager.extract(question),
            question=question,
        )
    composer = Composer(HCXClient(Settings(hcx_api_key="")))
    return decision, result, composer.build_context(question, decision.intent, result)


def _citation(excerpt: str, *, document_id: str = "doc10", citation_id: str = "ev") -> Citation:
    return Citation(id=citation_id, document_id=document_id, page=1, source="provided", excerpt=excerpt)


def _unsupported_factor_count(text: str) -> int:
    hits = 0
    for match in _ASSERTIVE_FACTOR.finditer(text):
        window = text[max(0, match.start() - 40): match.end() + 40]
        if any(marker in window for marker in _LIMIT_SKIP):
            continue
        hits += 1
    return hits


def test_g016_family_is_detected_without_exact_hardcoding() -> None:
    assert is_dc_contribution_determination_question(G016) is True
    assert is_dc_contribution_determination_question(G016_CRITERIA) is True
    assert is_dc_contribution_determination_question(G016_COMPANY) is True
    assert is_dc_contribution_determination_question(G016_TENURE_PROBE) is True
    assert is_dc_contribution_determination_question("DB형과 DC형의 차이는 무엇인가요?") is False
    assert is_dc_contribution_determination_question("DC형은 회사가 수익률을 책임지는 제도인가요?") is False
    assert is_dc_contribution_determination_question(IRP_TERMINATION) is False


def test_g016_is_not_account_termination() -> None:
    assert procedure_type(G016) != "ACCOUNT_TERMINATION"
    assert procedure_type(IRP_TERMINATION) == "ACCOUNT_TERMINATION"
    assert procedure_type(PENSION_TERMINATION) == "ACCOUNT_TERMINATION"


def test_g016_uses_supported_dc_structure_and_factor_limitation() -> None:
    _, _, context = _context(G016)
    subtasks = [str(item.get("subtask")) for item in context.claim_plan]
    assert "DC_CONTRIBUTION_STRUCTURE" in subtasks
    assert "CONTRIBUTION_DETERMINATION_FACTOR" in subtasks
    structure = next(item for item in context.claim_plan if item["subtask"] == "DC_CONTRIBUTION_STRUCTURE")
    factor = next(item for item in context.claim_plan if item["subtask"] == "CONTRIBUTION_DETERMINATION_FACTOR")
    assert structure.get("status") == "answerable"
    assert structure["claims"][0]["evidence_ids"]
    text = structure["claims"][0]["text"]
    assert "입금" in text and "운용" in text
    assert factor.get("status") == "unsupported"
    assert "[한계]" in str(factor.get("limitation"))
    assert "결정 요인" in str(factor.get("limitation"))
    answer = context.fallback_message
    assert _unsupported_factor_count(answer) == 0
    assert "입금" in answer
    assert "[한계]" in answer


def test_g016_criteria_paraphrase_uses_same_contract() -> None:
    _, _, context = _context(G016_CRITERIA)
    assert any(item.get("subtask") == "DC_CONTRIBUTION_STRUCTURE" and item.get("status") == "answerable" for item in context.claim_plan)
    assert any(
        item.get("subtask") == "CONTRIBUTION_DETERMINATION_FACTOR" and item.get("status") == "unsupported"
        for item in context.claim_plan
    )
    assert _unsupported_factor_count(context.fallback_message) == 0


def test_g016_does_not_affirm_tenure_without_direct_support() -> None:
    result = ToolResult(evidence=[
        _citation(_DC_STRUCTURE, citation_id="s1"),
        _citation(_ELIGIBILITY_NOISE, citation_id="noise"),
    ])
    assert excerpt_supports_dc_contribution_factor_relation(_ELIGIBILITY_NOISE) is False
    _, _, context = _context(G016_TENURE_PROBE, result)
    answer = context.fallback_message
    assert "그렇다" not in answer
    assert not re.search(r"근속.{0,20}달라집니다", answer)
    assert _unsupported_factor_count(answer) == 0
    assert "[한계]" in answer


def test_g016_keeps_direct_factor_only_when_evidence_supports_it() -> None:
    result = ToolResult(evidence=[
        _citation(_DC_STRUCTURE, citation_id="s1"),
        _citation(_FACTOR_SENTENCE, citation_id="f1"),
    ])
    assert excerpt_supports_dc_contribution_factor_relation(_FACTOR_SENTENCE) is True
    _, _, context = _context(G016, result)
    factor = next(item for item in context.claim_plan if item["subtask"] == "CONTRIBUTION_DETERMINATION_FACTOR")
    assert factor.get("status") == "answerable"
    assert "근속" in factor["claims"][0]["text"]


def test_g016_hcx_extra_factor_is_restored_to_contract() -> None:
    _, result, context = _context(G016)
    leaked = (
        context.fallback_message
        + "\n또한 DC 부담금은 근로자의 근속 기간과 연령에 따라 다르게 책정될 수 있습니다."
    )
    draft = Draft(message=leaked, citations=result.evidence, context=context)
    verifier = Verifier()
    issues = verifier.check(draft)
    assert "핵심 grounded contract 변경 또는 일부 누락" in issues
    assert verifier.repair_safe(draft, issues)
    assert draft.message == context.fallback_message
    assert _unsupported_factor_count(draft.message) == 0


def test_g016_does_not_change_db_dc_difference_contract() -> None:
    _, _, _, context = grounded("DB형과 DC형의 차이는 무엇인가요?")
    assert any(item.get("subtask") == "db_dc_difference" for item in context.claim_plan)
    assert not any(item.get("subtask") == "CONTRIBUTION_DETERMINATION_FACTOR" for item in context.claim_plan)
