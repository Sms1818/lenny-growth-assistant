from dataclasses import dataclass
import re

from sqlalchemy import func, select

from app.db.models import KnowledgeChunk, KnowledgeDocument
from app.db.session import AsyncSessionLocal
from app.knowledge.embeddings import OllamaEmbeddingClient


RRF_K = 60


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    document_id: str
    title: str
    source_type: str
    guest: str | None
    source_url: str | None
    youtube_url: str | None
    content: str
    start_timestamp: str | None
    end_timestamp: str | None
    similarity: float
    lexical_rank: float
    score: float


def build_lexical_query(query: str) -> str:
    terms = re.findall(r"[A-Za-z0-9]+", query.lower())

    seen: set[str] = set()
    unique_terms: list[str] = []

    for term in terms:
        if term not in seen:
            seen.add(term)
            unique_terms.append(term)

    return " | ".join(unique_terms)


ENTITY_MATCH_BOOST = 0.01

GENERIC_METADATA_TERMS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "by",
    "for",
    "from",
    "how",
    "in",
    "into",
    "is",
    "of",
    "on",
    "product",
    "products",
    "the",
    "to",
    "user",
    "users",
    "with",
    "growth",
    "retention",
    "podcast",
}


def normalize_metadata_text(value: str) -> str:
    return " ".join(
        re.findall(
            r"[a-z0-9]+",
            value.lower(),
        )
    )


def metadata_match_boost(
    query: str,
    *,
    title: str,
    guest: str | None,
) -> float:
    normalized_query = normalize_metadata_text(query)
    query_tokens = set(normalized_query.split())

    if guest:
        guest_tokens = [
            token
            for token in normalize_metadata_text(guest).split()
            if not token.isdigit()
        ]

        if len(guest_tokens) >= 2:
            guest_phrase = " ".join(guest_tokens)

            if guest_phrase in normalized_query:
                return ENTITY_MATCH_BOOST

    title_tokens = [
        token
        for token in normalize_metadata_text(title).split()
        if (
            token not in GENERIC_METADATA_TERMS
            and not token.isdigit()
            and len(token) >= 4
        )
    ]

    if any(
        token in query_tokens
        for token in title_tokens
    ):
        return ENTITY_MATCH_BOOST

    return 0.0


async def search_knowledge(
    query: str,
    *,
    limit: int = 8,
    embedding_client: OllamaEmbeddingClient | None = None,
) -> list[RetrievedChunk]:
    query = query.strip()

    if not query:
        return []

    if limit < 1:
        raise ValueError("limit must be at least 1")

    client = embedding_client or OllamaEmbeddingClient()
    query_embedding = (await client.embed([query]))[0]

    distance = KnowledgeChunk.embedding.cosine_distance(
        query_embedding
    )
    similarity = 1.0 - distance

    searchable_text = func.concat_ws(
        " ",
        KnowledgeDocument.title,
        func.coalesce(KnowledgeDocument.guest, ""),
        KnowledgeChunk.content,
    )

    search_vector = func.to_tsvector(
        "english",
        searchable_text,
    )

    lexical_query = build_lexical_query(query)
    search_query = func.to_tsquery(
        "english",
        lexical_query,
    )

    lexical_rank = func.ts_rank_cd(
        search_vector,
        search_query,
    )

    candidate_limit = max(limit * 5, 25)
    rerank_limit = max(limit * 4, 20)

    semantic_candidates = (
        select(
            KnowledgeChunk.id.label("chunk_id"),
            func.row_number()
            .over(order_by=distance)
            .label("semantic_position"),
        )
        .order_by(distance)
        .limit(candidate_limit)
        .cte("semantic_candidates")
    )

    lexical_candidates = (
        select(
            KnowledgeChunk.id.label("chunk_id"),
            func.row_number()
            .over(order_by=lexical_rank.desc())
            .label("lexical_position"),
        )
        .join(
            KnowledgeDocument,
            KnowledgeDocument.id
            == KnowledgeChunk.document_id,
        )
        .where(
            search_vector.op("@@")(search_query)
        )
        .order_by(lexical_rank.desc())
        .limit(candidate_limit)
        .cte("lexical_candidates")
    )

    candidate_ids = (
        select(
            semantic_candidates.c.chunk_id.label("chunk_id")
        )
        .union(
            select(
                lexical_candidates.c.chunk_id.label("chunk_id")
            )
        )
        .cte("candidate_ids")
    )

    candidates = (
        select(
            candidate_ids.c.chunk_id,
            semantic_candidates.c.semantic_position,
            lexical_candidates.c.lexical_position,
        )
        .select_from(candidate_ids)
        .outerjoin(
            semantic_candidates,
            semantic_candidates.c.chunk_id
            == candidate_ids.c.chunk_id,
        )
        .outerjoin(
            lexical_candidates,
            lexical_candidates.c.chunk_id
            == candidate_ids.c.chunk_id,
        )
        .cte("candidates")
    )

    semantic_rrf = func.coalesce(
        1.0
        / (
            RRF_K
            + candidates.c.semantic_position
        ),
        0.0,
    )

    lexical_rrf = func.coalesce(
        1.0
        / (
            RRF_K
            + candidates.c.lexical_position
        ),
        0.0,
    )

    rrf_score = semantic_rrf + lexical_rrf

    statement = (
        select(
            KnowledgeChunk.id,
            KnowledgeChunk.document_id,
            KnowledgeChunk.content,
            KnowledgeChunk.start_timestamp,
            KnowledgeChunk.end_timestamp,
            KnowledgeDocument.title,
            KnowledgeDocument.source_type,
            KnowledgeDocument.guest,
            KnowledgeDocument.source_url,
            KnowledgeDocument.youtube_url,
            similarity.label("similarity"),
            lexical_rank.label("lexical_rank"),
            candidates.c.semantic_position,
            candidates.c.lexical_position,
            rrf_score.label("score"),
        )
        .join(
            candidates,
            candidates.c.chunk_id
            == KnowledgeChunk.id,
        )
        .join(
            KnowledgeDocument,
            KnowledgeDocument.id
            == KnowledgeChunk.document_id,
        )
        .order_by(
            rrf_score.desc(),
            similarity.desc(),
        )
        .limit(rerank_limit)
    )

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(statement)).all()

    results = [
        RetrievedChunk(
            chunk_id=row.id,
            document_id=str(row.document_id),
            title=row.title,
            source_type=row.source_type,
            guest=row.guest,
            source_url=row.source_url,
            youtube_url=row.youtube_url,
            content=row.content,
            start_timestamp=row.start_timestamp,
            end_timestamp=row.end_timestamp,
            similarity=max(
                0.0,
                min(1.0, float(row.similarity)),
            ),
            lexical_rank=float(
                row.lexical_rank or 0.0
            ),
            score=(
                float(row.score)
                + metadata_match_boost(
                    query,
                    title=row.title,
                    guest=row.guest,
                )
            ),
        )
        for row in rows
    ]

    results.sort(
        key=lambda result: (
            result.score,
            result.similarity,
        ),
        reverse=True,
    )

    return results[:limit]
