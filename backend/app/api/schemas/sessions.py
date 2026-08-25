import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ProviderMode = Literal["auto", "local", "cloud"]


class SessionCreateRequest(BaseModel):
    title: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    user_metadata: dict[str, Any] | None = None


class SessionUpdateRequest(BaseModel):
    title: str = Field(
        min_length=1,
        max_length=255,
    )


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str | None
    user_metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
