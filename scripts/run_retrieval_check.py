from __future__ import annotations

import json
import argparse
from pathlib import Path

from app.data.schemas.models import Chunk
from app.tools.retriever import BM25Retriever
from scripts.parse_documents import build_inventory, parse_document, parse_targets


def to_chunk(record: dict[str, object]) -> Chunk:
    return Chunk(
        chunk_id=record["chunk_id"],
        document_id=record["document_id"],
        title=record["title"],
        page=record.get("page"),
        section=record["section"],
        text=record.get("content", record.get("text", "")),
        effective_from=record.get("effective_from"),
        valid_to=record.get("valid_to"),
        topics=record.get("topics", [record.get("topic", "")]),
        account_types=record.get("account_types", [record.get("account_type", "")]),
        source_type=record.get("source_type", "provided"),
        source_priority=record.get("source_priority", 0),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the two G2 retrieval checks.")
    parser.add_argument(
        "--output",
        default="app/data/processed/retrieval_results.json",
        help="Top-5 retrieval result output",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chunks_path = Path("app/data/processed/chunks.jsonl")
    base_chunks = [json.loads(line) for line in chunks_path.read_text(encoding="utf-8").splitlines() if line]
    unexpected = {row["document_id"] for row in base_chunks} - {"doc10", "doc51"}
    if unexpected:
        raise SystemExit(f"Index scope contains unexpected documents: {sorted(unexpected)}")

    chunks = [to_chunk(chunk) for chunk in base_chunks]
    retriever = BM25Retriever(chunks)
    queries = {
        "A": {
            "query": "DB형 퇴직연금과 DC형 퇴직연금은 무엇이 다르고 누가 적립금을 운용하나요?",
            "topics": ["pension_system"],
            "account_types": ["DB_DC"],
        },
        "B": {
            "query": "퇴직금을 일시금으로 받는 것과 연금으로 오래 나눠 받는 것의 세금 차이를 비교하려면 어떤 규칙을 확인해야 하나요?",
            "topics": ["withdrawal_tax"],
            "account_types": ["IRP"],
        },
    }

    output: dict[str, list[dict[str, object]]] = {}
    for label, spec in queries.items():
        print(f"QUERY {label}")
        hits = retriever.search(
            spec["query"],
            top_k=5,
            topics=spec["topics"],
            account_types=spec["account_types"],
        )
        output[label] = []
        for rank, hit in enumerate(hits, start=1):
            row = next(chunk for chunk in chunks if chunk.chunk_id == hit.chunk_id)
            result = {
                        "rank": rank,
                        "score": round(hit.score, 6),
                        "chunk_id": hit.chunk_id,
                        "document_id": hit.document_id,
                        "page": hit.page,
                        "section": row.section,
                        "topic": row.topics[0] if row.topics else None,
                        "account_type": row.account_types[0] if row.account_types else None,
                        "content": row.text[:120],
                        "metadata_filter_applied": True,
                    }
            output[label].append(result)
            print(json.dumps(result, ensure_ascii=False))

    output_path = Path(args.output)
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Results written: {output_path}")


if __name__ == "__main__":
    main()
