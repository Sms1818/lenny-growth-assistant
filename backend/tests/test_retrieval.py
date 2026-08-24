import pytest

from app.knowledge.retrieval import build_lexical_query, search_knowledge


def test_build_lexical_query_uses_or_semantics():
    result = build_lexical_query(
        "How did Duolingo restart its user growth?"
    )

    assert "duolingo" in result
    assert "growth" in result
    assert " | " in result


@pytest.mark.asyncio
async def test_retrieval_finds_duolingo_growth_article():
    results = await search_knowledge(
        "How did Duolingo restart its user growth?",
        limit=5,
    )

    assert results
    assert results[0].title == "How Duolingo reignited user growth"


@pytest.mark.asyncio
async def test_retrieval_finds_elena_verna_growth_episode():
    results = await search_knowledge(
        "What does Elena Verna say is working for growth at AI companies?",
        limit=5,
    )

    assert results
    assert results[0].title == "Elena Verna 4.0"


@pytest.mark.asyncio
async def test_retrieval_finds_ai_evals_article():
    results = await search_knowledge(
        "How should product managers evaluate AI products instead of relying on vibe checks?",
        limit=5,
    )

    assert results
    assert results[0].title == "Beyond vibe checks: A PM’s complete guide to evals"


@pytest.mark.asyncio
async def test_retrieval_finds_curr_in_duolingo_article():
    results = await search_knowledge(
        "What is CURR?",
        limit=5,
    )

    assert results
    assert any(
        result.title == "How Duolingo reignited user growth"
        and "CURR" in result.content
        for result in results[:3]
    )
