from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from app.data.schemas.models import Chunk
from app.tools.retriever import BM25Retriever


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate BM25 retriever build from chunk file.")
    parser.add_argument("--chunks", default="app/data/processed/chunks.jsonl")
    parser.add_argument("--sample-query", default="연금수령 세제")
    parser.add_argument(
        "--output",
        default="app/data/processed/retrieval_index.json",
        help="Deterministic BM25 corpus/index artifact",
    )
    return parser.parse_args()


def load_chunks(path: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            if not line.strip():
                continue
            row = json.loads(line)
            chunks.append(
                Chunk(
                    chunk_id=row["chunk_id"],
                    document_id=row["document_id"],
                    title=row["title"],
                    page=row.get("page"),
                    section=row["section"],
                    text=row.get("content", row.get("text", "")),
                    effective_from=row.get("effective_from"),
                    valid_to=row.get("valid_to"),
                    topics=row.get("topics", [row.get("topic", "")]),
                    account_types=row.get("account_types", [row.get("account_type", "")]),
                    source_type=row.get("source_type", "provided"),
                    source_priority=row.get("source_priority", 0),
                )
            )
    return chunks


def main() -> None:
    args = parse_args()
    chunks_path = Path(args.chunks)
    if not chunks_path.exists():
        raise FileNotFoundError(f"Chunk file not found: {chunks_path}")

    chunks = load_chunks(chunks_path)
    retriever = BM25Retriever(chunks)
    hits = retriever.search(args.sample_query, top_k=3)

    source_bytes = chunks_path.read_bytes()
    artifact = {
        "index_type": "bm25",
        "source": chunks_path.as_posix(),
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "chunk_count": len(chunks),
        "document_ids": sorted({chunk.document_id for chunk in chunks}),
        "chunk_ids": [chunk.chunk_id for chunk in chunks],
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Loaded chunks: {len(chunks)}")
    print(f"Index written: {output_path}")
    print(f"Sample query: {args.sample_query}")
    for hit in hits:
        print(f"- {hit.chunk_id} score={hit.score:.4f} doc={hit.document_id} p={hit.page}")


if __name__ == "__main__":
    main()
