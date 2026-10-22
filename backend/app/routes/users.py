from fastapi import APIRouter, Depends, HTTPException, Query, Request
from datetime import datetime, timezone
import httpx
import logging
import uuid

from app.config import settings
from app.database import get_database
from app.dependencies import get_current_user, require_verified_user
from app.schemas import UserProfileUpdate, PayoutAccountAdd, WithdrawRequest
from app.paystack_client import paystack
from app.rate_limit import limiter
from app.wallet import refund_withdrawal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/users", tags=["Users"])


# ============================================================================
# PROFILE
# ============================================================================

@router.get("/profile")
async def get_profile(current_user: dict = Depends(get_current_user)):
    # Counted from the projects themselves, so it is always right: it follows a
    # project being completed (or reopened) and needs no separate counter to keep in sync.
    db = get_database()
    owner_field = "assigned_to" if current_user["role"] == "developer" else "salesperson_id"
    completed_projects = await db.projects.count_documents(
        {owner_field: current_user["_id"], "status": "completed"}
    )

    return {
        "id": str(current_user["_id"]),
        "email": current_user["email"],
        "first_name": current_user["first_name"],
        "last_name": current_user["last_name"],
        "role": current_user["role"],
        "email_verified": bool(current_user.get("email_verified")),
        "phone": current_user.get("phone"),
        "bio": current_user.get("bio"),
        "location": current_user.get("location"),
        "skills": current_user.get("skills") if current_user["role"] == "developer" else None,
        "company_name": current_user.get("company_name") if current_user["role"] == "salesperson" else None,
        "wallet_balance": current_user.get("wallet_balance", 0.0),
        "total_earned": current_user.get("total_earned", 0.0),
        "average_rating": current_user.get("average_rating"),
        "total_reviews": current_user.get("total_reviews", 0),
        "completed_projects": completed_projects,
        "created_at": current_user["created_at"],
    }


@router.put("/profile")
async def update_profile(
    updates: UserProfileUpdate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()

    update_data = updates.model_dump(exclude_unset=True, exclude_none=True)

    # Prevent role-crossover pollution
    if current_user["role"] != "developer":
        update_data.pop("skills", None)
    if current_user["role"] != "salesperson":
        update_data.pop("company_name", None)

    if not update_data:
        raise HTTPException(status_code=400, detail="No valid fields provided to update")

    update_data["updated_at"] = datetime.now(timezone.utc)

    await db.users.update_one({"_id": current_user["_id"]}, {"$set": update_data})

    return {"message": "Profile updated successfully"}


# ============================================================================
# WALLET
# ============================================================================

def _mask_phone(phone: str) -> str:
    # 0712345678 -> 07******78
    return f"{phone[:2]}{'*' * (len(phone) - 4)}{phone[-2:]}"


@router.get("/wallet")
async def get_wallet(current_user: dict = Depends(get_current_user)):
    payout = current_user.get("payout_account")
    return {
        "wallet_balance": current_user.get("wallet_balance", 0.0),
        # Released earnings still inside the payout hold. They become withdrawable on their own.
        "pending_balance": max(round(current_user.get("pending_balance", 0.0), 2), 0.0),
        "total_earned": current_user.get("total_earned", 0.0),
        "currency": settings.CURRENCY,
        "payout_account": (
            {
                "account_name": payout["account_name"],
                "phone_number": _mask_phone(payout["phone_number"]),
            }
            if payout
            else None
        ),
    }


@router.get("/transactions")
async def get_wallet_transactions(
    current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
):
    db = get_database()

    query = {"user_id": current_user["_id"]}
    total = await db.wallet_transactions.count_documents(query)
    skip = (page - 1) * per_page

    cursor = db.wallet_transactions.find(query).sort("created_at", -1).skip(skip).limit(per_page)
    transactions = await cursor.to_list(length=per_page)

    return {
        "data": [
            {
                "id": str(t["_id"]),
                "transaction_type": t["transaction_type"],
                "amount": t["amount"],
                # Older entries have no status; they were already complete.
                "status": t.get("status", "success"),
                "available_at": t.get("available_at"),
                "description": t.get("description"),
                "created_at": t["created_at"],
            }
            for t in transactions
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


# ============================================================================
# PAYOUT ACCOUNT (M-Pesa number, required before withdrawing)
# ============================================================================

@router.post("/payout-account")
async def add_payout_account(
    payout_data: PayoutAccountAdd,
    current_user: dict = Depends(require_verified_user)
):
    db = get_database()

    account_name = f"{current_user['first_name']} {current_user['last_name']}"

    try:
        recipient = await paystack.create_mpesa_recipient(
            name=account_name,
            phone_number=payout_data.phone_number,
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"Paystack recipient creation failed: {e.response.text}")
        raise HTTPException(status_code=400, detail="Could not register this M-Pesa number for payouts")

    await db.users.update_one(
        {"_id": current_user["_id"]},
        {"$set": {
            "payout_account": {
                "method": "mpesa",
                "account_name": account_name,
                "phone_number": payout_data.phone_number,
                "currency": settings.CURRENCY,
            },
            "paystack_recipient_code": recipient["data"]["recipient_code"],
        }}
    )

    return {
        "message": "M-Pesa payout number saved",
        "account_name": account_name,
        "phone_number": _mask_phone(payout_data.phone_number),
    }


# ============================================================================
# WITHDRAW (fund transfer out of the platform wallet to the user's M-Pesa)
# ============================================================================

@router.post("/wallet/withdraw")
@limiter.limit("5/minute")
async def withdraw_funds(
    request: Request,
    withdraw_data: WithdrawRequest,
    current_user: dict = Depends(require_verified_user)
):
    db = get_database()

    # Only recipients created through the M-Pesa flow are usable. Anything saved
    # by the old bank-account flow has no payout_account and must be re-added.
    recipient_code = current_user.get("paystack_recipient_code")
    if not current_user.get("payout_account") or not recipient_code:
        raise HTTPException(status_code=400, detail="Please add your M-Pesa number before withdrawing")

    amount = withdraw_data.amount
    if amount > current_user.get("wallet_balance", 0.0):
        raise HTTPException(status_code=400, detail="Insufficient wallet balance")

    # Deduct first (atomically) to prevent double-withdraw race conditions
    result = await db.users.update_one(
        {"_id": current_user["_id"], "wallet_balance": {"$gte": amount}},
        {"$inc": {"wallet_balance": -amount}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Insufficient wallet balance")

    # Our own reference travels to Paystack and comes back in the transfer.*
    # webhooks, which is how the final outcome finds this ledger entry.
    # Paystack requires lowercase letters, digits, "_" or "-", 16-50 characters.
    reference = f"wd_{uuid.uuid4().hex}"

    # Record the withdrawal as pending BEFORE calling Paystack, so a webhook
    # that arrives immediately can always find it.
    await db.wallet_transactions.insert_one({
        "user_id": current_user["_id"],
        "transaction_type": "withdrawal",
        "amount": -amount,
        "status": "pending",
        "paystack_reference": reference,
        "description": "Withdrawal to M-Pesa",
        "created_at": datetime.now(timezone.utc),
    })

    try:
        transfer = await paystack.initiate_transfer(
            amount_kobo=int(round(amount * 100)),
            recipient_code=recipient_code,
            reason="Wallet withdrawal",
            reference=reference,
        )
    except httpx.HTTPStatusError as e:
        # Paystack rejected the request: nothing was sent, so give the money back.
        logger.error(f"Paystack transfer rejected: {e.response.text}")
        await refund_withdrawal(db, reference, "failed", ["pending"])
        raise HTTPException(status_code=502, detail="Withdrawal failed, funds have been returned to your wallet")
    except httpx.RequestError as e:
        # Timeout or network error: we cannot know whether Paystack sent the money.
        # Leave the withdrawal pending; the transfer webhook will settle it.
        logger.error(f"Paystack transfer outcome unknown for {reference}: {e}")
        return {
            "message": "Your withdrawal is being processed. Check your transaction history for the result.",
            "status": "pending",
            "amount": amount,
        }

    transfer_data = transfer.get("data", {})

    if transfer_data.get("status") == "otp":
        # Paystack is waiting for an OTP that no one can enter, so it will never complete.
        logger.error(f"Transfer {reference} needs OTP confirmation; disable it in the Paystack dashboard")
        await refund_withdrawal(db, reference, "failed", ["pending"])
        raise HTTPException(status_code=503, detail="Withdrawals are temporarily unavailable. Your funds are safe in your wallet.")

    await db.wallet_transactions.update_one(
        {"paystack_reference": reference, "transaction_type": "withdrawal"},
        {"$set": {"paystack_transfer_code": transfer_data.get("transfer_code")}}
    )

    # Stays "pending" until the transfer.success / transfer.failed webhook arrives.
    return {
        "message": "Withdrawal submitted. It will show as complete once M-Pesa confirms it.",
        "status": "pending",
        "amount": amount,
        "reference": reference,
    }
