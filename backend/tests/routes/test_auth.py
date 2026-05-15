from uuid import uuid4
from starlette.testclient import TestClient
from main import app


def test_register_returns_user_and_token(monkeypatch) -> None:
    from api.routes import auth as auth_module

    monkeypatch.setattr(auth_module, "register_user", lambda email, password: {
        "id": str(uuid4()),
        "email": email,
        "access_token": "token-123",
    })

    client = TestClient(app)
    response = client.post("/auth/register", json={"email": "user@example.com", "password": "secret123"})

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"
    assert response.json()["access_token"] == "token-123"


def test_login_returns_unauthorized_for_invalid_credentials(monkeypatch) -> None:
    from api.routes import auth as auth_module

    def fake_login(email: str, password: str):
        return None

    monkeypatch.setattr(auth_module, "authenticate_user", fake_login)

    client = TestClient(app)
    response = client.post("/auth/login", json={"email": "user@example.com", "password": "wrongpass"})

    assert response.status_code == 401