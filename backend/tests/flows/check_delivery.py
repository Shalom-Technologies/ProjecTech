"""Drives the real route functions (projects.py, payments.py) against a fake in-memory DB."""
import asyncio, importlib.util, itertools, json, sys, types, hashlib, hmac
from datetime import datetime, timezone

import os
BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# ---------- stubs for packages that aren't installable here ----------
class HTTPException(Exception):
    def __init__(self, status_code, detail=None): self.status_code, self.detail = status_code, detail
fastapi = types.ModuleType("fastapi")
class APIRouter:
    def __init__(self, *a, **k): pass
    def _d(self, *a, **k): return lambda f: f
    get = post = put = delete = websocket = _d
fastapi.APIRouter, fastapi.HTTPException = APIRouter, HTTPException
fastapi.Depends = lambda x=None: x
fastapi.Query = lambda default=None, **k: default
fastapi.Request = object
fastapi.status = types.SimpleNamespace(HTTP_201_CREATED=201, HTTP_204_NO_CONTENT=204)
sys.modules["fastapi"] = fastapi

class InvalidId(Exception): pass
_ctr = itertools.count(1)
class ObjectId:
    def __init__(self, v=None):
        if v is None: self.v = f"oid{next(_ctr)}"
        elif isinstance(v, ObjectId): self.v = v.v
        elif isinstance(v, str) and v.startswith("oid"): self.v = v
        else: raise InvalidId(v)
    def __eq__(self, o): return isinstance(o, ObjectId) and o.v == self.v
    def __hash__(self): return hash(self.v)
    def __repr__(self): return self.v
    __str__ = __repr__
bson = types.ModuleType("bson"); bson.ObjectId = ObjectId
berr = types.ModuleType("bson.errors"); berr.InvalidId = InvalidId
sys.modules["bson"], sys.modules["bson.errors"] = bson, berr

pk = types.ModuleType("pymongo"); pke = types.ModuleType("pymongo.errors")
class DuplicateKeyError(Exception): pass
pke.DuplicateKeyError = DuplicateKeyError; sys.modules["pymongo"], sys.modules["pymongo.errors"] = pk, pke
import pydantic; pydantic.EmailStr = str   # email_validator not installed

# ---------- fake DB ----------
def getp(d, path):
    for part in path.split("."):
        if not isinstance(d, dict) or part not in d: return None
        d = d[part]
    return d
def setp(d, path, v):
    parts = path.split(".")
    for part in parts[:-1]: d = d.setdefault(part, {})
    d[parts[-1]] = v
def vals(d, parts):
    """All values at a dotted path, looking inside lists like MongoDB does."""
    if not parts: return [d]
    if isinstance(d, list):
        out = []
        for x in d: out += vals(x, parts)
        return out
    if isinstance(d, dict) and parts[0] in d: return vals(d[parts[0]], parts[1:])
    return []
def cond(actual_list, v):
    if v is None: return not actual_list or all(a is None for a in actual_list)
    if isinstance(v, dict) and any(x.startswith("$") for x in v):
        ok = True
        if "$in" in v: ok &= any(a in v["$in"] for a in actual_list)
        if "$ne" in v: ok &= not any(a == v["$ne"] for a in actual_list)
        if "$lte" in v: ok &= any(a is not None and a <= v["$lte"] for a in actual_list)
        if "$gte" in v: ok &= any(a is not None and a >= v["$gte"] for a in actual_list)
        return ok
    return any(a == v for a in actual_list)
def match(doc, q):
    return all(cond(vals(doc, k.split(".")), v) for k, v in q.items())

class Coll:
    def __init__(self): self.docs, self.after_find = [], None
    async def find_one(self, q):
        for d in self.docs:
            if match(d, q):
                snap = json.loads(json.dumps(d, default=lambda o: o)) if False else dict(d)
                snap = {k: (dict(v) if isinstance(v, dict) else v) for k, v in d.items()}
                if self.after_find: hook, self.after_find = self.after_find, None; hook(d)
                return snap
        return None
    async def insert_one(self, doc):
        doc.setdefault("_id", ObjectId()); self.docs.append(doc)
        return types.SimpleNamespace(inserted_id=doc["_id"])
    def _apply(self, d, u, q=None, af=None):
        for k, v in u.get("$set", {}).items():
            if ".$[elem]." in k:       # array_filters update on every matching element
                arr, field = k.split(".$[elem].")
                for el in d[arr]:
                    if all(cond(vals(el, kk.split(".")[1:]), vv) for kk, vv in af[0].items()): el[field] = v
            elif ".$." in k:           # positional: the element matched by the query
                arr, field = k.split(".$.")
                want = next(vv for kk, vv in q.items() if kk.startswith(arr + "."))
                for el in d[arr]:
                    if el.get(next(kk for kk in q if kk.startswith(arr + ".")).split(".")[1]) == want: el[field] = v
            else: setp(d, k, v)
        for k, v in u.get("$inc", {}).items(): setp(d, k, (getp(d, k) or 0) + v)
    async def update_one(self, q, u, array_filters=None):
        for d in self.docs:
            if match(d, q): self._apply(d, u, q, array_filters); return types.SimpleNamespace(modified_count=1)
        return types.SimpleNamespace(modified_count=0)
    async def find_one_and_update(self, q, u):
        for d in self.docs:
            if match(d, q):
                before = {k: (dict(v) if isinstance(v, dict) else v) for k, v in d.items()}
                self._apply(d, u, q); return before
        return None
    async def update_many(self, q, u):
        n = 0
        for d in self.docs:
            if match(d, q): self._apply(d, u); n += 1
        return types.SimpleNamespace(modified_count=n)
class DB:
    def __init__(self): self.c = {}
    def __getattr__(self, n): return self.c.setdefault(n, Coll())
db = DB()

# ---------- app package stubs + real modules ----------
def mod(name, **attrs):
    m = types.ModuleType(name); m.__dict__.update(attrs); sys.modules[name] = m; return m
app = mod("app"); app.__path__ = []
mod("app.routes").__path__ = []
mod("app.config", settings=types.SimpleNamespace(
    CURRENCY="KES", REVIEW_WINDOW_DAYS=7, PAYOUT_HOLD_DAYS=7, MIN_PAYMENT_AMOUNT=100.0, MAX_PAYMENT_AMOUNT=5_000_000.0, FRONTEND_URL="http://x",
    PAYSTACK_SECRET_KEY="sk_test", DEVELOPER_COMMISSION=0.45, SALESPERSON_COMMISSION=0.35))
mod("app.database", get_database=lambda: db)
mod("app.dependencies", get_current_user=lambda: None, require_role=lambda *r: (lambda: None))
mod("app.rate_limit", limiter=types.SimpleNamespace(limit=lambda s: (lambda f: f)))
paystack_calls = []
class FakePaystack:
    async def verify_transaction(self, reference):
        return {"data": {"status": "success"}}   # pretend the client really paid
    async def initialize_transaction(self, **kw):
        paystack_calls.append(kw); n = len(paystack_calls)
        return {"data": {"reference": f"ref{n}", "access_code": f"ac{n}", "authorization_url": f"https://pay/{n}"}}
mod("app.paystack_client", paystack=FakePaystack())
mod("httpx", HTTPStatusError=Exception, RequestError=Exception)

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, f"{BACKEND}/{path}")
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m; spec.loader.exec_module(m); return m
emails = []
async def send_review_started_email(**kw): emails.append(kw)
mod("app.email_client", send_review_started_email=send_review_started_email)
load("app.lookups", "app/lookups.py"); load("app.schemas", "app/schemas.py"); load("app.pricing", "app/pricing.py"); load("app.wallet", "app/wallet.py")
load("app.escrow", "app/escrow.py"); delivery = load("app.delivery", "app/delivery.py")
projects = load("app.routes.projects", "app/routes/projects.py")
payments = load("app.routes.payments", "app/routes/payments.py")
invoices = load("app.routes.invoices", "app/routes/invoices.py")
from app.schemas import PriceProposalCreate, PriceProposalDecision, PaymentInitialize

# ---------- helpers ----------
results = []
def check(name, cond):
    results.append(cond); print("PASS" if cond else "FAIL", name)
async def expect_http(name, code, coro):
    try: await coro; check(f"{name} (expected {code}, got success)", False)
    except HTTPException as e: check(f"{name} -> {e.status_code}", e.status_code == code)

class FakeReq:
    def __init__(self, body, sig): self._b, self.headers = body, {"x-paystack-signature": sig}
    async def body(self): return self._b
    async def json(self): return json.loads(self._b)
async def webhook(event, data):
    body = json.dumps({"event": event, "data": data}).encode()
    sig = hmac.new(b"sk_test", body, hashlib.sha512).hexdigest()
    return await payments.paystack_webhook(FakeReq(body, sig))

async def make_project(proposed=80000.0, budget=90000.0):
    sales = {"_id": ObjectId(), "role": "salesperson"}; dev = {"_id": ObjectId(), "role": "developer"}
    appid = ObjectId()
    proj = {"_id": ObjectId(), "title": "Build a shop", "salesperson_id": sales["_id"], "status": "open", "assigned_to": None,
            "budget": budget, "client_email": "c@x.com",
            "applications": [{"application_id": appid, "developer_id": dev["_id"], "proposed_budget": proposed, "status": "pending"}]}
    db.projects.docs.append(proj)
    await projects.accept_application(str(proj["_id"]), str(appid), current_user=sales)
    return sales, dev, proj


from datetime import timedelta
from app.schemas import ProblemReport

async def funded_project():
    sales, dev, proj = await make_project(80000.0)
    pid = str(proj["_id"])
    link = await payments.create_or_get_payment_link(db, await db.projects.find_one({"_id": proj["_id"]}))
    tx = await db.transactions.find_one({"project_id": proj["_id"], "status": "pending"})
    tx["developer_id"] = dev["_id"]
    await payments._mark_transaction_successful(db, tx)
    return sales, dev, proj

async def user(u): return await db.users.find_one({"_id": u["_id"]})

async def main():
    for u in ("a",): pass
    # ---- happy path ----
    sales, dev, proj = await funded_project()
    pid = str(proj["_id"])
    for u in (sales, dev): db.users.docs.append({"_id": u["_id"], "first_name": "A", "last_name": "B", "email": "e@x.com", "wallet_balance": 0.0, "pending_balance": 0.0, "total_earned": 0.0})

    await expect_http("cannot deliver an unpaid project", 400, projects.mark_delivered(pid, current_user=dev)) if False else None
    r = await projects.mark_delivered(pid, current_user=dev)
    p = await db.projects.find_one({"_id": proj["_id"]})
    check("deliver sets delivered + 7 day deadline", p["delivery"]["status"] == "delivered" and 6.9 < (p["delivery"]["review_deadline"] - p["delivery"]["delivered_at"]).total_seconds() / 86400 < 7.1)
    check("client emailed on delivery", len(emails) == 1 and emails[0]["to_email"] == "c@x.com" and "/pay/" in emails[0]["invoice_url"])
    await expect_http("delivering twice -> 409", 409, projects.mark_delivered(pid, current_user=dev))
    await expect_http("another developer cannot deliver", 403, projects.mark_delivered(pid, current_user={"_id": ObjectId()}))

    token = p.get("invoice_token") or emails[0]["invoice_url"].rsplit("/", 1)[1]
    view = await invoices.view_invoice(None, token)
    check("invoice shows in_review with deadline", view["status"] == "in_review" and view["review_deadline"] is not None)

    # release route cannot release early
    tx = await db.transactions.find_one({"project_id": proj["_id"], "status": "success"})
    await expect_http("release before window ends -> 400", 400, payments.release_escrow(tx["transaction_id"], current_user=sales))
    await expect_http("salesperson cannot mark completed", 400, projects.update_project(pid, projects.ProjectUpdate(status="completed"), current_user=sales))
    await expect_http("funded project cannot be cancelled", 400, projects.update_project(pid, projects.ProjectUpdate(status="cancelled"), current_user=sales))

    # client accepts
    await invoices.accept_invoice_delivery(None, token)
    p = await db.projects.find_one({"_id": proj["_id"]})
    tx = await db.transactions.find_one({"project_id": proj["_id"], "status": "success"})
    check("accept completes project + releases escrow", p["status"] == "completed" and tx["escrow_status"] == "released")
    d, s = await user(dev), await user(sales)
    check("earnings go to pending, not wallet", d["wallet_balance"] == 0 and round(d["pending_balance"], 2) == 36000.0 and round(s["pending_balance"], 2) == 28000.0)
    await expect_http("accept twice -> 400", 400, invoices.accept_invoice_delivery(None, token))
    await expect_http("manual release after settle -> 400", 400, payments.release_escrow(tx["transaction_id"], current_user=sales))
    check("invoice shows completed", (await invoices.view_invoice(None, token))["status"] == "completed")

    # payout hold matures
    check("nothing matures early", await delivery.release_matured_holds(db) == 0)
    for w in db.wallet_transactions.docs:
        if w.get("status") == "held": w["available_at"] = datetime.now(timezone.utc) - timedelta(minutes=1)
    check("holds mature", await delivery.release_matured_holds(db) == 2)
    check("second maturity run is a no-op", await delivery.release_matured_holds(db) == 0)
    d, s = await user(dev), await user(sales)
    check("matured money is withdrawable", round(d["wallet_balance"], 2) == 36000.0 and round(d["pending_balance"], 2) == 0 and round(s["wallet_balance"], 2) == 28000.0)

    # ---- auto release ----
    sales2, dev2, proj2 = await funded_project()
    for u in (sales2, dev2): db.users.docs.append({"_id": u["_id"], "first_name": "A", "last_name": "B", "email": "e@x.com", "wallet_balance": 0.0, "pending_balance": 0.0, "total_earned": 0.0})
    await projects.mark_delivered(str(proj2["_id"]), current_user=dev2)
    check("not due yet", await delivery.process_due_deliveries(db) == 0)
    (await_p := [x for x in db.projects.docs if x["_id"] == proj2["_id"]][0])["delivery"]["review_deadline"] = datetime.now(timezone.utc) - timedelta(hours=1)
    check("window over -> auto accepted", await delivery.process_due_deliveries(db) == 1)
    check("auto run is idempotent", await delivery.process_due_deliveries(db) == 0)
    p2 = await db.projects.find_one({"_id": proj2["_id"]})
    check("auto acceptance recorded", p2["status"] == "completed" and p2["delivery"]["accepted_by"] == "auto")

    # ---- dispute freezes release, refund path ----
    sales3, dev3, proj3 = await funded_project()
    for u in (sales3, dev3): db.users.docs.append({"_id": u["_id"], "first_name": "A", "last_name": "B", "email": "e@x.com", "wallet_balance": 0.0, "pending_balance": 0.0, "total_earned": 0.0})
    pid3 = str(proj3["_id"])
    await projects.mark_delivered(pid3, current_user=dev3)
    token3 = (await db.projects.find_one({"_id": proj3["_id"]}))["invoice_token"]
    await invoices.report_invoice_problem(None, token3, ProblemReport(reason="The checkout page does not work at all"))
    check("invoice shows disputed", (await invoices.view_invoice(None, token3))["status"] == "disputed")
    await expect_http("second dispute -> 409", 409, projects.report_problem(pid3, ProblemReport(reason="Another problem report here"), current_user=sales3))
    await expect_http("stranger cannot dispute", 403, projects.report_problem(pid3, ProblemReport(reason="Not my project at all"), current_user={"_id": ObjectId()}))
    await expect_http("cannot accept during dispute", 400, invoices.accept_invoice_delivery(None, token3))
    [x for x in db.projects.docs if x["_id"] == proj3["_id"]][0]["delivery"]["review_deadline"] = datetime.now(timezone.utc) - timedelta(days=3)
    check("expired window does NOT auto release during dispute", await delivery.process_due_deliveries(db) == 0)
    tx3 = await db.transactions.find_one({"project_id": proj3["_id"], "status": "success"})
    await expect_http("manual release blocked during dispute", 400, payments.release_escrow(tx3["transaction_id"], current_user=sales3))
    check("developer was told about the dispute", any(n["type"] == "dispute_opened" and n["user_id"] == dev3["_id"] for n in db.notifications.docs))

    res = await delivery.resolve_dispute(db, proj3["_id"], "refund", None, "Never worked")
    tx3 = await db.transactions.find_one({"project_id": proj3["_id"], "status": "success"})
    p3 = await db.projects.find_one({"_id": proj3["_id"]})
    check("refund recorded, project cancelled, nothing paid out", tx3["escrow_status"] == "refunded" and tx3["refunded_amount"] == 80000.0 and p3["status"] == "cancelled" and p3["dispute"]["status"] == "resolved")
    check("developer wallet untouched by refund", (await user(dev3))["pending_balance"] == 0 and (await user(dev3))["wallet_balance"] == 0)
    check("invoice shows refunded", (await invoices.view_invoice(None, token3))["status"] == "refunded")
    try: await delivery.resolve_dispute(db, proj3["_id"], "refund"); check("resolving twice fails", False)
    except ValueError: check("resolving twice fails", True)

    # ---- split ----
    sales4, dev4, proj4 = await funded_project()
    for u in (sales4, dev4): db.users.docs.append({"_id": u["_id"], "first_name": "A", "last_name": "B", "email": "e@x.com", "wallet_balance": 0.0, "pending_balance": 0.0, "total_earned": 0.0})
    await projects.report_problem(str(proj4["_id"]), ProblemReport(reason="Half of the pages are missing"), current_user=sales4)
    try: await delivery.resolve_dispute(db, proj4["_id"], "split", 0); check("split needs an amount", False)
    except ValueError: check("split needs an amount", True)
    try: await delivery.resolve_dispute(db, proj4["_id"], "split", 80000.0); check("split cannot equal the total", False)
    except ValueError: check("split cannot equal the total", True)
    await delivery.resolve_dispute(db, proj4["_id"], "split", 20000.0, "Partial")
    d4, s4 = await user(dev4), await user(sales4)
    check("split pays commission on the remaining 60,000", round(d4["pending_balance"], 2) == 27000.0 and round(s4["pending_balance"], 2) == 21000.0)
    check("split project completed", (await db.projects.find_one({"_id": proj4["_id"]}))["status"] == "completed")

    # ---- dispute on release outcome ----
    sales5, dev5, proj5 = await funded_project()
    for u in (sales5, dev5): db.users.docs.append({"_id": u["_id"], "first_name": "A", "last_name": "B", "email": "e@x.com", "wallet_balance": 0.0, "pending_balance": 0.0, "total_earned": 0.0})
    await projects.report_problem(str(proj5["_id"]), ProblemReport(reason="Client says it is not good enough"), current_user=dev5)
    await delivery.resolve_dispute(db, proj5["_id"], "release")
    check("release outcome pays in full", round((await user(dev5))["pending_balance"], 2) == 36000.0)

    # ---- unpaid project ----
    sales6, dev6, proj6 = await make_project(50000.0)
    await expect_http("cannot deliver unpaid", 400, projects.mark_delivered(str(proj6["_id"]), current_user=dev6))
    await expect_http("cannot dispute unpaid", 400, projects.report_problem(str(proj6["_id"]), ProblemReport(reason="Nothing paid yet here"), current_user=sales6))
    await payments.create_or_get_payment_link(db, await db.projects.find_one({"_id": proj6["_id"]}))
    await projects.update_project(str(proj6["_id"]), projects.ProjectUpdate(status="cancelled"), current_user=sales6)
    check("cancelling unpaid project cancels its pending links", not [t for t in db.transactions.docs if t["project_id"] == proj6["_id"] and t["status"] == "pending"])


    # ---- atomicity ----
    sales7, dev7, proj7 = await funded_project()
    for u in (sales7, dev7): db.users.docs.append({"_id": u["_id"], "first_name": "A", "last_name": "B", "email": "e@x.com", "wallet_balance": 0.0, "pending_balance": 0.0, "total_earned": 0.0})
    await projects.mark_delivered(str(proj7["_id"]), current_user=dev7)
    p7 = await db.projects.find_one({"_id": proj7["_id"]})
    tx7 = await db.transactions.find_one({"project_id": proj7["_id"], "status": "success"})
    res = await asyncio.gather(*[delivery.settle_escrow(db, tx7) for _ in range(5)])
    check("5 concurrent settles pay out once", sum(1 for r in res if r) == 1 and round((await user(dev7))["pending_balance"], 2) == 36000.0)
    # late webhook retry after release must not put the money back to held
    ref = tx7["paystack_reference"]
    await webhook("charge.success", {"reference": ref})
    tx7b = await db.transactions.find_one({"_id": tx7["_id"]})
    check("late webhook does not reset released escrow", tx7b["escrow_status"] == "released")
    check("verify twice is harmless", (await payments.verify_payment(None, payments.PaymentVerify(reference=ref)))["status"] == "success")

    # webhook and verify racing on a pending payment fund it once
    sales8, dev8, proj8 = await make_project(60000.0)
    await payments.create_or_get_payment_link(db, await db.projects.find_one({"_id": proj8["_id"]}))
    tx8 = await db.transactions.find_one({"project_id": proj8["_id"], "status": "pending"})
    tx8["developer_id"] = dev8["_id"]
    oks = await asyncio.gather(payments._mark_transaction_successful(db, tx8), payments._mark_transaction_successful(db, tx8), payments._mark_transaction_successful(db, tx8))
    check("three racing confirmations: exactly one wins", sorted(oks) == [False, False, True])

    # unique-index collision (second paid link for the same project) is flagged, not counted
    sales9, dev9, proj9 = await funded_project()
    other = {"_id": ObjectId(), "transaction_id": "TXN_DUP", "project_id": proj9["_id"], "status": "pending", "total_amount": 80000.0, "paystack_reference": "dup", "salesperson_id": sales9["_id"]}
    db.transactions.docs.append(other)
    orig = db.transactions.find_one_and_update
    async def boom(q, u):
        if u.get("$set", {}).get("status") == "success": raise DuplicateKeyError()
        return await orig(q, u)
    db.transactions.find_one_and_update = boom
    ok = await payments._mark_transaction_successful(db, other)
    db.transactions.find_one_and_update = orig
    other = await db.transactions.find_one({"_id": other["_id"]})
    check("duplicate payment flagged for refund", ok is False and other["needs_refund"] and other["status"] == "cancelled")
    await payments._flag_for_refund(db, other, None, True)
    check("refund notification sent only once", len([n for n in db.notifications.docs if n["type"] == "payment_needs_refund" and n["project_id"] == proj9["_id"]]) == 1)

    # ---- status endpoint ----
    st = await payments.get_project_payment_status(pid, current_user=sales)
    check("status endpoint shows delivery", st["delivery"]["status"] == "accepted" and st["escrow_status"] == "released")

    print(f"\n{sum(results)}/{len(results)} passed")
    sys.exit(0 if all(results) else 1)

asyncio.run(main())
