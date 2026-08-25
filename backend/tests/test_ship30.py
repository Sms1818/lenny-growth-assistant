import pytest

from app.assistant.agent import AgentResponse
from app.assistant.service import ConversationTurn
from app.assistant.skills.ship30 import (
    SHIP30_SYSTEM_PROMPT,
    build_ship30_prompt,
    generate_ship30_essay,
)
from app.knowledge.retrieval import RetrievedChunk


class FakeShip30Agent:
    def __init__(self):
        self.calls = []

    async def generate(self, prompt, *, system=None):
        self.calls.append(
            {
                "prompt": prompt,
                "system": system,
            }
        )

        return AgentResponse(
            text=(
                "# Retention Before Acquisition\n\n"
                "Duolingo prioritized retention before acquisition. [1]\n\n"
                "## The takeaway\n\n"
                "Focus on the constraint that most affects growth. [1]"
            ),
            provider="test-provider",
            model="test-model",
            input_tokens=100,
            output_tokens=50,
        )


def make_chunk():
    return RetrievedChunk(
        chunk_id=5088,
        document_id="doc-1",
        title="How Duolingo reignited user growth",
        source_type="newsletter",
        guest=None,
        source_url=None,
        youtube_url=None,
        content=(
            "Duolingo prioritized retention over new-user acquisition. "
            "The team focused on CURR as a major growth lever."
        ),
        start_timestamp=None,
        end_timestamp=None,
        similarity=0.8,
        lexical_rank=1.0,
        score=0.03,
    )


def test_ship30_prompt_encodes_writing_contract():
    prompt = build_ship30_prompt(
        topic="Write about Duolingo retention",
        source_context="Source material",
        conversation_context="USER: Previous context",
    )

    assert "Approximately 1,250 words" in prompt
    assert "strong, specific headline" in prompt
    assert "compelling opening hook" in prompt
    assert "Selective bold emphasis" in prompt
    assert "concrete closing takeaway" in prompt
    assert "Inline source citations" in prompt


def test_ship30_system_prompt_forbids_fabricated_experience():
    assert "Do not pretend to have personal experience" in SHIP30_SYSTEM_PROMPT
    assert "Use only the supplied Lenny knowledge sources" in SHIP30_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_ship30_uses_source_chunks_directly(
    monkeypatch,
):
    captured_queries = []

    async def fake_search(
        query,
        *,
        limit=8,
        embedding_client=None,
    ):
        captured_queries.append(query)
        return [make_chunk()]

    monkeypatch.setattr(
        "app.assistant.skills.ship30.search_knowledge",
        fake_search,
    )

    agent = FakeShip30Agent()

    result = await generate_ship30_essay(
        "Turn the Duolingo discussion into an essay.",
        conversation_history=[
            ConversationTurn(
                role="user",
                content="Tell me about Duolingo growth.",
            ),
            ConversationTurn(
                role="assistant",
                content="Previous assistant summary.",
            ),
        ],
        agent_client=agent,
    )

    assert len(captured_queries) == 1
    assert "Tell me about Duolingo growth." in captured_queries[0]
    assert "Previous assistant summary." not in captured_queries[0]

    assert len(agent.calls) == 1

    prompt = agent.calls[0]["prompt"]

    assert "Duolingo prioritized retention" in prompt
    assert "Previous assistant summary." in prompt
    assert result.sources[0].chunk_id == 5088
    assert result.model_provider == "test-provider"
    assert result.model_name == "test-model"
    assert result.grounding_issues == []


@pytest.mark.asyncio
async def test_ship30_rejects_empty_topic():
    with pytest.raises(
        ValueError,
        match="topic cannot be empty",
    ):
        await generate_ship30_essay("   ")


@pytest.mark.asyncio
async def test_ship30_self_contained_topic_excludes_history_from_retrieval(
    monkeypatch,
):
    captured_queries = []

    async def fake_search(
        query,
        *,
        limit=8,
        embedding_client=None,
    ):
        captured_queries.append(query)
        return [make_chunk()]

    monkeypatch.setattr(
        "app.assistant.skills.ship30.search_knowledge",
        fake_search,
    )

    agent = FakeShip30Agent()

    topic = (
        "Create a Ship 30 essay about how Duolingo "
        "reignited user growth."
    )

    await generate_ship30_essay(
        topic,
        conversation_history=[
            ConversationTurn(
                role="user",
                content="Tell me about Anthropic growth.",
            ),
            ConversationTurn(
                role="assistant",
                content="Previous Anthropic discussion.",
            ),
        ],
        agent_client=agent,
    )

    assert captured_queries == [topic]
    assert "Anthropic" not in captured_queries[0]

