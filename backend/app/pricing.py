from fastapi import HTTPException

from app.config import settings


def round_money(value) -> float:
    return round(float(value), 2)


def get_agreed_amount(project: dict) -> float:
    """
    The price both sides have agreed to, and the only amount that can be invoiced.

    It is set when the salesperson accepts an application, and only changes when
    the developer approves a price proposal. Projects accepted before this field
    existed fall back to the accepted application's price, then the posted budget.
    """
    if project.get("agreed_amount") is not None:
        return round_money(project["agreed_amount"])

    for application in project.get("applications", []):
        if application.get("status") == "accepted":
            return round_money(application.get("proposed_budget") or project["budget"])

    return round_money(project["budget"])


def check_amount_limits(amount: float) -> None:
    if amount < settings.MIN_PAYMENT_AMOUNT:
        raise HTTPException(
            status_code=400,
            detail=f"The amount must be at least {settings.CURRENCY} {settings.MIN_PAYMENT_AMOUNT:,.2f}",
        )
    if amount > settings.MAX_PAYMENT_AMOUNT:
        raise HTTPException(
            status_code=400,
            detail=f"The amount cannot be more than {settings.CURRENCY} {settings.MAX_PAYMENT_AMOUNT:,.2f}",
        )


def serialize_proposal(proposal: dict | None) -> dict | None:
    if not proposal:
        return None
    return {
        "amount": proposal["amount"],
        "reason": proposal["reason"],
        "status": proposal["status"],  # pending | approved | rejected | withdrawn
        "proposed_at": proposal.get("proposed_at"),
        "responded_at": proposal.get("responded_at"),
        "response_note": proposal.get("response_note"),
    }
