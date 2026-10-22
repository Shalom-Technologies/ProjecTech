import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def send_or_record(db, kind: str, send_coro, *, to_email: str, user_id=None, project_id=None) -> bool:
    """
    Awaits an email-sending coroutine. Never raises.

    On failure, a row is written to `email_failures` (what, to whom, why) so a problem such as
    an expired Resend key shows up in the database and the logs instead of vanishing.
    Returns True if the email was handed to the provider, False otherwise.
    """
    try:
        await send_coro
        return True
    except Exception as e:  # noqa: BLE001 - any provider or network error
        logger.error(f"EMAIL FAILED kind={kind} to={to_email}: {e}")
        try:
            await db.email_failures.insert_one({
                "kind": kind,
                "to_email": to_email,
                "user_id": user_id,
                "project_id": project_id,
                "error": str(e)[:500],
                "created_at": datetime.now(timezone.utc),
            })
        except Exception:  # noqa: BLE001 - recording must not break the request either
            logger.exception("Could not record the email failure")
        return False
