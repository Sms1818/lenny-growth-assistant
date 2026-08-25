import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.messages import (
    MessageCreateRequest,
    MessageWithSourcesResponse,
    SendMessageResponse,
    SessionMessagesResponse,
    SourceResponse,
)
from app.api.services.sources import resolve_sources_for_chunk_ids
from app.assistant.provider import (
    CloudProviderUnavailableError,
    create_agent_client_for_plan,
    create_cloud_agent_client,
    normalize_provider_mode,
    resolve_provider_plan,
)
from app.assistant.service import (
    ConversationTurn,
    answer_question,
)
from app.core.config import get_settings
from app.db.dependencies import get_db_session
from app.db.models import Artifact, Message, Session


router = APIRouter(
    prefix="/sessions",
    tags=["messages"],
)


def build_session_title(
    content: str,
    *,
    max_length: int = 60,
) -> str:
    title = " ".join(content.split()).strip()

    prefixes = (
        "Create a Ship 30 for 30 essay:",
        "Create a Ship 30 essay:",
        "Create html artifact:",
        "Create HTML artifact:",
        "Create markdown artifact:",
        "Create Markdown artifact:",
    )

    for prefix in prefixes:
        if title.lower().startswith(prefix.lower()):
            title = title[len(prefix):].strip()
            break

    if not title:
        return "New conversation"

    if len(title) <= max_length:
        return title

    return title[: max_length - 1].rstrip() + "…"


async def touch_session(
    db: AsyncSession,
    session: Session,
) -> None:
    session.updated_at = datetime.now(timezone.utc)
    db.add(session)


async def get_recent_history(
    db: AsyncSession,
    session_id: uuid.UUID,
    *,
    limit: int = 6,
) -> list[ConversationTurn]:
    statement = (
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.sequence_number.desc())
        .limit(limit)
    )

    messages = list(
        (await db.scalars(statement)).all()
    )
    messages.reverse()

    return [
        ConversationTurn(
            role=message.role,
            content=message.content,
        )
        for message in messages
        if message.role in {"user", "assistant"}
    ]


@router.get(
    "/{session_id}/messages",
    response_model=SessionMessagesResponse,
)
async def list_session_messages(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> SessionMessagesResponse:
    session = await db.get(Session, session_id)

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    statement = (
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.sequence_number.asc())
    )

    messages = list(
        (await db.scalars(statement)).all()
    )

    artifact_by_message: dict[uuid.UUID, uuid.UUID] = {}

    if messages:
        assistant_ids = [
            message.id
            for message in messages
            if message.role == "assistant"
        ]

        if assistant_ids:
            artifact_statement = select(Artifact).where(
                Artifact.message_id.in_(assistant_ids)
            )
            artifacts = (
                await db.scalars(artifact_statement)
            ).all()

            for artifact in artifacts:
                artifact_by_message[artifact.message_id] = (
                    artifact.id
                )

    response_messages: list[MessageWithSourcesResponse] = []

    for message in messages:
        sources: list[SourceResponse] = []

        if message.role == "assistant":
            sources = await resolve_sources_for_chunk_ids(
                db,
                message.source_chunk_ids,
            )

        response_messages.append(
            MessageWithSourcesResponse(
                id=message.id,
                session_id=message.session_id,
                sequence_number=message.sequence_number,
                role=message.role,
                content=message.content,
                model_provider=message.model_provider,
                model_name=message.model_name,
                source_chunk_ids=message.source_chunk_ids,
                created_at=message.created_at,
                sources=sources,
                artifact_id=artifact_by_message.get(message.id),
            )
        )

    return SessionMessagesResponse(
        messages=response_messages,
    )


@router.post(
    "/{session_id}/messages",
    response_model=SendMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message(
    session_id: uuid.UUID,
    request: MessageCreateRequest,
    db: AsyncSession = Depends(get_db_session),
) -> SendMessageResponse:
    session = await db.get(Session, session_id)

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    settings = get_settings()
    provider_mode = normalize_provider_mode(
        request.provider_mode,
    )
    plan = resolve_provider_plan(
        provider_mode,
        purpose="chat",
        settings=settings,
    )

    history = await get_recent_history(
        db,
        session_id,
    )

    current_sequence = await db.scalar(
        select(
            func.coalesce(
                func.max(Message.sequence_number),
                0,
            )
        ).where(Message.session_id == session_id)
    )

    try:
        if plan.use_local_first:
            agent_client = create_agent_client_for_plan(
                plan,
                settings=settings,
                timeout=settings.agent_timeout_seconds,
            )
        else:
            try:
                from app.assistant.provider import (
                    ensure_cloud_available,
                )

                ensure_cloud_available(settings)
            except CloudProviderUnavailableError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail={
                        "code": "cloud_provider_unavailable",
                        "message": str(exc),
                    },
                ) from exc

            agent_client = create_cloud_agent_client(
                settings,
                timeout=settings.agent_timeout_seconds,
            )

        result = await answer_question(
            request.content,
            conversation_history=history,
            agent_client=agent_client,
        )

        user_message = Message(
            session_id=session_id,
            sequence_number=current_sequence + 1,
            role="user",
            content=request.content,
        )

        assistant_message = Message(
            session_id=session_id,
            sequence_number=current_sequence + 2,
            role="assistant",
            content=result.answer,
            model_provider=result.model_provider,
            model_name=result.model_name,
            source_chunk_ids=[
                str(source.chunk_id)
                for source in result.sources
            ],
        )

        db.add_all([
            user_message,
            assistant_message,
        ])

        if (
            current_sequence == 0
            and (
                session.title is None
                or session.title.strip().lower()
                == "new conversation"
            )
        ):
            session.title = build_session_title(
                request.content
            )

        await touch_session(db, session)
        await db.commit()

        await db.refresh(user_message)
        await db.refresh(assistant_message)

    except Exception:
        await db.rollback()
        raise

    return SendMessageResponse(
        user_message=user_message,
        assistant_message=assistant_message,
        sources=[
            SourceResponse(
                chunk_id=source.chunk_id,
                title=source.title,
                source_type=source.source_type,
                guest=source.guest,
                source_url=source.source_url,
                youtube_url=source.youtube_url,
                start_timestamp=source.start_timestamp,
                end_timestamp=source.end_timestamp,
            )
            for source in result.sources
        ],
        provider_mode=provider_mode,
    )
