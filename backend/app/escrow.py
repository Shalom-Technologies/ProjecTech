from datetime import datetime, timedelta, timezone
import logging

from app.config import settings
from app.pricing import round_money

logger = logging.getLogger(__name__)


def split_amount(amount: float) -> dict:
    """Divide an amount between developer, salesperson and platform."""
    developer = round(amount * settings.DEVELOPER_COMMISSION, 2)
    salesperson = round(amount * settings.SALESPERSON_COMMISSION, 2)
    platform = round(amount - developer - salesperson, 2)  # remainder avoids rounding drift
    return {
        "developer_amount": developer,
        "salesperson_amount": salesperson,
        "platform_amount": platform,
    }


async def settle_escrow(db, transaction: dict, refund_amount: float = 0.0):
    """
    Settles held money exactly once: pays it out, refunds it, or splits it.

    refund_amount = 0            -> everything is released to the wallets
    0 < refund_amount < total    -> that part is marked refunded to the client, the rest is
                                    released, with the commission split applied to what remains
    refund_amount = total        -> everything is marked refunded, nothing is paid out

    This only RECORDS a refund. The money itself goes back to the client from the Paystack
    dashboard, which is done by a person before this is called.

    The first step is one conditional update on the transaction ("held" -> settled), so
    however many times this runs for the same payment (a double click, two servers, a retry),
    only one call gets to pay out. Returns None if the money was already settled.
    """
    total = round_money(transaction["total_amount"])
    refund = round_money(refund_amount)
    if refund < 0 or refund > total:
        raise ValueError("The refund must be between 0 and the payment total")

    fully_refunded = refund >= total
    now = datetime.now(timezone.utc)

    claimed = await db.transactions.find_one_and_update(
        {"_id": transaction["_id"], "status": "success", "escrow_status": "held"},
        {"$set": {
            "escrow_status": "refunded" if fully_refunded else "released",
            # A fully refunded payment no longer funds the project, so the project can be
            # reopened and paid again. A partly refunded one stays "success".
            **({"status": "refunded"} if fully_refunded else {}),
            "settled_at": now,
            "refunded_amount": refund,
        }},
    )
    if not claimed:
        return None  # not held (already settled), or never paid

    if fully_refunded:
        logger.info(f"Escrow {transaction['transaction_id']} fully refunded ({refund})")
        return {"outcome": "refunded", "refunded": refund, "breakdown": None}

    breakdown = (
        transaction["commission_breakdown"] if refund == 0 else split_amount(round_money(total - refund))
    )
    await db.transactions.update_one(
        {"_id": transaction["_id"]},
        {"$set": {"released_at": now, "final_breakdown": breakdown}},
    )

    await _credit(db, transaction["developer_id"], breakdown["developer_amount"], "Project earnings", transaction, now)
    await _credit(db, transaction["salesperson_id"], breakdown["salesperson_amount"], "Sales commission", transaction, now)

    logger.info(f"Escrow {transaction['transaction_id']} released (refunded {refund})")
    return {"outcome": "released", "refunded": refund, "breakdown": breakdown}


async def _credit(db, user_id, amount: float, description: str, transaction: dict, now: datetime):
    """Add released money to a user. It waits in 'pending' for the payout hold, then becomes withdrawable."""
    if amount <= 0:
        return

    hold_days = settings.PAYOUT_HOLD_DAYS
    if hold_days > 0:
        available_at = now + timedelta(days=hold_days)
        await db.wallet_transactions.insert_one({
            "user_id": user_id,
            "transaction_type": "commission",
            "amount": amount,
            "status": "held",
            "available_at": available_at,
            "related_transaction_id": transaction["_id"],
            "description": description,
            "created_at": now,
        })
        await db.users.update_one(
            {"_id": user_id},
            {"$inc": {"pending_balance": amount, "total_earned": amount}},
        )
        availability = f" It can be withdrawn from {available_at:%d %b %Y}."
    else:
        await db.wallet_transactions.insert_one({
            "user_id": user_id,
            "transaction_type": "commission",
            "amount": amount,
            "status": "success",
            "related_transaction_id": transaction["_id"],
            "description": description,
            "created_at": now,
        })
        await db.users.update_one(
            {"_id": user_id},
            {"$inc": {"wallet_balance": amount, "total_earned": amount}},
        )
        availability = ""

    await db.notifications.insert_one({
        "user_id": user_id,
        "type": "payment_confirmed",
        "title": "Payment released",
        "description": f"{settings.CURRENCY} {amount:,.2f} was released to you.{availability}",
        "is_read": False,
        "created_at": now,
    })


async def release_matured_holds(db) -> int:
    """Move earnings whose payout hold has ended from 'pending' to the withdrawable balance."""
    moved = 0
    while True:
        entry = await db.wallet_transactions.find_one_and_update(
            {
                "transaction_type": "commission",
                "status": "held",
                "available_at": {"$lte": datetime.now(timezone.utc)},
            },
            {"$set": {"status": "success", "matured_at": datetime.now(timezone.utc)}},
        )
        if not entry:
            return moved
        await db.users.update_one(
            {"_id": entry["user_id"]},
            {"$inc": {"wallet_balance": entry["amount"], "pending_balance": -entry["amount"]}},
        )
        moved += 1
