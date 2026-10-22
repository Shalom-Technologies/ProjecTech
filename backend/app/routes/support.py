"""The support form: saves the message, then emails it to the admin."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from app.config import settings
from app.database import get_database
from app.email_client import send_support_email
from app.mailer import send_or_record
from app.rate_limit import limiter
from app.schemas import SupportRequest, SUPPORT_TOPICS

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/support", tags=["Support"])

FALLBACK = "Please email privacy@projectech.dev instead."


@router.post("", status_code=201)
@limiter.limit("5/hour")
async def send_support_request(request: Request, data: SupportRequest):
    # A bot that filled the hidden field gets the same answer as everyone, and nothing is sent.
    if data.website:
        return {"message": "Thanks. We received your message."}

    if not settings.ADMIN_EMAIL:
        logger.error("Support form used but ADMIN_EMAIL is not set")
        raise HTTPException(status_code=503, detail=f"Support messages are not available right now. {FALLBACK}")

    db = get_database()
    now = datetime.now(timezone.utc)
    doc = {
        "name": data.name.strip(),
        "email": data.email,
        "topic": data.topic,
        "message": data.message.strip(),
        "email_sent": False,
        "created_at": now,
    }
    # Saved first, so the message is not lost if the email provider is down.
    result = await db.support_requests.insert_one(doc)

    sent = await send_or_record(
        db, "support",
        send_support_email(
            settings.ADMIN_EMAIL, data.email, doc["name"], SUPPORT_TOPICS[data.topic], doc["message"],
            [f"Received {now:%d %b %Y %H:%M} UTC", f"Request id {result.inserted_id}"],
        ),
        to_email=settings.ADMIN_EMAIL,
    )
    if not sent:
        raise HTTPException(status_code=502, detail=f"We could not send your message just now. {FALLBACK}")

    await db.support_requests.update_one({"_id": result.inserted_id}, {"$set": {"email_sent": True}})
    return {"message": "Thanks. We received your message and will reply by email."}
