import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.assistant.service import answer_question
from app.knowledge.embeddings import (
    EmbeddingServiceError,
    EmbeddingServiceUnavailableError,
)
from app.main import (
    embedding_service_error_handler,
    embedding_unavailable_handler,
    sqlalchemy_exception_handler,
)


@pytest.mark.asyncio
async def test_empty_retrieval_returns_graceful_answer(
    monkeypatch,
):
    async def fake_search(
        query,
        *,
        limit=5,
        embedding_client=None,
    ):
        return []

    monkeypatch.setattr(
        "app.assistant.service.search_knowledge",
        fake_search,
    )

    result = await answer_question(
        "What does the knowledge base say?"
    )

    assert result.sources == []
    assert result.grounding_issues == []
    assert "couldn't find enough relevant information" in (
        result.answer.lower()
    )


@pytest.mark.asyncio
async def test_embedding_unavailable_maps_to_503():
    response = await embedding_unavailable_handler(
        None,
        EmbeddingServiceUnavailableError(
            "The local embedding service is unavailable."
        ),
    )

    assert response.status_code == 503
    assert b'"code":"embedding_unavailable"' in response.body


@pytest.mark.asyncio
async def test_embedding_failure_maps_to_502():
    response = await embedding_service_error_handler(
        None,
        EmbeddingServiceError(
            "The embedding service returned an error."
        ),
    )

    assert response.status_code == 502
    assert b'"code":"embedding_failed"' in response.body


@pytest.mark.asyncio
async def test_database_failure_maps_to_503():
    response = await sqlalchemy_exception_handler(
        None,
        SQLAlchemyError("database unavailable"),
    )

    assert response.status_code == 503
    assert b'"code":"database_unavailable"' in response.body
    assert b"database unavailable" not in response.body
