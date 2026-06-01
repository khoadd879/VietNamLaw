"""add case_facts and chat_session case columns

Revision ID: 1044176fa278
Revises: 13118a35765c
Create Date: 2026-06-01
"""
from alembic import op
import sqlalchemy as sa

revision = "1044176fa278"
down_revision = "13118a35765c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "case_facts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("session_id", sa.String(length=36), sa.ForeignKey("chat_sessions.id"), nullable=False, index=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("fact_key", sa.String(length=128), nullable=False),
        sa.Column("fact_value", sa.Text(), nullable=False),
        sa.Column("source_message_id", sa.String(length=36), sa.ForeignKey("chat_messages.id"), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.add_column("chat_sessions", sa.Column("case_type", sa.String(length=64), nullable=True))
    op.create_index("ix_chat_sessions_case_type", "chat_sessions", ["case_type"])
    op.add_column("chat_sessions", sa.Column("case_summary", sa.Text(), nullable=True))
    op.add_column("chat_sessions", sa.Column("conversation_phase", sa.String(length=32), nullable=False, server_default="intake"))
    op.add_column("chat_sessions", sa.Column("intake_completed_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_sessions", "intake_completed_at")
    op.drop_column("chat_sessions", "conversation_phase")
    op.drop_column("chat_sessions", "case_summary")
    op.drop_index("ix_chat_sessions_case_type", table_name="chat_sessions")
    op.drop_column("chat_sessions", "case_type")
    op.drop_table("case_facts")