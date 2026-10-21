from passlib.context import CryptContext
from datetime import datetime, timedelta, timezone
import jwt
from app.config import settings
import hashlib
import secrets

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    # bcrypt has a hard 72-byte limit
    truncated = password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
    return pwd_context.hash(truncated)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    truncated = plain_password.encode("utf-8")[:72].decode("utf-8", errors="ignore")
    return pwd_context.verify(truncated, hashed_password)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


def generate_reset_token() -> str:
    return secrets.token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    """Only this hash is stored. The real token exists only in the email link, so a copy of
    the database cannot be used to reset anyone's password."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()