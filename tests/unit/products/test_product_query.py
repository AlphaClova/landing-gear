from pathlib import Path

import pytest

from app.tools import product_query
from app.tools.product_query import ProductQueryInputError, ProductQueryService


def _rows() -> list[dict[str, object]]:
    return [
        {
            "product_id": "unit-multi-plan",
            "product_name": "Unit Multi Plan Equity",
            "plan_types": ["DB", "DC"],
            "category": "equity",
            "asset_type": "주식",
            "risk_level": 2,
            "document_id": "unit-doc-1",
            "page": 1,
            "source": "unit-fixture/product-1.pdf",
            "source_priority": 0,
            "plan_type_pages": {"DB": [5], "DC": [5]},
            "category_page": 1,
            "risk_page": 1,
        },
        {
            "product_id": "unit-irp-bond",
            "product_name": "Unit IRP Bond",
            "plan_types": ["IRP"],
            "category": "bond",
            "asset_type": "채권",
            "risk_level": 5,
            "document_id": "unit-doc-2",
            "page": None,
            "source": "unit-fixture/product-2.pdf",
            "source_priority": 7,
            "plan_type_pages": {"IRP": [8]},
            "category_page": None,
            "risk_page": None,
        },
        {
            "product_id": "unit-null-classification",
            "product_name": "Unit Unknown Classification",
            "plan_types": None,
            "category": None,
            "asset_type": None,
            "risk_level": None,
            "document_id": "unit-doc-3",
            "page": None,
            "source": "unit-fixture/product-3.pdf",
            "source_priority": 0,
            "plan_type_pages": {},
            "category_page": None,
            "risk_page": None,
        },
        {
            "product_id": "unit-irp-mixed",
            "product_name": "Unit IRP Mixed",
            "plan_types": ["IRP"],
            "category": "mixed",
            "asset_type": "채권혼합",
            "risk_level": 3,
            "document_id": "unit-doc-4",
            "page": 1,
            "source": "unit-fixture/product-4.pdf",
            "source_priority": 0,
            "plan_type_pages": {"IRP": [6]},
            "category_page": 1,
            "risk_page": 1,
        },
    ]


@pytest.fixture
def service(tmp_path: Path) -> ProductQueryService:
    instance = ProductQueryService(tmp_path / "unit-products.db")
    instance.initialize()
    instance.upsert_products(_rows())
    return instance


@pytest.mark.parametrize("plan_type", ["DB", "DC", "IRP"])
def test_plan_type_membership_filter(service: ProductQueryService, plan_type: str) -> None:
    results = service.query(plan_type=plan_type)

    assert results
    assert all(result.plan_types is not None and plan_type in result.plan_types for result in results)


@pytest.mark.parametrize("category", ["equity", "bond", "mixed"])
def test_category_filter(service: ProductQueryService, category: str) -> None:
    results = service.query(category=category)

    assert results
    assert all(result.category == category for result in results)


def test_plan_type_and_category_are_anded(service: ProductQueryService) -> None:
    assert [item.product_id for item in service.query("IRP", "mixed")] == ["unit-irp-mixed"]


def test_none_filters_return_all_in_deterministic_order(service: ProductQueryService) -> None:
    first = service.query(None, None)
    second = service.query(None, None)

    assert first == second
    assert [item.product_id for item in first] == sorted(item.product_id for item in first)


def test_no_match_returns_empty_list(service: ProductQueryService) -> None:
    assert service.query("DB", "bond") == []


def test_null_classifications_are_not_in_specific_filters(service: ProductQueryService) -> None:
    unknown = next(item for item in service.query() if item.product_id == "unit-null-classification")

    assert unknown.plan_types is None
    assert unknown.category is None
    assert all(item.product_id != unknown.product_id for item in service.query("IRP", None))
    assert all(item.product_id != unknown.product_id for item in service.query(None, "equity"))


def test_nullable_and_source_provenance_are_preserved(service: ProductQueryService) -> None:
    result = service.query("IRP", "bond")[0]

    assert result.page is None
    assert result.source_priority == 7
    assert result.document_id == "unit-doc-2"
    assert result.source == "unit-fixture/product-2.pdf"
    assert result.plan_type_pages == {"IRP": [8]}


@pytest.mark.parametrize(
    "plan_type,category,error",
    [("UNKNOWN", None, "unknown plan_type"), (None, "theme", "unknown category")],
)
def test_production_entry_rejects_invalid_filters(
    plan_type: str | None,
    category: str | None,
    error: str,
) -> None:
    with pytest.raises(ProductQueryInputError, match=error):
        product_query.query_products(plan_type, category)
