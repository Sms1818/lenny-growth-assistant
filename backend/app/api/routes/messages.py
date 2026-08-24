import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.messages import (
    MessageCreateRequest,
    SendMessageResponse,
    SourceResponse,
)
from app.assistant.service import (
    ConversationTurn,
    answer_question,
)
from app.db.dependencies import get_db_session
from app.db.models import Message, Session


router = APIRouter(
    prefix="/sessions",
    tags=["messages"],
)


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
        result = await answer_question(
            request.content,
            conversation_history=history,
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
    )
