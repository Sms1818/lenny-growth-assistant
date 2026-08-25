import uuid

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.sessions import (
    SessionCreateRequest,
    SessionListResponse,
    SessionResponse,
    SessionUpdateRequest,
)
from app.db.dependencies import get_db_session
from app.db.models import Session


router = APIRouter(
    prefix="/sessions",
    tags=["sessions"],
)

DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_db_session),
]


@router.get(
    "",
    response_model=SessionListResponse,
)
async def list_sessions(
    db: DatabaseSession,
) -> SessionListResponse:
    statement = (
        select(Session)
        .order_by(Session.updated_at.desc())
    )

    sessions = list(
        (await db.scalars(statement)).all()
    )

    return SessionListResponse(
        sessions=[
            SessionResponse.model_validate(session)
            for session in sessions
        ],
    )


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    request: SessionCreateRequest,
    db: DatabaseSession,
) -> Session:
    session = Session(
        title=request.title,
        user_metadata=request.user_metadata,
    )

    db.add(session)
    await db.commit()
    await db.refresh(session)

    return session



@router.patch(
    "/{session_id}",
    response_model=SessionResponse,
)
async def update_session(
    session_id: uuid.UUID,
    request: SessionUpdateRequest,
    db: DatabaseSession,
) -> Session:
    session = await db.get(Session, session_id)

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    session.title = request.title.strip()

    await db.commit()
    await db.refresh(session)

    return session


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_session(
    session_id: uuid.UUID,
    db: DatabaseSession,
) -> Response:
    session = await db.get(Session, session_id)

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    await db.delete(session)
    await db.commit()

    return Response(
        status_code=status.HTTP_204_NO_CONTENT,
    )
