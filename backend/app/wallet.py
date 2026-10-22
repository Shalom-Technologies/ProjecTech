from datetime import datetime, timedelta, timezone
import logging

import httpx

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


async def settle_withdrawal_from_status(db, reference: str, paystack_status: str) -> str:
    """
    Applies a transfer outcome reported by Paystack (in a response, a webhook or a status check).
    Every branch is a conditional update, so applying the same outcome twice is harmless.
    Returns "success", "failed", "reversed" or "pending" (not final yet).
    """
    if paystack_status == "success":
        await db.wallet_transactions.update_one(
            {"paystack_reference": reference, "transaction_type": "withdrawal", "status": "pending"},
            {"$set": {"status": "success", "settled_at": datetime.now(timezone.utc)}},
        )
        return "success"
    if paystack_status == "failed":
        await refund_withdrawal(db, reference, "failed", ["pending"])
        return "failed"
    if paystack_status == "reversed":
        await refund_withdrawal(db, reference, "reversed", ["pending", "success"])
        return "reversed"
    return "pending"


async def reconcile_pending_withdrawals(db, paystack, min_age_minutes: int = 15, give_up_after_minutes: int = 120) -> int:
    """
    Safety net for a missed or delayed transfer webhook: asks Paystack about withdrawals that
    have been pending for a while and settles them. A transfer Paystack has never heard of
    (the request never reached it) is given back to the wallet after give_up_after_minutes.
    Returns how many withdrawals it settled.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=min_age_minutes)
    pending = await db.wallet_transactions.find(
        {"transaction_type": "withdrawal", "status": "pending", "created_at": {"$lte": cutoff}}
    ).to_list(length=50)

    settled = 0
    for withdrawal in pending:
        reference = withdrawal.get("paystack_reference")
        if not reference:
            continue
        created = withdrawal["created_at"]
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)

        try:
            result = await paystack.verify_transfer(reference)
            outcome = await settle_withdrawal_from_status(db, reference, result.get("data", {}).get("status"))
            if outcome != "pending":
                settled += 1
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404 and (now - created) > timedelta(minutes=give_up_after_minutes):
                # Paystack has no such transfer: it was never created, so no money left.
                if await refund_withdrawal(db, reference, "failed", ["pending"]):
                    settled += 1
            else:
                logger.error(f"Could not check withdrawal {reference}: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error(f"Could not reach Paystack to check withdrawal {reference}: {e}")
    return settled
