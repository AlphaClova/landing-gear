from __future__ import annotations

from dataclasses import asdict
import argparse
import json
from pathlib import Path

from app.tools.evidence_builder import (
    build_claim_evidence_link,
    build_claim_record,
    build_evidence_card,
    build_internal_tool_result_record,
    validate_claims,
)
from app.tools.retriever import BM25Retriever
from app.tools.rule_engine import calc_retirement_pension_tax
from scripts.build_index import load_chunks


QUERY = "퇴직금을 연금으로 21년째 받고 있다면 퇴직소득세 적용 비율과 계산 근거는 무엇인가요?"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run B-only claim/evidence validation.")
    parser.add_argument("--chunks", default="app/data/processed/chunks.jsonl")
    parser.add_argument(
        "--output", default="app/data/processed/evidence_validation_results.json"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chunks = load_chunks(Path(args.chunks))
    retriever = BM25Retriever(chunks)
    hits = retriever.search(
        QUERY,
        top_k=20,
        topics=["withdrawal_tax"],
        account_types=["IRP"],
    )
    chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    evidence_hit = next(
        (
            hit
            for hit in hits
            if hit.document_id == "doc51"
            and hit.page == 2
            and "1 ~ 10년차" in chunks_by_id[hit.chunk_id].text
        ),
        None,
    )
    if evidence_hit is None:
        raise RuntimeError("doc51 page 2 retirement-tax evidence was not retrieved")

    evidence = build_evidence_card(evidence_hit, chunks_by_id[evidence_hit.chunk_id])
    calculation = calc_retirement_pension_tax(
        deferred_retirement_tax=10_000_000,
        actual_pension_year=21,
        rule_version="1.0.0",
    )
    tool_result = build_internal_tool_result_record(calculation)

    factual_claim = build_claim_record(
        "factual",
        "퇴직소득세의 연금수령 적용 비율은 실제 연금 수령연차에 따라 달라진다.",
        evidence_ids=[evidence["evidence_id"]],
        required_document_id="doc51",
        required_evidence_terms=["수령하는 기간", "감면율"],
        expected_evidence={
            key: evidence[key]
            for key in (
                "evidence_id",
                "chunk_id",
                "document_id",
                "page",
                "section",
                "source_priority",
            )
        },
    )
    numeric_claim = build_claim_record(
        "numeric",
        "이연퇴직소득세 10,000,000원을 21년차 기준으로 계산하면 적용 비율은 0.50이고 계산값은 5,000,000원이다.",
        tool_result_ids=[tool_result["tool_result_id"]],
        required_document_id="doc51",
        asserted_value=5_000_000,
        asserted_rate="0.50",
        rule_id="RETIRE_TAX_RATE_BY_YEAR",
        rule_version="1.0.0",
        expected_citation={"document_id": "doc51", "page": 2},
    )
    claims = [factual_claim, numeric_claim]
    links = [
        asdict(
            build_claim_evidence_link(
                claim["claim_id"],
                claim["claim_type"],
                claim["evidence_ids"],
                claim["tool_result_ids"],
            )
        )
        for claim in claims
    ]
    validation = validate_claims(
        claims,
        {evidence["evidence_id"]: evidence},
        {tool_result["tool_result_id"]: tool_result},
    )
    output = {
        "query": QUERY,
        "evidence": [evidence],
        "tool_results": [tool_result],
        "claims": claims,
        "claim_evidence_links": links,
        **validation,
    }
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"Results written: {output_path}")


if __name__ == "__main__":
    main()
