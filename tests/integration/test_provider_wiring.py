from app.agent.tools import BEvidenceProvider, BProductCatalog, BRuleEngine
from app.api.dependencies import get_tool_router


def test_tool_router_uses_all_production_providers() -> None:
    router = get_tool_router()
    assert isinstance(router._evidence, BEvidenceProvider)
    assert isinstance(router._rules, BRuleEngine)
    assert isinstance(router._products, BProductCatalog)
    assert router.provider_status() == {
        "EVIDENCE_PROVIDER": "real",
        "RULE_PROVIDER": "real",
        "PRODUCT_PROVIDER": "real",
    }


def test_evidence_adapter_preserves_provenance() -> None:
    results = BEvidenceProvider().retrieve_evidence("DB DC 퇴직연금", topic="제도", top_k=2)
    assert results
    assert all(x.id and x.document_id and x.page is not None and x.source for x in results)
    assert all(x.source_priority is not None and x.score is not None for x in results)


def test_product_adapter_preserves_nullable_values_and_provenance() -> None:
    results = BProductCatalog().query_products(plan_type=None, category=None)
    assert len(results) == 100
    assert all("document_id" in x and "page" in x and "source_priority" in x for x in results)
    assert any(x["plan_types"] is None for x in results)
    assert all(x["risk_label"] in {"매우 높은 위험", "높은 위험", "다소 높은 위험", "보통 위험", "낮은 위험", "매우 낮은 위험", None} for x in results)
    assert next(x for x in results if x["product_id"] == "r2_kr5153420063")["risk_label"] == "낮은 위험"
    assert next(x for x in results if x["product_id"] == "r2_kr5153450658")["risk_label"] == "매우 낮은 위험"
