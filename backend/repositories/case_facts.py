from sqlalchemy import select
from sqlalchemy.orm import Session

from entities.case_fact import CaseFact


def upsert_fact(
    db: Session,
    fact_id: str,
    session_id: str,
    user_id: str,
    fact_key: str,
    fact_value: str,
    source_message_id: str | None = None,
    confidence: float = 1.0,
) -> CaseFact:
    """Insert a fact, or update if (session_id, fact_key) already exists."""
    existing = db.execute(
        select(CaseFact).where(
            CaseFact.session_id == session_id,
            CaseFact.fact_key == fact_key,
        )
    ).scalar_one_or_none()

    from datetime import datetime
    now = datetime.utcnow()
    if existing is None:
        fact = CaseFact(
            id=fact_id,
            session_id=session_id,
            user_id=user_id,
            fact_key=fact_key,
            fact_value=fact_value,
            source_message_id=source_message_id,
            confidence=confidence,
            created_at=now,
            updated_at=now,
        )
        db.add(fact)
    else:
        existing.fact_value = fact_value
        existing.source_message_id = source_message_id
        existing.confidence = confidence
        existing.updated_at = now
        fact = existing
    db.commit()
    return fact


def list_facts_for_session(db: Session, session_id: str) -> list[CaseFact]:
    return db.execute(
        select(CaseFact).where(CaseFact.session_id == session_id).order_by(CaseFact.created_at.asc())
    ).scalars().all()


def delete_facts_for_session(db: Session, session_id: str) -> None:
    from sqlalchemy import delete as sql_delete
    db.execute(sql_delete(CaseFact).where(CaseFact.session_id == session_id))
    db.commit()