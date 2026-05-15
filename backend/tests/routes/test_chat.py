from uuid import uuid4
from starlette.testclient import TestClient
from main import app


client = TestClient(app)


def test_chat_requires_authorization() -> None:
    response = client.post("/chat", json={"session_id": str(uuid4()), "message": "Khi nào được ly hôn?"})
    assert response.status_code in (401, 403)


def test_chat_requires_session_id() -> None:
    response = client.post("/chat", json={"message": "Khi nào được ly hôn?"})
    assert response.status_code in (401, 403, 422)
