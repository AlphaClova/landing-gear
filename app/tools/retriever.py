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
    domain_query_coverage,
    meaningful_query_tokens,
    query_domain_anchors,
    has_alias,
    is_generic_pension_question,
    is_pension_receiving_question,
    is_tax_deduction_question,
    is_teacher_retirement_domain,
    pension_scope,
    population_scope,
)


TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣]+")
DEFAULT_CHUNKS_PATH = Path(__file__).resolve().parents[1] / "data" / "processed" / "chunks.jsonl"
RETRIEVAL_MIN_SCORE = 0.01
RETRIEVAL_MIN_QUERY_COVERAGE = 0.51
RETRIEVAL_MIN_DOMAIN_COVERAGE = 0.40

# Informal receiving wording is not added as standalone in-scope keywords.
# These aliases only absorb lexical mismatch against provided corpus phrasing.
# Bare "연금" is not a retirement-pension retrieval trigger; scope helpers decide.
_INFORMAL_RECEIVING_TERMS = ("받으려면", "받을", "받는", "받다", "언제", "몇 살", "나이", "살부터")
_PENSION_RECEIVING_EXPANSION = "수령 지급 수령 시점 개시 시점 수령 연령 개시 연령 연금 수령"
_PENSION_RECEIVING_TOKEN_ALIASES: dict[str, tuple[str, ...]] = {
    "받다": ("수령",),
    "받는": ("수령",),
    "받을": ("수령",),
    "받으려면": ("수령",),
    "받으면": ("수령",),
    "언제": ("수령", "개시"),
    "살부터": ("수령", "연령", "개시"),
    "몇살": ("수령", "연령", "개시"),
    "나이": ("수령", "연령", "개시"),
}
_RECEIVING_DOMAIN_ALIASES = frozenset({"수령", "개시", "연령"})

# Informal IRP account / compare / transfer wording. Parallel to receiving
# aliases: absorb lexical mismatch only. Do not encode ages, rates, or limits.
_IRP_ACCOUNT_INFORMAL = ("계좌인가요", "어떤 계좌", "무슨 계좌")
_IRP_COMPARE_INFORMAL = ("뭐가 다른", "다른가요", "달라요")
_IRP_TRANSFER_INFORMAL = ("옮길", "옮기", "넘겨", "넘길")
_IRP_ACCOUNT_EXPANSION = "개인형퇴직연금 계좌 정의"
_IRP_COMPARE_EXPANSION = "연금저축 계좌 비교 차이"
_IRP_TRANSFER_EXPANSION = "이전 이동 입금"
_IRP_SKIP_TOKENS = frozenset({"어떤", "뭐가", "다른가요", "달라요"})
_IRP_LEXICAL_TOKEN_ALIASES: dict[str, tuple[str, ...]] = {
    "계좌인가요": ("계좌", "개인형퇴직연금"),
    "옮길": ("이전", "이동", "입금"),
    "옮기": ("이전", "이동", "입금"),
    "넘겨": ("이전", "이동", "입금"),
    "넘길": ("이전", "이동", "입금"),
    "퇴직한": ("퇴직",),
}
_IRP_DOMAIN_TERMS = frozenset({"계좌", "이전", "이동", "입금", "비교", "차이", "정의", "개인형퇴직연금"})


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


def pension_receiving_normalization_applies(query: str) -> bool:
    """True only when a specific pension-domain question uses informal receiving wording."""
    if not isinstance(query, str) or not query.strip():
        return False
    if is_generic_pension_question(query) or pension_scope(query) in {"NONE", "NATIONAL_PENSION"}:
        return False
    if pension_scope(query) not in {"RETIREMENT_PENSION", "PENSION_SAVINGS", "IRP"}:
        return False
    if not is_pension_receiving_question(query):
        return False
    return any(term in query for term in _INFORMAL_RECEIVING_TERMS)


def _receiving_search_query(query: str) -> str:
    if not pension_receiving_normalization_applies(query):
        return query
    if _PENSION_RECEIVING_EXPANSION in query:
        return query
    return f"{query} {_PENSION_RECEIVING_EXPANSION}"


def irp_lexical_normalization_applies(query: str) -> bool:
    """True when an IRP question uses informal account, compare, or transfer wording."""
    if not isinstance(query, str) or not query.strip():
        return False
    if "IRP" not in query.upper() and "irp" not in query.lower():
        return False
    return (
        any(term in query for term in _IRP_ACCOUNT_INFORMAL)
        or any(term in query for term in _IRP_COMPARE_INFORMAL)
        or any(term in query for term in _IRP_TRANSFER_INFORMAL)
    )


def _irp_search_query(query: str) -> str:
    if not irp_lexical_normalization_applies(query):
        return query
    extra: list[str] = []
    if any(term in query for term in _IRP_ACCOUNT_INFORMAL):
        extra.append(_IRP_ACCOUNT_EXPANSION)
    if any(term in query for term in _IRP_COMPARE_INFORMAL):
        extra.append(_IRP_COMPARE_EXPANSION)
    if any(term in query for term in _IRP_TRANSFER_INFORMAL):
        extra.append(_IRP_TRANSFER_EXPANSION)
    blob = " ".join(extra)
    if not blob or blob in query:
        return query
    return f"{query} {blob}"


def _gate_query_tokens(query: str) -> tuple[str, ...]:
    tokens = meaningful_query_tokens(query)
    if not irp_lexical_normalization_applies(query):
        return tokens
    rewritten: list[str] = []
    for token in tokens:
        if token in _IRP_SKIP_TOKENS:
            continue
        aliases = _IRP_LEXICAL_TOKEN_ALIASES.get(token)
        if aliases:
            rewritten.append(aliases[0])
            continue
        rewritten.append(token)
    return tuple(dict.fromkeys(rewritten)) or tokens


def _irp_domain_coverage(query: str, meaningful: tuple[str, ...]) -> float:
    if not meaningful:
        return 0.0
    anchors = query_domain_anchors(query)
    supported = 0
    for token in meaningful:
        if any(token in anchor.lower() or anchor.lower() in token for anchor in anchors):
            supported += 1
            continue
        if token in _IRP_DOMAIN_TERMS:
            supported += 1
    return supported / len(meaningful)


def _irp_chunk_supported(query: str, compact: str) -> bool:
    if any(term in query for term in _IRP_TRANSFER_INFORMAL):
        return any(term in compact for term in ("이전", "이동", "계약이전"))
    if any(term in query for term in _IRP_COMPARE_INFORMAL):
        return "연금저축" in compact and "irp" in compact
    if any(term in query for term in _IRP_ACCOUNT_INFORMAL):
        return "irp" in compact and ("개인형" in compact or "연금계좌" in compact)
    return "irp" in compact


def _retrieval_topics(query: str, topic: str | None) -> list[str] | None:
    if topic is None:
        return None
    # IRP account/compare facts live in the tax corpus, not pension_system.
    if irp_lexical_normalization_applies(query) and topic == "pension_system":
        return ["pension_system", "withdrawal_tax"]
    return [topic]


def _token_matches_corpus(token: str, compact: str, *, use_aliases: bool) -> bool:
    if token in compact:
        return True
    if not use_aliases:
        return False
    return any(alias in compact for alias in _PENSION_RECEIVING_TOKEN_ALIASES.get(token, ()))


def _receiving_domain_coverage(query: str, meaningful: tuple[str, ...]) -> float:
    if not meaningful:
        return 0.0
    anchors = query_domain_anchors(query)
    supported = 0
    for token in meaningful:
        if any(token in anchor.lower() or anchor.lower() in token for anchor in anchors):
            supported += 1
            continue
        aliases = _PENSION_RECEIVING_TOKEN_ALIASES.get(token, ())
        if aliases and any(alias in _RECEIVING_DOMAIN_ALIASES for alias in aliases):
            supported += 1
    return supported / len(meaningful)


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


_PRODUCT_PROSPECTUS_MARKERS = ("2. 투자전략", "1. 투자목적", "수수료선취-오프라인(A)")


def prospectus_for_documents(document_ids: list[str] | tuple[str, ...]) -> list[EvidenceResult]:
    """Return prospectus chunks for already-matched product documents.

    Lookup is by Product Fact document_id identity, not BM25 or the 0.51
    lexical coverage gate. Threshold/top-k of retrieve_evidence are unchanged.
    """
    wanted = {str(item) for item in document_ids if str(item).startswith("r2_")}
    if not wanted:
        return []
    selected: list[EvidenceResult] = []
    for chunk in _load_chunks(DEFAULT_CHUNKS_PATH):
        if chunk.document_id not in wanted:
            continue
        if not any(marker in chunk.text for marker in _PRODUCT_PROSPECTUS_MARKERS):
            continue
        selected.append(
            EvidenceResult(
                evidence_id=chunk.chunk_id,
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                page=chunk.page,
                section=chunk.section,
                excerpt=chunk.text,
                source=chunk.title,
                source_priority=chunk.source_priority,
                score=chunk.source_priority * -0.001,
            )
        )
    return selected


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
        topics=_retrieval_topics(query, topic),
    )
    hits = _apply_relevance_gate(query, hits, chunks_by_id)
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


def relevance_diagnostics(
    query: str,
    hit: RetrievalHit,
    chunk: Chunk,
    aggregate_coverage: float | None = None,
) -> dict[str, object]:
    """Explain the deterministic relevance gate for tests and audit artifacts."""
    use_receiving = pension_receiving_normalization_applies(query)
    use_irp = irp_lexical_normalization_applies(query)
    meaningful = _gate_query_tokens(query)
    searchable = f"{chunk.title} {chunk.section} {chunk.text}".lower()
    compact = searchable.replace(" ", "")
    matched = tuple(
        token for token in meaningful if _token_matches_corpus(token, compact, use_aliases=use_receiving)
    )
    coverage = len(matched) / len(meaningful) if meaningful else 0.0
    anchors = query_domain_anchors(query)
    matched_anchors = tuple(anchor for anchor in anchors if anchor.lower() in compact)
    if use_receiving:
        domain_coverage = _receiving_domain_coverage(query, meaningful)
    elif use_irp:
        domain_coverage = _irp_domain_coverage(query, meaningful)
    else:
        domain_coverage = domain_query_coverage(query)
    # Informal receiving/IRP terms can be covered by one supporting chunk while
    # other candidates only share the domain noun. Keep per-hit coverage so
    # union coverage does not revive unrelated operational pages.
    effective_coverage = coverage if (aggregate_coverage is None or use_receiving or use_irp) else aggregate_coverage
    custom_exact_match = not anchors and effective_coverage == 1.0
    receiving_supported = True
    if use_receiving:
        receiving_supported = any(
            _token_matches_corpus(token, compact, use_aliases=True)
            for token in meaningful
            if token in _PENSION_RECEIVING_TOKEN_ALIASES
        )
    irp_supported = True
    if use_irp:
        irp_supported = _irp_chunk_supported(query, compact)
    accepted = (
        hit.score >= RETRIEVAL_MIN_SCORE
        and bool(meaningful)
        and receiving_supported
        and irp_supported
        and (
            custom_exact_match
            or (
                effective_coverage >= RETRIEVAL_MIN_QUERY_COVERAGE
                and domain_coverage >= RETRIEVAL_MIN_DOMAIN_COVERAGE
                and bool(matched_anchors)
            )
        )
    )
    normalized = " ".join(meaningful)
    if use_receiving:
        normalized = f"{normalized} {_PENSION_RECEIVING_EXPANSION}".strip()
    elif use_irp:
        normalized = _irp_search_query(normalized)
    return {
        "normalized_query": normalized,
        "meaningful_query_tokens": list(meaningful),
        "matched_query_tokens": list(matched),
        "token_coverage": coverage,
        "domain_anchors": list(anchors),
        "matched_domain_anchors": list(matched_anchors),
        "domain_query_coverage": domain_coverage,
        "aggregate_token_coverage": effective_coverage,
        "raw_retrieval_score": hit.score,
        "accepted": accepted,
    }


def _apply_relevance_gate(
    query: str,
    hits: list[RetrievalHit],
    chunks_by_id: dict[str, Chunk],
) -> list[RetrievalHit]:
    meaningful = _gate_query_tokens(query)
    if not meaningful or not hits:
        return []
    use_aliases = pension_receiving_normalization_applies(query)
    candidate_text = " ".join(
        f"{chunks_by_id[hit.chunk_id].title} {chunks_by_id[hit.chunk_id].section} "
        f"{chunks_by_id[hit.chunk_id].text}"
        for hit in hits
    ).lower().replace(" ", "")
    aggregate_matched = [
        token for token in meaningful
        if _token_matches_corpus(token, candidate_text, use_aliases=use_aliases)
    ]
    aggregate_coverage = len(aggregate_matched) / len(meaningful)
    return [
        hit for hit in hits
        if relevance_diagnostics(
            query, hit, chunks_by_id[hit.chunk_id], aggregate_coverage
        )["accepted"]
    ]


def _expand_query(query: str, topic: str | None) -> tuple[str, str | None]:
    if topic == "pension_system" and (has_alias(query, "db") or has_alias(query, "dc") or has_alias(query, "institution")):
        search_query, query_kind = (
            f"{query} 확정급여형 DB 회사 적립금 운용 확정기여형 DC 근로자 운용 퇴직급여",
            "institution",
        )
    elif topic == "withdrawal_tax" and is_tax_deduction_question(query):
        search_query, query_kind = (
            f"{query} 연금저축 IRP 세액공제 납입한도 합산 600만원 900만원",
            "tax_deduction",
        )
    elif topic == "withdrawal_tax" and is_teacher_retirement_domain(query):
        search_query, query_kind = (
            f"{query} 공무원 교사 퇴직수당 명예퇴직수당 퇴직소득 60일 연금계좌 환급",
            "teacher_retirement",
        )
    elif topic == "product" and has_alias(query, "product_family"):
        search_query, query_kind = (
            f"{query} 투자목적 투자전략 투자위험등급 변동성 VaR 금리변동위험",
            "product_compare",
        )
    else:
        search_query, query_kind = query, None
    if pension_receiving_normalization_applies(query):
        search_query = _receiving_search_query(search_query)
    if irp_lexical_normalization_applies(query):
        search_query = _irp_search_query(search_query)
    return search_query, query_kind


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
