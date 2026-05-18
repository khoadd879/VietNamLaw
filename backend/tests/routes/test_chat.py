from uuid import uuid4

import pytest

from repositories.messages import create_message


def test_message_repository_imports() -> None:
    assert callable(create_message)


@pytest.mark.anyio
async def test_chat_requires_authorization(client) -> None:
    response = await client.post(
        "/chat",
        json={"session_id": str(uuid4()), "message": "Khi nao duoc ly hon?"},
    )
    assert response.status_code in (401, 403)


@pytest.mark.anyio
async def test_chat_requires_session_id(client) -> None:
    response = await client.post("/chat", json={"message": "Khi nao duoc ly hon?"})
    assert response.status_code in (401, 403, 422)
