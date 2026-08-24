from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class ProductQueryService:
    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

    def initialize(self) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS products (
                    product_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    risk_level INTEGER NOT NULL,
                    share_class TEXT,
                    total_fee REAL,
                    return_1y REAL,
                    return_3y REAL,
                    aum INTEGER,
                    sources_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def upsert_products(self, rows: list[dict[str, Any]]) -> None:
        with sqlite3.connect(self._db_path) as conn:
            conn.executemany(
                """
                INSERT INTO products (
                    product_id, name, asset_type, risk_level, share_class,
                    total_fee, return_1y, return_3y, aum, sources_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_id) DO UPDATE SET
                    name = excluded.name,
                    asset_type = excluded.asset_type,
                    risk_level = excluded.risk_level,
                    share_class = excluded.share_class,
                    total_fee = excluded.total_fee,
                    return_1y = excluded.return_1y,
                    return_3y = excluded.return_3y,
                    aum = excluded.aum,
                    sources_json = excluded.sources_json
                """,
                [
                    (
                        row["product_id"],
                        row["name"],
                        row["asset_type"],
                        row["risk_level"],
                        row.get("share_class"),
                        row.get("total_fee"),
                        row.get("return_1y"),
                        row.get("return_3y"),
                        row.get("aum"),
                        json.dumps(row.get("sources", []), ensure_ascii=True),
                    )
                    for row in rows
                ],
            )
            conn.commit()

    def query(
        self,
        asset_type: str | None = None,
        max_risk_level: int | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM products WHERE 1=1"
        params: list[Any] = []

        if asset_type:
            sql += " AND asset_type = ?"
            params.append(asset_type)

        if max_risk_level is not None:
            sql += " AND risk_level <= ?"
            params.append(max_risk_level)

        sql += " ORDER BY risk_level ASC, total_fee ASC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["sources"] = json.loads(item.pop("sources_json"))
            results.append(item)
        return results
