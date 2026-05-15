from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool
from config import NEON_DATABASE_URL

Base = declarative_base()
_engine_args = {"future": True, "poolclass": StaticPool}
if not NEON_DATABASE_URL:
    _engine_args["connect_args"] = {"check_same_thread": False}
engine = create_engine(
    NEON_DATABASE_URL or "sqlite+pysqlite:///:memory:", **_engine_args
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Safe to call multiple times."""
    import models  # noqa: F401 - registers models with Base before create_all

    Base.metadata.create_all(bind=engine)