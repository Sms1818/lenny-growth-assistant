import re
from dataclasses import dataclass

from app.knowledge.parser import ParsedDocument, TranscriptTurn


PODCAST_TARGET_CHARS = 1200
NEWSLETTER_TARGET_CHARS = 1500
MAX_UNIT_CHARS = 1800

MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\([^)]+\)")
MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\([^)]+\)")


@dataclass(frozen=True)
class DocumentChunk:
    content: str
    start_timestamp: str | None = None
    end_timestamp: str | None = None
    section_title: str | None = None


def clean_markdown(text: str) -> str:
    text = MARKDOWN_IMAGE_PATTERN.sub("", text)
    text = MARKDOWN_LINK_PATTERN.sub(r"\1", text)

    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def split_oversized_text(text: str, max_chars: int = MAX_UNIT_CHARS) -> list[str]:
    text = text.strip()

    if len(text) <= max_chars:
        return [text] if text else []

    sentences = re.split(r"(?<=[.!?])\s+", text)

    parts: list[str] = []
    current: list[str] = []
    current_length = 0

    for sentence in sentences:
        sentence = sentence.strip()

        if not sentence:
            continue

        if len(sentence) > max_chars:
            if current:
                parts.append(" ".join(current))
                current = []
                current_length = 0

            for start in range(0, len(sentence), max_chars):
                parts.append(sentence[start : start + max_chars].strip())

            continue

        added_length = len(sentence) + (1 if current else 0)

        if current and current_length + added_length > max_chars:
            parts.append(" ".join(current))
            current = []
            current_length = 0
            added_length = len(sentence)

        current.append(sentence)
        current_length += added_length

    if current:
        parts.append(" ".join(current))

    return [part for part in parts if part]


def format_turn(turn: TranscriptTurn, text: str | None = None) -> str:
    timestamp = f" ({turn.timestamp})" if turn.timestamp else ""
    content = turn.text if text is None else text
    return f"{turn.speaker}{timestamp}:\n{content}"


def chunk_podcast(
    document: ParsedDocument,
    target_chars: int = PODCAST_TARGET_CHARS,
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []

    current_parts: list[str] = []
    current_start_timestamp: str | None = None
    current_end_timestamp: str | None = None
    current_length = 0

    def flush() -> None:
        nonlocal current_parts
        nonlocal current_start_timestamp
        nonlocal current_end_timestamp
        nonlocal current_length

        if not current_parts:
            return

        chunks.append(
            DocumentChunk(
                content="\n\n".join(current_parts),
                start_timestamp=current_start_timestamp,
                end_timestamp=current_end_timestamp,
            )
        )

        current_parts = []
        current_start_timestamp = None
        current_end_timestamp = None
        current_length = 0

    for turn in document.turns:
        cleaned_text = clean_markdown(turn.text)

        for text_part in split_oversized_text(cleaned_text):
            formatted = format_turn(turn, text_part)
            added_length = len(formatted) + (2 if current_parts else 0)

            if current_parts and current_length + added_length > target_chars:
                flush()
                added_length = len(formatted)

            if not current_parts:
                current_start_timestamp = turn.timestamp

            current_parts.append(formatted)
            current_end_timestamp = turn.timestamp
            current_length += added_length

    flush()

    return chunks


def chunk_newsletter(
    document: ParsedDocument,
    target_chars: int = NEWSLETTER_TARGET_CHARS,
) -> list[DocumentChunk]:
    cleaned_body = clean_markdown(document.body)

    paragraphs = [
        paragraph.strip()
        for paragraph in cleaned_body.split("\n\n")
        if paragraph.strip()
    ]

    chunks: list[DocumentChunk] = []
    current_parts: list[str] = []
    current_length = 0

    def flush() -> None:
        nonlocal current_parts, current_length

        if not current_parts:
            return

        chunks.append(
            DocumentChunk(
                content="\n\n".join(current_parts),
            )
        )

        current_parts = []
        current_length = 0

    for paragraph in paragraphs:
        for part in split_oversized_text(paragraph):
            added_length = len(part) + (2 if current_parts else 0)

            if current_parts and current_length + added_length > target_chars:
                flush()
                added_length = len(part)

            current_parts.append(part)
            current_length += added_length

    flush()

    return chunks


def chunk_document(document: ParsedDocument) -> list[DocumentChunk]:
    document_type = str(document.metadata.get("type", "")).lower()

    if document_type == "podcast":
        return chunk_podcast(document)

    if document_type == "newsletter":
        return chunk_newsletter(document)

    raise ValueError(f"Unsupported document type: {document_type or 'unknown'}")
