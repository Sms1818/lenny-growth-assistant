import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MessageCreateRequest(BaseModel):
    content: str = Field(
        min_length=1,
        max_length=10000,
    )


class SourceResponse(BaseModel):
    chunk_id: int
    title: str
    source_type: str
    guest: str | None
    source_url: str | None
    youtube_url: str | None
    start_timestamp: str | None
    end_timestamp: str | None


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    sequence_number: int
    role: str
    content: str
    model_provider: str | None
    model_name: str | None
    source_chunk_ids: list[str] | None
    created_at: datetime


class SendMessageResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse
    sources: list[SourceResponse]
