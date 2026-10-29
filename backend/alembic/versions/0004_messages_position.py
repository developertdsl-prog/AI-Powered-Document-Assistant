"""Add a per-conversation position to messages.

``messages.created_at`` is not a usable ordering: both messages of one
exchange are written in the same transaction, so ``now()`` is identical for
the user's question and the assistant's reply, and SQLite's second-resolution
timestamp ties as well. ``position`` records the real order inside a
conversation so history always replays question-then-answer.

The column is added on every dialect; the check constraint is PostgreSQL-only
because SQLite cannot alter constraints (the same split migration
``0003_embeddings`` uses for the vector index).

Revision ID: 0004_messages_position
Revises: 0003_embeddings
Create Date: 2026-10-29

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_messages_position"
down_revision: str | None = "0003_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()

    op.add_column(
        "messages",
        sa.Column(
            "position",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    if connection.dialect.name == "postgresql":
        op.create_check_constraint(
            "ck_messages_position",
            "messages",
            "position >= 0",
        )


def downgrade() -> None:
    connection = op.get_bind()

    if connection.dialect.name == "postgresql":
        op.drop_constraint("ck_messages_position", "messages", type_="check")

    op.drop_column("messages", "position")
