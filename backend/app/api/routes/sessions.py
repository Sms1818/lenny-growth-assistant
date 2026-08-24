from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.sessions import (
    SessionCreateRequest,
    SessionResponse,
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
