"""
Admin tool for problem reports (disputes). Run it from the backend folder, or on Fly with:

    fly ssh console -C "python -m scripts.resolve_dispute list"

Commands:
    list                         open disputes, oldest first
    show <project_id>            everything you need to decide one
    resolve <project_id> release|refund|split [--refund-amount N] [--note "..."]

For refund and split, issue the refund to the client in the Paystack dashboard FIRST
(Transactions -> the payment -> Refund). This tool then records the outcome, pays out
whatever remains and tells the developer and salesperson. It never moves money at Paystack.
"""
import argparse
import asyncio
import sys

from bson import ObjectId
from bson.errors import InvalidId

from app import database
from app.config import settings
from app.delivery import resolve_dispute, held_transaction


def _oid(value: str) -> ObjectId:
    try:
        return ObjectId(value)
    except InvalidId:
        sys.exit(f"'{value}' is not a valid project id")


async def _name(db, user_id) -> str:
    user = await db.users.find_one({"_id": user_id}) if user_id else None
    if not user:
        return "(none)"
    return f"{user['first_name']} {user['last_name']} <{user['email']}>"


async def cmd_list(db, _args):
    cursor = db.projects.find({"dispute.status": "open"}).sort("dispute.opened_at", 1)
    projects = await cursor.to_list(length=None)
    if not projects:
        print("No open disputes.")
        return
    for p in projects:
        d = p["dispute"]
        print(f"{p['_id']}  {p['title']!r}  opened by {d['opened_by']} on {d['opened_at']:%d %b %Y}")


async def cmd_show(db, args):
    project = await db.projects.find_one({"_id": _oid(args.project_id)})
    if not project:
        sys.exit("Project not found")

    tx = await held_transaction(db, project["_id"]) or await db.transactions.find_one(
        {"project_id": project["_id"], "status": "success"}
    )
    d = project.get("dispute") or {}
    delivery = project.get("delivery") or {}

    print(f"Project:     {project['title']}  ({project['_id']})  status={project['status']}")
    print(f"Client:      {project.get('client_name')} <{project.get('client_email')}>")
    print(f"Salesperson: {await _name(db, project['salesperson_id'])}")
    print(f"Developer:   {await _name(db, project.get('assigned_to'))}")
    print(f"Delivery:    {delivery.get('status', 'not delivered')}  delivered {delivery.get('delivered_at')}  window ends {delivery.get('review_deadline')}")
    print(f"Dispute:     {d.get('status')}  opened by {d.get('opened_by')} on {d.get('opened_at')}")
    print(f"Reason:      {d.get('reason')}")
    if d.get("status") == "resolved":
        print(f"Resolution:  {d.get('resolution')}  {d.get('resolution_note') or ''}")
    if tx:
        print(f"Payment:     {settings.CURRENCY} {tx['total_amount']:,.2f}  escrow={tx['escrow_status']}  paystack ref={tx.get('paystack_reference')}")
    else:
        print("Payment:     none found")


async def cmd_resolve(db, args):
    project_id = _oid(args.project_id)

    if args.outcome in ("refund", "split"):
        print("Before continuing: have you already issued this refund to the client in the Paystack dashboard?")
        if input("Type 'yes' to continue: ").strip().lower() != "yes":
            sys.exit("Stopped. Issue the refund in Paystack first, then run this again.")
    elif args.outcome == "release":
        if input("This pays out the full amount. Type 'yes' to continue: ").strip().lower() != "yes":
            sys.exit("Stopped.")

    try:
        result = await resolve_dispute(db, project_id, args.outcome, args.refund_amount, args.note)
    except ValueError as e:
        sys.exit(f"Could not resolve: {e}")

    print(f"Done. Outcome: {result['outcome']}. Recorded as refunded: {settings.CURRENCY} {result['refunded']:,.2f}. Project is now {result['project_status']}.")


async def main():
    parser = argparse.ArgumentParser(description="Resolve ProjecTech disputes")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list")

    show = sub.add_parser("show")
    show.add_argument("project_id")

    res = sub.add_parser("resolve")
    res.add_argument("project_id")
    res.add_argument("outcome", choices=["release", "refund", "split"])
    res.add_argument("--refund-amount", type=float, default=None, help="Required for split: the amount already refunded to the client")
    res.add_argument("--note", default=None, help="Short note recorded on the dispute")

    args = parser.parse_args()

    await database.connect_to_mongo()
    try:
        await {"list": cmd_list, "show": cmd_show, "resolve": cmd_resolve}[args.command](database.get_database(), args)
    finally:
        await database.close_mongo_connection()


if __name__ == "__main__":
    asyncio.run(main())
