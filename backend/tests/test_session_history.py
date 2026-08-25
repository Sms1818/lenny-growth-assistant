import uuid
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.api.routes.messages import list_session_messages
from app.api.routes.sessions import list_sessions
from app.db.models import Artifact, Message, Session


class FakeScalars:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class FakeExecuteResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeDb:
    def __init__(self):
        now = datetime.now(timezone.utc)
        self.session = Session(
            id=uuid.uuid4(),
            title="Growth research",
            user_metadata=None,
            created_at=now,
            updated_at=now,
        )
        self.other_session = Session(
            id=uuid.uuid4(),
            title=None,
            user_metadata=None,
            created_at=now,
            updated_at=now,
        )
        self.user_message = Message(
            id=uuid.uuid4(),
            session_id=self.session.id,
            sequence_number=1,
            role="user",
            content="How did Duolingo grow?",
            model_provider=None,
            model_name=None,
            source_chunk_ids=None,
            created_at=now,
        )
        self.assistant_message = Message(
            id=uuid.uuid4(),
            session_id=self.session.id,
            sequence_number=2,
            role="assistant",
            content="Duolingo focused on retention. [1]",
            model_provider="ollama",
            model_name="llama3.2:3b",
            source_chunk_ids=["101"],
            created_at=now,
        )
        self.artifact = Artifact(
            id=uuid.uuid4(),
            message_id=self.assistant_message.id,
            title="Retention Notes",
            artifact_type="markdown",
            content="# Retention Notes\n\nBody",
            created_at=now,
        )
        self.sessions = [
            self.other_session,
            self.session,
        ]
        self.messages = [
            self.user_message,
            self.assistant_message,
        ]

    async def scalars(self, statement):
        entity = statement.column_descriptions[0]["entity"]

        if entity is Session:
            return FakeScalars(self.sessions)

        if entity is Message:
            return FakeScalars(self.messages)

        if entity is Artifact:
            return FakeScalars([self.artifact])

        return FakeScalars([])

    async def execute(self, statement):
        return FakeExecuteResult([])

    async def get(self, model, object_id):
        if model is Session:
            for session in self.sessions:
                if session.id == object_id:
                    return session

        return None


@pytest.mark.asyncio
async def test_list_sessions_returns_recent_first():
    db = FakeDb()

    response = await list_sessions(db)

    assert len(response.sessions) == 2
    assert response.sessions[0].id == db.other_session.id


@pytest.mark.asyncio
async def test_list_session_messages_ordered_with_artifact():
    db = FakeDb()

    async def fake_resolve_sources(
        db_session,
        chunk_ids,
    ):
        assert chunk_ids == ["101"]
        from app.api.schemas.messages import SourceResponse

        return [
            SourceResponse(
                chunk_id=101,
                title="Duolingo episode",
                source_type="podcast",
                guest="Luis von Ahn",
                source_url=None,
                youtube_url=None,
                start_timestamp=None,
                end_timestamp=None,
            )
        ]

    import app.api.routes.messages as messages_route

    original = messages_route.resolve_sources_for_chunk_ids
    messages_route.resolve_sources_for_chunk_ids = fake_resolve_sources

    try:
        response = await list_session_messages(
            db.session.id,
            db,
        )
    finally:
        messages_route.resolve_sources_for_chunk_ids = original

    assert len(response.messages) == 2
    assert response.messages[0].sequence_number == 1
    assert response.messages[1].sequence_number == 2
    assert response.messages[1].artifact_id == db.artifact.id
    assert len(response.messages[1].sources) == 1


@pytest.mark.asyncio
async def test_list_session_messages_missing_session():
    db = FakeDb()

    with pytest.raises(HTTPException) as exc_info:
        await list_session_messages(uuid.uuid4(), db)

    assert exc_info.value.status_code == 404
