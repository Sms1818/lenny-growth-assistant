from app.assistant.service import (
    ConversationTurn,
    build_conversation_context,
    build_retrieval_query,
)


def test_retrieval_query_without_history_uses_question_only():
    question = "How did Duolingo restart growth?"

    assert build_retrieval_query(question, []) == question


def test_retrieval_query_uses_only_user_history():
    history = [
        ConversationTurn(
            role="user",
            content="Tell me about Duolingo's growth.",
        ),
        ConversationTurn(
            role="assistant",
            content="This assistant response must not enter retrieval.",
        ),
    ]

    result = build_retrieval_query(
        "What metric did they prioritize?",
        history,
    )

    assert "Tell me about Duolingo's growth." in result
    assert "What metric did they prioritize?" in result
    assert "This assistant response must not enter retrieval." not in result


def test_retrieval_query_bounds_user_history():
    history = [
        ConversationTurn(role="user", content=f"Question {index}")
        for index in range(1, 6)
    ]

    result = build_retrieval_query(
        "Current question",
        history,
        max_user_turns=3,
    )

    assert "Question 1" not in result
    assert "Question 2" not in result
    assert "Question 3" in result
    assert "Question 4" in result
    assert "Question 5" in result


def test_conversation_context_includes_both_roles():
    history = [
        ConversationTurn(role="user", content="First question"),
        ConversationTurn(role="assistant", content="First answer"),
    ]

    result = build_conversation_context(history)

    assert "USER: First question" in result
    assert "ASSISTANT: First answer" in result


def test_conversation_context_bounds_total_turns():
    history = [
        ConversationTurn(
            role="user" if index % 2 else "assistant",
            content=f"Turn {index}",
        )
        for index in range(1, 9)
    ]

    result = build_conversation_context(
        history,
        max_turns=4,
    )

    assert "Turn 4" not in result
    assert "Turn 5" in result
    assert "Turn 6" in result
    assert "Turn 7" in result
    assert "Turn 8" in result

import pytest

from app.assistant.agent import AgentResponse
from app.assistant.service import answer_question
from app.knowledge.retrieval import RetrievedChunk


class FakeAgentClient:
    def __init__(self):
        self.prompts = []

    async def generate(self, prompt, *, system=None):
        self.prompts.append(
            {
                "prompt": prompt,
                "system": system,
            }
        )

        return AgentResponse(
            text="Duolingo prioritized CURR. [1]",
            provider="test-provider",
            model="test-model",
            input_tokens=100,
            output_tokens=20,
        )


@pytest.mark.asyncio
async def test_answer_question_uses_history_without_treating_it_as_evidence(
    monkeypatch,
):
    captured_queries = []

    async def fake_search_knowledge(query, *, limit=8, embedding_client=None):
        captured_queries.append(query)

        return [
            RetrievedChunk(
                chunk_id=42,
                document_id="document-1",
                title="How Duolingo reignited user growth",
                source_type="newsletter",
                guest=None,
                source_url="https://example.com/duolingo",
                youtube_url=None,
                content="Duolingo decided to focus on CURR.",
                start_timestamp=None,
                end_timestamp=None,
                similarity=0.95,
                lexical_rank=0.5,
                score=0.88,
            )
        ]

    monkeypatch.setattr(
        "app.assistant.service.search_knowledge",
        fake_search_knowledge,
    )

    agent = FakeAgentClient()

    history = [
        ConversationTurn(
            role="user",
            content="Tell me about Duolingo's growth.",
        ),
        ConversationTurn(
            role="assistant",
            content="A previous assistant answer.",
        ),
    ]

    result = await answer_question(
        "What metric did they prioritize?",
        conversation_history=history,
        agent_client=agent,
    )

    assert len(captured_queries) == 1

    retrieval_query = captured_queries[0]

    assert "Tell me about Duolingo's growth." in retrieval_query
    assert "What metric did they prioritize?" in retrieval_query
    assert "A previous assistant answer." not in retrieval_query

    assert len(agent.prompts) == 1

    generation_prompt = agent.prompts[0]["prompt"]

    assert "USER: Tell me about Duolingo's growth." in generation_prompt
    assert "ASSISTANT: A previous assistant answer." in generation_prompt
    assert "Duolingo decided to focus on CURR." in generation_prompt
    assert "What metric did they prioritize?" in generation_prompt
    assert (
        "Do not treat conversation history as factual evidence"
        in generation_prompt
    )

    assert result.answer == "Duolingo prioritized CURR. [1]"
    assert result.model_provider == "test-provider"
    assert result.model_name == "test-model"
    assert result.sources[0].chunk_id == 42
    assert result.grounding_issues == []


def test_unresolved_reference_without_history_is_detected():
    from app.assistant.service import has_unresolved_reference

    assert has_unresolved_reference(
        "What metric did they prioritize?",
        [],
    )


def test_reference_with_history_is_allowed():
    from app.assistant.service import has_unresolved_reference

    history = [
        ConversationTurn(
            role="user",
            content="Tell me about Duolingo's growth.",
        )
    ]

    assert not has_unresolved_reference(
        "What metric did they prioritize?",
        history,
    )


def test_clear_standalone_question_is_allowed():
    from app.assistant.service import has_unresolved_reference

    assert not has_unresolved_reference(
        "What is CURR?",
        [],
    )


@pytest.mark.asyncio
async def test_answer_question_clarifies_unresolved_reference():
    agent = FakeAgentClient()

    result = await answer_question(
        "What metric did they prioritize?",
        conversation_history=[],
        agent_client=agent,
    )

    assert "missing the context" in result.answer.lower()
    assert result.sources == []
    assert result.model_provider is None
    assert result.model_name is None
    assert agent.prompts == []


@pytest.mark.parametrize(
    "question",
    [
        "Why is this strategy effective in product-led growth?",
        "What makes this retention strategy effective?",
        "How does it affect retention?",
        "What does Duolingo say about its retention strategy?",
    ],
)
def test_standalone_questions_are_not_overblocked(question):
    from app.assistant.service import has_unresolved_reference

    assert not has_unresolved_reference(
        question,
        [],
    )
