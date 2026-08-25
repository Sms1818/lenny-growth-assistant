from dataclasses import dataclass
import re

from app.assistant.grounding import (
    clean_grounding_issues,
    GroundingIssue,
    remove_unsupported_acronym_expansions,
    validate_grounding,
)
from app.assistant.agent import PiAgentClient
from app.core.config import get_settings
from app.knowledge.retrieval import RetrievedChunk, search_knowledge
from app.core.logger import log_event


SYSTEM_PROMPT = """You are Lenny Growth Assistant.

Answer product and growth questions using only the provided sources from
Lenny's Newsletter and Lenny's Podcast.

Grounding rules:
- Every factual claim must be supported by the provided sources.
- Do not use outside knowledge, even when you believe it is correct.
- Do not invent facts, numbers, examples, quotes, or recommendations.
- Never place text in quotation marks unless those exact words appear in a
  provided source.
- Never expand or define an acronym unless its expansion is explicitly stated
  in the provided sources. Otherwise, keep the acronym unchanged.
- Do not claim that an initiative caused an outcome unless the provided
  sources explicitly support that relationship.
- Prefer paraphrasing source material over quoting it.
- Cite factual claims with the relevant source number, such as [1] or [2].
- Do not cite a source unless it actually supports that claim.
- Synthesize across sources when useful instead of merely repeating chunks.
- If the sources are insufficient to answer the question, say that clearly.
- Be practical, direct, and concise.
"""


@dataclass(frozen=True)
class AnswerSource:
    chunk_id: int
    title: str
    source_type: str
    guest: str | None
    source_url: str | None
    youtube_url: str | None
    start_timestamp: str | None
    end_timestamp: str | None


@dataclass(frozen=True)
class ConversationTurn:
    role: str
    content: str


@dataclass(frozen=True)
class AssistantAnswer:
    answer: str
    sources: list[AnswerSource]
    grounding_retry_used: bool
    grounding_issues: list[GroundingIssue]
    model_provider: str | None = None
    model_name: str | None = None


def build_context(chunks: list[RetrievedChunk]) -> str:
    sections: list[str] = []

    for index, chunk in enumerate(chunks, start=1):
        metadata = [
            f"Source: [{index}]",
            f"Title: {chunk.title}",
            f"Type: {chunk.source_type}",
        ]

        if chunk.guest:
            metadata.append(f"Guest: {chunk.guest}")

        if chunk.start_timestamp:
            timestamp = chunk.start_timestamp

            if chunk.end_timestamp:
                timestamp += f" - {chunk.end_timestamp}"

            metadata.append(f"Timestamp: {timestamp}")

        sections.append(
            "\n".join(metadata)
            + "\n\n"
            + chunk.content.strip()
        )

    return "\n\n---\n\n".join(sections)


AMBIGUOUS_REFERENCE_PATTERNS = (
    r"\bthey\b",
    r"\bthem\b",
    r"\btheir\b",
    r"\bhe\b",
    r"\bhim\b",
    r"\bhis\b",
    r"\bshe\b",
    r"\bher\b",
)


def has_unresolved_reference(
    question: str,
    conversation_history: list[ConversationTurn],
) -> bool:
    if conversation_history:
        return False

    normalized = question.strip().lower()

    return any(
        re.search(pattern, normalized)
        for pattern in AMBIGUOUS_REFERENCE_PATTERNS
    )


CONTEXT_REFERENCE_PATTERNS = (
    r"\b(it|they|them|their|he|him|his|she|her)\b",
    r"\b(this|that|these|those)\b",
    r"\b(?:the|our)\b(?:\s+[a-z0-9'-]+){0,3}\s+(?:discussion|conversation|answer|topic|idea|analysis)\b",
    r"\b(previous|earlier|above)\b",
)


def needs_conversation_context(text: str) -> bool:
    normalized = text.strip().lower()

    return any(
        re.search(pattern, normalized)
        for pattern in CONTEXT_REFERENCE_PATTERNS
    )


def build_retrieval_query(
    question: str,
    conversation_history: list[ConversationTurn],
    *,
    max_user_turns: int = 3,
    include_history: bool = True,
) -> str:
    if (
        not include_history
        or max_user_turns < 1
        or not conversation_history
    ):
        return question

    previous_user_turns = [
        turn.content.strip()
        for turn in conversation_history
        if turn.role == "user" and turn.content.strip()
    ][-max_user_turns:]

    if not previous_user_turns:
        return question

    return "\n".join(
        [
            "Previous user context:",
            *previous_user_turns,
            "Current question:",
            question,
        ]
    )


def build_conversation_context(
    conversation_history: list[ConversationTurn],
    *,
    max_turns: int = 6,
) -> str:
    recent_turns = conversation_history[-max_turns:]

    return "\n".join(
        f"{turn.role.upper()}: {turn.content.strip()}"
        for turn in recent_turns
        if turn.content.strip()
    )


def build_correction_prompt(
    *,
    question: str,
    context: str,
    answer: str,
    issues: list[GroundingIssue],
    conversation_context: str = "",
) -> str:
    issue_lines = "\n".join(
        f"- {issue.issue_type}: {issue.text}"
        for issue in issues
    )

    return f"""Your previous answer failed grounding validation.

GROUNDING ISSUES

{issue_lines}

Rewrite the answer so every factual claim is supported by the provided
sources. Remove or correct every listed grounding issue.

Do not mention the validation process in the rewritten answer.

CONVERSATION HISTORY

{conversation_context or "No previous conversation."}

The conversation history is context only and is not factual evidence.

SOURCES

{context}

QUESTION

{question}

PREVIOUS ANSWER

{answer}

CORRECTED ANSWER
"""


async def answer_question(
    question: str,
    *,
    retrieval_limit: int = 5,
    conversation_history: list[ConversationTurn] | None = None,
    agent_client: PiAgentClient | None = None,
) -> AssistantAnswer:
    question = question.strip()

    if not question:
        raise ValueError("question cannot be empty")

    history = conversation_history or []

    if has_unresolved_reference(
        question,
        history,
    ):
        return AssistantAnswer(
            answer=(
                "I’m missing the context for who or what "
                "you’re referring to. Please name the "
                "person, company, product, or topic."
            ),
            sources=[],
            grounding_retry_used=False,
            grounding_issues=[],
        )

    retrieval_query = build_retrieval_query(
        question,
        history,
    )

    chunks = await search_knowledge(
        retrieval_query,
        limit=retrieval_limit,
    )

    log_event(
        "retrieval_complete",
        chunks_found=len(chunks),
        query_length=len(retrieval_query),
    )
    if not chunks:
        return AssistantAnswer(
            answer=(
                "I couldn't find enough relevant information "
                "in the Lenny knowledge base to answer that."
            ),
            sources=[],
            grounding_retry_used=False,
            grounding_issues=[],
        )

    context = build_context(chunks)
    conversation_context = build_conversation_context(history)

    conversation_section = (
        conversation_context
        if conversation_context
        else "No previous conversation."
    )

    prompt = f"""Use the sources below to answer the user's question.

The conversation history is provided only to understand what the user means.
Do not treat conversation history as factual evidence. Factual claims must be
supported by SOURCES.

CONVERSATION HISTORY

{conversation_section}

SOURCES

{context}

CURRENT QUESTION

{question}

ANSWER
"""

    if agent_client is None:
        settings = get_settings()

        agent_environment: dict[str, str] = {}

        if (
            settings.agent_provider == "openai"
            and settings.openai_api_key
        ):
            agent_environment["OPENAI_API_KEY"] = (
                settings.openai_api_key
            )

        client = PiAgentClient(
            provider=settings.agent_provider,
            model=settings.agent_model,
            executable=settings.agent_executable,
            timeout=settings.agent_timeout_seconds,
            environment=agent_environment,
        )
    else:
        client = agent_client

    agent_response = await client.generate(
        prompt,
        system=SYSTEM_PROMPT,
    )
    answer = agent_response.text

    answer, issues = clean_grounding_issues(
        answer,
        context,
    )
    grounding_retry_used = False

    if issues:
        grounding_retry_used = True
        log_event("grounding_retry_used", issues=[i.issue_type for i in issues])

        correction_prompt = build_correction_prompt(
            question=question,
            context=context,
            answer=answer,
            issues=issues,
            conversation_context=conversation_context,
        )

        agent_response = await client.generate(
            correction_prompt,
            system=SYSTEM_PROMPT,
        )
        answer = agent_response.text

        answer, issues = clean_grounding_issues(
            answer,
            context,
        )

    if issues:
        log_event("grounding_failed", issues=[i.issue_type for i in issues])
        answer = (
            "I found relevant material in the Lenny knowledge base, "
            "but I couldn't produce an answer that passed grounding "
            "validation. Please try rephrasing the question."
        )

    sources = [
        AnswerSource(
            chunk_id=chunk.chunk_id,
            title=chunk.title,
            source_type=chunk.source_type,
            guest=chunk.guest,
            source_url=chunk.source_url,
            youtube_url=chunk.youtube_url,
            start_timestamp=chunk.start_timestamp,
            end_timestamp=chunk.end_timestamp,
        )
        for chunk in chunks
    ]

    return AssistantAnswer(
        answer=answer,
        sources=sources,
        grounding_retry_used=grounding_retry_used,
        grounding_issues=issues,
        model_provider=agent_response.provider,
        model_name=agent_response.model,
    )
