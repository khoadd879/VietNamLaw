from uuid import uuid4

import pytest

from api.routes.sessions import _parse_sources_json
from dto.session import SessionResponse
from entities.chat_session import ChatSession


def test_new_session_modules_import() -> None:
    assert SessionResponse is not None
    assert ChatSession is not None


def test_parse_sources_json_returns_dict_for_valid_string() -> None:
    raw = '{"sources": ["https://example/51"], "structured": {"loi_chao": "Chào"}}'
    parsed = _parse_sources_json(raw)
    assert parsed == {"sources": ["https://example/51"], "structured": {"loi_chao": "Chào"}}


def test_parse_sources_json_returns_none_for_none_input() -> None:
    assert _parse_sources_json(None) is None


def test_parse_sources_json_returns_none_for_empty_string() -> None:
    assert _parse_sources_json("") is None


def test_parse_sources_json_returns_none_for_invalid_json() -> None:
    assert _parse_sources_json("not valid json {") is None


def test_parse_sources_json_handles_empty_object() -> None:
    assert _parse_sources_json("{}") == {}


@pytest.mark.anyio
async def test_list_messages_returns_parsed_sources_json_dict(client) -> None:
    """End-to-end: saved message with JSON-string sources_json must surface as dict."""
    from db.session import SessionLocal
    from entities.user import User
    from services.auth_service import create_access_token

    db = SessionLocal()
    try:
        u = User(id=str(uuid4()), email="parse-test@example.c", password_hash="x")
        db.add(u)
        db.commit()
        sid = str(uuid4())
        s = ChatSession(id=sid, user_id=u.id, title="parse-test")
        db.add(s)
        db.commit()
        from entities.chat_message import ChatMessage
        import json as _json
        msg = ChatMessage(
            id=str(uuid4()),
            session_id=sid,
            user_id=u.id,
            role="assistant",
            content="Test reply",
            sources_json=_json.dumps({"sources": ["https://example/51"], "structured": {"loi_chao": "ok"}}),
        )
        db.add(msg)
        db.commit()
        token = create_access_token({"sub": u.id})
    finally:
        db.close()

    response = await client.get(
        f"/chat/sessions/{sid}/messages",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data) == 1
    assert isinstance(data[0]["sources_json"], dict), f"expected dict, got {type(data[0]['sources_json'])}"
    assert data[0]["sources_json"]["sources"] == ["https://example/51"]


def test_list_sessions_route_exists(client):
    response = client.get("/chat/sessions")
    assert response.status_code != 404


def test_rename_session_route_exists(client):
    response = client.patch(f"/chat/sessions/{uuid4()}", json={"title": "Vụ việc đất đai"})
    assert response.status_code != 404


def test_list_sessions_requires_authorization(client):
    response = client.get("/chat/sessions")
    assert response.status_code in (401, 403)