from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from core.config import NEON_DATABASE_URL

_engine_args = {"future": True, "poolclass": StaticPool}
if not NEON_DATABASE_URL:
    _engine_args["connect_args"] = {"check_same_thread": False}

engine = create_engine(NEON_DATABASE_URL or "sqlite+pysqlite:///:memory:", **_engine_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)