from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from config import NEON_DATABASE_URL

Base = declarative_base()
engine = create_engine(NEON_DATABASE_URL or "sqlite+pysqlite:///:memory:", future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)