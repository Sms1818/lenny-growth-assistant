"""add message sequence number

Revision ID: 83b68112f086
Revises: 7da9578fde85
Create Date: 2026-08-24 17:41:58.438589
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "83b68112f086"
down_revision: Union[str, None] = "7da9578fde85"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column(
            "sequence_number",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.execute(
        """
        WITH numbered AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY session_id
                    ORDER BY created_at, id
                ) AS sequence_number
            FROM messages
        )
        UPDATE messages
        SET sequence_number = numbered.sequence_number
        FROM numbered
        WHERE messages.id = numbered.id
        """
    )

    op.alter_column(
        "messages",
        "sequence_number",
        nullable=False,
    )

    op.create_unique_constraint(
        "uq_messages_session_sequence",
        "messages",
        [
            "session_id",
            "sequence_number",
        ],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_messages_session_sequence",
        "messages",
        type_="unique",
    )
    op.drop_column(
        "messages",
        "sequence_number",
    )
