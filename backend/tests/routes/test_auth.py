import importlib.util

from starlette.testclient import TestClient
from main import app


def test_legacy_auth_module_removed() -> None:
    assert importlib.util.find_spec("auth") is None


def test_new_auth_dependency_module_imports() -> None:
    from api.dependencies.auth import get_current_user

    assert callable(get_current_user)


def test_register_returns_user_and_token() -> None:
    client = TestClient(app)
    response = client.post("/auth/register", json={"email": "user@example.com", "password": "secret123"})

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


def test_login_returns_unauthorized_for_invalid_credentials() -> None:
    client = TestClient(app)
    response = client.post("/auth/login", json={"email": "user@example.com", "password": "wrongpass"})

    assert response.status_code == 401


def test_me_requires_authorization() -> None:
    client = TestClient(app)
    response = client.get("/auth/me")
    assert response.status_code in (401, 403)
