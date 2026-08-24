import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


FRONTMATTER_PATTERN = re.compile(
    r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z",
    re.DOTALL,
)

PODCAST_TURN_PATTERN = re.compile(
    r"^\*\*(?P<speaker>.+?)\*\*\s+\((?P<timestamp>\d{1,2}:\d{2}:\d{2})\):\s*$"
)


@dataclass(frozen=True)
class TranscriptTurn:
    speaker: str
    timestamp: str | None
    text: str


@dataclass(frozen=True)
class ParsedDocument:
    path: Path
    metadata: dict[str, Any]
    body: str
    turns: list[TranscriptTurn]


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    match = FRONTMATTER_PATTERN.match(content)

    if match is None:
        return {}, content.strip()

    metadata = yaml.safe_load(match.group(1)) or {}
    body = match.group(2).strip()

    return metadata, body


def parse_podcast_turns(body: str) -> list[TranscriptTurn]:
    turns: list[TranscriptTurn] = []

    current_speaker: str | None = None
    current_timestamp: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_speaker, current_timestamp, current_lines

        text = "\n".join(current_lines).strip()

        if current_speaker and text:
            turns.append(
                TranscriptTurn(
                    speaker=current_speaker,
                    timestamp=current_timestamp,
                    text=text,
                )
            )

        current_speaker = None
        current_timestamp = None
        current_lines = []

    for raw_line in body.splitlines():
        line = raw_line.strip()

        header_match = PODCAST_TURN_PATTERN.match(line)

        if header_match:
            flush()

            current_speaker = header_match.group("speaker").strip()
            current_timestamp = header_match.group("timestamp")
            continue

        if current_speaker and line:
            current_lines.append(line)

    flush()

    return turns


def parse_document(path: Path) -> ParsedDocument:
    content = path.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(content)

    document_type = str(metadata.get("type", "")).lower()
    turns = parse_podcast_turns(body) if document_type == "podcast" else []

    return ParsedDocument(
        path=path,
        metadata=metadata,
        body=body,
        turns=turns,
    )
