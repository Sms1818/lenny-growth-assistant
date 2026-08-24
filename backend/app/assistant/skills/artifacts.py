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
)
from app.core.config import get_settings
from app.knowledge.retrieval import search_knowledge


DEFAULT_ARTIFACT_TITLE = "Untitled artifact"

SUPPORTED_ARTIFACT_TYPES = {
    "markdown",
    "html",
}

FORBIDDEN_HTML_PATTERNS = (
    r"<script\b",
    r"\bon\w+\s*=",
    r"javascript\s*:",
    r"<iframe\b",
    r"<object\b",
    r"<embed\b",
)


@dataclass(frozen=True)
class GeneratedArtifact:
    title: str
    artifact_type: str
    content: str
    sources: list[AnswerSource]
    grounding_issues: list[GroundingIssue]
    validation_issues: list[str]
    model_provider: str | None
    model_name: str | None


def extract_markdown_title(markdown: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()

        if stripped.startswith("# "):
            title = stripped[2:].strip()

            if title:
                return title[:255]

    return DEFAULT_ARTIFACT_TITLE


def extract_html_title(html: str) -> str:
    heading_match = re.search(
        r"<h1[^>]*>(.*?)</h1>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if heading_match:
        title = re.sub(
            r"<[^>]+>",
            "",
            heading_match.group(1),
        ).strip()

        if title:
            return title[:255]

    title_match = re.search(
        r"<title[^>]*>(.*?)</title>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if title_match:
        title = re.sub(
            r"<[^>]+>",
            "",
            title_match.group(1),
        ).strip()

        if title:
            return title[:255]

    return DEFAULT_ARTIFACT_TITLE


def validate_html_artifact(
    html: str,
) -> list[str]:
    issues: list[str] = []

    normalized = html.lower()

    if "<html" not in normalized:
        issues.append("missing_html_element")

    if "<body" not in normalized:
        issues.append("missing_body_element")

    for pattern in FORBIDDEN_HTML_PATTERNS:
        if re.search(
            pattern,
            html,
            flags=re.IGNORECASE,
        ):
            issues.append(
                f"forbidden_html_pattern:{pattern}"
            )

    return issues


def validate_markdown_artifact(
    markdown: str,
) -> list[str]:
    issues: list[str] = []

    if not markdown.strip():
        issues.append("empty_content")

    if not any(
        line.strip().startswith("# ")
        for line in markdown.splitlines()
    ):
        issues.append("missing_h1")

    return issues


def create_agent_client() -> PiAgentClient:
    settings = get_settings()

    environment: dict[str, str] = {}

    if (
        settings.agent_provider == "openai"
        and settings.openai_api_key
    ):
        environment["OPENAI_API_KEY"] = (
            settings.openai_api_key
        )

    return PiAgentClient(
        provider=settings.agent_provider,
        model=settings.agent_model,
        executable=settings.agent_executable,
        timeout=settings.agent_timeout_seconds,
        environment=environment,
    )


def build_artifact_system_prompt(
    artifact_type: str,
) -> str:
    if artifact_type == "markdown":
        output_rules = """
Output Markdown only.
Start with one H1 heading.
Use headings, paragraphs, lists, tables, and emphasis where useful.
Do not wrap the result in a Markdown code fence.
"""
    else:
        output_rules = """
Output one complete HTML document only.
Include <html>, <head>, <style>, and <body>.
Use embedded CSS only.
Do not use JavaScript.
Do not use script, iframe, object, or embed elements.
Do not use inline event handlers such as onclick.
Do not load external scripts, stylesheets, fonts, images, or other resources.
Do not wrap the result in a Markdown code fence.
"""

    return f"""You are the artifact-generation skill inside Lenny Growth
Assistant.

Create polished artifacts from Lenny's Podcast and Newsletter knowledge.

Grounding rules:
- Use only the supplied Lenny knowledge sources for factual claims.
- Conversation history may clarify intent but is not evidence.
- Do not use outside knowledge.
- Do not invent facts, statistics, quotes, examples, or personal experience.
- Never expand an acronym unless the supplied sources explicitly define it.
- Prefer paraphrasing.
- Cite factual claims with source numbers such as [1] and [2].
- If source material does not support the requested content, say so.

{output_rules}
"""


def build_artifact_prompt(
    *,
    instruction: str,
    artifact_type: str,
    source_context: str,
    conversation_context: str,
) -> str:
    return f"""Create a {artifact_type} artifact based on the request below.

CONVERSATION CONTEXT

{conversation_context or "No previous conversation."}

Use this only to understand the user's intent.

LENNY KNOWLEDGE SOURCES

{source_context}

USER REQUEST

{instruction}

ARTIFACT
"""


async def generate_artifact(
    instruction: str,
    *,
    artifact_type: str,
    conversation_history: list[ConversationTurn] | None = None,
    retrieval_limit: int = 8,
    agent_client: PiAgentClient | None = None,
) -> GeneratedArtifact:
    instruction = instruction.strip()
    artifact_type = artifact_type.strip().lower()

    if not instruction:
        raise ValueError("instruction cannot be empty")

    if artifact_type not in SUPPORTED_ARTIFACT_TYPES:
        raise ValueError(
            f"unsupported artifact type: {artifact_type}"
        )

    history = conversation_history or []

    retrieval_query = build_retrieval_query(
        instruction,
        history,
    )

    chunks = await search_knowledge(
        retrieval_query,
        limit=retrieval_limit,
    )

    if not chunks:
        return GeneratedArtifact(
            title=DEFAULT_ARTIFACT_TITLE,
            artifact_type=artifact_type,
            content="",
            sources=[],
            grounding_issues=[],
            validation_issues=[
                "insufficient_source_material"
            ],
            model_provider=None,
            model_name=None,
        )

    source_context = build_context(chunks)
    conversation_context = build_conversation_context(
        history
    )

    client = agent_client or create_agent_client()

    response = await client.generate(
        build_artifact_prompt(
            instruction=instruction,
            artifact_type=artifact_type,
            source_context=source_context,
            conversation_context=conversation_context,
        ),
        system=build_artifact_system_prompt(
            artifact_type
        ),
    )

    content, grounding_issues = clean_grounding_issues(
        response.text,
        source_context,
    )

    if artifact_type == "markdown":
        validation_issues = validate_markdown_artifact(
            content
        )
        title = extract_markdown_title(content)
    else:
        validation_issues = validate_html_artifact(
            content
        )
        title = extract_html_title(content)

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

    return GeneratedArtifact(
        title=title,
        artifact_type=artifact_type,
        content=content,
        sources=sources,
        grounding_issues=grounding_issues,
        validation_issues=validation_issues,
        model_provider=response.provider,
        model_name=response.model,
    )
