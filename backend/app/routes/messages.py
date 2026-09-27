from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timezone
from bson import ObjectId

from app.database import get_database
from app.dependencies import get_current_user
from app.schemas import MessageCreate
from app.websocket_manager import manager
import time
start = time.time()

router = APIRouter(prefix="/api/messages", tags=["Messages"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def send_message(
    message_data: MessageCreate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()

    try:
        receiver_oid = ObjectId(message_data.receiver_id)
        project_oid = ObjectId(message_data.project_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid receiver_id or project_id")

    project = await db.projects.find_one({"_id": project_oid})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    receiver = await db.users.find_one({"_id": receiver_oid})
    if not receiver:
        raise HTTPException(status_code=404, detail="Receiver not found")

    # Both users must be tied to this project (salesperson or assigned developer)
    project_people = {project["salesperson_id"], project.get("assigned_to")}
    if current_user["_id"] not in project_people or receiver_oid not in project_people:
        raise HTTPException(
            status_code=403,
            detail="Both users must be involved in this project to exchange messages"
        )

    # Find or create conversation
    conversation = await db.conversations.find_one({
        "participants": {"$all": [current_user["_id"], receiver_oid]},
        "project_id": project_oid
    })

    if not conversation:
        conv_result = await db.conversations.insert_one({
            "participants": [current_user["_id"], receiver_oid],
            "project_id": project_oid,
            "last_message": None,
            "last_message_at": None,
            "unread_count": {str(current_user["_id"]): 0, str(receiver_oid): 0},
            "created_at": datetime.now(timezone.utc),
        })
        conversation_id = conv_result.inserted_id
    else:
        conversation_id = conversation["_id"]

    message_doc = {
        "conversation_id": conversation_id,
        "sender_id": current_user["_id"],
        "receiver_id": receiver_oid,
        "project_id": project_oid,
        "content": message_data.content,
        "is_read": False,
        "created_at": datetime.now(timezone.utc),
    }

    result = await db.messages.insert_one(message_doc)

    await db.conversations.update_one(
        {"_id": conversation_id},
        {
            "$set": {
                "last_message": message_data.content,
                "last_message_at": datetime.now(timezone.utc),
            },
            "$inc": {f"unread_count.{str(receiver_oid)}": 1}
        }
    )

    # Create a notification
    await db.notifications.insert_one({
        "user_id": receiver_oid,
        "type": "message_received",
        "title": "New message",
        "description": f"{current_user['first_name']} sent you a message",
        "project_id": project_oid,
        "conversation_id": conversation_id,
        "is_read": False,
        "created_at": datetime.now(timezone.utc),
    })

    payload = {
        "event": "new_message",
        "message_id": str(result.inserted_id),
        "conversation_id": str(conversation_id),
        "sender_id": str(current_user["_id"]),
        "sender_name": f"{current_user['first_name']} {current_user['last_name']}",
        "content": message_data.content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Push live to receiver if connected
    await manager.send_personal_message(str(receiver_oid), payload)
    # Echo back to sender's other tabs/devices if connected
    await manager.send_personal_message(str(current_user["_id"]), payload)

    return {
        "message": "Message sent",
        "message_id": str(result.inserted_id),
        "conversation_id": str(conversation_id),
    }