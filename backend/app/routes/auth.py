from fastapi import APIRouter, HTTPException, status, Request, Depends
from datetime import datetime, timezone

from app.database import get_database
from app.schemas import UserRegister, UserLogin, TokenResponse, UserResponse
from app.security import hash_password, verify_password, create_access_token
from app.rate_limit import limiter
from datetime import timedelta
from app.schemas import ForgotPasswordRequest, ResetPasswordRequest, VerifyEmailRequest
from app.verification import issue_verification_email, confirm_email
from app.mailer import send_or_record
from app.security import generate_reset_token, hash_reset_token, hash_password
from app.email_client import send_password_reset_email
from app.config import settings

from app.schemas import ChangePasswordRequest
from app.security import verify_password

from app.dependencies import get_current_user

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, user_data: UserRegister):
    db = get_database()

    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_doc = {
        "email": user_data.email,
        "password_hash": hash_password(user_data.password),
        "first_name": user_data.first_name,
        "last_name": user_data.last_name,
        "role": user_data.role,
        "created_at": datetime.now(timezone.utc),
        "wallet_balance": 0.0,
        "email_verified": False,
    }

    # Role-specific fields
    if user_data.role == "developer":
        user_doc["skills"] = user_data.skills or []
    else:  # salesperson
        user_doc["company_name"] = user_data.company_name

    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)

    token = create_access_token({"sub": user_id, "role": user_data.role})

    # Welcome + confirmation link. If it fails the account still works, and the dashboard
    # offers "resend" (the failure is recorded in email_failures).
    user_doc["_id"] = result.inserted_id
    await issue_verification_email(db, user_doc, is_welcome=True, enforce_cooldown=False)

    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user_id,
            email=user_doc["email"],
            first_name=user_doc["first_name"],
            last_name=user_doc["last_name"],
            role=user_doc["role"],
            created_at=user_doc["created_at"],
            email_verified=False,
        )
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, credentials: UserLogin):
    db = get_database()

    user = await db.users.find_one({"email": credentials.email})
    if not user or not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token({"sub": str(user["_id"]), "role": user["role"]})

    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=str(user["_id"]),
            email=user["email"],
            first_name=user["first_name"],
            last_name=user["last_name"],
            role=user["role"],
            created_at=user["created_at"],
            email_verified=bool(user.get("email_verified")),
        )
    )

@router.post("/forgot-password")
@limiter.limit("3/minute")
async def forgot_password(request: Request, data: ForgotPasswordRequest):
    db = get_database()
    user = await db.users.find_one({"email": data.email})

    # Always return the same response whether or not the email exists —
    # prevents attackers from using this endpoint to check registered emails
    generic_response = {"message": "If an account exists for this email, a reset link has been sent."}

    if not user:
        return generic_response

    token = generate_reset_token()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)

    # Invalidate any previous unused tokens for this user, then store the new one
    await db.password_resets.delete_many({"user_id": user["_id"]})
    await db.password_resets.insert_one({
        "user_id": user["_id"],
        "token_hash": hash_reset_token(token),
        "expires_at": expires_at,
        "used": False,
        "created_at": datetime.now(timezone.utc),
    })

    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"

    # The person always sees the same message, but a failure is logged and recorded
    # (email_failures) so a broken email setup does not go unnoticed.
    await send_or_record(
        db, "password_reset",
        send_password_reset_email(user["email"], reset_link, user["first_name"]),
        to_email=user["email"], user_id=user["_id"],
    )

    return generic_response


@router.post("/reset-password")
@limiter.limit("10/minute")
async def reset_password(request: Request, data: ResetPasswordRequest):
    db = get_database()

    # Claim the token in one step so it can only ever be used once, even if the link is
    # submitted twice at the same moment.
    reset_record = await db.password_resets.find_one_and_update(
        {"token_hash": hash_reset_token(data.token), "used": False},
        {"$set": {"used": True, "used_at": datetime.now(timezone.utc)}},
    )

    if not reset_record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    expires_at = reset_record["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    await db.users.update_one(
        {"_id": reset_record["user_id"]},
        {"$set": {"password_hash": hash_password(data.new_password), "updated_at": datetime.now(timezone.utc)}}
    )

    return {"message": "Password reset successfully. You can now log in with your new password."}

@router.post("/change-password")
@limiter.limit("5/minute")
async def change_password(
    request: Request,
    data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user)
):
    if not verify_password(data.current_password, current_user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    db = get_database()
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {"$set": {"password_hash": hash_password(data.new_password), "updated_at": datetime.now(timezone.utc)}}
    )
    return {"message": "Password changed successfully"}


@router.post("/verify-email")
@limiter.limit("20/minute")
async def verify_email(request: Request, data: VerifyEmailRequest):
    """Called by the confirmation page when someone opens the link in their email."""
    await confirm_email(get_database(), data.token)
    return {"message": "Your email address is confirmed."}


@router.post("/resend-verification")
@limiter.limit("5/minute")
async def resend_verification(request: Request, current_user: dict = Depends(get_current_user)):
    if current_user.get("email_verified"):
        raise HTTPException(status_code=400, detail="Your email address is already confirmed.")

    sent = await issue_verification_email(get_database(), current_user)
    if not sent:
        raise HTTPException(
            status_code=502,
            detail="We couldn't send the email just now. Please try again in a few minutes.",
        )
    return {"message": f"We sent a confirmation link to {current_user['email']}."}
