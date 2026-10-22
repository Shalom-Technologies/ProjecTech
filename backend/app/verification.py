"""Email verification. A user must verify before applying, posting, paying or withdrawing."""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from app.config import settings
from app.email_client import send_verification_email
from app.mailer import send_or_record
from app.security import generate_reset_token, hash_reset_token

VERIFY_TOKEN_HOURS = 24
RESEND_COOLDOWN_SECONDS = 60


async def issue_verification_email(db, user: dict, is_welcome: bool = False, enforce_cooldown: bool = True) -> bool:
    """Creates a fresh link (older ones stop working) and emails it. Returns whether it was sent."""
    now = datetime.now(timezone.utc)

    if enforce_cooldown:
        last = await db.email_verifications.find_one({"user_id": user["_id"], "used": False})
        if last:
            created = last["created_at"]
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            wait = RESEND_COOLDOWN_SECONDS - (now - created).total_seconds()
            if wait > 0:
                raise HTTPException(
                    status_code=429,
                    detail=f"We just sent you an email. Please wait {int(wait) + 1} seconds before asking for another.",
                )

    token = generate_reset_token()
    await db.email_verifications.delete_many({"user_id": user["_id"]})
    await db.email_verifications.insert_one({
        "user_id": user["_id"],
        "token_hash": hash_reset_token(token),
        "expires_at": now + timedelta(hours=VERIFY_TOKEN_HOURS),
        "used": False,
        "created_at": now,
    })

    link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
    return await send_or_record(
        db, "verification",
        send_verification_email(user["email"], link, user["first_name"], is_welcome=is_welcome),
        to_email=user["email"], user_id=user["_id"],
    )


async def confirm_email(db, token: str):
    """Marks the email verified. Raises 400 for an unknown, used or expired link."""
    record = await db.email_verifications.find_one_and_update(
        {"token_hash": hash_reset_token(token), "used": False},
        {"$set": {"used": True, "used_at": datetime.now(timezone.utc)}},
    )
    invalid = HTTPException(
        status_code=400,
        detail="This confirmation link is invalid or has expired. Sign in and ask for a new one.",
    )
    if not record:
        raise invalid

    expires_at = record["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise invalid

    await db.users.update_one(
        {"_id": record["user_id"]},
        {"$set": {"email_verified": True, "email_verified_at": datetime.now(timezone.utc)}},
    )
