from app.agent.composer import Draft
from app.agent.product_evidence import (
    answer_fee_mapping,
    extract_fee_table,
    render_fee_table_claim,
    structured_fee_mapping,
)
from app.agent.verifier import Verifier
from app.api.schemas import Citation
from tests.contract.test_public_evidence_pruning_gates import _public
from tests.unit.test_content_p0_policies import grounded


G072 = "총보수 0% 상품만 찾아줘"
FEE_TABLE = """
구분 | 지급비용(연간%)
| 집합투자업자 보수 | 판매회사 보수 | 신탁업자 보수 | 일반사무관리회사 보수
| 총 보수 | 기타비용 | 총보수비용 | 동종유형 총 보수 | 합성총보수비용
종류A 수수료선취-오프라인 | 0.12 | 0.19 | 0.02 | 0.02 | 0.35 | 0.01 | 0.36 | 0.33 | 0.36
"""


def _citation(excerpt: str = FEE_TABLE) -> Citation:
    return Citation(id="fee-table", document_id="prospectus", page=27, source="prospectus", excerpt=excerpt)


def test_fee_table_parser_preserves_each_adjacent_label_value() -> None:
    mapping = structured_fee_mapping(extract_fee_table(_citation()))
    assert mapping == {
        "집합투자업자 보수": "0.12",
        "판매회사 보수": "0.19",
        "신탁업자 보수": "0.02",
        "일반사무관리회사 보수": "0.02",
        "총 보수": "0.35",
        "기타비용": "0.01",
        "총보수비용": "0.36",
        "동종유형 총 보수": "0.33",
        "합성총보수비용": "0.36",
    }


def test_missing_fee_column_does_not_borrow_an_adjacent_value() -> None:
    missing_peer_label = FEE_TABLE.replace("동종유형 총 보수", "동종유형")
    missing_peer_value = FEE_TABLE.replace("| 0.36 | 0.33 | 0.36", "| 0.36 | 0.36")
    assert extract_fee_table(_citation(missing_peer_label)) == {}
    assert extract_fee_table(_citation(missing_peer_value)) == {}


def test_rendered_fee_claim_round_trips_without_label_collision() -> None:
    fields = extract_fee_table(_citation())
    claim = render_fee_table_claim(fields)
    assert claim is not None
    assert answer_fee_mapping(claim) == {
        label: [value] for label, value in structured_fee_mapping(fields).items()
    }


def test_g072_claim_contract_contains_structured_fee_mapping() -> None:
    _, _, result, context = grounded(G072)
    cost = next(item for item in context.claim_plan if item["subtask"] == "product_cost")
    assert cost["status"] == "answerable"
    assert cost["structured_fee_mapping"]["총 보수"] == "0.35"
    assert cost["structured_fee_mapping"]["총보수비용"] == "0.36"
    assert cost["structured_fee_mapping"]["동종유형 총 보수"] == "0.33"
    assert any(item.page == 27 for item in result.evidence)


def test_verifier_rejects_and_repairs_swapped_fee_mapping() -> None:
    _, _, result, context = grounded(G072)
    draft = Draft(
        message="총 보수: 0.36%, 총보수비용: 0.35%, 동종유형 총 보수: 0.36%",
        citations=result.evidence,
        context=context,
    )
    verifier = Verifier()
    issues = verifier.check(draft)
    assert "product fee mapping mismatch" in issues
    assert verifier.repair_safe(draft, issues)
    assert draft.message == context.fallback_message
    assert verifier.check(draft) == []


def test_g072_public_support_restore_keeps_direct_fee_page() -> None:
    _, public = _public(G072, "G072")
    assert "[PAGE 27]" in public.retrieved_context
    assert all(value in public.retrieved_context for value in ("0.12", "0.19", "0.35", "0.36", "0.33"))
