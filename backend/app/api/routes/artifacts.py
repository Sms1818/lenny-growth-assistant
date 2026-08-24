import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.messages import get_recent_history
from app.api.schemas.artifacts import (
    ArtifactCreateRequest,
    ArtifactResponse,
    CreateArtifactResponse,
    Ship30ArtifactRequest,
)
from app.api.schemas.messages import SourceResponse
from app.assistant.skills.artifacts import (
    extract_markdown_title,
    generate_artifact,
)
from app.assistant.skills.ship30 import (
    generate_ship30_essay,
    validate_ship30_structure,
)
from app.db.dependencies import get_db_session
from app.db.models import Artifact, Message, Session


router = APIRouter(tags=["artifacts"])


@router.post(
    "/sessions/{session_id}/artifacts",
    response_model=CreateArtifactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_artifact(
    session_id: uuid.UUID,
    request: ArtifactCreateRequest,
    db: AsyncSession = Depends(get_db_session),
) -> CreateArtifactResponse:
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
        result = await generate_artifact(
            request.instruction,
            artifact_type=request.artifact_type,
            conversation_history=history,
        )

        if (
            result.grounding_issues
            or result.validation_issues
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "artifact_generation_failed",
                    "message": (
                        "The generated artifact did not meet "
                        "grounding or validation requirements."
                    ),
                    "grounding_issues": [
                        {
                            "type": issue.issue_type,
                            "text": issue.text,
                        }
                        for issue in result.grounding_issues
                    ],
                    "validation_issues": (
                        result.validation_issues
                    ),
                },
            )

        user_message = Message(
            session_id=session_id,
            sequence_number=current_sequence + 1,
            role="user",
            content=(
                f"Create a {request.artifact_type} artifact: "
                f"{request.instruction}"
            ),
        )

        assistant_message = Message(
            session_id=session_id,
            sequence_number=current_sequence + 2,
            role="assistant",
            content=(
                f"Created {request.artifact_type} artifact: "
                f"{result.title}"
            ),
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

        await db.flush()

        artifact = Artifact(
            message_id=assistant_message.id,
            title=result.title,
            artifact_type=result.artifact_type,
            content=result.content,
        )

        db.add(artifact)

        await db.commit()

        await db.refresh(user_message)
        await db.refresh(assistant_message)
        await db.refresh(artifact)

    except Exception:
        await db.rollback()
        raise

    return CreateArtifactResponse(
        user_message=user_message,
        assistant_message=assistant_message,
        artifact=ArtifactResponse.model_validate(
            artifact
        ),
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


@router.post(
    "/sessions/{session_id}/artifacts/ship30",
    response_model=CreateArtifactResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_ship30_artifact(
    session_id: uuid.UUID,
    request: Ship30ArtifactRequest,
    db: AsyncSession = Depends(get_db_session),
) -> CreateArtifactResponse:
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
        result = await generate_ship30_essay(
            request.topic,
            conversation_history=history,
        )

        structure_issues = validate_ship30_structure(
            result.markdown
        )

        if result.grounding_issues or structure_issues:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "code": "artifact_generation_failed",
                    "message": (
                        "The generated Ship 30 essay did not meet "
                        "grounding or structure requirements."
                    ),
                    "grounding_issues": [
                        {
                            "type": issue.issue_type,
                            "text": issue.text,
                        }
                        for issue in result.grounding_issues
                    ],
                    "structure_issues": structure_issues,
                },
            )

        user_message = Message(
            session_id=session_id,
            sequence_number=current_sequence + 1,
            role="user",
            content=(
                "Create a Ship 30 for 30 essay: "
                + request.topic
            ),
        )

        title = extract_markdown_title(
            result.markdown
        )

        assistant_message = Message(
            session_id=session_id,
            sequence_number=current_sequence + 2,
            role="assistant",
            content=f"Created Ship 30 essay: {title}",
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

        await db.flush()

        artifact = Artifact(
            message_id=assistant_message.id,
            title=title,
            artifact_type="markdown",
            content=result.markdown,
        )

        db.add(artifact)

        await db.commit()

        await db.refresh(user_message)
        await db.refresh(assistant_message)
        await db.refresh(artifact)

    except Exception:
        await db.rollback()
        raise

    return CreateArtifactResponse(
        user_message=user_message,
        assistant_message=assistant_message,
        artifact=ArtifactResponse.model_validate(
            artifact
        ),
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


@router.get(
    "/artifacts/{artifact_id}",
    response_model=ArtifactResponse,
)
async def get_artifact(
    artifact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> Artifact:
    artifact = await db.get(
        Artifact,
        artifact_id,
    )

    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Artifact not found",
        )

    return artifact
