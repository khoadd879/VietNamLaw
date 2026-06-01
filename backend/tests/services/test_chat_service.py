import pytest

from services import chat_service
from services.chat_service import send_chat_message


@pytest.fixture
def fake_session(monkeypatch):
    """Patch dependencies; return a small handle to inspect saved data."""
    class FakeDB:
        def __init__(self):
            self.saved = []
        def add(self, obj):
            self.saved.append(obj)
        def commit(self):
            pass
        def refresh(self, obj):
            pass
    db = FakeDB()

    monkeypatch.setattr(chat_service, "get_session", lambda *_: object())
    return db


def test_send_chat_message_returns_structured_dict(fake_session, monkeypatch) -> None:
    monkeypatch.setattr(
        chat_service, "search_legal_context",
        lambda *_, **__: [{"content_text": "Điều 51", "title": "Luật HNGĐ", "source_url": "https://example/51"}],
    )
    saved = {"messages": []}
    def fake_save(db, *args, **kwargs):
        saved["messages"].append((args, kwargs))
        return object()
    monkeypatch.setattr(chat_service, "save_message", fake_save)
    monkeypatch.setattr(
        chat_service, "list_recent_messages",
        lambda *_, **__: [],
    )

    monkeypatch.setattr(
        chat_service, "generate_structured_answer",
        lambda *_, **__: {
            "loi_chao": "Chào bạn",
            "tom_tat_vu_viec": "Ly hôn",
            "phan_tich_phap_ly": "Điều 51 quy định...",
            "phuong_an_khuyen_nghi": ["Thỏa thuận"],
            "rui_ro_can_luu_y": ["Thời hiệu"],
            "cau_hoi_hoi_them": [],
            "disclaimer": "ok",
            "trich_dan_nguon": ["Điều 51 - Luật HNGĐ"],
        },
    )

    reply, sources, structured = send_chat_message(
        db=fake_session, session_id="s1", user_id="u1", message="Tôi muốn ly hôn"
    )
    assert "Điều 51" in reply
    assert "https://example/51" in sources
    assert structured["loi_chao"] == "Chào bạn"


def test_send_chat_message_falls_back_to_text_when_structured_fails(fake_session, monkeypatch) -> None:
    monkeypatch.setattr(
        chat_service, "search_legal_context",
        lambda *_, **__: [{"content_text": "ctx", "title": "T", "source_url": "u"}],
    )
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *_, **__: [])
    monkeypatch.setattr(chat_service, "save_message", lambda *_, **__: object())

    def raise_json(*_, **__):
        raise ValueError("bad json")
    monkeypatch.setattr(chat_service, "generate_structured_answer", raise_json)
    monkeypatch.setattr(
        chat_service, "generate_answer",
        lambda *_, **__: "Câu trả lời dạng text fallback.",
    )

    reply, sources, structured = send_chat_message(
        db=fake_session, session_id="s1", user_id="u1", message="q"
    )
    assert "fallback" in reply
    assert structured is None


def test_send_chat_message_returns_clarify_when_no_contexts(fake_session, monkeypatch) -> None:
    monkeypatch.setattr(chat_service, "search_legal_context", lambda *_, **__: [])
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *_, **__: [])
    captured = {}
    def fake_structured(*_, **kwargs):
        captured["contexts_empty"] = len(kwargs.get("contexts", []))
        return {
            "loi_chao": "Chào",
            "tom_tat_vu_viec": "Chưa rõ",
            "phan_tich_phap_ly": "Hiện chưa tìm thấy điều luật phù hợp...",
            "phuong_an_khuyen_nghi": [],
            "rui_ro_can_luu_y": [],
            "cau_hoi_hoi_them": ["Bạn cho biết thời điểm kết hôn?"],
            "disclaimer": "ok",
            "trich_dan_nguon": [],
        }
    monkeypatch.setattr(chat_service, "generate_structured_answer", fake_structured)
    monkeypatch.setattr(chat_service, "save_message", lambda *_, **__: object())

    reply, sources, structured = send_chat_message(
        db=fake_session, session_id="s1", user_id="u1", message="Hỏi chung chung"
    )
    assert captured["contexts_empty"] == 0
    assert structured["cau_hoi_hoi_them"] == ["Bạn cho biết thời điểm kết hôn?"]


def test_send_chat_message_passes_history_to_llm(fake_session, monkeypatch) -> None:
    monkeypatch.setattr(
        chat_service, "search_legal_context",
        lambda *_, **__: [{"content_text": "ctx", "title": "T", "source_url": "u"}],
    )
    captured = {}
    def fake_structured(*_, **kwargs):
        captured["history_len"] = len(kwargs.get("history", []))
        return {
            "loi_chao": "", "tom_tat_vu_viec": "", "phan_tich_phap_ly": "ok",
            "phuong_an_khuyen_nghi": [], "rui_ro_can_luu_y": [],
            "cau_hoi_hoi_them": [], "disclaimer": "ok", "trich_dan_nguon": [],
        }
    monkeypatch.setattr(chat_service, "generate_structured_answer", fake_structured)
    monkeypatch.setattr(chat_service, "save_message", lambda *_, **__: object())

    class FakeMsg:
        def __init__(self, role, content):
            self.role = role
            self.content = content
    history = [FakeMsg("user", "cũ"), FakeMsg("assistant", "trả lời cũ")]
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *_, **__: history)

    send_chat_message(db=fake_session, session_id="s1", user_id="u1", message="mới")
    assert captured["history_len"] == 1
