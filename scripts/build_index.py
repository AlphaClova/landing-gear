from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.data.schemas.models import Chunk
from app.tools.retriever import BM25Retriever


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate BM25 retriever build from chunk file.")
    parser.add_argument("--chunks", default="app/data/processed/chunks.jsonl")
    parser.add_argument("--sample-query", default="연금수령 세제")
    return parser.parse_args()


def load_chunks(path: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            if not line.strip():
                continue
            row = json.loads(line)
            chunks.append(Chunk(**row))
    return chunks


def main() -> None:
    args = parse_args()
    chunks_path = Path(args.chunks)
    if not chunks_path.exists():
        raise FileNotFoundError(f"Chunk file not found: {chunks_path}")

    chunks = load_chunks(chunks_path)
    retriever = BM25Retriever(chunks)
    hits = retriever.search(args.sample_query, top_k=3)

    print(f"Loaded chunks: {len(chunks)}")
    print(f"Sample query: {args.sample_query}")
    for hit in hits:
        print(f"- {hit.chunk_id} score={hit.score:.4f} doc={hit.document_id} p={hit.page}")


if __name__ == "__main__":
    main()
