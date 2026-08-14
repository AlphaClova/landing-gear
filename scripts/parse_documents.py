from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse raw text files into chunked JSONL data.")
    parser.add_argument("--raw-dir", default="app/data/raw", help="Raw document directory")
    parser.add_argument(
        "--output", default="app/data/processed/chunks.jsonl", help="Output JSONL path"
    )
    parser.add_argument("--document-id", default="doc51", help="Document id to stamp chunks")
    return parser.parse_args()


def chunk_text(text: str, chunk_size: int = 650) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    chunks: list[str] = []
    current = ""

    for line in lines:
        candidate = f"{current} {line}".strip()
        if len(candidate) > chunk_size and current:
            chunks.append(current)
            current = line
        else:
            current = candidate

    if current:
        chunks.append(current)
    return chunks


def main() -> None:
    args = parse_args()
    raw_dir = Path(args.raw_dir)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, object]] = []
    for file_path in sorted(raw_dir.glob("*.txt")):
        text = file_path.read_text(encoding="utf-8")
        for index, chunk_text_value in enumerate(chunk_text(text), start=1):
            records.append(
                {
                    "chunk_id": f"{args.document_id}-p01-c{index:03d}",
                    "document_id": args.document_id,
                    "title": file_path.stem,
                    "page": 1,
                    "section": "parsed",
                    "effective_from": "2026-01-01",
                    "valid_to": None,
                    "topics": ["tax"],
                    "account_types": ["IRP"],
                    "source_type": "provided",
                    "source_priority": 0,
                    "text": chunk_text_value,
                }
            )

    with output.open("w", encoding="utf-8") as fp:
        for record in records:
            fp.write(json.dumps(record, ensure_ascii=True) + "\n")

    print(f"Wrote {len(records)} chunks to {output}")


if __name__ == "__main__":
    main()
