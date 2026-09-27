from fastapi import APIRouter, Depends, HTTPException, Query
from bson import ObjectId
from bson.errors import InvalidId

from app.database import get_database
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])


def to_object_id(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ID format")


@router.get("")
async def list_conversations(current_user: dict = Depends(get_current_user)):
    db = get_database()

    cursor = db.conversations.find(
        {"participants": current_user["_id"]}
    ).sort("last_message_at", -1)

    conversations = await cursor.to_list(length=100)

    result = []
    for conv in conversations:
        other_id = next((p for p in conv["participants"] if p != current_user["_id"]), None)
        other_user = await db.users.find_one({"_id": other_id}) if other_id else None
        project = await db.projects.find_one({"_id": conv["project_id"]})

        result.append({
            "id": str(conv["_id"]),
            "other_participant_id": str(other_id) if other_id else None,
            "other_participant_name": f"{other_user['first_name']} {other_user['last_name']}" if other_user else None,
            "project_id": str(conv["project_id"]),
            "project_title": project["title"] if project else None,
            "last_message": conv.get("last_message"),
            "last_message_at": conv.get("last_message_at"),
            "unread_count": conv.get("unread_count", {}).get(str(current_user["_id"]), 0),
        })

    return {"data": result, "total": len(result)}

@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    conv_oid = to_object_id(conversation_id)

    conversation = await db.conversations.find_one({"_id": conv_oid})
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if current_user["_id"] not in conversation["participants"]:
        raise HTTPException(status_code=403, detail="You are not part of this conversation")

    other_id = next((p for p in conversation["participants"] if p != current_user["_id"]), None)
    other_user = await db.users.find_one({"_id": other_id}) if other_id else None
    project = await db.projects.find_one({"_id": conversation["project_id"]})

    return {
        "id": str(conversation["_id"]),
        "other_participant_id": str(other_id) if other_id else None,
        "other_participant_name": f"{other_user['first_name']} {other_user['last_name']}" if other_user else None,
        "project_id": str(conversation["project_id"]),
        "project_title": project["title"] if project else None,
        "last_message_at": conversation.get("last_message_at"),
        "created_at": conversation.get("created_at"),
    }


@router.get("/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    db = get_database()
    print(f"DEBUG: querying database '{db.name}' for conversation_id '{conversation_id}'")
    conv_oid = to_object_id(conversation_id)

    conversation = await db.conversations.find_one({"_id": conv_oid})
    print(f"DEBUG: found conversation? {conversation is not None}")
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if current_user["_id"] not in conversation["participants"]:
        raise HTTPException(status_code=403, detail="You are not part of this conversation")

    total = await db.messages.count_documents({"conversation_id": conv_oid})
    skip = (page - 1) * per_page

    cursor = db.messages.find({"conversation_id": conv_oid}) \
        .sort("created_at", -1).skip(skip).limit(per_page)
    messages = await cursor.to_list(length=per_page)
    messages.reverse()  # chronological order for display

    data = []
    for m in messages:
        sender = await db.users.find_one({"_id": m["sender_id"]})
        data.append({
            "id": str(m["_id"]),
            "sender_id": str(m["sender_id"]),
            "sender_name": f"{sender['first_name']} {sender['last_name']}" if sender else None,
            "content": m["content"],
            "is_read": m.get("is_read", False),
            "created_at": m["created_at"],
        })

    # Mark unread messages (sent to current user) as read
    await db.messages.update_many(
        {"conversation_id": conv_oid, "receiver_id": current_user["_id"], "is_read": False},
        {"$set": {"is_read": True}}
    )
    await db.conversations.update_one(
        {"_id": conv_oid},
        {"$set": {f"unread_count.{str(current_user['_id'])}": 0}}
    )

    return {
        "data": data,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }