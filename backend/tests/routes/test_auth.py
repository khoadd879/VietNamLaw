from starlette.testclient import TestClient
from main import app


def test_register_route_exists() -> None:
    client = TestClient(app)
    response = client.post("/auth/register", json={"email": "user@example.com", "password": "secret123"})
    assert response.status_code != 404