import pytest
from fastapi import HTTPException

from app.api.services.generation import (
    resolve_artifact_provider_plan,
    run_with_provider_plan,
)
from app.assistant.provider import (
    CloudProviderUnavailableError,
    ensure_cloud_available,
    resolve_provider_plan,
)


class FakeSettings:
    agent_provider = "ollama"
    ollama_base_url = "http://localhost:11434"
    agent_model = "llama3.2:3b"
    artifact_model = "qwen3:4b-instruct"
    agent_executable = "pi"
    agent_timeout_seconds = 120.0
    artifact_timeout_seconds = 300.0
    cloud_provider = "openai"
    cloud_model = "gpt-5.4-mini"
    cloud_fallback_enabled = True
    openai_api_key = "test-key"


def test_auto_artifact_plan_goes_to_cloud_directly():
    plan = resolve_artifact_provider_plan(
        "auto",
        FakeSettings(),
    )

    assert plan.mode == "auto"
    assert plan.use_local_first is False
    assert plan.allow_cloud_fallback is False
    assert plan.provider == "openai"
    assert plan.model == "gpt-5.4-mini"


def test_local_artifact_plan_disables_cloud_fallback():
    plan = resolve_artifact_provider_plan(
        "local",
        FakeSettings(),
    )

    assert plan.mode == "local"
    assert plan.allow_cloud_fallback is False


def test_cloud_chat_plan_uses_cloud_model():
    plan = resolve_provider_plan(
        "cloud",
        purpose="chat",
        settings=FakeSettings(),
    )

    assert plan.provider == "openai"
    assert plan.model == "gpt-5.4-mini"
    assert plan.use_local_first is False


def test_cloud_unavailable_raises():
    settings = FakeSettings()
    settings.openai_api_key = None

    with pytest.raises(CloudProviderUnavailableError):
        ensure_cloud_available(settings)


@pytest.mark.asyncio
async def test_local_timeout_does_not_cloud_fallback():
    plan = resolve_artifact_provider_plan(
        "local",
        FakeSettings(),
    )

    async def failing_call(agent_client):
        raise TimeoutError("timed out")

    with pytest.raises(HTTPException) as exc_info:
        await run_with_provider_plan(
            settings=FakeSettings(),
            plan=plan,
            timeout=1.0,
            local_call=failing_call,
        )

    assert exc_info.value.status_code == 504
    assert exc_info.value.detail["code"] == (
        "artifact_generation_timeout"
    )


@pytest.mark.asyncio
async def test_auto_timeout_attempts_cloud_fallback():
    plan = resolve_provider_plan(
        "auto",
        purpose="chat",
        settings=FakeSettings(),
    )
    calls = []

    async def fake_call(agent_client):
        calls.append(agent_client)

        if len(calls) == 1:
            raise TimeoutError("timed out")

        return "cloud-result"

    result = await run_with_provider_plan(
        settings=FakeSettings(),
        plan=plan,
        timeout=1.0,
        local_call=fake_call,
    )

    assert result == "cloud-result"
    assert len(calls) == 2
    assert calls[0] is not None
    assert calls[1] is not None


@pytest.mark.asyncio
async def test_cloud_mode_calls_cloud_directly():
    plan = resolve_artifact_provider_plan(
        "cloud",
        FakeSettings(),
    )
    calls = []

    async def fake_call(agent_client):
        calls.append(agent_client)
        return "cloud-only"

    result = await run_with_provider_plan(
        settings=FakeSettings(),
        plan=plan,
        timeout=1.0,
        local_call=fake_call,
    )

    assert result == "cloud-only"
    assert len(calls) == 1
