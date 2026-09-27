from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import datetime, timezone
from bson import ObjectId
from bson.errors import InvalidId

from app.database import get_database
from app.dependencies import get_current_user
from app.schemas import ReviewCreate

router = APIRouter(prefix="/api/reviews", tags=["Reviews"])


def to_object_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ID format")


@router.post("", status_code=201)
async def create_review(
    review_data: ReviewCreate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    project_oid = to_object_id(review_data.project_id)
    reviewed_oid = to_object_id(review_data.reviewed_user_id)

    project = await db.projects.find_one({"_id": project_oid})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if project["status"] != "completed":
        raise HTTPException(status_code=400, detail="You can only review completed projects")

    project_people = {project["salesperson_id"], project.get("assigned_to")}
    if current_user["_id"] not in project_people or reviewed_oid not in project_people:
        raise HTTPException(status_code=403, detail="You can only review someone you worked with on this project")

    if current_user["_id"] == reviewed_oid:
        raise HTTPException(status_code=400, detail="You cannot review yourself")

    existing = await db.reviews.find_one({
        "project_id": project_oid,
        "reviewer_id": current_user["_id"],
    })
    if existing:
        raise HTTPException(status_code=400, detail="You have already reviewed this project")

    review_doc = {
        "project_id": project_oid,
        "reviewer_id": current_user["_id"],
        "reviewed_user_id": reviewed_oid,
        "rating": review_data.rating,
        "comment": review_data.comment,
        "created_at": datetime.now(timezone.utc),
    }
    await db.reviews.insert_one(review_doc)

    # Recalculate the reviewed user's average rating
    cursor = db.reviews.find({"reviewed_user_id": reviewed_oid})
    all_reviews = await cursor.to_list(length=1000)
    avg_rating = sum(r["rating"] for r in all_reviews) / len(all_reviews)

    await db.users.update_one(
        {"_id": reviewed_oid},
        {"$set": {"average_rating": round(avg_rating, 2), "total_reviews": len(all_reviews)}}
    )
    print(f"DEBUG: updated user {reviewed_oid} -> avg={round(avg_rating,2)}, total={len(all_reviews)}")

    return {"message": "Review submitted successfully"}


@router.get("/user/{user_id}")
async def get_user_reviews(
    user_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
):
    db = get_database()
    user_oid = to_object_id(user_id)

    query = {"reviewed_user_id": user_oid}
    total = await db.reviews.count_documents(query)
    skip = (page - 1) * per_page

    cursor = db.reviews.find(query).sort("created_at", -1).skip(skip).limit(per_page)
    reviews = await cursor.to_list(length=per_page)

    data = []
    for r in reviews:
        reviewer = await db.users.find_one({"_id": r["reviewer_id"]})
        project = await db.projects.find_one({"_id": r["project_id"]})
        data.append({
            "id": str(r["_id"]),
            "reviewer_name": f"{reviewer['first_name']} {reviewer['last_name']}" if reviewer else "Unknown",
            "project_title": project["title"] if project else None,
            "rating": r["rating"],
            "comment": r["comment"],
            "created_at": r["created_at"],
        })

    return {
        "data": data,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


@router.get("/check/{project_id}")
async def check_has_reviewed(
    project_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    project_oid = to_object_id(project_id)

    existing = await db.reviews.find_one({
        "project_id": project_oid,
        "reviewer_id": current_user["_id"],
    })
    return {"has_reviewed": existing is not None}