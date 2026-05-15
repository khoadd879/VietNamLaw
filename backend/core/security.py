from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.hash import sha256_crypt
from core.config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET_KEY


def hash_password(password: str) -> str:
    return sha256_crypt.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return sha256_crypt.verify(password, password_hash)


def create_access_token(user_id: str) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": user_id, "exp": expires_at}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)