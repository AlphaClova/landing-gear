from __future__ import annotations

import json
import re
from pathlib import Path

from app.core.query_normalization import meaningful_query_tokens
from app.tools.retriever import (
    BM25Retriever,
    DEFAULT_CHUNKS_PATH,
    _expand_query,
    _load_chunks,
    relevance_diagnostics,
    retrieve_evidence,
)
from scripts.parse_documents import parse_document


OUTPUT_DIR = Path("artifacts/quality-audit")
RAW_PRODUCTS = Path("app/data/raw/products")
QUERIES = [
    ("positive", "DB와 DC 차이 알려줘", "pension_system"),
    ("positive", "연금저축과 IRP 세액공제 한도 알려줘", "withdrawal_tax"),
    ("positive", "솔로몬 국공채 단기형 특징 알려줘", "product"),
    ("positive", "퇴직소득세 연금 21년 수령", "withdrawal_tax"),
    ("positive", "IRP 중도인출 조건 알려줘", None),
    ("partial_negative", "연금 날씨 알려줘", None),
    ("partial_negative", "세금 야구 결과", None),
    ("partial_negative", "상품 저녁 메뉴", None),
    ("partial_negative", "IRP 축구 경기", None),
    ("partial_negative", "퇴직금 아이스크림 추천", None),
    ("unrelated", "은하수 초콜릿 양자역학", None),
    ("unrelated", "오늘 저녁 뭐 먹지", None),
    ("unrelated", "파이썬 정렬 알고리즘", None),
]

PATTERNS = {
    "DIRECT_DC": re.compile(r"(?:확정기여형(?:\s*\(?\s*DC\s*\)?)?|DC\s*형|DC\s*가입자)", re.I),
    "DIRECT_DB": re.compile(r"(?:확정급여형(?:\s*\(?\s*DB\s*\)?)?|DB\s*형|DB\s*가입자)", re.I),
    "DIRECT_IRP": re.compile(r"(?:개인형\s*퇴직연금|개인퇴직계좌|IRP\s*가입자)", re.I),
    "GENERIC_RETIREMENT_PENSION": re.compile(
        r"(?:퇴직연금\s*가입자|퇴직연금\s*적립금|퇴직연금\s*사업자|근로자퇴직급여\s*보장법)", re.I
    ),
}


def retrieval_audit() -> None:
    chunks = _load_chunks(DEFAULT_CHUNKS_PATH)
    by_id = {chunk.chunk_id: chunk for chunk in chunks}
    retriever = BM25Retriever(chunks)
    rows = []
    for label, query, topic in QUERIES:
        expanded, _ = _expand_query(query, topic)
        raw = retriever.search(expanded, top_k=5, topics=[topic] if topic else None)
        final_ids = {item.evidence_id for item in retrieve_evidence(query, topic, 5)}
        candidates = []
        for hit in raw:
            diagnostic = relevance_diagnostics(query, hit, by_id[hit.chunk_id])
            diagnostic.update(
                {
                    "document_id": hit.document_id,
                    "page": hit.page,
                    "final_returned": hit.chunk_id in final_ids,
                }
            )
            candidates.append(diagnostic)
        rows.append(
            {
                "label": label,
                "query": query,
                "topic": topic,
                "normalized_query": " ".join(meaningful_query_tokens(query)),
                "raw_result_count": len(raw),
                "final_result_count": len(final_ids),
                "candidates": candidates,
            }
        )
    (OUTPUT_DIR / "retrieval-baseline-and-gate.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def product_audit() -> None:
    matches = []
    products = sorted(RAW_PRODUCTS.glob("*.pdf"))
    for path in products:
        inventory, chunks = parse_document(path)
        for chunk in chunks:
            if chunk.get("content_type") != "text":
                continue
            text = str(chunk.get("content", ""))
            for evidence_type, pattern in PATTERNS.items():
                for match in pattern.finditer(text):
                    start = max(0, match.start() - 100)
                    end = min(len(text), match.end() + 100)
                    matches.append(
                        {
                            "product_id": inventory["document_id"],
                            "document_id": inventory["document_id"],
                            "page": chunk.get("page"),
                            "exact_surrounding_text": text[start:end],
                            "matched_text": match.group(0),
                            "candidate_plan_type": {
                                "DIRECT_DC": "DC", "DIRECT_DB": "DB", "DIRECT_IRP": "IRP"
                            }.get(evidence_type),
                            "evidence_type": evidence_type,
                            "confidence": "HIGH" if evidence_type.startswith("DIRECT_") else "MEDIUM",
                        }
                    )
    counts = {key: sum(row["evidence_type"] == key for row in matches) for key in PATTERNS}
    result = {
        "total_products": len(products),
        "counts": counts,
        "dc_zero_root_cause": "PARSER_BUG" if counts["DIRECT_DC"] else "SOURCE_GAP",
        "inferred_dc_facts": 0,
        "matches": matches,
    }
    (OUTPUT_DIR / "product-plan-eligibility-audit.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    retrieval_audit()
    product_audit()


if __name__ == "__main__":
    main()
