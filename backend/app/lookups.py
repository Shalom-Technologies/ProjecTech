"""Fetch many documents in one query instead of one query per row."""


async def users_by_id(db, ids) -> dict:
    ids = list({i for i in ids if i})
    if not ids:
        return {}
    return {u["_id"]: u async for u in db.users.find({"_id": {"$in": ids}})}


async def projects_by_id(db, ids) -> dict:
    ids = list({i for i in ids if i})
    if not ids:
        return {}
    return {p["_id"]: p async for p in db.projects.find({"_id": {"$in": ids}})}
