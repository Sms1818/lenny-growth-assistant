from app.assistant.skills.artifacts import (
    DEFAULT_ARTIFACT_TITLE,
    extract_markdown_title,
)


def test_extract_markdown_title_from_h1():
    markdown = """
# The Retention Lever That Changed Duolingo

Body.
"""

    assert (
        extract_markdown_title(markdown)
        == "The Retention Lever That Changed Duolingo"
    )


def test_extract_markdown_title_ignores_lower_headings():
    markdown = """
## Introduction

Body.
"""

    assert (
        extract_markdown_title(markdown)
        == DEFAULT_ARTIFACT_TITLE
    )


def test_extract_markdown_title_limits_database_length():
    markdown = "# " + ("A" * 400)

    assert len(
        extract_markdown_title(markdown)
    ) == 255


def test_grounding_cleanup_removes_unsupported_quote():
    from app.assistant.grounding import clean_grounding_issues

    context = "Duolingo prioritized retention."

    answer = (
        'The article "How Duolingo Reignited User Growth" '
        "describes the retention strategy."
    )

    cleaned, issues = clean_grounding_issues(
        answer,
        context,
    )

    assert '"How Duolingo Reignited User Growth"' not in cleaned
    assert "How Duolingo Reignited User Growth" in cleaned
    assert issues == []


def test_grounding_cleanup_removes_unsupported_acronym_expansion():
    from app.assistant.grounding import clean_grounding_issues

    context = "Duolingo focused on CURR."

    answer = "Duolingo focused on CURR (current user retention)."

    cleaned, issues = clean_grounding_issues(
        answer,
        context,
    )

    assert cleaned == "Duolingo focused on CURR."
    assert issues == []


def test_extract_html_title_prefers_h1():
    from app.assistant.skills.artifacts import (
        extract_html_title,
    )

    html = """
    <html>
      <head><title>Fallback</title></head>
      <body><h1>Retention Playbook</h1></body>
    </html>
    """

    assert (
        extract_html_title(html)
        == "Retention Playbook"
    )


def test_html_validation_accepts_safe_document():
    from app.assistant.skills.artifacts import (
        validate_html_artifact,
    )

    html = """
    <html>
      <head>
        <style>body { font-family: sans-serif; }</style>
      </head>
      <body>
        <h1>Retention</h1>
        <p>Grounded content.</p>
      </body>
    </html>
    """

    assert validate_html_artifact(html) == []


def test_html_validation_blocks_script():
    from app.assistant.skills.artifacts import (
        validate_html_artifact,
    )

    html = """
    <html>
      <body>
        <script>alert('xss')</script>
      </body>
    </html>
    """

    issues = validate_html_artifact(html)

    assert any(
        "forbidden_html_pattern" in issue
        for issue in issues
    )


def test_html_validation_blocks_event_handlers():
    from app.assistant.skills.artifacts import (
        validate_html_artifact,
    )

    html = """
    <html>
      <body>
        <button onclick="alert('xss')">
          Click
        </button>
      </body>
    </html>
    """

    issues = validate_html_artifact(html)

    assert any(
        "forbidden_html_pattern" in issue
        for issue in issues
    )


def test_markdown_validation_requires_h1():
    from app.assistant.skills.artifacts import (
        validate_markdown_artifact,
    )

    assert validate_markdown_artifact(
        "## Retention\n\nBody"
    ) == ["missing_h1"]
