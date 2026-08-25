from collections.abc import Awaitable, Callable
from typing import TypeVar

from fastapi import HTTPException, status

from app.api.schemas.sessions import ProviderMode
from app.assistant.provider import (
    CloudProviderUnavailableError,
    ProviderPlan,
    create_agent_client_for_plan,
    create_cloud_agent_client,
    ensure_cloud_available,
    resolve_provider_plan,
)
from app.core.config import Settings


T = TypeVar("T")


from app.core.logger import log_event

async def run_with_provider_plan(
    *,
    settings: Settings,
    plan: ProviderPlan,
    timeout: float,
    local_call: Callable[[object | None], Awaitable[T]],
) -> T:
    log_event("generation_started", plan=vars(plan), timeout=timeout)

    if not plan.use_local_first:
        try:
            ensure_cloud_available(settings)
        except CloudProviderUnavailableError as exc:
            log_event(
                "cloud_provider_unavailable",
                error_type=exc.__class__.__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "cloud_provider_unavailable",
                    "message": str(exc),
                },
            ) from exc

        cloud_client = create_cloud_agent_client(
            settings,
            timeout=timeout,
        )

        try:
            result = await local_call(cloud_client)
            log_event("generation_success", provider="cloud")
            return result
        except TimeoutError as cloud_exc:
            log_event(
                "cloud_generation_timeout",
                error_type=cloud_exc.__class__.__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={
                    "code": "cloud_fallback_timeout",
                    "message": (
                        "Cloud generation timed out before completion."
                    ),
                },
            ) from cloud_exc
        except RuntimeError as cloud_exc:
            log_event(
                "cloud_generation_failed",
                error_type=cloud_exc.__class__.__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "code": "cloud_generation_failed",
                    "message": "Cloud generation failed.",
                },
            ) from cloud_exc

    local_client = create_agent_client_for_plan(
        plan,
        settings=settings,
        timeout=timeout,
    )

    try:
        result = await local_call(local_client)
        log_event("generation_success", provider="local")
        return result
    except (TimeoutError, RuntimeError) as exc:
        is_timeout = isinstance(exc, TimeoutError)
        log_event(
            "local_generation_failed",
            is_timeout=is_timeout,
            error_type=exc.__class__.__name__,
        )

        if not plan.allow_cloud_fallback:
            code = (
                "artifact_generation_timeout"
                if is_timeout else "artifact_generation_failed"
            )
            msg = (
                "Generation timed out"
                if is_timeout else "Generation failed"
            )
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT if is_timeout else status.HTTP_502_BAD_GATEWAY,
                detail={
                    "code": code,
                    "message": f"{msg} before completion. Local mode does not fall back to cloud.",
                },
            ) from exc

        try:
            ensure_cloud_available(settings)
        except CloudProviderUnavailableError as cloud_exc:
            log_event(
                "cloud_fallback_unavailable",
                error_type=cloud_exc.__class__.__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "cloud_fallback_unavailable",
                    "message": (
                        "Local generation failed, but the "
                        "configured cloud fallback is unavailable."
                    ),
                },
            ) from cloud_exc

        log_event("falling_back_to_cloud")
        cloud_client = create_cloud_agent_client(
            settings,
            timeout=timeout,
        )

        try:
            result = await local_call(cloud_client)
            log_event("generation_success", provider="cloud_fallback")
            return result
        except TimeoutError as cloud_exc:
            log_event(
                "cloud_fallback_timeout",
                error_type=cloud_exc.__class__.__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail={
                    "code": "cloud_fallback_timeout",
                    "message": (
                        "Local generation failed and the "
                        "cloud fallback timed out before completion."
                    ),
                },
            ) from cloud_exc
        except RuntimeError as cloud_exc:
            log_event(
                "cloud_fallback_failed",
                error_type=cloud_exc.__class__.__name__,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "code": "cloud_fallback_failed",
                    "message": (
                        "Local generation failed and the "
                        "cloud fallback also failed."
                    ),
                },
            ) from cloud_exc


def resolve_artifact_provider_plan(
    provider_mode: ProviderMode | None,
    settings: Settings,
) -> ProviderPlan:
    return resolve_provider_plan(
        provider_mode,
        purpose="artifact",
        settings=settings,
    )
