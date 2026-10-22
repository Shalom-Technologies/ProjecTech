from fastapi import APIRouter, Depends, HTTPException, Request
from bson import ObjectId
from bson.errors import InvalidId

from app.config import settings
from app.database import get_database
from app.dependencies import require_verified_role
from app.pricing import get_agreed_amount
from app.schemas import ProblemReport
from app.delivery import ensure_invoice_token, invoice_url, accept_delivery, open_dispute
from app.rate_limit import limiter
from app.routes.payments import create_or_get_payment_link

router = APIRouter(prefix="/api/invoices", tags=["Invoices"])

# An invoice link looks like  https://projectech.dev/pay/<token>.
# The token belongs to the project and never changes, so it stays valid when the
# price changes. The client only ever sees the CURRENT price and, when they press
# "Pay", a fresh Paystack link is produced for it. That is why a link already sent
# can never lead to a payment at an outdated price.


async def _invoice_status(db, project: dict) -> str:
    """
    payable | awaiting_price_approval | unavailable, before payment
    paid | in_review | disputed | completed | refunded, after payment (refunded also while the
    project stays cancelled after a refund; once reopened it is payable again)
    """
    paid = await db.transactions.find_one({"project_id": project["_id"], "status": "success"})
    if paid:
        if paid.get("escrow_status") == "refunded":
            return "refunded"
        if (project.get("dispute") or {}).get("status") == "open":
            return "disputed"
        if project["status"] == "completed":
            return "completed"
        if (project.get("delivery") or {}).get("status") == "delivered":
            return "in_review"
        return "paid"
    if project["status"] == "cancelled" and await db.transactions.find_one(
        {"project_id": project["_id"], "status": "refunded"}
    ):
        return "refunded"
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
    current_user: dict = Depends(require_verified_role("salesperson"))
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

    token = await ensure_invoice_token(db, project)
    return {"invoice_token": token, "invoice_url": invoice_url(token)}


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
        "review_deadline": (project.get("delivery") or {}).get("review_deadline"),
        "dispute_resolution": (project.get("dispute") or {}).get("resolution"),
    }


@router.post("/{token}/pay")
@limiter.limit("10/minute")
async def pay_invoice(request: Request, token: str):
    db = get_database()
    project = await _project_for_token(db, token)

    status = await _invoice_status(db, project)
    if status in ("paid", "in_review", "disputed", "completed", "refunded"):
        raise HTTPException(status_code=400, detail="This invoice has already been paid")
    if status == "awaiting_price_approval":
        raise HTTPException(status_code=409, detail="The price is still being confirmed. Please try again shortly.")
    if status == "unavailable":
        raise HTTPException(status_code=400, detail="This invoice can no longer be paid")

    link = await create_or_get_payment_link(db, project)
    return {"authorization_url": link["authorization_url"]}



@router.post("/{token}/accept")
@limiter.limit("10/minute")
async def accept_invoice_delivery(request: Request, token: str):
    """The client confirms the work is fine. This releases the payment."""
    db = get_database()
    project = await _project_for_token(db, token)

    if await _invoice_status(db, project) != "in_review":
        raise HTTPException(status_code=400, detail="There is no delivery waiting for your review")

    await accept_delivery(db, project, "client")
    return {"message": "Thank you. The payment has been released."}


@router.post("/{token}/dispute")
@limiter.limit("5/minute")
async def report_invoice_problem(request: Request, token: str, report: ProblemReport):
    """The client reports a problem. The payment stays held until ProjecTech has reviewed it."""
    db = get_database()
    project = await _project_for_token(db, token)

    if await _invoice_status(db, project) not in ("paid", "in_review"):
        raise HTTPException(status_code=400, detail="A problem can only be reported on a paid, unfinished project")

    await open_dispute(db, project, "client", report.reason)
    return {"message": "Your report was received. The payment will not be released until it has been reviewed."}
