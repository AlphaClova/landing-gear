from app.tools.product_query import query_products


def test_actual_product_fact_db_loads_all_source_products() -> None:
    results = query_products(None, None)

    assert len(results) == 100
    assert all(result.product_id and result.product_name for result in results)


def test_actual_plan_filters_use_membership_without_fallback() -> None:
    db_results = query_products("DB", None)
    dc_results = query_products("DC", None)
    irp_results = query_products("IRP", None)

    assert db_results
    assert dc_results == []
    assert irp_results
    assert all("DB" in (item.plan_types or []) for item in db_results)
    assert all("IRP" in (item.plan_types or []) for item in irp_results)


def test_actual_category_and_combined_filters() -> None:
    equity = query_products(None, "equity")
    bonds = query_products(None, "bond")
    mixed = query_products(None, "mixed")
    db_equity = query_products("DB", "equity")

    assert equity and bonds and mixed and db_equity
    assert all(item.category == "equity" for item in equity)
    assert all(item.category == "bond" for item in bonds)
    assert all(item.category == "mixed" for item in mixed)
    assert all(item.category == "equity" and "DB" in (item.plan_types or []) for item in db_equity)


def test_actual_product_provenance_is_preserved() -> None:
    result = query_products("DB", "equity")[0]

    assert result.document_id == result.product_id
    assert result.page == 1
    assert result.source.endswith(".pdf")
    assert result.source_priority == 0
    assert result.plan_type_pages["DB"]


def test_actual_query_is_deterministic() -> None:
    assert query_products("IRP", "bond") == query_products("IRP", "bond")
