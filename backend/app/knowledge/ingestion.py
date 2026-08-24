import hashlib
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import KnowledgeChunk, KnowledgeDocument
from app.knowledge.chunker import DocumentChunk, chunk_document
from app.knowledge.embeddings import OllamaEmbeddingClient
from app.knowledge.parser import ParsedDocument, parse_document


DEFAULT_BATCH_SIZE = 32


def calculate_content_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_date(value: Any) -> date | None:
    if value is None:
        return None

    if isinstance(value, date):
        return value

    text = str(value).strip()

    if not text:
        return None

    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def estimate_token_count(text: str) -> int:
    # A lightweight approximation is sufficient for corpus diagnostics.
    return max(1, len(text) // 4)


def build_source_metadata(document: ParsedDocument) -> dict[str, Any]:
    metadata = document.metadata

    excluded = {
        "title",
        "type",
        "guest",
        "date",
        "published_at",
        "url",
        "source_url",
        "youtube_url",
        "description",
    }

    return {
        str(key): value
        for key, value in metadata.items()
        if key not in excluded
    }


async def embed_chunks(
    chunks: list[DocumentChunk],
    embedding_client: OllamaEmbeddingClient,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list[list[float]]:
    embeddings: list[list[float]] = []

    for start in range(0, len(chunks), batch_size):
        batch = chunks[start : start + batch_size]
        batch_embeddings = await embedding_client.embed(
            [chunk.content for chunk in batch]
        )
        embeddings.extend(batch_embeddings)

    return embeddings


async def ingest_document(
    session: AsyncSession,
    path: Path,
    embedding_client: OllamaEmbeddingClient,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> tuple[str, int]:
    document = parse_document(path)
    chunks = chunk_document(document)
    content_hash = calculate_content_hash(path)

    result = await session.execute(
        select(KnowledgeDocument).where(
            KnowledgeDocument.filename == path.name
        )
    )
    existing = result.scalar_one_or_none()

    if existing and existing.content_hash == content_hash:
        return "skipped", len(chunks)

    metadata = document.metadata
    source_type = str(metadata.get("type", "")).lower()

    if source_type not in {"podcast", "newsletter"}:
        raise ValueError(
            f"Unsupported source type {source_type!r} for {path.name}"
        )

    embeddings = await embed_chunks(
        chunks,
        embedding_client,
        batch_size=batch_size,
    )

    if existing is None:
        db_document = KnowledgeDocument(
            source_type=source_type,
            filename=path.name,
            title=str(metadata.get("title") or path.stem),
            guest=metadata.get("guest"),
            published_at=parse_date(
                metadata.get("published_at") or metadata.get("date")
            ),
            source_url=metadata.get("source_url") or metadata.get("url"),
            youtube_url=metadata.get("youtube_url"),
            description=metadata.get("description"),
            word_count=len(document.body.split()),
            content_hash=content_hash,
            source_metadata=build_source_metadata(document),
        )

        session.add(db_document)
        await session.flush()
        status = "inserted"
    else:
        db_document = existing

        db_document.source_type = source_type
        db_document.title = str(metadata.get("title") or path.stem)
        db_document.guest = metadata.get("guest")
        db_document.published_at = parse_date(
            metadata.get("published_at") or metadata.get("date")
        )
        db_document.source_url = (
            metadata.get("source_url") or metadata.get("url")
        )
        db_document.youtube_url = metadata.get("youtube_url")
        db_document.description = metadata.get("description")
        db_document.word_count = len(document.body.split())
        db_document.content_hash = content_hash
        db_document.source_metadata = build_source_metadata(document)

        await session.execute(
            delete(KnowledgeChunk).where(
                KnowledgeChunk.document_id == db_document.id
            )
        )

        status = "updated"

    for index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        session.add(
            KnowledgeChunk(
                document_id=db_document.id,
                chunk_index=index,
                content=chunk.content,
                start_timestamp=chunk.start_timestamp,
                end_timestamp=chunk.end_timestamp,
                section_title=chunk.section_title,
                token_count=estimate_token_count(chunk.content),
                embedding=embedding,
            )
        )

    return status, len(chunks)
