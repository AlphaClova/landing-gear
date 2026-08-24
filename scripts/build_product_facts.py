from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
from typing import Any

from scripts.parse_documents import parse_document


ASSET_TYPE_CATEGORY = {
    "주식": "equity",
    "주식-재간접형": "equity",
    "채권": "bond",
    "채권-재간접형": "bond",
    "주식혼합": "mixed",
    "주식혼합-재간접형": "mixed",
    "채권혼합": "mixed",
    "채권혼합-재간접형": "mixed",
    "혼합자산": "multi_asset",
    "국공채": "bond",
    "주식-파생형": "equity",
}
PLAN_PATTERNS = {
    "DB": re.compile(r"(?:확정급여형|DB형)\s*퇴직연금", re.IGNORECASE),
    "DC": re.compile(r"(?:확정기여형|DC형)\s*퇴직연금", re.IGNORECASE),
    "IRP": re.compile(r"(?:개인형?퇴직연금|개인퇴직계좌)\s*\(?IRP\)?", re.IGNORECASE),
}
ELIGIBILITY_TERMS = ("매입이 가능", "가입자", "가입 가능", "가입대상", "수수료미징구")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build source-backed Product Fact JSON.")
    parser.add_argument("--raw-dir", default="app/data/raw/products")
    parser.add_argument("--output", default="app/data/products/products.json")
    parser.add_argument("--report", default="app/data/products/product_fact_build_report.json")
    return parser.parse_args()


def _normalized(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _product_name(page_text: str) -> str | None:
    patterns = (
        r"이\s*투자설명서는\s+(.+?)(?:에\s+대한|의\s+내용)",
        r"집\s*합\s*투\s*자\s*기\s*구(?:의)?\s*명\s*칭\s*:?\s*(.+?)(?=\s+2\.)",
    )
    for pattern in patterns:
        match = re.search(pattern, page_text)
        if match:
            return match.group(1).strip()
    return None


def _asset_type(product_name: str) -> str | None:
    matches = re.findall(
        r"[\(\[]\s*(주식혼합(?:-재간접형)?|채권혼합(?:-재간접형)?|"
        r"주식(?:-재간접형|-파생형)?|채권(?:-재간접형)?|혼합자산|국공채)\s*[\)\]]",
        product_name,
    )
    return matches[-1] if matches else None


def _risk_level(page_text: str) -> int | None:
    match = re.search(r"투자\s*위험\s*등급.*?([1-6])\s*등급", page_text)
    if match is None:
        match = re.search(r"([1-6])\s*등급", page_text)
    return int(match.group(1)) if match else None


def _plan_type_pages(chunks: list[dict[str, Any]]) -> dict[str, list[int]]:
    pages: dict[str, set[int]] = {code: set() for code in PLAN_PATTERNS}
    for chunk in chunks:
        if chunk["content_type"] != "text" or chunk["page"] is None:
            continue
        text = _normalized(chunk["content"])
        if not any(term in text for term in ELIGIBILITY_TERMS):
            continue
        for code, pattern in PLAN_PATTERNS.items():
            if pattern.search(text):
                pages[code].add(chunk["page"])
    return {code: sorted(values) for code, values in pages.items() if values}


def build_product_fact(path: Path) -> dict[str, Any]:
    inventory, chunks = parse_document(path)
    page_one = _normalized(
        " ".join(
            chunk["content"]
            for chunk in chunks
            if chunk["page"] == 1 and chunk["content_type"] == "text"
        )
    )
    product_name = _product_name(page_one)
    if product_name is None:
        raise ValueError("product name not found on page 1")
    asset_type = _asset_type(product_name)
    plan_type_pages = _plan_type_pages(chunks)
    plan_types = [code for code in ("DB", "DC", "IRP") if code in plan_type_pages] or None
    risk_level = _risk_level(page_one)
    return {
        "product_id": inventory["document_id"],
        "product_name": product_name,
        "plan_types": plan_types,
        "category": ASSET_TYPE_CATEGORY.get(asset_type),
        "asset_type": asset_type,
        "risk_level": risk_level,
        "document_id": inventory["document_id"],
        "page": 1,
        "source": path.as_posix(),
        "source_priority": inventory["source_priority"],
        "plan_type_pages": plan_type_pages,
        "category_page": 1 if asset_type in ASSET_TYPE_CATEGORY else None,
        "risk_page": 1 if risk_level is not None else None,
    }


def main() -> None:
    args = parse_args()
    raw_paths = sorted(Path(args.raw_dir).glob("*.pdf"))
    products: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for path in raw_paths:
        try:
            products.append(build_product_fact(path))
        except Exception as exc:  # noqa: BLE001 - source variance is reported, never filled
            failures.append({"source": path.as_posix(), "error": f"{type(exc).__name__}: {exc}"})

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(products, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    plan_distribution = Counter(code for product in products for code in (product["plan_types"] or []))
    category_distribution = Counter(product["category"] for product in products)
    report = {
        "raw_document_count": len(raw_paths),
        "loaded_product_count": len(products),
        "failed_product_count": len(failures),
        "plan_types_known_count": sum(product["plan_types"] is not None for product in products),
        "plan_types_null_count": sum(product["plan_types"] is None for product in products),
        "plan_type_distribution": dict(sorted(plan_distribution.items())),
        "category_known_count": sum(product["category"] is not None for product in products),
        "category_null_count": sum(product["category"] is None for product in products),
        "category_distribution": {
            "null" if key is None else key: value
            for key, value in sorted(category_distribution.items(), key=lambda item: str(item[0]))
        },
        "risk_level_null_count": sum(product["risk_level"] is None for product in products),
        "failures": failures,
    }
    report_path = Path(args.report)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
