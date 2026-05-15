from uuid import uuid4


def test_list_sessions_route_exists(client):
    response = client.get("/chat/sessions")
    assert response.status_code != 404


def test_rename_session_route_exists(client):
    response = client.patch(f"/chat/sessions/{uuid4()}", json={"title": "Vụ việc đất đai"})
    assert response.status_code != 404


def test_list_sessions_requires_authorization(client):
    response = client.get("/chat/sessions")
    assert response.status_code in (401, 403)