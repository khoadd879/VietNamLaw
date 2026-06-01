from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.base import Base
from entities.case_fact import CaseFact
from entities.chat_session import ChatSession
from entities.user import User
from repositories.case_facts import list_facts_for_session, upsert_fact


def _make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _seed(db):
    db.add_all([
        User(id="u1", email="a@b.c", password_hash="x"),
        ChatSession(id="s1", user_id="u1", title="t"),
    ])
    db.commit()


def test_upsert_fact_inserts_new_row() -> None:
    db = _make_db()
    _seed(db)
    f = upsert_fact(db, "f1", "s1", "u1", "ngay_ket_hon", "2018-03-15")
    assert f.id == "f1"
    rows = list_facts_for_session(db, "s1")
    assert len(rows) == 1
    assert rows[0].fact_key == "ngay_ket_hon"


def test_upsert_fact_updates_existing_row_with_same_key() -> None:
    db = _make_db()
    _seed(db)
    upsert_fact(db, "f1", "s1", "u1", "ngay_ket_hon", "2018-03-15")
    f2 = upsert_fact(db, "f2", "s1", "u1", "ngay_ket_hon", "2020-05-01")
    rows = list_facts_for_session(db, "s1")
    assert len(rows) == 1
    assert rows[0].fact_value == "2020-05-01"
    assert rows[0].id == "f2"