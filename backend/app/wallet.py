from datetime import datetime, timezone
import logging

from app.config import settings

logger = logging.getLogger(__name__)


async def refund_withdrawal(db, reference: str, new_status: str, allowed_from: list) -> bool:
    """
    Marks a withdrawal as failed/reversed and returns the money to the user's wallet.

    The status change is a single conditional update on the withdrawal's current
    status, so no matter how many times this is called for the same reference
    (a repeated webhook, or the webhook racing the withdraw request), the wallet
    is refunded at most once. Returns True only when this call did the refund.
    """
    withdrawal = await db.wallet_transactions.find_one_and_update(
        {
            "paystack_reference": reference,
            "transaction_type": "withdrawal",
            "status": {"$in": allowed_from},
        },
        {"$set": {"status": new_status, "settled_at": datetime.now(timezone.utc)}},
    )
    if not withdrawal:
        return False  # unknown reference, or already settled

    refund_amount = abs(withdrawal["amount"])

    await db.users.update_one(
        {"_id": withdrawal["user_id"]},
        {"$inc": {"wallet_balance": refund_amount}},
    )
    await db.wallet_transactions.insert_one({
        "user_id": withdrawal["user_id"],
        "transaction_type": "refund",
        "amount": refund_amount,
        "status": "success",
        "paystack_reference": reference,
        "description": "Withdrawal could not be completed, funds returned to your wallet",
        "created_at": datetime.now(timezone.utc),
    })
    await db.notifications.insert_one({
        "user_id": withdrawal["user_id"],
        "type": "withdrawal_failed",
        "title": "Withdrawal failed",
        "description": (
            f"Your withdrawal of {settings.CURRENCY} {refund_amount:,.2f} "
            f"could not be completed and was returned to your wallet"
        ),
        "is_read": False,
        "created_at": datetime.now(timezone.utc),
    })
    logger.warning(
        f"Withdrawal {reference} {new_status}: refunded {refund_amount} to user {withdrawal['user_id']}"
    )
    return True
