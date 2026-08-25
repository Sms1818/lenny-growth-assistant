import re
from dataclasses import dataclass
from html.parser import HTMLParser


ACRONYM_THEN_EXPANSION_PATTERN = re.compile(
    r"\b(?P<acronym>[A-Z][A-Z0-9]{1,})\s*"
    r"\((?P<expansion>[^)]+)\)"
)

EXPANSION_THEN_ACRONYM_PATTERN = re.compile(
    r"(?P<prefix>[^.!?\n]{1,160}?)"
    r"\((?P<acronym>[A-Z][A-Z0-9]{1,})\)"
)

QUOTED_TEXT_PATTERN = re.compile(
    r'"(?P<straight>[^"\n]{12,})"'
    r'|“(?P<curly>[^”\n]{12,})”'
)


@dataclass(frozen=True)
class GroundingIssue:
    issue_type: str
    text: str


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def acronym_expansion_is_supported(
    acronym: str,
    expansion: str,
    context: str,
) -> bool:
    normalized_context = normalize(context)

    acronym_first = normalize(
        f"{acronym} ({expansion})"
    )
    expansion_first = normalize(
        f"{expansion} ({acronym})"
    )

    if acronym_first in normalized_context:
        return True

    if expansion_first in normalized_context:
        return True

    return False


def find_supported_reverse_expansion(
    *,
    acronym: str,
    prefix: str,
    context: str,
) -> str | None:
    words = re.findall(
        r"[A-Za-z0-9][A-Za-z0-9-]*",
        prefix,
    )

    # Try suffixes nearest to the acronym. An actual expansion is normally
    # a short noun phrase such as "resurrected user retention rate".
    max_words = min(8, len(words))

    for size in range(max_words, 1, -1):
        expansion = " ".join(words[-size:])

        if acronym_expansion_is_supported(
            acronym,
            expansion,
            context,
        ):
            return expansion

    return None


def candidate_reverse_expansion(prefix: str) -> str:
    words = re.findall(
        r"[A-Za-z0-9][A-Za-z0-9-]*",
        prefix,
    )

    # For unsupported definitions, keep a compact phrase in diagnostics
    # instead of reporting the whole preceding sentence.
    return " ".join(words[-3:])


def validate_grounding(
    answer: str,
    context: str,
) -> list[GroundingIssue]:
    issues: list[GroundingIssue] = []
    normalized_context = normalize(context)

    acronym_first_spans: list[tuple[int, int]] = []

    for match in ACRONYM_THEN_EXPANSION_PATTERN.finditer(answer):
        acronym_first_spans.append(match.span())

        acronym = match.group("acronym").strip()
        expansion = match.group("expansion").strip()

        if not acronym_expansion_is_supported(
            acronym,
            expansion,
            context,
        ):
            issues.append(
                GroundingIssue(
                    issue_type="unsupported_acronym_expansion",
                    text=match.group(0),
                )
            )

    for match in EXPANSION_THEN_ACRONYM_PATTERN.finditer(answer):
        # Do not process text already recognized as ACRONYM (expansion).
        if any(
            start <= match.start() < end
            for start, end in acronym_first_spans
        ):
            continue

        acronym = match.group("acronym").strip()
        prefix = match.group("prefix").strip()

        supported_expansion = find_supported_reverse_expansion(
            acronym=acronym,
            prefix=prefix,
            context=context,
        )

        if supported_expansion is not None:
            continue

        expansion = candidate_reverse_expansion(prefix)

        if expansion:
            issues.append(
                GroundingIssue(
                    issue_type="unsupported_acronym_expansion",
                    text=f"{expansion} ({acronym})",
                )
            )

    for match in QUOTED_TEXT_PATTERN.finditer(answer):
        quote = (
            match.group("straight")
            or match.group("curly")
        ).strip()

        if normalize(quote) not in normalized_context:
            issues.append(
                GroundingIssue(
                    issue_type="unsupported_quote",
                    text=quote,
                )
            )

    return issues


def remove_unsupported_acronym_expansions(
    answer: str,
    issues: list[GroundingIssue],
) -> str:
    cleaned = answer

    for issue in issues:
        if issue.issue_type != "unsupported_acronym_expansion":
            continue

        text = issue.text

        acronym_match = re.search(
            r"\(([A-Z][A-Z0-9]{1,})\)$",
            text,
        )

        if acronym_match:
            acronym = acronym_match.group(1)
            cleaned = cleaned.replace(text, acronym)
            continue

        acronym_match = re.match(
            r"([A-Z][A-Z0-9]{1,})\s*\(",
            text,
        )

        if acronym_match:
            acronym = acronym_match.group(1)
            cleaned = cleaned.replace(text, acronym)

    return cleaned


def remove_unsupported_quotes(
    answer: str,
    issues: list[GroundingIssue],
) -> str:
    cleaned = answer

    for issue in issues:
        if issue.issue_type != "unsupported_quote":
            continue

        quote = issue.text

        cleaned = cleaned.replace(
            f'"{quote}"',
            quote,
        )
        cleaned = cleaned.replace(
            f'“{quote}”',
            quote,
        )

    return cleaned


class _VisibleTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return

        text = data.strip()

        if text:
            self._parts.append(text)

    def get_text(self) -> str:
        return "\n".join(self._parts)


def extract_visible_text_from_html(html: str) -> str:
    parser = _VisibleTextExtractor()
    parser.feed(html)
    parser.close()
    return parser.get_text()


def validate_html_grounding(
    html: str,
    context: str,
) -> list[GroundingIssue]:
    visible_text = extract_visible_text_from_html(html)

    if not visible_text.strip():
        return []

    return validate_grounding(
        visible_text,
        context,
    )


def clean_grounding_issues(
    answer: str,
    context: str,
    *,
    max_passes: int = 3,
) -> tuple[str, list[GroundingIssue]]:
    cleaned = answer

    for _ in range(max_passes):
        issues = validate_grounding(
            cleaned,
            context,
        )

        if not issues:
            return cleaned, []

        updated = remove_unsupported_acronym_expansions(
            cleaned,
            issues,
        )

        updated = remove_unsupported_quotes(
            updated,
            issues,
        )

        if updated == cleaned:
            return cleaned, issues

        cleaned = updated

    return (
        cleaned,
        validate_grounding(
            cleaned,
            context,
        ),
    )


class _HtmlGroundingCleaner(HTMLParser):
    def __init__(
        self,
        issues: list[GroundingIssue],
    ) -> None:
        super().__init__(convert_charrefs=False)
        self._parts: list[str] = []
        self._issues = issues
        self._skip_depth = 0

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        raw = self.get_starttag_text()
        if raw:
            self._parts.append(raw)

        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        raw = self.get_starttag_text()
        if raw:
            self._parts.append(raw)

    def handle_endtag(self, tag: str) -> None:
        self._parts.append(f"</{tag}>")

        if (
            tag in {"script", "style", "noscript"}
            and self._skip_depth
        ):
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            self._parts.append(data)
            return

        cleaned = remove_unsupported_acronym_expansions(
            data,
            self._issues,
        )
        cleaned = remove_unsupported_quotes(
            cleaned,
            self._issues,
        )
        self._parts.append(cleaned)

    def handle_entityref(self, name: str) -> None:
        self._parts.append(f"&{name};")

    def handle_charref(self, name: str) -> None:
        self._parts.append(f"&#{name};")

    def handle_comment(self, data: str) -> None:
        self._parts.append(f"<!--{data}-->")

    def handle_decl(self, decl: str) -> None:
        self._parts.append(f"<!{decl}>")

    def handle_pi(self, data: str) -> None:
        self._parts.append(f"<?{data}>")

    def get_html(self) -> str:
        return "".join(self._parts)


def clean_html_grounding_issues(
    html: str,
    context: str,
    *,
    max_passes: int = 3,
) -> tuple[str, list[GroundingIssue]]:
    cleaned = html

    for _ in range(max_passes):
        issues = validate_html_grounding(
            cleaned,
            context,
        )

        if not issues:
            return cleaned, []

        parser = _HtmlGroundingCleaner(issues)
        parser.feed(cleaned)
        parser.close()

        updated = parser.get_html()

        if updated == cleaned:
            return cleaned, issues

        cleaned = updated

    return (
        cleaned,
        validate_html_grounding(
            cleaned,
            context,
        ),
    )
