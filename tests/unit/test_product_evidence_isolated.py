import json
import re
from pathlib import Path

import pytest

from app.agent.composer import Composer, Draft, GroundedContext
from app.agent.hcx_client import HCXClient
from app.agent.product_evidence import (
    BLOCKED_INTENTS,
    G033_FORBIDDEN_TAX_CLAIMS,
    PRODUCT_EVIDENCE_INTENTS,
    ProductEvidenceIsolationError,
    allows_product_evidence_enrichment,
    build_product_evidence_bundles,
    citations_for_product,
    render_product_comparison,
)
from app.agent.router import IntentRouter
from app.agent.slots import SlotManager
from app.agent.tools import BEvidenceProvider, BProductCatalog, BRuleEngine, ToolRouter
from app.agent.verifier import Verifier
from app.api.schemas import Citation
from app.core.config import Settings


G033_BASELINE = json.loads(
    Path("artifacts/eval/g033-v7-baseline/g033.json").read_text(encoding="utf-8")
)

SHORT = {
    "product_id": "short",
    "product_name": "미래에셋솔로몬단기국공채증권자투자신탁1호(채권)",
    "asset_type": "채권",
    "risk_level": 5,
    "risk_label": "낮은 위험",
    "plan_types": ["IRP"],
    "document_id": "r2_short",
    "page": 1,
}
MID = {
    "product_id": "mid",
    "product_name": "미래에셋솔로몬중장기국공채증권자투자신탁1호(채권)",
    "asset_type": "채권",
    "risk_level": 5,
    "risk_label": "낮은 위험",
    "plan_types": ["IRP"],
    "document_id": "r2_mid",
    "page": 1,
}
LONG = {
    "product_id": "long",
    "product_name": "미래에셋솔로몬장기국공채증권자투자신탁1호(채권)",
    "asset_type": "채권",
    "risk_level": 5,
    "risk_label": "낮은 위험",
    "plan_types": ["IRP"],
    "document_id": "r2_long",
    "page": 1,
}

SHORT_EXCERPT = (
    "<요약정보> (작성기준일 : 2025년 02월 07일) 미래에셋솔로몬단기국공채증권자투자신탁1호(채권) "
    "2. 투자전략 투자전략 이 투자신탁은 “미래에셋 솔로몬 단기 국공채 증권모투자신탁(채권)“에 90% 이상 투자합니다. "
    "분류 투자신탁, 증권(채권형) 수수료선취-오프라인(A) - 0.65 0.45 0.25 0.66 67 138 212 371 824"
)
ULTRA_EXCERPT = (
    "<요약정보> (작성기준일 : 2025년 11월 21일) 미래에셋솔로몬초단기국공채증권자투자신탁2호(채권) "
    "2. 투자전략 투자전략 ① 이 투자신탁은 \"미래에셋솔로몬초단기국공채증권모투자신탁(채권)”에 80% 이상으로 투자합니다. "
    "분류 수수료선취-오프라인(A) 0.32 0.2 0.25 0.32 42 77 113 189 409"
)
MID_EXCERPT = (
    "<요약정보> (작성기준일 : 2025년 08월 22일) 미래에셋솔로몬중장기국공채증권자투자신탁1호(채권) "
    "2. 투자전략 투자전략 이 투자신탁은 \"미래에셋솔로몬중장기국공채증권모투자신탁(채권)”에 80% 이상으로 투자합니다. "
    "분류 수수료선취-오프라인(A) 0.43 0.31 0.25 0.43 74 120 168 271 567"
)
LONG_EXCERPT = (
    "<요약정보> (작성기준일 : 2025년 12월 23일) 미래에셋솔로몬장기국공채증권자투자신탁1호(채권) "
    "2. 투자전략 투자전략 미래에셋솔로몬장기국공채증권모투자신탁(채권)에 90% 이상 투자합니다. "
    "분류 수수료선취-오프라인(A) 0.35 0.19 0.33 0.36 66 105 146 232 479"
)


def _cite(eid: str, doc: str, excerpt: str) -> Citation:
    return Citation(id=eid, document_id=doc, page=1, source="prospectus", excerpt=excerpt)


def grounded(question: str):
    decision = IntentRouter().classify(question)
    slots = SlotManager.extract(question)
    tools = ToolRouter(BEvidenceProvider(), BRuleEngine(), BProductCatalog())
    result = tools.run(decision.intent, slots, question=question, rule_id={"세제": "retirement_income_tax", "종합": "lump_sum_vs_pension"}.get(decision.intent))
    composer = Composer(HCXClient(Settings(hcx_api_key="")))
    return decision, result, composer.build_context(question, decision.intent, result)


def test_enrichment_allowed_only_for_product_intent() -> None:
    assert PRODUCT_EVIDENCE_INTENTS == {"상품"}
    assert allows_product_evidence_enrichment("상품") is True
    for intent in BLOCKED_INTENTS:
        assert allows_product_evidence_enrichment(intent) is False
        with pytest.raises(ProductEvidenceIsolationError):
            build_product_evidence_bundles([SHORT], [], intent=intent)


def test_g033_intent_blocks_product_enrichment() -> None:
    decision, result, context = grounded(G033_BASELINE["question"])
    assert decision.intent == "종합"
    assert allows_product_evidence_enrichment(decision.intent) is False
    assert G033_BASELINE["answer"].strip() in context.fallback_message
    for claim in G033_FORBIDDEN_TAX_CLAIMS:
        assert claim not in context.fallback_message
    assert "총보수·비용 비율" not in context.fallback_message
    assert json.loads(G033_BASELINE["think_trace"])["intent"] == "종합"
    assert json.loads(G033_BASELINE["think_trace"])["tools"] == ["retrieve_evidence"]


def test_g033_hallucinated_tax_claim_is_repaired() -> None:
    _, result, context = grounded(G033_BASELINE["question"])
    draft = Draft(
        message="법정 외 퇴직금의 경우에는 IRP 추가 납입 시에는 과세가 발생하지만 퇴직금 재원은 과세가 발생하지 않습니다.",
        citations=result.evidence,
        context=context,
    )
    verifier = Verifier()
    issues = verifier.check(draft)
    assert "unsupported factual claim" in issues
    assert verifier.repair_safe(draft, issues)
    assert draft.message == context.fallback_message
    assert "과세가 발생하지 않습니다" not in draft.message


def test_g033_tax_claim_variant_hana_is_repaired() -> None:
    _, result, context = grounded(G033_BASELINE["question"])
    draft = Draft(
        message=(
            "법정 외 퇴직금의 경우에는 IRP 추가 납입 시에는 과세가 발생하나 "
            "퇴직금 재원은 과세가 발생하지 않습니다."
        ),
        citations=result.evidence,
        context=context,
    )
    verifier = Verifier()
    issues = verifier.check(draft)
    assert "unsupported factual claim" in issues
    assert verifier.repair_safe(draft, issues)
    assert draft.message == context.fallback_message
    assert "과세가 발생하지 않습니다" not in draft.message


NEGATIVE_TAXABILITY_CLAIMS = [
    "이 재원은 과세되지 않습니다.",
    "법정외 퇴직금은 비과세입니다.",
    "그 돈은 세금이 없습니다.",
    "퇴직금 재원은 세금이 발생하지 않습니다.",
    "추가납입과 다른 재원은 과세 대상이 아닙니다.",
    "이 재원은 세금을 내지 않습니다.",
    "법정외 퇴직금 재원은 과세가 면제됩니다.",
    "옮기는 돈은 세금 부담이 없습니다.",
    "이 돈은 세금 없이 옮길 수 있습니다.",
    "과세가 발생하지 않습니다.",
    "법정퇴직금 이전 시 세금이 부과되지 않습니다.",
    "퇴직금은 세금 안 붙습니다.",
    "이 재원은 세금이 붙지 않습니다.",
]

POSITIVE_TAXABILITY_CLAIMS = [
    "IRP 추가납입은 과세됩니다.",
    "그 재원은 세금이 발생합니다.",
    "법정외 퇴직금은 과세 대상입니다.",
    "일시금으로 받으면 퇴직소득세를 전액 납부해야 합니다.",
    "금융 소득은 과세의 대상이 됩니다.",
]


@pytest.mark.parametrize("claim", NEGATIVE_TAXABILITY_CLAIMS + POSITIVE_TAXABILITY_CLAIMS)
def test_g033_ungrounded_taxability_polarity_is_repaired(claim: str) -> None:
    _, result, context = grounded(G033_BASELINE["question"])
    draft = Draft(message=claim, citations=result.evidence, context=context)
    verifier = Verifier()
    issues = verifier.check(draft)
    assert "unsupported factual claim" in issues
    assert verifier.repair_safe(draft, issues)
    assert draft.message == context.fallback_message
    compact = re.sub(r"\s+", "", draft.message)
    assert "비과세" not in compact
    assert "과세가발생하지" not in compact


def test_g033_ungrounded_tax_rate_reduction_is_repaired() -> None:
    _, result, context = grounded(G033_BASELINE["question"])
    draft = Draft(
        message=(
            "| DB | 일시금/연금 | 퇴직소득세 100%/30%-50% 감면 |\n"
            "| DC | IRP 의무이전 | 퇴직소득세 30%-50% 감면 |"
        ),
        citations=result.evidence,
        context=context,
    )
    verifier = Verifier()
    issues = verifier.check(draft)
    assert "unsupported factual claim" in issues
    assert verifier.repair_safe(draft, issues)
    assert draft.message == context.fallback_message


def test_g033_limitation_only_answer_is_allowed() -> None:
    _, result, context = grounded(G033_BASELINE["question"])
    draft = Draft(message=context.fallback_message, citations=result.evidence, context=context)
    assert "unsupported factual claim" not in Verifier().check(draft)


def test_supported_lump_sum_tax_claim_is_preserved() -> None:
    _, result, context = grounded("퇴직금을 일시금으로 받으면 세율이 무조건 16.5%인가요?")
    draft = Draft(message=context.fallback_message, citations=result.evidence, context=context)
    issues = Verifier().check(draft)
    assert "unsupported factual claim" not in issues
    assert "퇴직소득세" in draft.message or "[한계]" in draft.message


def test_short_name_does_not_attach_ultrashort_evidence() -> None:
    ultra = _cite("u1", "r2_ultra", ULTRA_EXCERPT)
    short = _cite("s1", "r2_short", SHORT_EXCERPT)
    matched = citations_for_product(SHORT, [ultra, short])
    assert [item.id for item in matched] == ["s1"]
    text, _, _ = render_product_comparison("솔로몬 단기 특징", [SHORT], [ultra, short], intent="상품")
    assert "0.66" in text
    assert "0.32" not in text
    assert "초단기" not in text


def test_official_axes_are_source_linked() -> None:
    cites = [
        _cite("s1", "r2_short", SHORT_EXCERPT),
        _cite("m1", "r2_mid", MID_EXCERPT),
        _cite("l1", "r2_long", LONG_EXCERPT),
    ]
    bundles = build_product_evidence_bundles([SHORT, MID, LONG], cites, intent="상품")
    assert [b.product_name for b in bundles] == [SHORT["product_name"], MID["product_name"], LONG["product_name"]]
    short, mid, long = bundles
    assert short.evidence_fields["total_fee_rate_percent"].value == "0.66"
    assert short.evidence_fields["total_fee_rate_percent"].unit == "percent"
    assert short.evidence_fields["cost_example_10m_krw_1y"].unit == "천원"
    assert short.evidence_fields["sales_class"].value == "수수료선취-오프라인(A)"
    assert "90%" in short.evidence_fields["investment_strategy"].value
    assert mid.evidence_fields["total_fee_rate_percent"].value == "0.43"
    assert "80%" in mid.evidence_fields["investment_strategy"].value
    assert long.evidence_fields["total_fee_rate_percent"].value == "0.36"
    assert all(item.value is None for item in short.provenance if item.field == "historical_return_1y")
    assert all(item.value is None for item in short.provenance if item.field == "aum")
    question = "솔로몬 국공채 단기형과 중장기형, 장기형은 어떤 차이가 있나요? 안정적인 걸 원해요."
    text, _, limits = render_product_comparison(question, [SHORT, MID, LONG], cites, intent="상품")
    assert "단기" in text and "중장기" in text and "장기" in text
    assert "0.66" in text and "0.43" in text and "0.36" in text
    assert "단정 추천하지 않습니다" in "\n".join(limits)
    assert "미래" in "\n".join(limits) or "단정" in "\n".join(limits)


def test_missing_aum_is_null_not_zero() -> None:
    bundle = build_product_evidence_bundles([SHORT], [_cite("s1", "r2_short", SHORT_EXCERPT)], intent="상품")[0]
    assert "aum" not in bundle.evidence_fields
    aum_prov = next(item for item in bundle.provenance if item.field == "aum")
    assert aum_prov.value is None
    assert aum_prov.value != "0"


def test_volatility_is_not_treated_as_historical_return() -> None:
    excerpt = SHORT_EXCERPT + " 이 집합투자기구의 최근 결산일 기준 과거 3년간 수익률 변동성(97.5% VaR)은 6.21% 로서 위험등급 5등급"
    bundle = build_product_evidence_bundles([SHORT], [_cite("s1", "r2_short", excerpt)], intent="상품")[0]
    assert "historical_return_3y" not in bundle.evidence_fields


def test_product_unit_confusion_repaired_only_on_product_intent() -> None:
    cites = [_cite("s1", "r2_short", SHORT_EXCERPT)]
    composer = Composer(HCXClient(Settings(hcx_api_key="")))
    from app.agent.tools import ToolResult
    result = ToolResult(evidence=cites, products=[SHORT])
    product_ctx = composer.build_context("솔로몬 단기 비용", "상품", result)
    tax_ctx = composer.build_context("IRP 추가납입과 퇴직금 재원의 과세 차이를 설명해줘", "종합", result)
    verifier = Verifier()
    confused = "총보수·비용 비율 67천원입니다."
    product_draft = Draft(message=confused, citations=cites, context=product_ctx)
    assert "product unit confusion" in verifier.check(product_draft)
    tax_draft = Draft(message=G033_BASELINE["answer"], citations=cites, context=tax_ctx)
    assert "product unit confusion" not in verifier.check(tax_draft)


def test_common_questions_keep_non_product_routes() -> None:
    c1 = grounded("DB형과 DC형은 퇴직급여가 정해지는 방식과 운용 주체가 어떻게 다른가요?")
    assert c1[0].intent == "제도"
    assert allows_product_evidence_enrichment(c1[0].intent) is False
    assert "확정급여형(DB)" in c1[2].fallback_message
    c2 = grounded("연금저축과 IRP를 합치면 세액공제를 받을 수 있는 납입 한도가 얼마인가요?")
    assert c2[0].intent == "세제"
    assert "600만원" in c2[2].fallback_message
    assert "900만원" in c2[2].fallback_message
    c6 = grounded("오늘 비트코인 가격이 오를까요?")
    assert c6[0].intent == "범위 밖" or "벗어나" in c6[2].fallback_message
