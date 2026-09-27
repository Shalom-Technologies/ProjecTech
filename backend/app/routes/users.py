from fastapi import APIRouter, Depends, HTTPException, Query, Request
from datetime import datetime, timezone
import httpx
import logging

from app.database import get_database
from app.dependencies import get_current_user
from app.schemas import UserProfileUpdate, BankAccountAdd, WithdrawRequest
from app.paystack_client import paystack
from app.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/users", tags=["Users"])


# ============================================================================
# PROFILE
# ============================================================================

@router.get("/profile")
async def get_profile(current_user: dict = Depends(get_current_user)):
    return {
        "id": str(current_user["_id"]),
        "email": current_user["email"],
        "first_name": current_user["first_name"],
        "last_name": current_user["last_name"],
        "role": current_user["role"],
        "phone": current_user.get("phone"),
        "bio": current_user.get("bio"),
        "location": current_user.get("location"),
        "skills": current_user.get("skills") if current_user["role"] == "developer" else None,
        "company_name": current_user.get("company_name") if current_user["role"] == "salesperson" else None,
        "wallet_balance": current_user.get("wallet_balance", 0.0),
        "total_earned": current_user.get("total_earned", 0.0),
        "average_rating": current_user.get("average_rating"),
        "total_reviews": current_user.get("total_reviews", 0),
        "completed_projects": current_user.get("completed_projects", 0),
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

@router.get("/wallet")
async def get_wallet(current_user: dict = Depends(get_current_user)):
    return {
        "wallet_balance": current_user.get("wallet_balance", 0.0),
        "total_earned": current_user.get("total_earned", 0.0),
        "currency": "NGN",
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
# BANK ACCOUNT (required before withdrawing)
# ============================================================================

@router.post("/bank-account")
async def add_bank_account(
    bank_data: BankAccountAdd,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()

    # Resolve account name with Paystack (confirms account number is real & matches bank)
    try:
        resolved = await paystack.resolve_account(bank_data.account_number, bank_data.bank_code)
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=400, detail="Could not verify bank account details")

    account_name = resolved["data"]["account_name"]

    try:
        recipient = await paystack.create_transfer_recipient(
            name=account_name,
            account_number=bank_data.account_number,
            bank_code=bank_data.bank_code,
        )
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=400, detail="Could not register bank account for payouts")

    await db.users.update_one(
        {"_id": current_user["_id"]},
        {"$set": {
            "bank_account": {
                "account_name": account_name,
                "account_number": bank_data.account_number,
                "bank_code": bank_data.bank_code,
            },
            "paystack_recipient_code": recipient["data"]["recipient_code"],
        }}
    )

    return {"message": "Bank account added successfully", "account_name": account_name}


# ============================================================================
# WITHDRAW (fund transfer out of the platform wallet to user's bank)
# ============================================================================

@router.post("/wallet/withdraw")
@limiter.limit("5/minute")
async def withdraw_funds(
    request: Request,   # <-- this was missing
    withdraw_data: WithdrawRequest,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()

    if withdraw_data.amount > current_user.get("wallet_balance", 0.0):
        raise HTTPException(status_code=400, detail="Insufficient wallet balance")

    recipient_code = current_user.get("paystack_recipient_code")
    if not recipient_code:
        raise HTTPException(status_code=400, detail="Please add a bank account before withdrawing")

    # Deduct first to prevent double-withdraw race conditions, refund on failure
    result = await db.users.update_one(
        {"_id": current_user["_id"], "wallet_balance": {"$gte": withdraw_data.amount}},
        {"$inc": {"wallet_balance": -withdraw_data.amount}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Insufficient wallet balance")

    try:
        transfer = await paystack.initiate_transfer(
            amount_kobo=int(withdraw_data.amount * 100),
            recipient_code=recipient_code,
            reason="Wallet withdrawal",
        )
    except httpx.HTTPStatusError as e:
        # Refund on failure
        await db.users.update_one(
            {"_id": current_user["_id"]},
            {"$inc": {"wallet_balance": withdraw_data.amount}}
        )
        logger.error(f"Paystack transfer failed: {e.response.text}")
        raise HTTPException(status_code=502, detail="Withdrawal failed, funds have been refunded to your wallet")

    await db.wallet_transactions.insert_one({
        "user_id": current_user["_id"],
        "transaction_type": "withdrawal",
        "amount": -withdraw_data.amount,
        "description": "Wallet withdrawal to bank account",
        "paystack_transfer_code": transfer["data"]["transfer_code"],
        "created_at": datetime.now(timezone.utc),
    })

    return {
        "message": "Withdrawal initiated successfully",
        "amount": withdraw_data.amount,
        "transfer_code": transfer["data"]["transfer_code"],
    }