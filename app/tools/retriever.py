from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.data.schemas.models import Chunk, EvidenceResult, RetrievalHit
from app.core.query_normalization import (
    has_alias,
    is_tax_deduction_question,
    is_teacher_retirement_domain,
    population_scope,
)


TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣]+")
DEFAULT_CHUNKS_PATH = Path(__file__).resolve().parents[1] / "data" / "processed" / "chunks.jsonl"


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


def _soft_term_freq(term: str, term_freq: Counter[str]) -> int:
    exact = term_freq.get(term, 0)
    if exact > 0:
        return exact

    # Korean tokens often include suffixes (e.g., "연금수령시").
    count = 0
    for token, token_count in term_freq.items():
        # Match a query stem inside a suffixed corpus token.  The reverse
        # direction makes an arbitrary long query token match short unrelated
        # corpus words (e.g. a word embedded by chance).
        if term in token:
            count += token_count
    return count


@dataclass
class _IndexedChunk:
    chunk: Chunk
    term_freq: Counter[str]
    doc_length: int


class BM25Retriever:
    """Simple BM25 retriever with metadata filtering for MVP baseline."""

    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75) -> None:
        self._k1 = k1
        self._b = b
        self._indexed: list[_IndexedChunk] = []
        self._doc_freq: Counter[str] = Counter()
        self._avg_doc_length = 0.0
        self._fit(chunks)

    def _fit(self, chunks: list[Chunk]) -> None:
        total_length = 0
        for chunk in chunks:
            tokens = _tokenize(chunk.text)
            term_freq = Counter(tokens)
            doc_length = len(tokens)
            total_length += doc_length
            self._indexed.append(_IndexedChunk(chunk=chunk, term_freq=term_freq, doc_length=doc_length))

            for term in set(term_freq):
                self._doc_freq[term] += 1

        if self._indexed:
            self._avg_doc_length = total_length / len(self._indexed)

    def search(
        self,
        query: str,
        top_k: int = 5,
        topics: list[str] | None = None,
        account_types: list[str] | None = None,
        on_date: date | None = None,
    ) -> list[RetrievalHit]:
        query_terms = _tokenize(query)
        if not query_terms:
            return []

        hits: list[RetrievalHit] = []
        for indexed_chunk in self._indexed:
            chunk = indexed_chunk.chunk
            if not _passes_filters(chunk, topics, account_types, on_date):
                continue

            score = self._score(query_terms, indexed_chunk)
            if score <= 0:
                continue

            # Prefer provided sources (priority 0) when scores are close.
            adjusted_score = score - (chunk.source_priority * 0.001)
            hits.append(
                RetrievalHit(
                    chunk_id=chunk.chunk_id,
                    score=adjusted_score,
                    document_id=chunk.document_id,
                    page=chunk.page,
                    quote=chunk.text[:220],
                )
            )

        # Explicit secondary key keeps equal-score results stable across runs.
        return sorted(hits, key=lambda h: (-h.score, h.chunk_id))[:top_k]

    def _score(self, query_terms: list[str], indexed_chunk: _IndexedChunk) -> float:
        score = 0.0
        total_docs = len(self._indexed)
        if total_docs == 0:
            return 0.0

        for term in query_terms:
            term_freq = _soft_term_freq(term, indexed_chunk.term_freq)
            if term_freq == 0:
                continue

            doc_freq = self._doc_freq.get(term, 0)
            idf = math.log(1 + ((total_docs - doc_freq + 0.5) / (doc_freq + 0.5)))
            denominator = term_freq + self._k1 * (
                1 - self._b + self._b * (indexed_chunk.doc_length / max(self._avg_doc_length, 1e-9))
            )
            score += idf * ((term_freq * (self._k1 + 1)) / denominator)
        return score


def _load_chunks(path: Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    with path.open("r", encoding="utf-8") as stream:
        for line in stream:
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


def retrieve_evidence(
    query: str,
    topic: str | None,
    top_k: int,
) -> list[EvidenceResult]:
    """Search the production chunk corpus without manufacturing fallback evidence."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must not be empty")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k <= 0:
        raise ValueError("top_k must be a positive integer")

    chunks = _load_chunks(DEFAULT_CHUNKS_PATH)
    chunks_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    search_query, query_kind = _expand_query(query, topic)
    hits = BM25Retriever(chunks).search(
        search_query,
        top_k=max(top_k * 20, 80),
        topics=[topic] if topic is not None else None,
    )
    hits = _rerank_and_diversify(hits, chunks_by_id, query_kind, top_k)
    return [
        EvidenceResult(
            evidence_id=hit.chunk_id,
            chunk_id=hit.chunk_id,
            document_id=hit.document_id,
            page=hit.page,
            section=chunks_by_id[hit.chunk_id].section,
            excerpt=chunks_by_id[hit.chunk_id].text,
            source=chunks_by_id[hit.chunk_id].title,
            source_priority=chunks_by_id[hit.chunk_id].source_priority,
            score=hit.score,
        )
        for hit in hits
    ]


def _expand_query(query: str, topic: str | None) -> tuple[str, str | None]:
    if topic == "pension_system" and (has_alias(query, "db") or has_alias(query, "dc") or has_alias(query, "institution")):
        return f"{query} 확정급여형 DB 회사 적립금 운용 확정기여형 DC 근로자 운용 퇴직급여", "institution"
    if topic == "withdrawal_tax" and is_tax_deduction_question(query):
        return f"{query} 연금저축 IRP 세액공제 납입한도 합산 600만원 900만원", "tax_deduction"
    if topic == "withdrawal_tax" and is_teacher_retirement_domain(query):
        return f"{query} 공무원 교사 퇴직수당 명예퇴직수당 퇴직소득 60일 연금계좌 환급", "teacher_retirement"
    if topic == "product" and has_alias(query, "product_family"):
        return f"{query} 투자목적 투자전략 투자위험등급 변동성 VaR 금리변동위험", "product_compare"
    return query, None


def _rerank_and_diversify(
    hits: list[RetrievalHit],
    chunks_by_id: dict[str, Chunk],
    query_kind: str | None,
    top_k: int,
) -> list[RetrievalHit]:
    if query_kind is None:
        return hits[:top_k]

    preferred_terms = {
        "institution": ("확정급여형", "확정기여형", "적립금", "운용", "퇴직급여"),
        "tax_deduction": ("세액공제", "600만원", "900만원", "16.5%", "13.2%", "납입한도"),
        "teacher_retirement": ("교사", "공무원", "명예퇴직수당", "퇴직수당", "60일", "환급"),
        "product_compare": ("투자목적", "투자위험등급", "변동성", "VaR", "금리변동위험"),
    }[query_kind]

    rescored: list[RetrievalHit] = []
    for hit in hits:
        chunk = chunks_by_id[hit.chunk_id]
        searchable = f"{chunk.title} {chunk.section} {chunk.text}"
        compact = searchable.replace(" ", "").lower()
        if query_kind == "tax_deduction" and not (
            "세액공제" in compact and ("연금저축" in compact or "irp" in compact)
        ):
            continue
        if query_kind == "institution" and not any(term.lower() in compact for term in ("확정급여", "확정기여", "퇴직연금", "퇴직금")):
            continue
        if query_kind == "teacher_retirement" and not (
            any(term in compact for term in ("교사", "공무원", "명예퇴직", "퇴직수당", "명퇴"))
            or ("퇴직소득세" in compact and "연금" in compact)
        ):
            continue
        boost = sum(2.0 for term in preferred_terms if term.lower() in searchable.lower())
        if query_kind == "teacher_retirement":
            # Applicability signals are independent: general tax evidence can
            # remain secondary, while a source covering the named population,
            # procedure, and tax source receives the appropriate boosts.
            chunk_scope = population_scope(searchable)
            if chunk_scope in {"TEACHER", "PUBLIC_OFFICIAL", "TEACHER_PUBLIC_OFFICIAL"}:
                boost += 8.0
            if any(term in compact for term in ("60일", "입금", "환급")):
                boost += 4.0
            if any(term in compact for term in ("퇴직소득", "퇴직소득세")):
                boost += 2.0
        rescored.append(
            RetrievalHit(
                chunk_id=hit.chunk_id,
                score=hit.score + boost,
                document_id=hit.document_id,
                page=hit.page,
                quote=hit.quote,
            )
        )
    rescored.sort(key=lambda hit: (-hit.score, hit.chunk_id))

    # Comparison and cross-document policy questions need source diversity before
    # repeated chunks from a single long document.
    selected: list[RetrievalHit] = []
    seen_documents: set[str] = set()
    for hit in rescored:
        if hit.document_id not in seen_documents:
            selected.append(hit)
            seen_documents.add(hit.document_id)
            if len(selected) == top_k:
                return selected
    for hit in rescored:
        if hit not in selected:
            selected.append(hit)
            if len(selected) == top_k:
                break
    return selected


def _passes_filters(
    chunk: Chunk,
    topics: list[str] | None,
    account_types: list[str] | None,
    on_date: date | None,
) -> bool:
    if topics and not set(topics).intersection(chunk.topics):
        return False

    if account_types and not set(account_types).intersection(chunk.account_types):
        return False

    if on_date:
        if chunk.effective_from and on_date < date.fromisoformat(chunk.effective_from):
            return False
        if chunk.valid_to and on_date > date.fromisoformat(chunk.valid_to):
            return False

    return True
