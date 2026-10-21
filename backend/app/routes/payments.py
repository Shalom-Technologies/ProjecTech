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
from app.wallet import refund_withdrawal
from app.pricing import get_agreed_amount, check_amount_limits, round_money


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

    # The invoice is always for the agreed price. It can only change through a
    # price proposal that the assigned developer has approved.
    amount = get_agreed_amount(project)

    if payment_data.amount is not None and round_money(payment_data.amount) != amount:
        raise HTTPException(
            status_code=400,
            detail=(
                f"The agreed price is {settings.CURRENCY} {amount:,.2f}. "
                "To invoice a different amount, request a price change and wait for the developer to approve it."
            ),
        )

    proposal = project.get("price_proposal")
    if proposal and proposal["status"] == "pending":
        raise HTTPException(
            status_code=400,
            detail="A price change is waiting for the developer's approval. Payment opens once they respond.",
        )

    check_amount_limits(amount)

    # Never take payment twice for one project
    if await db.transactions.find_one({"project_id": project["_id"], "status": "success"}):
        raise HTTPException(status_code=400, detail="This project has already been paid for")

    # An unpaid link already exists: hand the same one back instead of making another.
    pending = await db.transactions.find_one({"project_id": project["_id"], "status": "pending"})
    if pending:
        if pending["total_amount"] == amount and pending.get("paystack_authorization_url"):
            return {
                "transaction_id": pending["transaction_id"],
                "authorization_url": pending["paystack_authorization_url"],
                "reference": pending["paystack_reference"],
                "amount": amount,
            }
        # Stale (older price, or created before links were stored): retire it.
        await db.transactions.update_many(
            {"project_id": project["_id"], "status": "pending"},
            {"$set": {"status": "cancelled", "cancelled_reason": "replaced"}}
        )

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
        "currency": settings.CURRENCY,
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
            amount_kobo=int(round(amount * 100)),
            metadata={
                "transaction_id": transaction_id,
                "project_id": str(project["_id"]),
            },
            callback_url=f"{settings.FRONTEND_URL}/payment/verify",
            currency=settings.CURRENCY,
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
            "paystack_authorization_url": data["authorization_url"],
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

    if transaction["status"] == "cancelled":
        if data["status"] != "success":
            raise HTTPException(status_code=400, detail="This payment link is no longer valid. Ask for a new one.")

        outcome = await _handle_payment_on_cancelled(db, transaction)
        if outcome == "accepted":
            return {
                "status": "success",
                "message": "Payment verified successfully",
                "transaction_id": transaction["transaction_id"],
            }
        raise HTTPException(
            status_code=400,
            detail=(
                "This payment link was replaced after the project's price changed, so the payment "
                "could not be applied to the project. It will be refunded. Please use the new link."
            ),
        )

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


async def _handle_payment_on_cancelled(db, transaction: dict) -> str:
    """
    A client paid a link that ProjecTech had already retired (usually because the
    price changed after the link was sent). Paystack cannot switch such a link off.

    - If the amount paid equals the project's current agreed price and the project
      is not already funded, the payment is exactly what we were waiting for, so
      it is accepted as the funding.
    - Otherwise it is NOT counted towards the project (the developer's pay depends
      on the price). It is flagged for refund and the salesperson is told.

    Safe to call repeatedly for the same payment. Returns "accepted" or "flagged".
    """
    if transaction.get("paid_while_cancelled"):
        return "flagged"  # already handled and the salesperson already told

    project = await db.projects.find_one({"_id": transaction["project_id"]})
    already_funded = await db.transactions.find_one(
        {"project_id": transaction["project_id"], "status": "success"}
    ) is not None

    if project and not already_funded and round_money(transaction["total_amount"]) == get_agreed_amount(project):
        await _mark_transaction_successful(db, transaction)
        await db.transactions.update_one(
            {"_id": transaction["_id"]},
            {"$set": {"accepted_after_cancel": True}}
        )
        # Another unpaid link for this project must not be payable any more.
        await db.transactions.update_many(
            {"project_id": transaction["project_id"], "status": "pending"},
            {"$set": {"status": "cancelled", "cancelled_reason": "project_already_funded"}}
        )
        logger.info(
            f"Payment on retired link {transaction['transaction_id']} matched the agreed price: accepted as funding"
        )
        return "accepted"

    await db.transactions.update_one(
        {"_id": transaction["_id"]},
        {"$set": {
            "paid_while_cancelled": True,
            "needs_refund": True,
            "paid_at": datetime.now(timezone.utc),
        }}
    )
    logger.error(
        f"Payment received on cancelled transaction {transaction['transaction_id']} "
        f"(ref {transaction.get('paystack_reference')}, {settings.CURRENCY} {transaction['total_amount']:,.2f}): "
        f"refund required"
    )

    if project:
        reason = "the project is already funded" if already_funded else "the price changed after that link was sent"
        await db.notifications.insert_one({
            "user_id": project["salesperson_id"],
            "type": "payment_needs_refund",
            "title": "Client paid an outdated link",
            "description": (
                f"{project.get('client_email', 'The client')} paid {settings.CURRENCY} "
                f"{transaction['total_amount']:,.2f} for '{project['title']}', but {reason}. "
                f"That payment will be refunded; ask the client to use the current link."
            ),
            "project_id": project["_id"],
            "is_read": False,
            "created_at": datetime.now(timezone.utc),
        })
    return "flagged"


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
        if transaction and transaction["status"] == "cancelled":
            await _handle_payment_on_cancelled(db, transaction)
        elif transaction and transaction["status"] != "success":
            await _mark_transaction_successful(db, transaction)

    elif event in ("transfer.success", "transfer.failed", "transfer.reversed"):
        await _handle_transfer_event(db, event, data)

    # Always return 200 quickly so Paystack doesn't retry unnecessarily
    return {"status": "received"}


async def _handle_transfer_event(db, event: str, data: dict):
    """
    Settles a withdrawal once Paystack reports the final outcome of the transfer.

    Every step is a conditional update on the withdrawal's current status, so if
    Paystack sends the same event twice (or sends failed then reversed), the
    wallet is refunded at most once.
    """
    reference = data.get("reference")
    if not reference:
        return

    if event == "transfer.success":
        await db.wallet_transactions.update_one(
            {"paystack_reference": reference, "transaction_type": "withdrawal", "status": "pending"},
            {"$set": {"status": "success", "settled_at": datetime.now(timezone.utc)}},
        )
        return

    # transfer.failed: only a still-pending withdrawal can fail.
    # transfer.reversed: money was sent, then came back, so success -> reversed is valid too.
    new_status = "failed" if event == "transfer.failed" else "reversed"
    allowed_from = ["pending"] if event == "transfer.failed" else ["pending", "success"]

    await refund_withdrawal(db, reference, new_status, allowed_from)


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
            "description": f"{settings.CURRENCY} {amount:,.2f} has been added to your wallet",
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
    project_oid = to_object_id(project_id)
    transaction = await db.transactions.find_one({
        "project_id": project_oid,
        "status": "success",
    })

    response = {
        "is_funded": transaction is not None,
        "transaction_id": None,
        "escrow_status": None,
    }

    # Only the two people on the project may see the payment reference
    if transaction and current_user["_id"] in (
        transaction["salesperson_id"],
        transaction["developer_id"],
    ):
        response["transaction_id"] = transaction["transaction_id"]
        response["escrow_status"] = transaction["escrow_status"]

    return response