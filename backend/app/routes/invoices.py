from fastapi import APIRouter, Depends, HTTPException, Request
from bson import ObjectId
from bson.errors import InvalidId
import secrets

from app.config import settings
from app.database import get_database
from app.dependencies import require_role
from app.pricing import get_agreed_amount
from app.rate_limit import limiter
from app.routes.payments import create_or_get_payment_link

router = APIRouter(prefix="/api/invoices", tags=["Invoices"])

# An invoice link looks like  https://projectech.dev/pay/<token>.
# The token belongs to the project and never changes, so it stays valid when the
# price changes. The client only ever sees the CURRENT price and, when they press
# "Pay", a fresh Paystack link is produced for it. That is why a link already sent
# can never lead to a payment at an outdated price.


def _invoice_url(token: str) -> str:
    return f"{settings.FRONTEND_URL.rstrip('/')}/pay/{token}"


async def _invoice_status(db, project: dict) -> str:
    """payable | paid | awaiting_price_approval | unavailable"""
    if await db.transactions.find_one({"project_id": project["_id"], "status": "success"}):
        return "paid"
    if project["status"] != "in_progress" or not project.get("assigned_to"):
        return "unavailable"
    proposal = project.get("price_proposal")
    if proposal and proposal["status"] == "pending":
        return "awaiting_price_approval"
    return "payable"


async def _project_for_token(db, token: str) -> dict:
    project = await db.projects.find_one({"invoice_token": token}) if token else None
    if not project:
        # Same answer for "never existed" and "mistyped", so tokens cannot be probed.
        raise HTTPException(status_code=404, detail="This invoice link is not valid")
    return project


# ============================================================================
# SALESPERSON: get the shareable invoice link for a project
# ============================================================================

@router.post("/for-project/{project_id}")
async def get_invoice_link(
    project_id: str,
    current_user: dict = Depends(require_role("salesperson"))
):
    db = get_database()
    try:
        project = await db.projects.find_one({"_id": ObjectId(project_id)})
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ID format")

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project["salesperson_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Only the project owner can create an invoice link")

    if not project.get("assigned_to"):
        raise HTTPException(status_code=400, detail="Project has no assigned developer yet")

    token = project.get("invoice_token")
    if not token:
        token = secrets.token_urlsafe(24)
        # Only set it if still missing, so two open tabs cannot create two different links.
        result = await db.projects.update_one(
            {"_id": project["_id"], "invoice_token": None},
            {"$set": {"invoice_token": token}}
        )
        if result.modified_count == 0:
            project = await db.projects.find_one({"_id": project["_id"]})
            token = project["invoice_token"]

    return {"invoice_token": token, "invoice_url": _invoice_url(token)}


# ============================================================================
# CLIENT (no login): see the invoice, then pay it
# ============================================================================

@router.get("/{token}")
@limiter.limit("60/minute")
async def view_invoice(request: Request, token: str):
    db = get_database()
    project = await _project_for_token(db, token)
    salesperson = await db.users.find_one({"_id": project["salesperson_id"]})

    from_name = None
    if salesperson:
        from_name = salesperson.get("company_name") or f"{salesperson['first_name']} {salesperson['last_name']}"

    # Only what a client needs to recognise and pay the invoice. No emails or internal ids.
    return {
        "project_title": project["title"],
        "client_name": project.get("client_name"),
        "from_name": from_name,
        "amount": get_agreed_amount(project),
        "currency": project.get("currency", settings.CURRENCY),
        "status": await _invoice_status(db, project),
    }


@router.post("/{token}/pay")
@limiter.limit("10/minute")
async def pay_invoice(request: Request, token: str):
    db = get_database()
    project = await _project_for_token(db, token)

    status = await _invoice_status(db, project)
    if status == "paid":
        raise HTTPException(status_code=400, detail="This invoice has already been paid")
    if status == "awaiting_price_approval":
        raise HTTPException(status_code=409, detail="The price is still being confirmed. Please try again shortly.")
    if status == "unavailable":
        raise HTTPException(status_code=400, detail="This invoice can no longer be paid")

    link = await create_or_get_payment_link(db, project)
    return {"authorization_url": link["authorization_url"]}
