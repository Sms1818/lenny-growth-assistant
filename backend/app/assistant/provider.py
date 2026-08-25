from dataclasses import dataclass
from typing import Literal

from app.assistant.agent import OllamaAgentClient, PiAgentClient
from app.core.config import Settings


ProviderMode = Literal["auto", "local", "cloud"]
GenerationPurpose = Literal["chat", "artifact"]


class CloudProviderUnavailableError(Exception):
    """Raised when cloud generation is requested but not configured."""


@dataclass(frozen=True)
class ProviderPlan:
    mode: ProviderMode
    provider: str
    model: str
    allow_cloud_fallback: bool
    use_local_first: bool
    max_output_tokens: int | None = None


def normalize_provider_mode(
    mode: ProviderMode | None,
) -> ProviderMode:
    return mode or "auto"


def resolve_provider_plan(
    mode: ProviderMode | None,
    *,
    purpose: GenerationPurpose,
    settings: Settings,
) -> ProviderPlan:
    effective_mode = normalize_provider_mode(mode)

    if effective_mode == "cloud":
        model = settings.cloud_model
        return ProviderPlan(
            mode="cloud",
            provider=settings.cloud_provider,
            model=model,
            allow_cloud_fallback=False,
            use_local_first=False,
            max_output_tokens=400 if purpose == "chat" else None,
        )

    if effective_mode == "local":
        model = (
            settings.agent_model
            if purpose == "chat"
            else settings.artifact_model
        )
        return ProviderPlan(
            mode="local",
            provider=settings.agent_provider,
            model=model,
            allow_cloud_fallback=False,
            use_local_first=True,
            max_output_tokens=400 if purpose == "chat" else None,
        )

    if purpose == "artifact":
        return ProviderPlan(
            mode="auto",
            provider=settings.cloud_provider,
            model=settings.cloud_model,
            allow_cloud_fallback=False,
            use_local_first=False,
            max_output_tokens=None,
        )

    return ProviderPlan(
        mode="auto",
        provider=settings.agent_provider,
        model=settings.agent_model,
        allow_cloud_fallback=settings.cloud_fallback_enabled,
        use_local_first=True,
        max_output_tokens=400,
    )


def ensure_cloud_available(settings: Settings) -> None:
    if (
        settings.cloud_provider == "openai"
        and not settings.openai_api_key
    ):
        raise CloudProviderUnavailableError(
            "Cloud provider is not configured. "
            "Set OPENAI_API_KEY or choose Auto/Local mode."
        )


def build_agent_environment(
    provider: str,
    settings: Settings,
) -> dict[str, str]:
    environment: dict[str, str] = {}

    if provider == "openai" and settings.openai_api_key:
        environment["OPENAI_API_KEY"] = settings.openai_api_key

    return environment


def create_agent_client_for_plan(
    plan: ProviderPlan,
    *,
    settings: Settings,
    timeout: float,
) -> OllamaAgentClient | PiAgentClient:
    if plan.provider == "ollama":
        return OllamaAgentClient(
            model=plan.model,
            base_url=settings.ollama_base_url,
            timeout=timeout,
            max_output_tokens=plan.max_output_tokens,
        )

    return PiAgentClient(
        provider=plan.provider,
        model=plan.model,
        executable=settings.agent_executable,
        timeout=timeout,
        environment=build_agent_environment(
            plan.provider,
            settings,
        ),
    )


def create_cloud_agent_client(
    settings: Settings,
    *,
    timeout: float,
) -> PiAgentClient:
    return PiAgentClient(
        provider=settings.cloud_provider,
        model=settings.cloud_model,
        executable=settings.agent_executable,
        timeout=timeout,
        environment=build_agent_environment(
            settings.cloud_provider,
            settings,
        ),
    )
