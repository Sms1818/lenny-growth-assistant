from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.messages import SourceResponse
from app.db.models import KnowledgeChunk, KnowledgeDocument


async def resolve_sources_for_chunk_ids(
    db: AsyncSession,
    chunk_ids: list[str] | None,
) -> list[SourceResponse]:
    if not chunk_ids:
        return []

    numeric_ids: list[int] = []

    for chunk_id in chunk_ids:
        try:
            numeric_ids.append(int(chunk_id))
        except ValueError:
            continue

    if not numeric_ids:
        return []

    statement = (
        select(KnowledgeChunk, KnowledgeDocument)
        .join(
            KnowledgeDocument,
            KnowledgeChunk.document_id == KnowledgeDocument.id,
        )
        .where(KnowledgeChunk.id.in_(numeric_ids))
    )

    rows = (await db.execute(statement)).all()
    by_id = {
        chunk.id: SourceResponse(
            chunk_id=chunk.id,
            title=document.title,
            source_type=document.source_type,
            guest=document.guest,
            source_url=document.source_url,
            youtube_url=document.youtube_url,
            start_timestamp=chunk.start_timestamp,
            end_timestamp=chunk.end_timestamp,
        )
        for chunk, document in rows
    }

    return [
        by_id[chunk_id]
        for chunk_id in numeric_ids
        if chunk_id in by_id
    ]
