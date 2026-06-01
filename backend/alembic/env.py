from logging.config import fileConfig

from alembic import context

import os
from dotenv import load_dotenv
load_dotenv()

from db.base import Base
from entities.case_fact import CaseFact
from entities.chat_session import ChatSession
from entities.chat_message import ChatMessage
from entities.user import User

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

NEON_DATABASE_URL = os.getenv("NEON_DATABASE_URL", "")
if not NEON_DATABASE_URL:
    raise RuntimeError("NEON_DATABASE_URL must be set for migrations")


def run_migrations_offline() -> None:
    context.configure(
        url=NEON_DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import create_engine
    connectable = create_engine(NEON_DATABASE_URL, poolclass=None)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()