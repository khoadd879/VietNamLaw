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
    """Create tables once per test session."""
    from db.base import Base
    from db.session import engine
    from db.init_db import init_db

    init_db()
    yield
    Base.metadata.drop_all(bind=engine)
