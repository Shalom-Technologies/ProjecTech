"""
Tells the admin, by email, about things only a person can fix.

Once per background cycle, anything new that needs attention is gathered into ONE email:
  - problem reports waiting for a decision
  - payments that must be refunded (paid on an outdated link, or on a cancelled project)
  - refunds Paystack says failed
  - emails the platform could not send
Each item is marked as alerted, so it is mentioned once. A failed refund is mentioned again
if it fails again. If ADMIN_EMAIL is not set, nothing is sent and the items stay in the database.

If sending the alert itself fails (for example the email provider is down), the items are put
back and the next cycle tries again. The failure is only logged, never recorded as another
email failure, so it cannot create an endless loop of alerts about alerts.
"""
import logging
import uuid
from datetime import datetime, timezone

from app.config import settings
from app import email_client

logger = logging.getLogger(__name__)

# (collection, where the "already told the admin" mark lives, filter for "needs attention",
#  how to describe one item). The mark for a problem report lives inside the report itself, so a
#  project reopened and disputed again is announced again. A failed refund comes before a
#  refund-due payment so a payment that is both is described as failed.
def _sources():
    return [
        ("projects", "dispute.", {"dispute.status": "open"}, _describe_dispute),
        ("transactions", "", {"refund_status": "failed"}, _describe_refund_failed),
        ("transactions", "", {"needs_refund": True, "refund_status": {"$ne": "processed"}}, _describe_refund_due),
        ("email_failures", "", {}, _describe_email_failure),
    ]


def _describe_dispute(d):
    reason = (d.get("dispute") or {}).get("reason", "")
    return f"Problem report on '{d.get('title')}' ({d['_id']}): {reason[:200]}"


def _describe_refund_due(d):
    return (f"Refund needed: {settings.CURRENCY} {d.get('total_amount', 0):,.2f} paid for project {d.get('project_id')} "
            f"(Paystack reference {d.get('paystack_reference')}). It was paid on a link that can no longer be used.")


def _describe_refund_failed(d):
    return (f"Paystack says a refund FAILED: {settings.CURRENCY} {d.get('total_amount', 0):,.2f}, "
            f"Paystack reference {d.get('paystack_reference')}. The client has not been paid back.")


def _describe_email_failure(d):
    return f"Email not sent: {d.get('kind')} to {d.get('to_email')}: {d.get('error', '')[:150]}"


async def send_admin_digest(db) -> int:
    """Returns how many items were reported. Never raises."""
    try:
        return await _send_admin_digest(db)
    except Exception:  # noqa: BLE001 - alerting must never break the background job
        logger.exception("Admin alert digest failed")
        return 0


async def _send_admin_digest(db) -> int:
    admin_email = getattr(settings, "ADMIN_EMAIL", "")
    if not admin_email:
        return 0

    batch = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    claimed = []
    for collection, prefix, flt, describe in _sources():
        coll = db[collection]
        # Claim in one step so two servers never send the same item twice.
        await coll.update_many(
            {**flt, f"{prefix}admin_alerted_at": {"$exists": False}},
            {"$set": {f"{prefix}admin_alerted_at": now, f"{prefix}admin_alert_batch": batch}},
        )
        docs = await coll.find({f"{prefix}admin_alert_batch": batch}).to_list(length=100)
        claimed.append((collection, prefix, describe, docs))

    lines = [describe(d) for _, _, describe, docs in claimed for d in docs]
    if not lines:
        return 0

    try:
        await email_client.send_admin_alert_email(
            admin_email, f"ProjecTech: {len(lines)} item(s) need attention", lines
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"Could not email the admin alert, will retry next cycle: {e}")
        for collection, prefix, _, _ in claimed:
            await db[collection].update_many(
                {f"{prefix}admin_alert_batch": batch},
                {"$unset": {f"{prefix}admin_alerted_at": "", f"{prefix}admin_alert_batch": ""}},
            )
        return 0

    for collection, prefix, _, _ in claimed:
        await db[collection].update_many(
            {f"{prefix}admin_alert_batch": batch}, {"$unset": {f"{prefix}admin_alert_batch": ""}}
        )
    return len(lines)
