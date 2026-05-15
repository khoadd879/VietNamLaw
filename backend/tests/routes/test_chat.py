from fastapi.testclient import TestClient


def test_chat_returns_reply_and_sources(monkeypatch) -> None:
    from main import app

    client = TestClient(app)
    from api.routes import chat as chat_module

    monkeypatch.setattr(
        chat_module,
        "search_legal_context",
        lambda message: [
            {"source": "Luật Hôn nhân và Gia đình", "content": "Quy định về ly hôn."}
        ],
    )
    monkeypatch.setattr(
        chat_module,
        "generate_answer",
        lambda question, contexts: "Cần xem xét căn cứ ly hôn theo luật hiện hành.",
    )

    response = client.post("/chat", json={"message": "Khi nào được ly hôn?"})

    assert response.status_code == 200
    assert response.json() == {
        "reply": "Cần xem xét căn cứ ly hôn theo luật hiện hành.",
        "sources": ["Luật Hôn nhân và Gia đình"],
    }