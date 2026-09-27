from fastapi import APIRouter, Depends
from app.database import get_database
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("")
async def list_notifications(current_user: dict = Depends(get_current_user)):
    db = get_database()
    cursor = db.notifications.find(
        {"user_id": current_user["_id"]}
    ).sort("created_at", -1).limit(50)

    notifications = await cursor.to_list(length=50)

    return {
        "data": [
            {
                "id": str(n["_id"]),
                "type": n["type"],
                "title": n["title"],
                "description": n["description"],
                "is_read": n.get("is_read", False),
                "created_at": n["created_at"],
            }
            for n in notifications
        ]
    }


@router.put("/{notification_id}/read")
async def mark_notification_read(notification_id: str, current_user: dict = Depends(get_current_user)):
    from bson import ObjectId
    db = get_database()
    await db.notifications.update_one(
        {"_id": ObjectId(notification_id), "user_id": current_user["_id"]},
        {"$set": {"is_read": True}}
    )
    return {"message": "Marked as read"}