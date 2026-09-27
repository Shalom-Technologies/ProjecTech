from fastapi import APIRouter, Depends, HTTPException, Request, status
from datetime import datetime, timezone
from bson import ObjectId
from bson.errors import InvalidId
import httpx
import hmac
import hashlib
import uuid
import logging

from app.database import get_database
from app.dependencies import get_current_user, require_role
from app.schemas import PaymentInitialize, PaymentVerify
from app.paystack_client import paystack
from app.config import settings
from app.rate_limit import limiter


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["Payments"])


def to_object_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ID format")


# ============================================================================
# INITIALIZE PAYMENT — salesperson (project owner) only
# ============================================================================

@router.post("/initialize")
@limiter.limit("10/minute")
async def initialize_payment(
    request: Request,
    payment_data: PaymentInitialize,
    current_user: dict = Depends(require_role("salesperson"))
):

    db = get_database()
    project = await db.projects.find_one({"_id": to_object_id(payment_data.project_id)})

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project["salesperson_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Only the project owner can initiate payment")

    if not project.get("assigned_to"):
        raise HTTPException(status_code=400, detail="Project has no assigned developer yet")

    # Prevent double payment
    existing = await db.transactions.find_one({
        "project_id": project["_id"],
        "status": {"$in": ["pending", "success"]}
    })
    if existing:
        raise HTTPException(status_code=400, detail="A payment already exists for this project")

    amount = payment_data.amount
    developer_amount = round(amount * settings.DEVELOPER_COMMISSION, 2)
    salesperson_amount = round(amount * settings.SALESPERSON_COMMISSION, 2)
    platform_amount = round(amount - developer_amount - salesperson_amount, 2)  # remainder avoids rounding drift

    transaction_id = f"TXN_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"

    transaction_doc = {
        "transaction_id": transaction_id,
        "project_id": project["_id"],
        "salesperson_id": current_user["_id"],
        "developer_id": project["assigned_to"],
        "total_amount": amount,
        "currency": project.get("currency", "NGN"),
        "commission_breakdown": {
            "developer_amount": developer_amount,
            "salesperson_amount": salesperson_amount,
            "platform_amount": platform_amount,
        },
        "paystack_reference": None,
        "status": "pending",          # pending -> success | failed
        "escrow_status": "held",      # held -> released | refunded
        "created_at": datetime.now(timezone.utc),
    }

    result = await db.transactions.insert_one(transaction_doc)

    try:
        paystack_response = await paystack.initialize_transaction(
            email=project["client_email"],
            amount_kobo=int(amount * 100),
            metadata={
                "transaction_id": transaction_id,
                "project_id": str(project["_id"]),
            },
            callback_url=f"{settings.FRONTEND_URL}/payment/verify",
        )
    except httpx.HTTPStatusError as e:
        await db.transactions.update_one({"_id": result.inserted_id}, {"$set": {"status": "failed"}})
        logger.error(f"Paystack init failed: {e.response.text}")
        raise HTTPException(status_code=502, detail="Failed to initialize payment with Paystack")

    data = paystack_response["data"]

    await db.transactions.update_one(
        {"_id": result.inserted_id},
        {"$set": {
            "paystack_reference": data["reference"],
            "paystack_access_code": data["access_code"],
        }}
    )

    return {
        "transaction_id": transaction_id,
        "authorization_url": data["authorization_url"],
        "reference": data["reference"],
        "amount": amount,
    }


# ============================================================================
# VERIFY PAYMENT
# ============================================================================

@router.post("/verify")
async def verify_payment(verify_data: PaymentVerify):
    db = get_database()

    transaction = await db.transactions.find_one({"paystack_reference": verify_data.reference})
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if transaction["status"] == "success":
        return {"status": "success", "message": "Already verified", "transaction_id": transaction["transaction_id"]}

    try:
        paystack_response = await paystack.verify_transaction(verify_data.reference)
    except httpx.HTTPStatusError as e:
        logger.error(f"Paystack verify failed: {e.response.text}")
        raise HTTPException(status_code=502, detail="Failed to verify payment with Paystack")

    data = paystack_response["data"]

    if data["status"] != "success":
        await db.transactions.update_one({"_id": transaction["_id"]}, {"$set": {"status": "failed"}})
        raise HTTPException(status_code=400, detail=f"Payment not successful: {data['status']}")

    await _mark_transaction_successful(db, transaction)

    return {
        "status": "success",
        "message": "Payment verified successfully",
        "transaction_id": transaction["transaction_id"],
    }


async def _mark_transaction_successful(db, transaction: dict):
    """
    Shared logic: called by both /verify and the webhook.
    Money stays in escrow (held) until the project is marked complete —
    it is NOT released to wallets here.
    """
    await db.transactions.update_one(
        {"_id": transaction["_id"]},
        {"$set": {
            "status": "success",
            "escrow_status": "held",
            "paid_at": datetime.now(timezone.utc),
        }}
    )
    logger.info(f"Transaction {transaction['transaction_id']} marked successful, funds held in escrow")


# ============================================================================
# WEBHOOK — Paystack calls this server-to-server
# ============================================================================

@router.post("/webhook")
async def paystack_webhook(request: Request):
    db = get_database()
    body = await request.body()
    signature = request.headers.get("x-paystack-signature", "")

    expected_signature = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode("utf-8"),
        body,
        hashlib.sha512
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, signature):
        logger.warning("Invalid Paystack webhook signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    event = payload.get("event")
    data = payload.get("data", {})

    if event == "charge.success":
        reference = data.get("reference")
        transaction = await db.transactions.find_one({"paystack_reference": reference})
        if transaction and transaction["status"] != "success":
            await _mark_transaction_successful(db, transaction)

    # Always return 200 quickly so Paystack doesn't retry unnecessarily
    return {"status": "received"}


# ============================================================================
# RELEASE ESCROW — triggered on project completion
# ============================================================================

@router.post("/{transaction_id}/release")
async def release_escrow(
    transaction_id: str,
    current_user: dict = Depends(require_role("salesperson"))
):
    """
    Releases held funds to developer & salesperson wallets.
    Only the salesperson who owns the project can trigger this,
    and only once the project is marked 'completed'.
    """
    db = get_database()
    transaction = await db.transactions.find_one({"transaction_id": transaction_id})

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if transaction["salesperson_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Not authorized for this transaction")

    if transaction["status"] != "success":
        raise HTTPException(status_code=400, detail="Payment has not been confirmed yet")

    if transaction["escrow_status"] != "held":
        raise HTTPException(status_code=400, detail=f"Funds already {transaction['escrow_status']}")

    project = await db.projects.find_one({"_id": transaction["project_id"]})
    if not project or project["status"] != "completed":
        raise HTTPException(status_code=400, detail="Project must be marked completed before funds are released")

    breakdown = transaction["commission_breakdown"]

    # Credit wallets
    await db.users.update_one(
        {"_id": transaction["developer_id"]},
        {"$inc": {"wallet_balance": breakdown["developer_amount"], "total_earned": breakdown["developer_amount"]}}
    )
    await db.users.update_one(
        {"_id": transaction["salesperson_id"]},
        {"$inc": {"wallet_balance": breakdown["salesperson_amount"], "total_earned": breakdown["salesperson_amount"]}}
    )

    await db.transactions.update_one(
        {"_id": transaction["_id"]},
        {"$set": {"escrow_status": "released", "released_at": datetime.now(timezone.utc)}}
    )

    # Wallet ledger entries
    for user_id, amount, desc in [
        (transaction["developer_id"], breakdown["developer_amount"], "Project earnings"),
        (transaction["salesperson_id"], breakdown["salesperson_amount"], "Sales commission"),
    ]:
        await db.wallet_transactions.insert_one({
            "user_id": user_id,
            "transaction_type": "commission",
            "amount": amount,
            "related_transaction_id": transaction["_id"],
            "description": desc,
            "created_at": datetime.now(timezone.utc),
        })

    # Notifications
    for user_id, amount in [
        (transaction["developer_id"], breakdown["developer_amount"]),
        (transaction["salesperson_id"], breakdown["salesperson_amount"]),
    ]:
        await db.notifications.insert_one({
            "user_id": user_id,
            "type": "payment_confirmed",
            "title": "Payment released",
            "description": f"KES{amount:,.2f} has been added to your wallet",
            "is_read": False,
            "created_at": datetime.now(timezone.utc),
        })

    return {"message": "Escrow released successfully", "breakdown": breakdown}


# ============================================================================
# GET TRANSACTION DETAILS
# ============================================================================

@router.get("/{transaction_id}")
async def get_transaction(transaction_id: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    transaction = await db.transactions.find_one({"transaction_id": transaction_id})

    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if current_user["_id"] not in (transaction["developer_id"], transaction["salesperson_id"]):
        raise HTTPException(status_code=403, detail="Not authorized to view this transaction")

    return {
        "transaction_id": transaction["transaction_id"],
        "project_id": str(transaction["project_id"]),
        "total_amount": transaction["total_amount"],
        "currency": transaction["currency"],
        "status": transaction["status"],
        "escrow_status": transaction["escrow_status"],
        "commission_breakdown": transaction["commission_breakdown"],
        "created_at": transaction["created_at"],
    }

@router.get("/project/{project_id}/status")
async def get_project_payment_status(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    transaction = await db.transactions.find_one({
        "project_id": to_object_id(project_id),
        "status": "success",
    })

    return {"is_funded": transaction is not None}