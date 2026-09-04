from app.agent.composer import Composer
from app.agent.router import IntentRouter
from app.agent.slots import SlotManager
from app.agent.tools import BProductCatalog, ToolRouter


class _NoHCX:
    pass


def _result(question: str):
    decision = IntentRouter().classify(question)
    result = ToolRouter(product_catalog=BProductCatalog()).run(
        decision.intent,
        SlotManager.extract(question),
        question=question,
    )
    context = Composer(_NoHCX()).build_context(question, decision.intent, result)
    return result, context


def test_account_matches_but_exact_type_does_not_use_account_absence_limitation() -> None:
    result, context = _result("IRP에서 살 수 있는 예금형 상품을 설명해줘")
    constraints = {item["constraint"]: item for item in result.recommendation_constraints}
    assert constraints["account_type"]["applied"] is True
    assert constraints["product_type"]["applied"] is False
    assert "IRP 가입 가능 상품은 확인되지만" in context.fallback_message
    assert "계좌 유형에 가입 가능하다고 확인된 상품이 없어" not in context.fallback_message


def test_zero_account_matches_keeps_account_absence_limitation() -> None:
    _, context = _result("DC 계좌의 펀드 목록과 위험등급을 보여줘")
    assert "계좌 유형에 가입 가능하다고 확인된 상품이 없어" in context.fallback_message


def test_unsupported_account_scoped_product_type_stays_in_product_fact_scope() -> None:
    result, context = _result("IRP 예금형 상품을 보여줘")
    assert result.products == []
    assert "현재 Product Fact" in context.fallback_message
    assert "예금형으로 확인되는 상품은 찾지 못했습니다" in context.fallback_message


def test_unknown_account_products_are_not_inferred_as_irp_or_dc() -> None:
    catalog = BProductCatalog()
    unknown_ids = {
        item["product_id"] for item in catalog.query_products(plan_type=None, category=None)
        if item.get("plan_types") is None
    }
    assert unknown_ids
    assert unknown_ids.isdisjoint(item["product_id"] for item in catalog.query_products(plan_type="IRP", category=None))
    assert unknown_ids.isdisjoint(item["product_id"] for item in catalog.query_products(plan_type="DC", category=None))


def test_irp_with_existing_product_condition_returns_products_normally() -> None:
    result, _ = _result("IRP 솔로몬 채권 상품 비교해줘")
    assert result.products
    assert all("IRP" in (item.get("plan_types") or []) for item in result.products)
    assert all(item.get("category") == "bond" for item in result.products)


def test_irp_recommendation_keeps_existing_clarification_policy() -> None:
    question = "IRP 상품 추천해줘"
    decision = IntentRouter().classify(question)
    missing = SlotManager().required(decision.intent, SlotManager.extract(question), question)
    assert decision.intent == "상품"
    assert [item.name for item in missing] == ["investment_horizon", "risk_tolerance"]
