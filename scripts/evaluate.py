from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate unsupported claim rate from result JSONL.")
    parser.add_argument("--input", required=True, help="JSONL file with claims[]")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    path = Path(args.input)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    total_claims = 0
    unsupported_claims = 0

    with path.open("r", encoding="utf-8") as fp:
        for line in fp:
            row = json.loads(line)
            claims = row.get("claims", [])
            for claim in claims:
                total_claims += 1
                evidence_ids = claim.get("evidence_ids", [])
                tool_result_ids = claim.get("tool_result_ids", [])
                if not evidence_ids and not tool_result_ids:
                    unsupported_claims += 1

    if total_claims == 0:
        print("No claims found.")
        return

    rate = unsupported_claims / total_claims
    print(f"total_claims={total_claims}")
    print(f"unsupported_claims={unsupported_claims}")
    print(f"unsupported_claim_rate={rate:.6f}")


if __name__ == "__main__":
    main()
