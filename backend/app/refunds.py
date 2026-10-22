"""
Refund bookkeeping for the messages Paystack sends about refunds.

ProjecTech never moves refund money itself: a person issues the refund in the Paystack
dashboard, and the admin script records the outcome on the project. Paystack then tells us
how the refund went (refund.pending, refund.processing, refund.processed, refund.failed).
We keep the latest state on the payment, so a refund that fails does not go unnoticed.
"""
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

REFUND_EVENTS = {
    "refund.pending": "pending",
    "refund.processing": "processing",
    "refund.processed": "processed",
    "refund.failed": "failed",
}


def _reference_of(data: dict):
    """The payment reference a refund event belongs to (Paystack names it in a few ways)."""
    ref = data.get("transaction_reference")
    if not ref and isinstance(data.get("transaction"), dict):
        ref = data["transaction"].get("reference")
    return ref


async def record_refund_event(db, event: str, data: dict) -> bool:
    """
    Stores a refund's latest state on its payment. Returns True if a payment was updated.

    - processed: the client has the money back, so a payment that was waiting for a refund
      is no longer waiting.
    - failed: the client has NOT been refunded. The payment is marked so the admin is told,
      even when ProjecTech's own records already say "refunded".
    Events can arrive late or twice; a processed refund is never downgraded to an earlier state.
    """
    status = REFUND_EVENTS.get(event)
    reference = _reference_of(data or {})
    if not status or not reference:
        return False

    now = datetime.now(timezone.utc)
    update = {
        "refund_status": status,
        "refund_updated_at": now,
        "refund_reference": data.get("refund_reference") or data.get("id"),
    }
    unset = {}
    if status == "processed":
        update["needs_refund"] = False
        update["refunded_at"] = now
    if status == "failed":
        # Make sure the admin hears about it, even if an earlier alert already went out.
        unset["admin_alerted_at"] = ""
        logger.error(f"Paystack reports the refund for payment {reference} FAILED")

    # Never move a finished refund backwards (a late "pending" after "processed").
    flt = {"paystack_reference": reference}
    if status in ("pending", "processing"):
        flt["refund_status"] = {"$nin": ["processed"]}

    ops = {"$set": update}
    if unset:
        ops["$unset"] = unset
    result = await db.transactions.update_one(flt, ops)
    return bool(getattr(result, "matched_count", 0))
