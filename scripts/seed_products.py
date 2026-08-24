from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.tools.product_query import ProductQueryService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed product dataset into SQLite.")
    parser.add_argument("--source", default="app/data/products/products.json")
    parser.add_argument("--db", default="app/data/processed/products.db")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = Path(args.source)
    if not source.exists():
        raise FileNotFoundError(f"Source product file does not exist: {source}")

    rows = json.loads(source.read_text(encoding="utf-8"))
    service = ProductQueryService(args.db)
    service.initialize()
    service.upsert_products(rows)
    print(f"Seeded {len(rows)} products into {args.db}")


if __name__ == "__main__":
    main()
