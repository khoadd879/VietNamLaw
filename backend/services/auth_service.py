from uuid import uuid4
from core.security import create_access_token, hash_password, verify_password
from entities.user import User
from repositories.users import create_user, get_user_by_email, get_user_by_id


def register_user(db, email: str, password: str) -> User:
    user = User(id=str(uuid4()), email=email, password_hash=hash_password(password))
    return create_user(db, user)


def authenticate_user(db, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_token_for_user(user: User) -> str:
    return create_access_token(str(user.id))