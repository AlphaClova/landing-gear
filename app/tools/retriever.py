from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date

from app.data.schemas.models import Chunk, RetrievalHit


TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣]+")


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


def _soft_term_freq(term: str, term_freq: Counter[str]) -> int:
    exact = term_freq.get(term, 0)
    if exact > 0:
        return exact

    # Korean tokens often include suffixes (e.g., "연금수령시").
    count = 0
    for token, token_count in term_freq.items():
        if term in token or token in term:
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

        return sorted(hits, key=lambda h: h.score, reverse=True)[:top_k]

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
