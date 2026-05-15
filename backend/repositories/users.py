from sqlalchemy import select
from sqlalchemy.orm import Session
from entities.user import User


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


def get_user_by_id(db: Session, user_id: str) -> User | None:
    return db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()


def create_user(db: Session, user: User) -> User:
    db.add(user)
    db.commit()
    db.refresh(user)
    return user