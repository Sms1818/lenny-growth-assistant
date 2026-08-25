from dataclasses import dataclass
import re

from app.assistant.agent import PiAgentClient
from app.assistant.grounding import (
    GroundingIssue,
    clean_grounding_issues,
)
from app.assistant.service import (
    AnswerSource,
    ConversationTurn,
    build_context,
    build_conversation_context,
    build_retrieval_query,
    needs_conversation_context,
)
from app.core.config import get_settings
from app.knowledge.retrieval import search_knowledge


SHIP30_SYSTEM_PROMPT = """You are the Ship 30 writing skill inside
Lenny Growth Assistant.

Your job is to turn grounded material from Lenny's Podcast and Newsletter
into a polished long-form essay.

Writing principles:
- Be specific about the reader, topic, and promised outcome.
- Prefer clear headlines over clever headlines.
- Open with a strong hook that quickly establishes why the reader should care.
- Create a clear narrative progression rather than a collection of notes.
- Make the essay easy to scan with useful headings and short paragraphs.
- Use bullets only when they improve clarity.
- Use bold emphasis selectively, not excessively.
- Vary paragraph length and rhythm.
- Deliver on the promise made by the headline and hook.
- End with a concrete and useful takeaway.
- Write approximately 1,250 words. A practical target is 1,100-1,350 words.

Grounding rules:
- Use only the supplied Lenny knowledge sources for factual claims.
- Conversation history may clarify the requested angle, but it is not evidence.
- Do not use outside knowledge.
- Do not invent examples, statistics, quotes, anecdotes, or personal experience.
- Do not pretend to have personal experience or authority.
- Curate and synthesize the source experts instead.
- Never expand an acronym unless the supplied sources explicitly define it.
- Prefer paraphrasing over direct quotation.
- Never place text in quotation marks unless those exact words occur in a source.
- Cite factual claims with source numbers such as [1] or [2].
- Do not cite a source that does not support the claim.
- If the supplied material is insufficient for the requested essay, say so.

Output rules:
- Return Markdown only.
- Start with a single H1 headline.
- Do not include meta-commentary about prompts, grounding, or the writing process.
"""


@dataclass(frozen=True)
class Ship30Result:
    markdown: str
    sources: list[AnswerSource]
    grounding_retry_used: bool
    grounding_issues: list[GroundingIssue]
    model_provider: str | None
    model_name: str | None


def build_ship30_prompt(
    *,
    topic: str,
    source_context: str,
    conversation_context: str,
) -> str:
    return f"""Create a Ship 30 for 30-style essay for the user's request.

CONVERSATION CONTEXT

{conversation_context or "No previous conversation."}

Use conversation context only to understand the requested angle.

LENNY KNOWLEDGE SOURCES

{source_context}

USER REQUEST

{topic}

ESSAY REQUIREMENTS

- Approximately 1,250 words.
- One strong, specific headline.
- A compelling opening hook.
- Clear narrative progression.
- Skimmable Markdown with meaningful headings.
- Short, varied paragraphs.
- Bullets where useful.
- Selective bold emphasis.
- A concrete closing takeaway.
- Inline source citations such as [1] and [2].
- Every factual claim must be supported by the supplied sources.
- Do not fabricate personal stories, examples, quotes, or expertise.

MARKDOWN ESSAY
"""


def build_ship30_correction_prompt(
    *,
    topic: str,
    source_context: str,
    conversation_context: str,
    markdown: str,
    issues: list[GroundingIssue],
) -> str:
    issue_lines = "\n".join(
        f"- {issue.issue_type}: {issue.text}"
        for issue in issues
    )

    return f"""Rewrite the essay so it remains useful and polished while
correcting every grounding problem below.

GROUNDING ISSUES

{issue_lines}

CONVERSATION CONTEXT

{conversation_context or "No previous conversation."}

Conversation context is not factual evidence.

LENNY KNOWLEDGE SOURCES

{source_context}

USER REQUEST

{topic}

PREVIOUS ESSAY

{markdown}

Return only the corrected Markdown essay.
"""


def create_agent_client() -> PiAgentClient:
    settings = get_settings()

    environment: dict[str, str] = {}

    if (
        settings.agent_provider == "openai"
        and settings.openai_api_key
    ):
        environment["OPENAI_API_KEY"] = settings.openai_api_key

    return PiAgentClient(
        provider=settings.agent_provider,
        model=settings.artifact_model,
        executable=settings.agent_executable,
        timeout=settings.artifact_timeout_seconds,
        environment=environment,
    )


def create_cloud_agent_client() -> PiAgentClient:
    settings = get_settings()

    environment: dict[str, str] = {}

    if (
        settings.cloud_provider == "openai"
        and settings.openai_api_key
    ):
        environment["OPENAI_API_KEY"] = (
            settings.openai_api_key
        )

    return PiAgentClient(
        provider=settings.cloud_provider,
        model=settings.cloud_model,
        executable=settings.agent_executable,
        timeout=settings.agent_timeout_seconds,
        environment=environment,
    )


async def generate_ship30_essay(
    topic: str,
    *,
    conversation_history: list[ConversationTurn] | None = None,
    retrieval_limit: int = 8,
    agent_client: PiAgentClient | None = None,
) -> Ship30Result:
    topic = topic.strip()

    if not topic:
        raise ValueError("topic cannot be empty")

    history = conversation_history or []

    retrieval_query = build_retrieval_query(
        topic,
        history,
        include_history=needs_conversation_context(
            topic
        ),
    )

    chunks = await search_knowledge(
        retrieval_query,
        limit=retrieval_limit,
    )

    if not chunks:
        return Ship30Result(
            markdown=(
                "I couldn't find enough relevant material in the "
                "Lenny knowledge base to create this essay."
            ),
            sources=[],
            grounding_retry_used=False,
            grounding_issues=[],
            model_provider=None,
            model_name=None,
        )

    source_context = build_context(chunks)
    conversation_context = build_conversation_context(history)

    client = agent_client or create_agent_client()

    prompt = build_ship30_prompt(
        topic=topic,
        source_context=source_context,
        conversation_context=conversation_context,
    )

    response = await client.generate(
        prompt,
        system=SHIP30_SYSTEM_PROMPT,
    )

    markdown, issues = clean_grounding_issues(
        response.text,
        source_context,
    )

    grounding_retry_used = False

    if issues:
        markdown = (
            "I found relevant Lenny material, but I couldn't create "
            "an essay that passed grounding validation."
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

    return Ship30Result(
        markdown=markdown,
        sources=sources,
        grounding_retry_used=grounding_retry_used,
        grounding_issues=issues,
        model_provider=response.provider,
        model_name=response.model,
    )


MIN_SHIP30_WORDS = 1000
MAX_SHIP30_WORDS = 1500


def validate_ship30_structure(
    markdown: str,
) -> list[str]:
    issues: list[str] = []

    words = markdown.split()
    word_count = len(words)

    if word_count < MIN_SHIP30_WORDS:
        issues.append(
            f"essay_too_short:{word_count}"
        )

    if word_count > MAX_SHIP30_WORDS:
        issues.append(
            f"essay_too_long:{word_count}"
        )

    first_content_line = next(
        (
            line.strip()
            for line in markdown.splitlines()
            if line.strip()
        ),
        "",
    )

    if not first_content_line.startswith("# "):
        issues.append("missing_h1")

    if not re.search(r"\[\d+\]", markdown):
        issues.append("missing_source_citations")

    return issues
