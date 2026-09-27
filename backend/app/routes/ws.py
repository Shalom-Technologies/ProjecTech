from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from bson import ObjectId
from bson.errors import InvalidId
import jwt

from app.security import decode_access_token
from app.database import get_database
from app.websocket_manager import manager

router = APIRouter(tags=["WebSocket"])


async def get_contact_ids(db, user_id: ObjectId) -> set:
    """All other users this person has a conversation with."""
    cursor = db.conversations.find({"participants": user_id})
    conversations = await cursor.to_list(length=200)
    contacts = set()
    for conv in conversations:
        for p in conv["participants"]:
            if p != user_id:
                contacts.add(str(p))
    return contacts


@router.websocket("/ws/messages")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(...)):
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        if not user_id:
            await websocket.close(code=4001)
            return
    except jwt.PyJWTError:
        await websocket.close(code=4001)
        return

    db = get_database()
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except InvalidId:
        await websocket.close(code=4001)
        return

    if not user:
        await websocket.close(code=4001)
        return

    await manager.connect(user_id, websocket)

    contact_ids = await get_contact_ids(db, user["_id"])

    # Tell this user which of their contacts are currently online
    online_now = manager.get_online_ids(contact_ids)
    await manager.send_personal_message(user_id, {
        "event": "presence_snapshot",
        "online_user_ids": online_now,
    })

    # Tell each online contact that this user just came online
    for contact_id in contact_ids:
        if manager.is_online(contact_id):
            await manager.send_personal_message(contact_id, {
                "event": "presence_online",
                "user_id": user_id,
            })

    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, RuntimeError):
        manager.disconnect(user_id, websocket)
        # Only announce "offline" if the user has no other open connections/tabs
        if not manager.is_online(user_id):
            for contact_id in contact_ids:
                await manager.send_personal_message(contact_id, {
                    "event": "presence_offline",
                    "user_id": user_id,
                })