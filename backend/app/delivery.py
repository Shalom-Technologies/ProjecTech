"""
Delivery, review window and disputes.

A funded project moves like this:

    in progress --(developer marks delivered)--> delivered, client review window starts
    delivered   --(client accepts)-------------> completed, money released
    delivered   --(window ends, no objection)--> completed, money released automatically
    funded      --(anyone reports a problem)---> release frozen until ProjecTech resolves it

Nobody can release the money early on the client's behalf: only acceptance or the end
of the review window does.
"""
from datetime import datetime, timedelta, timezone
import logging
import secrets

from fastapi import HTTPException

from app.config import settings
from app.escrow import settle_escrow, release_matured_holds
from app.mailer import send_or_record
from app.pricing import round_money

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

async def held_transaction(db, project_oid):
    """The paid transaction whose money ProjecTech is still holding for a project."""
    return await db.transactions.find_one(
        {"project_id": project_oid, "status": "success", "escrow_status": "held"}
    )


async def notify(db, user_id, type_: str, title: str, description: str, project_id):
    await db.notifications.insert_one({
        "user_id": user_id,
        "type": type_,
        "title": title,
        "description": description,
        "project_id": project_id,
        "is_read": False,
        "created_at": _now(),
    })


async def ensure_invoice_token(db, project: dict) -> str:
    """The permanent token behind a project's /pay/<token> link, created on first use."""
    token = project.get("invoice_token")
    if token:
        return token

    token = secrets.token_urlsafe(24)
    # Only set it if still missing, so two open tabs cannot create two different links.
    result = await db.projects.update_one(
        {"_id": project["_id"], "invoice_token": None},
        {"$set": {"invoice_token": token}},
    )
    if result.modified_count == 0:
        project = await db.projects.find_one({"_id": project["_id"]})
        token = project["invoice_token"]
    return token


def invoice_url(token: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/pay/{token}"


def serialize_delivery(project: dict):
    delivery = project.get("delivery")
    if not delivery:
        return None
    return {
        "status": delivery["status"],  # delivered | accepted
        "delivered_at": delivery.get("delivered_at"),
        "review_deadline": delivery.get("review_deadline"),
        "accepted_at": delivery.get("accepted_at"),
        "accepted_by": delivery.get("accepted_by"),  # client | auto
        "client_email_sent": delivery.get("client_email_sent"),  # False = the review email failed
    }


def serialize_dispute(project: dict):
    dispute = project.get("dispute")
    if not dispute:
        return None
    return {
        "status": dispute["status"],  # open | resolved
        "opened_by": dispute["opened_by"],
        "reason": dispute["reason"],
        "opened_at": dispute.get("opened_at"),
        "resolution": dispute.get("resolution"),
        "resolution_note": dispute.get("resolution_note"),
        "resolved_at": dispute.get("resolved_at"),
    }


# ---------------------------------------------------------------------------
# developer marks the work delivered
# ---------------------------------------------------------------------------

async def send_review_email(db, project: dict, deadline) -> bool:
    from app.email_client import send_review_started_email
    token = await ensure_invoice_token(db, project)
    return await send_or_record(
        db, "review_started",
        send_review_started_email(
            to_email=project["client_email"],
            project_title=project["title"],
            invoice_url=invoice_url(token),
            review_deadline=deadline,
        ),
        to_email=project["client_email"], user_id=project["salesperson_id"], project_id=project["_id"],
    )


async def resend_review_email(db, project: dict) -> dict:
    delivery = project.get("delivery") or {}
    if delivery.get("status") != "delivered" or project["status"] != "in_progress":
        raise HTTPException(status_code=400, detail="There is no delivery waiting for the client's review.")

    last = delivery.get("client_email_last_attempt")
    if last:
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        wait = 60 - (_now() - last).total_seconds()
        if wait > 0:
            raise HTTPException(status_code=429, detail=f"Please wait {int(wait) + 1} seconds before sending it again.")

    deadline = delivery["review_deadline"]
    sent = await send_review_email(db, project, deadline)
    await db.projects.update_one(
        {"_id": project["_id"]},
        {"$set": {"delivery.client_email_sent": sent, "delivery.client_email_last_attempt": _now()}},
    )
    token = await ensure_invoice_token(db, project)
    return {"sent": sent, "invoice_url": invoice_url(token)}


async def deliver_project(db, project: dict) -> dict:
    if project["status"] != "in_progress":
        raise HTTPException(status_code=400, detail="Only a project in progress can be marked delivered")

    if not await held_transaction(db, project["_id"]):
        raise HTTPException(status_code=400, detail="The client must pay before work can be marked delivered")

    if (project.get("dispute") or {}).get("status") == "open":
        raise HTTPException(status_code=400, detail="A problem report is open, so this cannot be delivered yet")

    now = _now()
    deadline = now + timedelta(days=settings.REVIEW_WINDOW_DAYS)

    result = await db.projects.update_one(
        {
            "_id": project["_id"],
            "status": "in_progress",
            "delivery.status": {"$ne": "delivered"},
            "dispute.status": {"$ne": "open"},
        },
        {"$set": {
            "delivery": {
                "status": "delivered",
                "delivered_at": now,
                "review_deadline": deadline,
                "accepted_at": None,
                "accepted_by": None,
            },
            "updated_at": now,
        }},
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=409, detail="This project is already marked delivered")

    await notify(
        db, project["salesperson_id"], "project_delivered", "Work delivered",
        f"'{project['title']}' was marked delivered. The client has until {deadline:%d %b %Y} to review it.",
        project["_id"],
    )

    # Tell the client too, on the same link they paid through. If the email cannot be sent,
    # that is recorded on the project so the salesperson sees a warning and can resend it or
    # copy the link; the invoice page shows the review state either way.
    sent = await send_review_email(db, project, deadline)
    result_note = {"delivery.client_email_sent": sent, "delivery.client_email_last_attempt": _now()}
    await db.projects.update_one({"_id": project["_id"]}, {"$set": result_note})

    return {"review_deadline": deadline}


# ---------------------------------------------------------------------------
# client accepts, or the review window ends
# ---------------------------------------------------------------------------

async def accept_delivery(db, project: dict, accepted_by: str):
    """accepted_by is "client" or "auto". Completes the project and releases the money."""
    now = _now()
    result = await db.projects.update_one(
        {
            "_id": project["_id"],
            "status": "in_progress",
            "delivery.status": "delivered",
            "dispute.status": {"$ne": "open"},
        },
        {"$set": {
            "delivery.status": "accepted",
            "delivery.accepted_at": now,
            "delivery.accepted_by": accepted_by,
            "status": "completed",
            "updated_at": now,
        }},
    )
    if result.modified_count == 0:
        raise HTTPException(
            status_code=409,
            detail="This delivery can no longer be accepted (it may already be accepted, or a problem is open).",
        )

    transaction = await held_transaction(db, project["_id"])
    if transaction:
        await settle_escrow(db, transaction)
    else:
        logger.error(f"Project {project['_id']} accepted but no held payment was found")

    how = "accepted by the client" if accepted_by == "client" else "accepted automatically after the review window"
    for user_id in (project["salesperson_id"], project.get("assigned_to")):
        if user_id:
            await notify(
                db, user_id, "project_completed", "Project completed",
                f"'{project['title']}' was {how}. The payment has been released.",
                project["_id"],
            )


async def process_due_deliveries(db) -> int:
    """Accept every delivery whose review window has ended with no objection."""
    accepted = 0
    seen = set()
    for _ in range(500):
        project = await db.projects.find_one({
            "status": "in_progress",
            "delivery.status": "delivered",
            "delivery.review_deadline": {"$lte": _now()},
            "dispute.status": {"$ne": "open"},
        })
        if not project or project["_id"] in seen:
            break
        seen.add(project["_id"])
        try:
            await accept_delivery(db, project, "auto")
            accepted += 1
        except HTTPException as e:
            logger.warning(f"Auto-release of {project['_id']} skipped: {e.detail}")
    return accepted


async def run_periodic_jobs(db):
    """Run on a timer. Safe on several servers at once, because every step is an atomic claim."""
    released = await process_due_deliveries(db)
    matured = await release_matured_holds(db)
    if released or matured:
        logger.info(f"Periodic jobs: {released} deliveries auto-released, {matured} payout holds matured")


# ---------------------------------------------------------------------------
# problem reports (disputes)
# ---------------------------------------------------------------------------

async def open_dispute(db, project: dict, opened_by: str, reason: str):
    """opened_by is "client", "salesperson" or "developer". Freezes the release."""
    if not await held_transaction(db, project["_id"]):
        raise HTTPException(
            status_code=400,
            detail="No payment is being held for this project, so there is nothing to dispute.",
        )

    now = _now()
    result = await db.projects.update_one(
        {"_id": project["_id"], "status": "in_progress", "dispute.status": {"$ne": "open"}},
        {"$set": {
            "dispute": {
                "status": "open",
                "opened_by": opened_by,
                "reason": reason.strip(),
                "opened_at": now,
                "resolution": None,
                "resolution_note": None,
                "resolved_at": None,
            },
            "updated_at": now,
        }},
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=409, detail="A problem report is already open for this project.")

    logger.warning(f"DISPUTE OPENED on project {project['_id']} by {opened_by}: {reason.strip()[:200]}")

    people = {"salesperson": project["salesperson_id"], "developer": project.get("assigned_to")}
    for role, user_id in people.items():
        if user_id and role != opened_by:
            await notify(
                db, user_id, "dispute_opened", "A problem was reported",
                f"A problem was reported on '{project['title']}'. The payment will not be released until ProjecTech has reviewed it.",
                project["_id"],
            )


async def resolve_dispute(db, project_id, outcome: str, refund_amount: float | None = None, note: str | None = None) -> dict:
    """
    Closes an open dispute. Called by the admin script after the money has been dealt with
    in the Paystack dashboard (for a refund or split, the client has already been refunded).

    outcome "release" -> the project is completed and everything is paid out
    outcome "refund"  -> everything is recorded as refunded and the project is cancelled
    outcome "split"   -> refund_amount is recorded as refunded, the rest is paid out
    """
    project = await db.projects.find_one({"_id": project_id})
    if not project:
        raise ValueError("Project not found")
    if (project.get("dispute") or {}).get("status") != "open":
        raise ValueError("This project has no open dispute")

    transaction = await held_transaction(db, project["_id"])
    if not transaction:
        raise ValueError("No held payment was found for this project (already settled?)")

    total = round_money(transaction["total_amount"])
    if outcome == "release":
        refund, new_status = 0.0, "completed"
    elif outcome == "refund":
        refund, new_status = total, "cancelled"
    elif outcome == "split":
        refund = round_money(refund_amount or 0)
        if not 0 < refund < total:
            raise ValueError(f"A split needs a refund amount between 0 and {total}")
        new_status = "completed"
    else:
        raise ValueError("Outcome must be release, refund or split")

    settled = await settle_escrow(db, transaction, refund)
    if settled is None:
        raise ValueError("The payment was already settled")

    now = _now()
    await db.projects.update_one(
        {"_id": project["_id"]},
        {"$set": {
            "status": new_status,
            "dispute.status": "resolved",
            "dispute.resolution": outcome,
            "dispute.resolution_note": note,
            "dispute.resolved_at": now,
            "updated_at": now,
        }},
    )

    summary = {
        "release": "The payment was released to the developer and the salesperson.",
        "refund": f"The client was refunded {settings.CURRENCY} {refund:,.2f}.",
        "split": f"The client was refunded {settings.CURRENCY} {refund:,.2f} and the rest was released.",
    }[outcome]
    for user_id in (project["salesperson_id"], project.get("assigned_to")):
        if user_id:
            await notify(
                db, user_id, "dispute_resolved", "Problem report resolved",
                f"The problem on '{project['title']}' was resolved by ProjecTech. {summary}",
                project["_id"],
            )

    return {"outcome": outcome, "refunded": refund, "project_status": new_status, "settled": settled}
