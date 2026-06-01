import pytest

from services import chat_service
from services.chat_service import send_chat_message


class FakeMsg:
    """Fake message object returned by save_message stubs."""
    def __init__(self, id="fake-msg-id"):
        self.id = id
        self.role = "user"
        self.content = ""


@pytest.fixture
def fake_session(monkeypatch):
    """Patch all side-effect dependencies; return a FakeDB handle."""
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

    # Stub session retrieval — tests can override via monkeypatch
    monkeypatch.setattr(chat_service, "get_session", lambda *_: object())
    # Stub save_message to return a FakeMsg with a real .id
    monkeypatch.setattr(chat_service, "save_message", lambda *_, **__: FakeMsg())
    # Stub list_case_facts to return empty list by default
    monkeypatch.setattr(chat_service, "list_case_facts", lambda *_, **__: [])
    # Stub add_fact
    monkeypatch.setattr(chat_service, "add_fact", lambda *_, **__: object())
    # Stub update_session_case
    monkeypatch.setattr(chat_service, "update_session_case", lambda *_, **__: object())

    # Sprint 3: stub hybrid retrieval pipeline (can be overridden per-test)
    monkeypatch.setattr(chat_service, "hybrid_search", lambda *_, **__: [])
    monkeypatch.setattr(chat_service, "multi_query_expand", lambda q, n_variants=2: [q])
    monkeypatch.setattr(chat_service, "verify_citations", lambda s, c: s)

    return db


def test_send_chat_message_returns_structured_dict(fake_session, monkeypatch) -> None:
    monkeypatch.setattr(
        chat_service, "hybrid_search",
        lambda *_, **__: [{"id": "ctx1", "content_text": "Điều 51", "title": "Luật HNGĐ", "source_url": "https://example/51", "score": 0.9}],
    )
    saved = {"messages": []}
    def fake_save(db, *args, **kwargs):
        saved["messages"].append((args, kwargs))
        return FakeMsg()
    monkeypatch.setattr(chat_service, "save_message", fake_save)
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *_, **__: [])

    monkeypatch.setattr(
        chat_service, "two_stage_reason",
        lambda **_: {
            "structured": {
                "loi_chao": "Chào bạn",
                "tom_tat_vu_viec": "Ly hôn",
                "phan_tich_phap_ly": "Điều 51 quy định...",
                "phuong_an_khuyen_nghi": ["Thỏa thuận"],
                "rui_ro_can_luu_y": ["Thời hiệu"],
                "cau_hoi_hoi_them": [],
                "disclaimer": "ok",
                "trich_dan_nguon": ["Điều 51 - Luật HNGĐ"],
            },
            "extracted": {"case_type": None, "extracted_facts": [], "case_summary": None},
            "updated_case_type": None,
            "updated_case_summary": None,
        },
    )

    reply, sources, structured, case_brief = send_chat_message(
        db=fake_session, session_id="s1", user_id="u1", message="Tôi muốn ly hôn"
    )
    assert "Điều 51" in reply
    assert "https://example/51" in sources
    assert structured["loi_chao"] == "Chào bạn"


def test_send_chat_message_falls_back_to_text_when_structured_fails(fake_session, monkeypatch) -> None:
    monkeypatch.setattr(
        chat_service, "hybrid_search",
        lambda *_, **__: [{"id": "ctx1", "content_text": "ctx", "title": "T", "source_url": "u", "score": 0.9}],
    )
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *_, **__: [])
    monkeypatch.setattr(chat_service, "save_message", lambda *_, **__: FakeMsg())
    monkeypatch.setattr(chat_service, "save_message", lambda *_, **__: FakeMsg())

    def raise_json(**kwargs):
        raise ValueError("bad json")
    monkeypatch.setattr(chat_service, "two_stage_reason", raise_json)
    # generate_answer is dynamically imported inside send_chat_message except block,
    # so patch at source module
    import services.groq_service as groq_mod
    monkeypatch.setattr(groq_mod, "generate_answer",
        lambda **__: "Câu trả lời dạng text fallback.")

    reply, sources, structured, case_brief = send_chat_message(
        db=fake_session, session_id="s1", user_id="u1", message="q"
    )
    assert "fallback" in reply
    assert structured is None


def test_send_chat_message_returns_clarify_when_no_contexts(fake_session, monkeypatch) -> None:
    monkeypatch.setattr(chat_service, "hybrid_search", lambda *_, **__: [])
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *_, **__: [])
    captured = {}
    def fake_two_stage(**kwargs):
        captured["contexts_empty"] = len(kwargs.get("contexts", []))
        return {
            "structured": {
                "loi_chao": "Chào",
                "tom_tat_vu_viec": "Chưa rõ",
                "phan_tich_phap_ly": "Hiện chưa tìm thấy điều luật phù hợp...",
                "phuong_an_khuyen_nghi": [],
                "rui_ro_can_luu_y": [],
                "cau_hoi_hoi_them": ["Bạn cho biết thời điểm kết hôn?"],
                "disclaimer": "ok",
                "trich_dan_nguon": [],
            },
            "extracted": {"case_type": None, "extracted_facts": [], "case_summary": None},
            "updated_case_type": None,
            "updated_case_summary": None,
        }
    monkeypatch.setattr(chat_service, "two_stage_reason", fake_two_stage)
    monkeypatch.setattr(chat_service, "save_message", lambda *_, **__: FakeMsg())

    reply, sources, structured, case_brief = send_chat_message(
        db=fake_session, session_id="s1", user_id="u1", message="Hỏi chung chung"
    )
    assert captured["contexts_empty"] == 0
    assert structured["cau_hoi_hoi_them"] == ["Bạn cho biết thời điểm kết hôn?"]


def test_send_chat_message_passes_history_to_llm(fake_session, monkeypatch) -> None:
    monkeypatch.setattr(
        chat_service, "hybrid_search",
        lambda *_, **__: [{"id": "ctx1", "content_text": "ctx", "title": "T", "source_url": "u", "score": 0.9}],
    )
    captured = {}
    def capture_history(**kwargs):
        captured["history_len"] = len(kwargs.get("history", []))
        return {
            "structured": {
                "loi_chao": "", "tom_tat_vu_viec": "", "phan_tich_phap_ly": "ok",
                "phuong_an_khuyen_nghi": [], "rui_ro_can_luu_y": [],
                "cau_hoi_hoi_them": [], "disclaimer": "ok", "trich_dan_nguon": [],
            },
            "extracted": {"case_type": None, "extracted_facts": [], "case_summary": None},
            "updated_case_type": None,
            "updated_case_summary": None,
        }
    monkeypatch.setattr(chat_service, "two_stage_reason", capture_history)
    monkeypatch.setattr(chat_service, "save_message", lambda *_, **__: FakeMsg())

    class FakeMsgObj:
        def __init__(self, role, content):
            self.role = role
            self.content = content
    history = [FakeMsgObj("user", "cũ"), FakeMsgObj("assistant", "trả lời cũ")]
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *_, **__: history)

    send_chat_message(db=fake_session, session_id="s1", user_id="u1", message="mới")
    assert captured["history_len"] == 1


def test_chat_returns_empty_sources_when_llm_does_not_cite(fake_session, monkeypatch) -> None:
    """When the LLM returns empty trich_dan_nguon, chat must NOT leak raw context URLs."""
    monkeypatch.setattr(
        chat_service, "hybrid_search",
        lambda *_, **__: [
            {"id": "ctx1", "content_text": "ctx1", "title": "L1", "source_url": "https://phapdien/1", "score": 0.9},
            {"id": "ctx2", "content_text": "ctx2", "title": "L2", "source_url": "https://phapdien/2", "score": 0.9},
        ],
    )
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *_, **__: [])
    monkeypatch.setattr(chat_service, "save_message", lambda *_, **__: FakeMsg())
    monkeypatch.setattr(
        chat_service, "two_stage_reason",
        lambda **_: {
            "structured": {
                "loi_chao": "Chào",
                "tom_tat_vu_viec": "Chưa rõ vụ việc",
                "phan_tich_phap_ly": "Hiện chưa tìm thấy điều luật phù hợp...",
                "phuong_an_khuyen_nghi": [],
                "rui_ro_can_luu_y": [],
                "cau_hoi_hoi_them": ["Bạn đang gặp vấn đề gì?"],
                "disclaimer": "ok",
                "trich_dan_nguon": [],  # LLM correctly refused to cite
            },
            "extracted": {"case_type": None, "extracted_facts": [], "case_summary": None},
            "updated_case_type": None,
            "updated_case_summary": None,
        },
    )

    reply, sources, structured, case_brief = send_chat_message(
        db=fake_session, session_id="s1", user_id="u1", message="Hỏi chung chung"
    )
    assert sources == [], f"Expected no sources, got {sources}"
    assert structured["trich_dan_nguon"] == []


def test_chat_returns_sources_when_llm_cites(fake_session, monkeypatch) -> None:
    """When the LLM cites a specific article, the matching context URL is surfaced."""
    monkeypatch.setattr(
        chat_service, "hybrid_search",
        lambda *_, **__: [
            {"id": "ctx1", "content_text": "Điều 51 quy định...", "title": "L1", "source_url": "https://phapdien/51", "score": 0.9},
        ],
    )
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *_, **__: [])
    monkeypatch.setattr(chat_service, "save_message", lambda *_, **__: FakeMsg())
    monkeypatch.setattr(
        chat_service, "two_stage_reason",
        lambda **_: {
            "structured": {
                "loi_chao": "Chào",
                "tom_tat_vu_viec": "Ly hôn",
                "phan_tich_phap_ly": "Điều 51 áp dụng...",
                "phuong_an_khuyen_nghi": [],
                "rui_ro_can_luu_y": [],
                "cau_hoi_hoi_them": [],
                "disclaimer": "ok",
                "trich_dan_nguon": ["Điều 51 - Luật HNGĐ"],
            },
            "extracted": {"case_type": None, "extracted_facts": [], "case_summary": None},
            "updated_case_type": None,
            "updated_case_summary": None,
        },
    )

    reply, sources, structured, case_brief = send_chat_message(
        db=fake_session, session_id="s1", user_id="u1", message="ly hôn đơn phương"
    )
    assert sources == ["https://phapdien/51"]
    assert structured["trich_dan_nguon"] == ["Điều 51 - Luật HNGĐ"]


def test_chat_persists_extracted_facts(fake_session, monkeypatch) -> None:
    monkeypatch.setattr(chat_service, "hybrid_search", lambda *_, **__: [])
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *_, **__: [])

    extracted = {
        "case_type": "hôn nhân gia đình",
        "extracted_facts": [{"key": "ngay_ket_hon", "value": "2018", "confidence": 0.9}],
        "case_summary": "User kết hôn 2018.",
    }
    monkeypatch.setattr(
        chat_service, "two_stage_reason",
        lambda **_: {
            "structured": {
                "loi_chao": "Chào", "tom_tat_vu_viec": "ok", "phan_tich_phap_ly": "ok",
                "phuong_an_khuyen_nghi": [], "rui_ro_can_luu_y": [],
                "cau_hoi_hoi_them": [], "disclaimer": "ok", "trich_dan_nguon": []
            },
            "extracted": extracted,
            "updated_case_type": "hôn nhân gia đình",
            "updated_case_summary": "User kết hôn 2018.",
        },
    )

    saved_facts = []
    def fake_add_fact(db, session_id, user_id, fact_key, fact_value, **kwargs):
        saved_facts.append((fact_key, fact_value))
        return object()
    monkeypatch.setattr(chat_service, "add_fact", fake_add_fact)

    case_updates = []
    def fake_update_session_case(db, session_id, user_id, **kwargs):
        case_updates.append(kwargs)
        return object()
    monkeypatch.setattr(chat_service, "update_session_case", fake_update_session_case)
    monkeypatch.setattr(chat_service, "list_case_facts", lambda *_, **__: [])
    monkeypatch.setattr(chat_service, "save_message", lambda *_, **__: FakeMsg())

    send_chat_message(db=fake_session, session_id="s1", user_id="u1", message="Tôi kết hôn 2018")
    assert ("ngay_ket_hon", "2018") in saved_facts
    assert case_updates[0]["case_type"] == "hôn nhân gia đình"
    assert case_updates[0]["case_summary"] == "User kết hôn 2018."


def test_chat_skips_fact_persist_when_no_extraction(fake_session, monkeypatch) -> None:
    monkeypatch.setattr(chat_service, "hybrid_search", lambda *_, **__: [])
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *_, **__: [])
    monkeypatch.setattr(
        chat_service, "two_stage_reason",
        lambda **_: {
            "structured": {
                "loi_chao": "", "tom_tat_vu_viec": "", "phan_tich_phap_ly": "ok",
                "phuong_an_khuyen_nghi": [], "rui_ro_can_luu_y": [],
                "cau_hoi_hoi_them": [], "disclaimer": "ok", "trich_dan_nguon": []
            },
            "extracted": {"case_type": None, "extracted_facts": [], "case_summary": None},
            "updated_case_type": None,
            "updated_case_summary": None,
        },
    )
    add_called = {"flag": False}
    def fake_add_fact(*_, **__):
        add_called["flag"] = True
        return object()
    monkeypatch.setattr(chat_service, "add_fact", fake_add_fact)
    monkeypatch.setattr(chat_service, "update_session_case", lambda *_, **__: object())
    monkeypatch.setattr(chat_service, "list_case_facts", lambda *_, **__: [])
    monkeypatch.setattr(chat_service, "save_message", lambda *_, **__: FakeMsg())

    send_chat_message(db=fake_session, session_id="s1", user_id="u1", message="chào bạn")
    assert add_called["flag"] is False


def test_chat_uses_existing_case_brief_in_two_stage(fake_session, monkeypatch) -> None:
    monkeypatch.setattr(chat_service, "hybrid_search", lambda *_, **__: [])

    class FakeFact:
        def __init__(self, k, v): self.fact_key, self.fact_value, self.confidence = k, v, 1.0

    captured = {}
    def fake_two_stage(**kwargs):
        captured["existing_facts_keys"] = [f.fact_key for f in kwargs["existing_facts"]]
        captured["case_type"] = kwargs["case_type"]
        return {
            "structured": {
                "loi_chao": "", "tom_tat_vu_viec": "", "phan_tich_phap_ly": "ok",
                "phuong_an_khuyen_nghi": [], "rui_ro_can_luu_y": [],
                "cau_hoi_hoi_them": [], "disclaimer": "ok", "trich_dan_nguon": []
            },
            "extracted": {"case_type": None, "extracted_facts": [], "case_summary": None},
            "updated_case_type": None,
            "updated_case_summary": None,
        }
    monkeypatch.setattr(chat_service, "two_stage_reason", fake_two_stage)
    monkeypatch.setattr(chat_service, "add_fact", lambda *_, **__: object())
    monkeypatch.setattr(chat_service, "update_session_case", lambda *_, **__: object())
    monkeypatch.setattr(chat_service, "save_message", lambda *_, **__: FakeMsg())
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *_, **__: [])

    # Inject existing facts and case_type/case_summary on the session
    monkeypatch.setattr(chat_service, "list_case_facts", lambda *_, **__: [FakeFact("ngay_ket_hon", "2018")])

    class FakeSession:
        case_type = "hôn nhân gia đình"
        case_summary = "User kết hôn 2018."
    monkeypatch.setattr(chat_service, "get_session", lambda *_: FakeSession())

    send_chat_message(db=fake_session, session_id="s1", user_id="u1", message="thêm nữa tôi có con")
    assert captured["existing_facts_keys"] == ["ngay_ket_hon"]
    assert captured["case_type"] == "hôn nhân gia đình"


# ─── Sprint 3 wiring tests ─────────────────────────────────────────────────────

def test_chat_uses_hybrid_search_instead_of_pure_vector(fake_session, monkeypatch) -> None:
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *_, **__: [])
    monkeypatch.setattr(chat_service, "list_case_facts", lambda *_: [])
    class FakeS:
        case_type = None
        case_summary = None
    monkeypatch.setattr(chat_service, "get_session", lambda *_: FakeS())

    captured = {}
    def fake_hybrid(query, **kwargs):
        captured["query"] = query
        return [{"id": "1", "content_text": "Điều 51", "title": "Luật HNGĐ", "source_url": "u", "score": 0.9}]

    monkeypatch.setattr(chat_service, "hybrid_search", fake_hybrid)
    # multi_query_expand must return variant queries so hybrid_search gets called multiple times
    def multi_expand(msg, n_variants=2):
        return [msg, msg + " variant", msg + " variant 2"]
    monkeypatch.setattr(chat_service, "multi_query_expand", multi_expand)
    monkeypatch.setattr(
        chat_service, "two_stage_reason",
        lambda **_: {
            "structured": {
                "loi_chao": "Chào", "tom_tat_vu_viec": "ok", "phan_tich_phap_ly": "ok",
                "phuong_an_khuyen_nghi": [], "rui_ro_can_luu_y": [],
                "cau_hoi_hoi_them": [], "disclaimer": "ok",
                "trich_dan_nguon": ["Điều 51 - Luật HNGĐ"]
            },
            "extracted": {"case_type": None, "extracted_facts": [], "case_summary": None},
            "updated_case_type": None, "updated_case_summary": None,
        },
    )
    monkeypatch.setattr(chat_service, "verify_citations", lambda s, c: s)
    monkeypatch.setattr(chat_service, "add_fact", lambda *_, **__: object())
    monkeypatch.setattr(chat_service, "update_session_case", lambda *_, **__: object())
    monkeypatch.setattr(chat_service, "save_message", lambda *_, **__: FakeMsg())

    send_chat_message(db=fake_session, session_id="s1", user_id="u1", message="ly hôn đơn phương")
    # Verify hybrid_search was called (at least once) with the original query
    assert captured["query"].startswith("ly hôn đơn phương")


def test_chat_verifies_citations_before_persisting(fake_session, monkeypatch) -> None:
    monkeypatch.setattr(chat_service, "list_recent_messages", lambda *_, **__: [])
    monkeypatch.setattr(chat_service, "list_case_facts", lambda *_: [])
    class FakeS:
        case_type = None
        case_summary = None
    monkeypatch.setattr(chat_service, "get_session", lambda *_: FakeS())
    monkeypatch.setattr(chat_service, "hybrid_search", lambda *_, **__: [])
    monkeypatch.setattr(chat_service, "multi_query_expand", lambda q, n_variants=2: [q])

    captured = {}
    def fake_verify(structured, contexts):
        structured["trich_dan_nguon"] = ["Điều 51 - Luật HNGĐ"]
        captured["called"] = True
        return structured
    monkeypatch.setattr(chat_service, "verify_citations", fake_verify)

    monkeypatch.setattr(
        chat_service, "two_stage_reason",
        lambda **_: {
            "structured": {
                "loi_chao": "", "tom_tat_vu_viec": "", "phan_tich_phap_ly": "ok",
                "phuong_an_khuyen_nghi": [], "rui_ro_can_luu_y": [],
                "cau_hoi_hoi_them": [], "disclaimer": "ok",
                "trich_dan_nguon": ["Điều 51 - Luật HNGĐ", "Điều 999 - Fabricated"]
            },
            "extracted": {"case_type": None, "extracted_facts": [], "case_summary": None},
            "updated_case_type": None, "updated_case_summary": None,
        },
    )
    # Instead of hooking save_message, verify citations by patching at the
    # source module level. We only need to verify that:
    # 1. verify_citations was called
    # 2. fake_verify replaced the fabricated citation
    # We can't easily observe the raw structured passed to save_message from
    # within pytest without understanding the exact call signature. Instead,
    # we verify at a higher level: after the call, structured has only verified
    # citations. We use a global capture to observe the structured object
    # stored by the real save_message.
    global_verify_result_captured = {}
    original_save = chat_service.save_message 

    def capture_save_message_wrapper(*args, **kwargs):
        # Capture structured dict from the assistant save_message call.
        # Supports both positional (db, sid, uid, role, content, sources_json?)
        # and keyword (role=, sources_json=) calling conventions.
        role = args[3] if len(args) >= 4 else kwargs.get("role", "")
        if role == "assistant":
            metadata = kwargs.get("sources_json", {})
            if not metadata and len(args) >= 6:
                metadata = args[5] or {}
            global_verify_result_captured["structured"] = (
                metadata.get("structured") if isinstance(metadata, dict) else None
            )
        return original_save(*args, **kwargs)
    
    monkeypatch.setattr(chat_service, "save_message", capture_save_message_wrapper)
    monkeypatch.setattr(chat_service, "add_fact", lambda *_, **__: object())
    monkeypatch.setattr(chat_service, "update_session_case", lambda *_, **__: object())

    send_chat_message(db=fake_session, session_id="s1", user_id="u1", message="q")
    assert captured["called"] is True
    assert global_verify_result_captured.get("structured") is not None, \
        "structured was not captured in save_message call"
    assert "Điều 999" not in global_verify_result_captured["structured"]["trich_dan_nguon"]
