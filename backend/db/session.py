from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import QueuePool
from core.config import NEON_DATABASE_URL

# QueuePool for Postgres (Neon). StaticPool is only for SQLite in-memory tests
# and would prevent real connection pooling for a serverless DB.
#
# Neon reaps idle connections after ~5 min, so a connection pulled from the
# pool may have been closed server-side. The combination below handles that:
#   - pool_pre_ping:   run SELECT 1 before checkout; if dead, create a new one
#   - pool_recycle:    rebuild connections every 4 min (before Neon's timeout)
#   - TCP keepalives:  prevent intermediate firewalls/NAT from dropping idle TCP
engine = create_engine(
    NEON_DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=240,
    future=True,
    connect_args={
        "connect_timeout": 10,
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
    },
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
