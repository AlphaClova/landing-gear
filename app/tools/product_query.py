from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from app.data.schemas.models import ProductResult


DEFAULT_PRODUCTS_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "processed" / "products.db"
VALID_PLAN_TYPES = frozenset({"DB", "DC", "IRP"})
VALID_CATEGORIES = frozenset({"equity", "bond", "mixed", "multi_asset"})


class ProductQueryInputError(ValueError):
    """Raised when a product filter is outside the normalized B contract."""


class ProductQueryService:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

    def initialize(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    product_id TEXT PRIMARY KEY,
                    product_name TEXT NOT NULL,
                    plan_types_json TEXT,
                    category TEXT,
                    asset_type TEXT,
                    risk_level INTEGER,
                    document_id TEXT NOT NULL,
                    page INTEGER,
                    source TEXT NOT NULL,
                    source_priority INTEGER NOT NULL,
                    plan_type_pages_json TEXT NOT NULL,
                    category_page INTEGER,
                    risk_page INTEGER
                )
                """
            )
            conn.commit()

    def upsert_products(self, rows: list[dict[str, Any]]) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.executemany(
                """
                INSERT INTO products (
                    product_id, product_name, plan_types_json, category, asset_type,
                    risk_level, document_id, page, source, source_priority,
                    plan_type_pages_json, category_page, risk_page
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_id) DO UPDATE SET
                    product_name = excluded.product_name,
                    plan_types_json = excluded.plan_types_json,
                    category = excluded.category,
                    asset_type = excluded.asset_type,
                    risk_level = excluded.risk_level,
                    document_id = excluded.document_id,
                    page = excluded.page,
                    source = excluded.source,
                    source_priority = excluded.source_priority,
                    plan_type_pages_json = excluded.plan_type_pages_json,
                    category_page = excluded.category_page,
                    risk_page = excluded.risk_page
                """,
                [
                    (
                        row["product_id"],
                        row["product_name"],
                        (
                            json.dumps(row["plan_types"], ensure_ascii=True)
                            if row.get("plan_types") is not None
                            else None
                        ),
                        row.get("category"),
                        row.get("asset_type"),
                        row.get("risk_level"),
                        row["document_id"],
                        row.get("page"),
                        row["source"],
                        row["source_priority"],
                        json.dumps(row.get("plan_type_pages", {}), ensure_ascii=True),
                        row.get("category_page"),
                        row.get("risk_page"),
                    )
                    for row in rows
                ],
            )
            conn.commit()

    def query(
        self,
        plan_type: str | None = None,
        category: str | None = None,
    ) -> list[ProductResult]:
        sql = "SELECT * FROM products WHERE 1=1"
        params: list[str] = []
        if plan_type is not None:
            sql += " AND plan_types_json IS NOT NULL AND EXISTS ("
            sql += "SELECT 1 FROM json_each(products.plan_types_json) WHERE value = ?)"
            params.append(plan_type)
        if category is not None:
            sql += " AND category = ?"
            params.append(category)
        sql += " ORDER BY product_id ASC"

        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        return [_to_product_result(row) for row in rows]


def _to_product_result(row: sqlite3.Row) -> ProductResult:
    return ProductResult(
        product_id=row["product_id"],
        product_name=row["product_name"],
        plan_types=(
            json.loads(row["plan_types_json"])
            if row["plan_types_json"] is not None
            else None
        ),
        category=row["category"],
        asset_type=row["asset_type"],
        risk_level=row["risk_level"],
        document_id=row["document_id"],
        page=row["page"],
        source=row["source"],
        source_priority=row["source_priority"],
        plan_type_pages=json.loads(row["plan_type_pages_json"]),
        category_page=row["category_page"],
        risk_page=row["risk_page"],
    )


def _normalize_filter(value: str | None) -> str | None:
    return value.strip() if value is not None else None


def query_products(
    plan_type: str | None,
    category: str | None,
) -> list[ProductResult]:
    """Query the production Product Fact DB using exact normalized filters."""
    plan_type = _normalize_filter(plan_type)
    category = _normalize_filter(category)
    if plan_type is not None and plan_type not in VALID_PLAN_TYPES:
        raise ProductQueryInputError(f"unknown plan_type: {plan_type}")
    if category is not None and category not in VALID_CATEGORIES:
        raise ProductQueryInputError(f"unknown category: {category}")
    return ProductQueryService(DEFAULT_PRODUCTS_DB_PATH).query(plan_type, category)
