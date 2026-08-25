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


def test_html_grounding_ignores_aria_label_attributes():
    from app.assistant.grounding import validate_html_grounding

    context = "Duolingo prioritized retention metrics."

    html = """
    <html>
      <body>
        <button aria-label="Retention metric dashboard">
          Open
        </button>
        <p>Duolingo prioritized retention metrics. [1]</p>
      </body>
    </html>
    """

    issues = validate_html_grounding(html, context)

    assert not any(
        issue.issue_type == "unsupported_quote"
        and "Retention metric dashboard" in issue.text
        for issue in issues
    )


def test_html_grounding_catches_unsupported_visible_quote():
    from app.assistant.grounding import validate_html_grounding

    context = "Duolingo prioritized retention."

    html = """
    <html>
      <body>
        <p>The article said "How Duolingo Reignited User Growth" clearly.</p>
      </body>
    </html>
    """

    issues = validate_html_grounding(html, context)

    assert any(
        issue.issue_type == "unsupported_quote"
        for issue in issues
    )


def test_markdown_grounding_unchanged_for_quotes():
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
    assert issues == []


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


import uuid

import pytest
from fastapi import HTTPException

from app.api.routes.artifacts import create_ship30_artifact
from app.api.schemas.artifacts import Ship30ArtifactRequest
from app.db.models import Session


class FakeDb:
    def __init__(self):
        self.session = Session(
            id=uuid.uuid4(),
            title="Timeout test",
            user_metadata=None,
        )
        self.rolled_back = False

    async def get(self, model, object_id):
        if model is Session and object_id == self.session.id:
            return self.session

        return None

    async def scalar(self, statement):
        return 0

    async def rollback(self):
        self.rolled_back = True


@pytest.mark.asyncio
async def test_ship30_timeout_returns_structured_504(
    monkeypatch,
):
    from app.api.services.generation import run_with_provider_plan
    from app.assistant.provider import resolve_provider_plan

    db = FakeDb()

    class FakeSettings:
        cloud_fallback_enabled = False
        cloud_provider = "openai"
        cloud_model = "gpt-5.4-mini"
        openai_api_key = None
        agent_provider = "ollama"
        ollama_base_url = "http://localhost:11434"
        agent_model = "llama3.2:3b"
        artifact_model = "qwen3:4b-instruct"
        agent_executable = "pi"
        agent_timeout_seconds = 120.0
        artifact_timeout_seconds = 300.0

    monkeypatch.setattr(
        "app.api.routes.artifacts.get_settings",
        lambda: FakeSettings(),
    )

    async def fake_history(
        db_session,
        session_id,
        *,
        limit=6,
    ):
        return []

    async def fake_generate(
        topic,
        *,
        conversation_history=None,
        retrieval_limit=8,
        agent_client=None,
    ):
        raise TimeoutError(
            "Pi agent timed out after 300s"
        )

    async def fake_run_with_provider_plan(**kwargs):
        plan = resolve_provider_plan(
            "local",
            purpose="artifact",
            settings=FakeSettings(),
        )
        return await run_with_provider_plan(
            settings=FakeSettings(),
            plan=plan,
            timeout=1.0,
            local_call=kwargs["local_call"],
        )

    monkeypatch.setattr(
        "app.api.routes.artifacts.get_recent_history",
        fake_history,
    )

    monkeypatch.setattr(
        "app.api.routes.artifacts.generate_ship30_essay",
        fake_generate,
    )

    monkeypatch.setattr(
        "app.api.routes.artifacts.run_with_provider_plan",
        fake_run_with_provider_plan,
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_ship30_artifact(
            db.session.id,
            Ship30ArtifactRequest(
                topic="Write a Ship 30 essay",
                provider_mode="local",
            ),
            db,
        )

    error = exc_info.value

    assert error.status_code == 504
    assert error.detail["code"] == (
        "artifact_generation_timeout"
    )
    assert "timed out" in (
        error.detail["message"].lower()
    )
    assert db.rolled_back is True


@pytest.mark.asyncio
async def test_generic_artifact_timeout_uses_cloud_fallback(
    monkeypatch,
):
    from app.api.routes.artifacts import create_artifact
    from app.api.schemas.artifacts import ArtifactCreateRequest
    from app.assistant.skills.artifacts import GeneratedArtifact

    db = FakeDb()

    class FakeSettings:
        cloud_fallback_enabled = True
        cloud_provider = "openai"
        cloud_model = "gpt-5.4-mini"
        openai_api_key = "test-key"
        agent_provider = "ollama"
        ollama_base_url = "http://localhost:11434"
        agent_model = "llama3.2:3b"
        artifact_model = "qwen3:4b-instruct"
        agent_executable = "pi"
        agent_timeout_seconds = 120.0
        artifact_timeout_seconds = 300.0

    monkeypatch.setattr(
        "app.api.routes.artifacts.get_settings",
        lambda: FakeSettings(),
    )

    async def fake_history(
        db_session,
        session_id,
        *,
        limit=6,
    ):
        return []

    calls = []

    async def fake_generate(
        instruction,
        *,
        artifact_type,
        conversation_history=None,
        retrieval_limit=8,
        agent_client=None,
    ):
        calls.append(agent_client)

        return GeneratedArtifact(
            title="Retention Brief",
            artifact_type="html",
            content="""
<html>
<head><style>body { font-family: sans-serif; }</style></head>
<body>
<h1>Retention Brief</h1>
<p>Grounded artifact. [1]</p>
</body>
</html>
""".strip(),
            sources=[],
            grounding_issues=[],
            validation_issues=[],
            model_provider="openai",
            model_name="test-cloud-model",
        )

    monkeypatch.setattr(
        "app.api.routes.artifacts.get_recent_history",
        fake_history,
    )

    monkeypatch.setattr(
        "app.api.routes.artifacts.generate_artifact",
        fake_generate,
    )

    with pytest.raises(AttributeError):
        await create_artifact(
            db.session.id,
            ArtifactCreateRequest(
                artifact_type="html",
                instruction="Create a retention brief",
                provider_mode="auto",
            ),
            db,
        )

    assert len(calls) == 1
    assert calls[0] is not None


@pytest.mark.asyncio
async def test_auto_artifact_local_and_cloud_timeout_returns_504(
    monkeypatch,
):
    from app.api.services.generation import run_with_provider_plan
    from app.assistant.provider import ProviderPlan

    class FakeSettings:
        cloud_fallback_enabled = True
        cloud_provider = "openai"
        cloud_model = "test-cloud-model"
        openai_api_key = "test-key"
        agent_executable = "pi"
        agent_provider = "ollama"
        ollama_base_url = "http://localhost:11434"
        artifact_model = "test-local-model"

    settings = FakeSettings()

    plan = ProviderPlan(
        mode="auto",
        provider="ollama",
        model="test-local-model",
        allow_cloud_fallback=True,
        use_local_first=True,
    )

    calls = []

    class FakeClient:
        def __init__(self, name):
            self.name = name

    local_client = FakeClient("local")
    cloud_client = FakeClient("cloud")

    monkeypatch.setattr(
        "app.api.services.generation.create_agent_client_for_plan",
        lambda *args, **kwargs: local_client,
    )

    monkeypatch.setattr(
        "app.api.services.generation.create_cloud_agent_client",
        lambda *args, **kwargs: cloud_client,
    )

    monkeypatch.setattr(
        "app.api.services.generation.ensure_cloud_available",
        lambda settings: None,
    )

    async def fake_call(client):
        calls.append(client.name)
        raise TimeoutError(
            f"{client.name} timed out"
        )

    with pytest.raises(HTTPException) as exc_info:
        await run_with_provider_plan(
            settings=settings,
            plan=plan,
            timeout=180,
            local_call=fake_call,
        )

    error = exc_info.value

    assert calls == ["local", "cloud"]
    assert error.status_code == 504
    assert error.detail["code"] == (
        "cloud_fallback_timeout"
    )
    assert "cloud fallback timed out" in (
        error.detail["message"].lower()
    )


def test_html_grounding_cleanup_removes_unsupported_visible_quote():
    from app.assistant.grounding import (
        clean_html_grounding_issues,
    )

    html = '''
<html>
  <body>
    <p>The team focused on the "leaky bucket" problem.</p>
  </body>
</html>
'''

    context = (
        "The team focused on retention and reducing user churn."
    )

    cleaned, issues = clean_html_grounding_issues(
        html,
        context,
    )

    assert '"leaky bucket"' not in cleaned
    assert "leaky bucket" in cleaned
    assert issues == []


def test_html_grounding_cleanup_does_not_modify_attributes():
    from app.assistant.grounding import (
        clean_html_grounding_issues,
    )

    html = '''
<html>
  <body>
    <section aria-label="Retention strategy">
      <p>The "retention strategy" improved engagement.</p>
    </section>
  </body>
</html>
'''

    context = "The retention strategy improved engagement."

    cleaned, issues = clean_html_grounding_issues(
        html,
        context,
    )

    assert 'aria-label="Retention strategy"' in cleaned
    assert issues == []


def test_html_grounding_cleanup_preserves_security_relevant_markup():
    from app.assistant.grounding import (
        clean_html_grounding_issues,
    )
    from app.assistant.skills.artifacts import (
        validate_html_artifact,
    )

    html = '''
<html>
  <body>
    <script>alert("unsafe content here")</script>
    <p>Grounded content.</p>
  </body>
</html>
'''

    cleaned, _ = clean_html_grounding_issues(
        html,
        "Grounded content.",
    )

    issues = validate_html_artifact(cleaned)

    assert "<script>" in cleaned
    assert any(
        "forbidden_html_pattern" in issue
        for issue in issues
    )
