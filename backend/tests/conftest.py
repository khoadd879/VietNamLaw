import pytest
from starlette.testclient import TestClient


@pytest.fixture
def client():
    from main import app

    return TestClient(app)


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create tables once per test session."""
    # Import models to register them with Base before create_all
    import models as _  # noqa: F401
    from db import Base, engine, init_db

    init_db()
    yield
    Base.metadata.drop_all(bind=engine)
