import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client():
    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create tables (idempotent) once per test session.

    NOTE: The previous version of this fixture called
    ``Base.metadata.drop_all(bind=engine)`` after each test session. Because
    ``db.session.engine`` is bound to ``NEON_DATABASE_URL`` (i.e. production),
    that drop wiped the live database on every test run. The lifespan handler
    in ``main.py`` already runs ``init_db()`` (idempotent ``create_all``) on
    app startup, so we only need the same idempotent create here — no drop.
    """
    from db.init_db import init_db

    init_db()
