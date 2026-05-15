from uuid import uuid4
from starlette.testclient import TestClient
from main import app
from repositories.messages import create_message


def test_message_repository_imports() -> None:
    assert callable(create_message)


client = TestClient(app)


def test_chat_requires_authorization() -> None:
    response = client.post("/chat", json={"session_id": str(uuid4()), "message": "Khi nao duoc ly hon?"})
    assert response.status_code in (401, 403)


def test_chat_requires_session_id() -> None:
    response = client.post("/chat", json={"message": "Khi nao duoc ly hon?"})
    assert response.status_code in (401, 403, 422)