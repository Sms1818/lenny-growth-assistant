import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.api.schemas.messages import (
    MessageResponse,
    SourceResponse,
)


class ArtifactCreateRequest(BaseModel):
    artifact_type: str = Field(
        pattern="^(markdown|html)$",
    )
    instruction: str = Field(
        min_length=1,
        max_length=4000,
    )


class Ship30ArtifactRequest(BaseModel):
    topic: str = Field(
        min_length=1,
        max_length=2000,
    )


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    message_id: uuid.UUID
    title: str
    artifact_type: str
    content: str
    created_at: datetime


class CreateArtifactResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse
    artifact: ArtifactResponse
    sources: list[SourceResponse]
