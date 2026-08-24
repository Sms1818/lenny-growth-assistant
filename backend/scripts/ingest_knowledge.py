import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import func, select

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.models import KnowledgeChunk, KnowledgeDocument
from app.db.session import AsyncSessionLocal
from app.knowledge.embeddings import OllamaEmbeddingClient
from app.knowledge.ingestion import ingest_document


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Ingest Lenny's podcast and newsletter corpus."
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Path containing podcasts/ and newsletters/ directories.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Number of chunks sent to Ollama per embedding request.",
    )
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    source = args.source.expanduser().resolve()

    if args.batch_size < 1:
        raise ValueError("--batch-size must be at least 1")

    if not source.exists():
        raise FileNotFoundError(f"Source directory does not exist: {source}")

    paths = [
        *sorted((source / "podcasts").glob("*.md")),
        *sorted((source / "newsletters").glob("*.md")),
    ]

    if not paths:
        raise FileNotFoundError(
            f"No Markdown documents found under {source}"
        )

    embedding_client = OllamaEmbeddingClient()

    counts = {
        "inserted": 0,
        "updated": 0,
        "skipped": 0,
        "failed": 0,
    }

    processed_chunks = 0

    print(f"Source: {source}")
    print(f"Documents discovered: {len(paths)}")
    print(f"Embedding batch size: {args.batch_size}")
    print()

    async with AsyncSessionLocal() as session:
        for index, path in enumerate(paths, start=1):
            try:
                status, chunk_count = await ingest_document(
                    session,
                    path,
                    embedding_client,
                    batch_size=args.batch_size,
                )

                await session.commit()

                counts[status] += 1
                processed_chunks += chunk_count

                print(
                    f"[{index:02d}/{len(paths):02d}] "
                    f"{status.upper():8} "
                    f"{path.name} "
                    f"({chunk_count} chunks)"
                )
            except Exception as exc:
                await session.rollback()
                counts["failed"] += 1

                print(
                    f"[{index:02d}/{len(paths):02d}] "
                    f"FAILED   {path.name}: {exc}",
                    file=sys.stderr,
                )

        document_count = await session.scalar(
            select(func.count()).select_from(KnowledgeDocument)
        )
        chunk_count = await session.scalar(
            select(func.count()).select_from(KnowledgeChunk)
        )

    print()
    print("Ingestion complete")
    print("------------------")
    print(f"Inserted: {counts['inserted']}")
    print(f"Updated:  {counts['updated']}")
    print(f"Skipped:  {counts['skipped']}")
    print(f"Failed:   {counts['failed']}")
    print(f"Processed chunks: {processed_chunks}")
    print(f"Documents in DB:  {document_count}")
    print(f"Chunks in DB:     {chunk_count}")

    if counts["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
