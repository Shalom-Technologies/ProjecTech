from fastapi import APIRouter, Depends, HTTPException, status, Query
from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from bson.errors import InvalidId

from app.config import settings
from app.database import get_database
from app.dependencies import get_current_user, require_role
from app.schemas import ProjectCreate, ProjectUpdate, ApplicationCreate, PriceProposalCreate, PriceProposalDecision, ProblemReport
from app.delivery import deliver_project, open_dispute, serialize_delivery, serialize_dispute
from app.pricing import get_agreed_amount, check_amount_limits, round_money, serialize_proposal

router = APIRouter(prefix="/api/projects", tags=["Projects"])


def to_object_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ID format")


# ============================================================================
# CREATE PROJECT — salesperson only
# ============================================================================

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    current_user: dict = Depends(require_role("salesperson"))
):
    db = get_database()

    project_doc = {
        "title": project_data.title,
        "description": project_data.description,
        "category": project_data.category,
        "budget": project_data.budget,
        "currency": settings.CURRENCY,
        "deadline": project_data.deadline,
        "client_name": project_data.client_name,
        "client_email": project_data.client_email,
        "tags": project_data.tags or [],
        "salesperson_id": current_user["_id"],
        "status": "open",
        "assigned_to": None,
        "applications": [],
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    result = await db.projects.insert_one(project_doc)

    return {
        "message": "Project created successfully",
        "project_id": str(result.inserted_id)
    }


# ============================================================================
# LIST PROJECTS — any authenticated user, with filters
# ============================================================================

@router.get("")
async def list_projects(
    current_user: dict = Depends(get_current_user),
    status_filter: Optional[str] = Query(None, alias="status"),
    category: Optional[str] = None,
    min_budget: Optional[float] = None,
    max_budget: Optional[float] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
):
    db = get_database()

    query = {}
    if status_filter:
        query["status"] = status_filter
    if category:
        query["category"] = category
    if min_budget is not None or max_budget is not None:
        budget_q = {}
        if min_budget is not None:
            budget_q["$gte"] = min_budget
        if max_budget is not None:
            budget_q["$lte"] = max_budget
        query["budget"] = budget_q
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
        ]

    total = await db.projects.count_documents(query)
    skip = (page - 1) * per_page

    cursor = db.projects.find(query).sort("created_at", -1).skip(skip).limit(per_page)
    projects = await cursor.to_list(length=per_page)

    formatted_projects = []
    for project in projects:
        assigned_name = None
        if project.get("assigned_to"):
            dev = await db.users.find_one({"_id": project["assigned_to"]})
            if dev:
                assigned_name = f"{dev['first_name']} {dev['last_name']}"

        formatted_projects.append({
            "id": str(project["_id"]),
            "title": project["title"],
            "description": project["description"],
            "category": project["category"],
            "budget": project["budget"],
            "currency": project.get("currency", settings.CURRENCY),
            "status": project["status"],
            "deadline": project.get("deadline"),
            "applications_count": len(project.get("applications", [])),
            "assigned_to": str(project["assigned_to"]) if project.get("assigned_to") else None,
            "assigned_to_name": assigned_name,
            "created_at": project.get("created_at"),
        })

    return {
        "data": formatted_projects,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }

# ============================================================================
# GET MY ASSIGNED PROJECTS — developer only
# ============================================================================

@router.get("/mine/assigned")
async def get_my_assigned_projects(
    current_user: dict = Depends(require_role("developer")),
    status_filter: Optional[str] = Query(None, alias="status"),
):
    db = get_database()

    query = {"assigned_to": current_user["_id"]}
    if status_filter:
        query["status"] = status_filter

    cursor = db.projects.find(query).sort("created_at", -1)
    projects = await cursor.to_list(length=100)

    funded_ids = set()
    if projects:
        paid = db.transactions.find(
            {"project_id": {"$in": [p["_id"] for p in projects]}, "status": "success"}
        )
        funded_ids = {t["project_id"] for t in await paid.to_list(length=None)}

    data = []
    for p in projects:
        salesperson = await db.users.find_one({"_id": p["salesperson_id"]})
        data.append({
            "id": str(p["_id"]),
            "title": p["title"],
            "description": p["description"],
            "category": p["category"],
            "budget": p["budget"],
            "agreed_amount": get_agreed_amount(p),
            "price_proposal": serialize_proposal(p.get("price_proposal")),
            "currency": p.get("currency", settings.CURRENCY),
            "status": p["status"],
            "is_funded": p["_id"] in funded_ids,
            "delivery": serialize_delivery(p),
            "dispute": serialize_dispute(p),
            "deadline": p.get("deadline"),
            "assignment_date": p.get("assignment_date"),
            "salesperson_id": str(p["salesperson_id"]),
            "salesperson_name": f"{salesperson['first_name']} {salesperson['last_name']}" if salesperson else None,
            "created_at": p["created_at"],
        })

    return {"data": data, "total": len(data)}


# ============================================================================
# GET PROJECT DETAILS
# ============================================================================

@router.get("/{project_id}")
async def get_project(project_id: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    project = await db.projects.find_one({"_id": to_object_id(project_id)})

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    salesperson = await db.users.find_one({"_id": project["salesperson_id"]})

    return {
        "id": str(project["_id"]),
        "title": project["title"],
        "description": project["description"],
        "category": project["category"],
        "budget": project["budget"],
        "currency": project.get("currency", settings.CURRENCY),
        "status": project["status"],
        "deadline": project["deadline"],
        "client_name": project["client_name"],
        "client_email": project["client_email"],
        "salesperson_id": str(project["salesperson_id"]),
        "salesperson_name": f"{salesperson['first_name']} {salesperson['last_name']}" if salesperson else None,
        "assigned_to": str(project["assigned_to"]) if project.get("assigned_to") else None,
        "applications_count": len(project.get("applications", [])),
        "tags": project.get("tags", []),
        "created_at": project["created_at"],
    }


# ============================================================================
# UPDATE PROJECT — salesperson (owner) only
# ============================================================================

@router.put("/{project_id}")
async def update_project(
    project_id: str,
    updates: ProjectUpdate,
    current_user: dict = Depends(require_role("salesperson"))
):
    db = get_database()
    project = await db.projects.find_one({"_id": to_object_id(project_id)})

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project["salesperson_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="You can only update your own projects")

    if updates.status is not None and updates.status != project["status"]:
        if updates.status == "completed":
            raise HTTPException(
                status_code=400,
                detail="A project is completed when the client accepts the delivered work. The developer marks it delivered first.",
            )

        funded = await db.transactions.find_one({
            "project_id": project["_id"],
            "status": "success",
        })
        if funded:
            raise HTTPException(
                status_code=400,
                detail="This project has been paid for, so its status can no longer be changed here. If something is wrong, report a problem on it.",
            )

        if updates.status == "cancelled":
            # Nobody should still be able to pay a project that was called off.
            await db.transactions.update_many(
                {"project_id": project["_id"], "status": "pending"},
                {"$set": {"status": "cancelled", "cancelled_reason": "project_cancelled"}},
            )

    update_data = {k: v for k, v in updates.model_dump(exclude_unset=True).items() if v is not None}
    update_data["updated_at"] = datetime.now(timezone.utc)

    await db.projects.update_one({"_id": project["_id"]}, {"$set": update_data})

    return {"message": "Project updated successfully"}


# ============================================================================
# DELETE PROJECT — salesperson (owner) only, only if open
# ============================================================================

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    current_user: dict = Depends(require_role("salesperson"))
):
    db = get_database()
    project = await db.projects.find_one({"_id": to_object_id(project_id)})

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project["salesperson_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="You can only delete your own projects")

    if project["status"] != "open" or project.get("assigned_to"):
        raise HTTPException(
            status_code=400,
            detail="Cannot delete a project that is in progress or has an assigned developer"
        )

    await db.projects.delete_one({"_id": project["_id"]})
    return None


# ============================================================================
# APPLY FOR PROJECT — developer only
# ============================================================================

@router.post("/{project_id}/apply", status_code=status.HTTP_201_CREATED)
async def apply_for_project(
    project_id: str,
    application: ApplicationCreate,
    current_user: dict = Depends(require_role("developer"))
):
    db = get_database()
    project = await db.projects.find_one({"_id": to_object_id(project_id)})

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project["status"] != "open":
        raise HTTPException(status_code=400, detail="Project is not open for applications")

    for app in project.get("applications", []):
        if app["developer_id"] == current_user["_id"]:
            raise HTTPException(status_code=400, detail="You have already applied for this project")

    application_doc = {
        "application_id": ObjectId(),
        "developer_id": current_user["_id"],
        "proposed_budget": application.proposed_budget or project["budget"],
        "cover_letter": application.cover_letter,
        "applied_at": datetime.now(timezone.utc),
        "status": "pending",
    }

    await db.projects.update_one(
        {"_id": project["_id"]},
        {"$push": {"applications": application_doc}}
    )

    return {
        "message": "Application submitted successfully",
        "application_id": str(application_doc["application_id"])
    }


# ============================================================================
# VIEW APPLICATIONS — salesperson (owner) only
# ============================================================================

@router.get("/{project_id}/applications")
async def get_applications(
    project_id: str,
    current_user: dict = Depends(require_role("salesperson"))
):
    db = get_database()
    project = await db.projects.find_one({"_id": to_object_id(project_id)})

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project["salesperson_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="You can only view applications for your own projects")

    applications = project.get("applications", [])
    result = []

    for app in applications:
        developer = await db.users.find_one({"_id": app["developer_id"]})
        result.append({
            "application_id": str(app["application_id"]),
            "developer_id": str(app["developer_id"]),
            "developer_name": f"{developer['first_name']} {developer['last_name']}" if developer else None,
            "developer_email": developer["email"] if developer else None,
            "proposed_budget": app["proposed_budget"],
            "cover_letter": app["cover_letter"],
            "applied_at": app["applied_at"],
            "status": app["status"],
        })

    return {"data": result, "total": len(result)}

# ============================================================================
# ACCEPT APPLICATION — salesperson (owner) only
# ============================================================================

@router.post("/{project_id}/applications/{application_id}/accept")
async def accept_application(
    project_id: str,
    application_id: str,
    current_user: dict = Depends(require_role("salesperson"))
):
    db = get_database()
    project = await db.projects.find_one({"_id": to_object_id(project_id)})

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project["salesperson_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="You can only manage applications for your own projects")

    if project["status"] != "open":
        raise HTTPException(status_code=400, detail="This project is no longer open for assignment")

    try:
        application_oid = ObjectId(application_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid application ID")

    application = next(
        (a for a in project.get("applications", []) if a["application_id"] == application_oid),
        None
    )

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if application["status"] != "pending":
        raise HTTPException(status_code=400, detail="This application has already been processed")

    # Assign developer, move project to in_progress, mark this application accepted
    await db.projects.update_one(
        {"_id": project["_id"], "applications.application_id": application_oid},
        {
            "$set": {
                "applications.$.status": "accepted",
                "assigned_to": application["developer_id"],
                "agreed_amount": round_money(application["proposed_budget"]),
                "assignment_date": datetime.now(timezone.utc),
                "status": "in_progress",
                "updated_at": datetime.now(timezone.utc),
            }
        }
    )

    # Auto-reject all other pending applications for this project
    await db.projects.update_one(
        {"_id": project["_id"]},
        {
            "$set": {
                "applications.$[elem].status": "rejected"
            }
        },
        array_filters=[
            {"elem.application_id": {"$ne": application_oid}, "elem.status": "pending"}
        ]
    )

    # Notify the accepted developer
    await db.notifications.insert_one({
        "user_id": application["developer_id"],
        "type": "project_assigned",
        "title": "You've been assigned to a project",
        "description": f"You were selected for '{project['title']}'",
        "project_id": project["_id"],
        "is_read": False,
        "created_at": datetime.now(timezone.utc),
    })

    return {"message": "Application accepted and developer assigned", "assigned_to": str(application["developer_id"])}


# ============================================================================
# REJECT APPLICATION — salesperson (owner) only
# ============================================================================

@router.post("/{project_id}/applications/{application_id}/reject")
async def reject_application(
    project_id: str,
    application_id: str,
    current_user: dict = Depends(require_role("salesperson"))
):
    db = get_database()
    project = await db.projects.find_one({"_id": to_object_id(project_id)})

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project["salesperson_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="You can only manage applications for your own projects")

    try:
        application_oid = ObjectId(application_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid application ID")

    application = next(
        (a for a in project.get("applications", []) if a["application_id"] == application_oid),
        None
    )

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    if application["status"] != "pending":
        raise HTTPException(status_code=400, detail="This application has already been processed")

    result = await db.projects.update_one(
        {"_id": project["_id"], "applications.application_id": application_oid},
        {"$set": {"applications.$.status": "rejected"}}
    )

    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="Could not reject this application")

    return {"message": "Application rejected"}

# ============================================================================
# PRICE: the agreed amount, and proposals to change it
#
# The salesperson can ask for a different price at any time before the project
# is funded, but the new price only takes effect once the assigned developer
# approves it. Only the agreed price can be invoiced.
# ============================================================================

async def _is_funded(db, project_oid: ObjectId) -> bool:
    return await db.transactions.find_one({"project_id": project_oid, "status": "success"}) is not None


@router.get("/{project_id}/price")
async def get_price(project_id: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    project = await db.projects.find_one({"_id": to_object_id(project_id)})

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if current_user["_id"] not in (project["salesperson_id"], project.get("assigned_to")):
        raise HTTPException(status_code=403, detail="Only the people working on this project can see its price")

    return {
        "agreed_amount": get_agreed_amount(project),
        "currency": project.get("currency", settings.CURRENCY),
        "price_proposal": serialize_proposal(project.get("price_proposal")),
        "is_funded": await _is_funded(db, project["_id"]),
    }


@router.post("/{project_id}/price-proposal", status_code=status.HTTP_201_CREATED)
async def propose_price(
    project_id: str,
    proposal: PriceProposalCreate,
    current_user: dict = Depends(require_role("salesperson"))
):
    db = get_database()
    project = await db.projects.find_one({"_id": to_object_id(project_id)})

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project["salesperson_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="You can only change the price of your own projects")

    if project["status"] != "in_progress" or not project.get("assigned_to"):
        raise HTTPException(status_code=400, detail="A price can only be changed while a developer is working on the project")

    if await _is_funded(db, project["_id"]):
        raise HTTPException(status_code=400, detail="This project is already funded, so its price can no longer change")

    amount = round_money(proposal.amount)
    check_amount_limits(amount)

    if amount == get_agreed_amount(project):
        raise HTTPException(status_code=400, detail="That is already the agreed price")

    await db.projects.update_one(
        {"_id": project["_id"]},
        {"$set": {
            "price_proposal": {
                "amount": amount,
                "reason": proposal.reason.strip(),
                "status": "pending",
                "proposed_by": current_user["_id"],
                "proposed_at": datetime.now(timezone.utc),
                "responded_at": None,
                "response_note": None,
            },
            "updated_at": datetime.now(timezone.utc),
        }}
    )

    await db.notifications.insert_one({
        "user_id": project["assigned_to"],
        "type": "price_change_requested",
        "title": "Price change needs your approval",
        "description": (
            f"The price for '{project['title']}' would change from "
            f"{settings.CURRENCY} {get_agreed_amount(project):,.2f} to {settings.CURRENCY} {amount:,.2f}"
        ),
        "project_id": project["_id"],
        "is_read": False,
        "created_at": datetime.now(timezone.utc),
    })

    return {"message": "Price change sent to the developer for approval"}


@router.delete("/{project_id}/price-proposal")
async def withdraw_price_proposal(
    project_id: str,
    current_user: dict = Depends(require_role("salesperson"))
):
    db = get_database()
    project = await db.projects.find_one({"_id": to_object_id(project_id)})

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project["salesperson_id"] != current_user["_id"]:
        raise HTTPException(status_code=403, detail="You can only change the price of your own projects")

    result = await db.projects.update_one(
        {"_id": project["_id"], "price_proposal.status": "pending"},
        {"$set": {"price_proposal.status": "withdrawn", "price_proposal.responded_at": datetime.now(timezone.utc)}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=400, detail="There is no pending price change to withdraw")

    return {"message": "Price change withdrawn"}


@router.post("/{project_id}/price-proposal/respond")
async def respond_to_price_proposal(
    project_id: str,
    decision: PriceProposalDecision,
    current_user: dict = Depends(require_role("developer"))
):
    db = get_database()
    project = await db.projects.find_one({"_id": to_object_id(project_id)})

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project.get("assigned_to") != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Only the assigned developer can respond to a price change")

    proposal = project.get("price_proposal")
    if not proposal or proposal["status"] != "pending":
        raise HTTPException(status_code=400, detail="There is no pending price change to respond to")

    if decision.approve and await _is_funded(db, project["_id"]):
        raise HTTPException(status_code=400, detail="This project is already funded, so its price can no longer change")

    new_status = "approved" if decision.approve else "rejected"
    changes = {
        "price_proposal.status": new_status,
        "price_proposal.responded_at": datetime.now(timezone.utc),
        "price_proposal.response_note": decision.note.strip() if decision.note else None,
        "updated_at": datetime.now(timezone.utc),
    }
    if decision.approve:
        changes["agreed_amount"] = proposal["amount"]

    # Conditional on the proposal still being the same pending one we looked at,
    # so a double click, or a proposal replaced in the meantime, cannot slip through.
    result = await db.projects.update_one(
        {
            "_id": project["_id"],
            "assigned_to": current_user["_id"],
            "price_proposal.status": "pending",
            "price_proposal.amount": proposal["amount"],
        },
        {"$set": changes}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=409, detail="This price change was updated by the salesperson. Please review it again.")

    if decision.approve:
        # Any unpaid payment link was created at the old price and must not be payable any more.
        await db.transactions.update_many(
            {"project_id": project["_id"], "status": "pending"},
            {"$set": {"status": "cancelled", "cancelled_reason": "price_changed"}}
        )

    await db.notifications.insert_one({
        "user_id": project["salesperson_id"],
        "type": "price_change_approved" if decision.approve else "price_change_rejected",
        "title": "Price change approved" if decision.approve else "Price change declined",
        "description": (
            f"The developer {'approved' if decision.approve else 'declined'} "
            f"{settings.CURRENCY} {proposal['amount']:,.2f} for '{project['title']}'"
        ),
        "project_id": project["_id"],
        "is_read": False,
        "created_at": datetime.now(timezone.utc),
    })

    return {
        "message": "Price change approved" if decision.approve else "Price change declined",
        "agreed_amount": proposal["amount"] if decision.approve else get_agreed_amount(project),
    }



# ============================================================================
# DELIVERY AND PROBLEM REPORTS
# ============================================================================

@router.post("/{project_id}/deliver")
async def mark_delivered(
    project_id: str,
    current_user: dict = Depends(require_role("developer"))
):
    """The assigned developer says the work is done. This starts the client's review window."""
    db = get_database()
    project = await db.projects.find_one({"_id": to_object_id(project_id)})

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.get("assigned_to") != current_user["_id"]:
        raise HTTPException(status_code=403, detail="Only the assigned developer can mark this delivered")

    result = await deliver_project(db, project)
    return {
        "message": "Marked as delivered. The client now has time to review it.",
        "review_deadline": result["review_deadline"],
    }


@router.post("/{project_id}/dispute", status_code=status.HTTP_201_CREATED)
async def report_problem(
    project_id: str,
    report: ProblemReport,
    current_user: dict = Depends(get_current_user)
):
    """The salesperson or developer on a paid project reports a problem. This freezes the release."""
    db = get_database()
    project = await db.projects.find_one({"_id": to_object_id(project_id)})

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if current_user["_id"] == project["salesperson_id"]:
        role = "salesperson"
    elif current_user["_id"] == project.get("assigned_to"):
        role = "developer"
    else:
        raise HTTPException(status_code=403, detail="Only the people on this project can report a problem")

    await open_dispute(db, project, role, report.reason)
    return {"message": "Your report was received. The payment will not be released until it has been reviewed."}
