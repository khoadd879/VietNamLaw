import pytest
from starlette.testclient import TestClient


@pytest.fixture
def client():
    from main import app

    return TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create tables once per test session."""
    from db.base import Base
    from db.session import engine
    from db.init_db import init_db

    init_db()
    yield
    Base.metadata.drop_all(bind=engine)