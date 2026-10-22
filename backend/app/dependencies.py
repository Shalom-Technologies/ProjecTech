from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from bson import ObjectId
from bson.errors import InvalidId
import jwt

from app.security import decode_access_token
from app.database import get_database

security_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme)
):
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    db = get_database()
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except InvalidId:
        raise HTTPException(status_code=401, detail="Invalid token")

    if user is None:
        raise HTTPException(status_code=401, detail="User not found")

    return user


async def require_verified_user(current_user: dict = Depends(get_current_user)):
    """Any signed-in user, who must also have confirmed their email address."""
    if not current_user.get("email_verified"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please confirm your email address first. Check your inbox, or ask for a new email from your dashboard.",
        )
    return current_user


def require_verified_role(*allowed_roles: str):
    """Like require_role, and the person must also have confirmed their email address."""
    base = require_role(*allowed_roles)

    async def checker(current_user: dict = Depends(base)):
        if not current_user.get("email_verified"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Please confirm your email address first. Check your inbox, or ask for a new email from your dashboard.",
            )
        return current_user

    return checker


def require_role(*allowed_roles: str):
    """
    Dependency factory for role-based access control.
    Usage: Depends(require_role("salesperson"))
    """
    async def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of these roles: {', '.join(allowed_roles)}"
            )
        return current_user

    return role_checker