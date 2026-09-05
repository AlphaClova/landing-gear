from app.agent.composer import Draft, GroundedContext
from app.agent.verifier import Verifier
from app.api.schemas import Citation, InternalAnswer, ThinkTrace
from app.api.public_evidence import select_public_citations
from tests.unit.test_content_p0_policies import grounded


G013 = "공무원도 회사 DB형에 가입할 수 있죠?"
G099 = "퇴직위로금과 법정퇴직금을 분리 입금하려면?"
G002 = "연금저축이랑 IRP에 넣으면 세액공제 얼마까지 되나요? 다 합쳐서요."


def _citation(evidence_id: str, excerpt: str, *, document_id: str = "doc", page: int = 1) -> Citation:
    return Citation(id=evidence_id, document_id=document_id, page=page, source="provided", excerpt=excerpt)


def test_eligibility_spacing_normalization_binds_direct_relation() -> None:
    _, _, result, context = grounded(G013)
    relation = next(item for item in context.claim_plan if item["subtask"] == "eligibility_relation")
    evidence_ids = relation["claims"][0]["evidence_ids"]
    assert evidence_ids
    support = next(item for item in result.evidence if item.id in evidence_ids)
    assert "가입대상" in support.excerpt.replace(" ", "")
    assert "가입 대상" in relation["claims"][0]["text"]


def test_bound_eligibility_relation_preserves_direct_public_citation() -> None:
    _, _, result, context = grounded(G013)
    answer = context.fallback_message
    internal = InternalAnswer(
        type="result", message=answer, request_id="req-c6", citations=result.evidence,
        trace=ThinkTrace(intent="제도", route="fast_path", route_confidence=1.0, claim_plan=context.claim_plan),
    )
    selected = select_public_citations(internal, G013)
    assert len(selected) == 1
    assert selected[0].page == 2
    assert "공무원" in selected[0].excerpt and "별도" in selected[0].excerpt


def test_unsupported_negative_eligibility_relation_is_repaired_to_limitation() -> None:
    unrelated = _citation("unrelated", "일반 퇴직연금 제도 안내")
    context = GroundedContext(
        question=G013, intent="제도", response_mode="result", evidence=[unrelated],
        fallback_message="[한계] 제공된 근거로 가입 대상을 확인할 수 없습니다.",
    )
    draft = Draft(
        message="공무원은 일반 퇴직연금 가입 대상이 아니며 별도 제도를 적용받습니다.",
        citations=[unrelated], context=context,
    )
    verifier = Verifier()
    assert "unsupported factual claim" in verifier.check(draft)
    assert verifier.repair_safe(draft, verifier.check(draft))
    assert draft.message == context.fallback_message


def test_spaced_retirement_income_tax_is_detected() -> None:
    _, _, result, context = grounded(G099)
    message = (
        "법정외퇴직금은 연금저축에서 중도인출할 수 있습니다. "
        "중도 인출 시 퇴직 소득세가 공제됩니다."
    )
    draft = Draft(message=message, citations=result.evidence, context=context)
    assert "unsupported factual claim" in Verifier().check(draft)


def test_irp_legal_retirement_tax_does_not_support_pension_savings_nonstatutory_tuple() -> None:
    _, _, result, context = grounded(G099)
    draft = Draft(
        message="연금저축의 법정외퇴직금은 중도인출 시 퇴직소득세가 차감됩니다.",
        citations=result.evidence, context=context,
    )
    assert "unsupported factual claim" in Verifier().check(draft)


def test_direct_tax_tuple_support_passes() -> None:
    support = _citation(
        "direct-tax-tuple",
        "연금저축의 법정외퇴직금은 중도인출 시 퇴직소득세가 차감됩니다.",
    )
    context = GroundedContext(
        question=G099, intent="세제", response_mode="result", evidence=[support],
        fallback_message="[한계] 제공된 근거만 안내합니다.",
    )
    draft = Draft(message=support.excerpt, citations=[support], context=context)
    assert "unsupported factual claim" not in Verifier().check(draft)


def test_clean_tax_credit_support_drops_redundant_mixed_scope_public_citation() -> None:
    clean = _citation("clean", "세액공제 납입한도는 연금저축 연600만원, IRP 합산 연900만원입니다.", document_id="doc41")
    mixed = _citation(
        "mixed",
        "IRP에만 900만원 납입해도 세액공제 효과는 같습니다. 중도인출 시 과세재원에는 16.5% 기타소득세가 적용됩니다.",
        document_id="doc41",
    )
    answer = "연금저축 세액공제 대상 납입한도는 연 600만원이고 IRP 합산 한도는 연 900만원입니다."
    internal = InternalAnswer(
        type="result", message=answer, request_id="req-c6", citations=[clean, mixed],
        trace=ThinkTrace(intent="세제", route="fast_path", route_confidence=1.0),
    )
    assert select_public_citations(internal, G002) == [clean]
