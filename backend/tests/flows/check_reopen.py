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
    async def find_one(self, q, sort=None):
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
        af = af or []
        # MongoDB evaluates array filters against the document as it was before the update
        # started, so work out which elements match before changing anything.
        _hits = {}
        for _k in list(u.get("$set", {})) + list(u.get("$unset", {})):
            if ".$[" in _k and "].$" not in _k:
                _arr, _rest = _k.split(".$[", 1); _ident = _rest.split("].", 1)[0]
                if (_arr, _ident) not in _hits:
                    _filt = {kk: vv for f in af for kk, vv in f.items() if kk.startswith(_ident + ".")}
                    _hits[(_arr, _ident)] = [i for i, el in enumerate(d[_arr]) if all(cond(vals(el, kk.split(".")[1:]), vv) for kk, vv in _filt.items())]
        for k, v in u.get("$set", {}).items():
            if ".$[" in k and "].$" not in k and ".$[" in k:   # array_filters update on every matching element
                arr, rest = k.split(".$[", 1)
                ident, field = rest.split("].", 1)
                for i in _hits[(arr, ident)]: d[arr][i][field] = v
            elif ".$." in k:           # positional: the element matched by the query
                arr, field = k.split(".$.")
                want = next(vv for kk, vv in q.items() if kk.startswith(arr + "."))
                for el in d[arr]:
                    if el.get(next(kk for kk in q if kk.startswith(arr + ".")).split(".")[1]) == want: el[field] = v
            else: setp(d, k, v)
        for k, v in u.get("$inc", {}).items(): setp(d, k, (getp(d, k) or 0) + v)
        for k in u.get("$unset", {}):
            if ".$[" in k:
                arr, rest = k.split(".$[", 1); ident, field = rest.split("].", 1)
                for i in _hits[(arr, ident)]: d[arr][i].pop(field, None)
            else:
                parts = k.split("."); t = d
                for p_ in parts[:-1]: t = t.get(p_, {})
                if isinstance(t, dict): t.pop(parts[-1], None)
        for k, v in u.get("$push", {}).items(): d.setdefault(k, []).append(v)
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
mod("app.dependencies", get_current_user=lambda: None, require_role=lambda *r: (lambda: None), require_verified_role=lambda *r: (lambda: None), require_verified_user=lambda: None)
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
load("app.lookups", "app/lookups.py"); load("app.mailer", "app/mailer.py"); load("app.schemas", "app/schemas.py"); load("app.pricing", "app/pricing.py"); load("app.wallet", "app/wallet.py")
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

async def user(u): return await db.users.find_one({"_id": u["_id"]})
def raw(pid): return [x for x in db.projects.docs if x["_id"] == pid][0]

async def fund(proj, dev):
    await payments.create_or_get_payment_link(db, raw(proj["_id"]))
    tx = [t for t in db.transactions.docs if t["project_id"] == proj["_id"] and t["status"] == "pending"][0]
    tx["developer_id"] = dev["_id"]
    await payments._mark_transaction_successful(db, tx)
    return tx

async def main():
    # ---- a project with several applicants, paid, disputed and refunded ----
    sales = {"_id": ObjectId(), "role": "salesperson", "first_name": "S", "last_name": "P", "email": "s@x.com"}
    dev1, dev2, dev3 = ({"_id": ObjectId(), "role": "developer", "first_name": n, "last_name": "D", "email": f"{n}@x.com"} for n in "ABC")
    for u in (sales, dev1, dev2, dev3): db.users.docs.append({**u, "wallet_balance": 0.0, "pending_balance": 0.0, "total_earned": 0.0})
    a1, a2, a3 = ObjectId(), ObjectId(), ObjectId()
    proj = {"_id": ObjectId(), "title": "Build a shop", "salesperson_id": sales["_id"], "status": "open", "assigned_to": None,
            "budget": 90000.0, "client_email": "c@x.com", "client_name": "Client",
            "applications": [
                {"application_id": a1, "developer_id": dev1["_id"], "proposed_budget": 80000.0, "status": "pending"},
                {"application_id": a2, "developer_id": dev2["_id"], "proposed_budget": 70000.0, "status": "pending"},
                {"application_id": a3, "developer_id": dev3["_id"], "proposed_budget": 60000.0, "status": "pending"}]}
    db.projects.docs.append(proj); pid = str(proj["_id"])
    await projects.accept_application(pid, str(a1), current_user=sales)
    # dev3 was turned away by hand before the project was assigned
    for a in raw(proj["_id"])["applications"]:
        if a["developer_id"] == dev3["_id"]: a["auto_rejected"] = False
    raw(proj["_id"])["applications"][2]["status"] = "rejected"
    apps = {str(a["developer_id"]): a for a in raw(proj["_id"])["applications"]}
    check("others auto-rejected are flagged", apps[str(dev2["_id"])]["status"] == "rejected" and apps[str(dev2["_id"])].get("auto_rejected") is True)

    await expect_http("cannot reopen a project that is not cancelled", 400, projects.reopen_cancelled_project(pid, current_user=sales))
    tx1 = await fund(proj, dev1)
    token = None
    await projects.mark_delivered(pid, current_user=dev1)
    token = raw(proj["_id"])["invoice_token"]
    await projects.report_problem(pid, ProblemReport(reason="The client says it is not what was agreed"), current_user=sales)
    await delivery.resolve_dispute(db, proj["_id"], "refund", None, "refunded in paystack")

    # ---- after the refund ----
    t1 = [t for t in db.transactions.docs if t["_id"] == tx1["_id"]][0]
    check("a full refund stops counting as paid", t1["status"] == "refunded" and t1["escrow_status"] == "refunded")
    st = await payments.get_project_payment_status(pid, current_user=sales)
    check("cancelled project still shows the refund", st["is_funded"] is False and st["escrow_status"] == "refunded" and st["refunded_amount"] == 80000.0)
    check("invoice says refunded while cancelled", (await invoices.view_invoice(None, token))["status"] == "refunded")
    await expect_http("a refunded payment cannot be verified again", 400, payments.verify_payment(None, payments.PaymentVerify(reference=t1["paystack_reference"])))
    await webhook("charge.success", {"reference": t1["paystack_reference"]})
    check("late webhook cannot revive a refunded payment", [t for t in db.transactions.docs if t["_id"] == tx1["_id"]][0]["status"] == "refunded")
    await expect_http("cannot reopen through the edit form", 400, projects.update_project(pid, projects.ProjectUpdate(status="open"), current_user=sales))
    await expect_http("only the owner can reopen", 403, projects.reopen_cancelled_project(pid, current_user={"_id": ObjectId()}))

    # ---- reopen ----
    await projects.reopen_cancelled_project(pid, current_user=sales)
    p = raw(proj["_id"])
    check("project is open with a clean slate", p["status"] == "open" and p.get("assigned_to") is None and "agreed_amount" not in p and "delivery" not in p and "dispute" not in p and "price_proposal" not in p)
    check("the finished engagement is kept", len(p["previous_engagements"]) == 1 and p["previous_engagements"][0]["developer_id"] == dev1["_id"] and p["previous_engagements"][0]["dispute"]["resolution"] == "refund")
    apps = {a["developer_id"]: a for a in p["applications"]}
    check("previous developer stays rejected", apps[dev1["_id"]]["status"] == "rejected" and "auto_rejected" not in apps[dev1["_id"]])
    check("auto-rejected applicant is back to pending", apps[dev2["_id"]]["status"] == "pending" and "auto_rejected" not in apps[dev2["_id"]])
    check("hand-rejected applicant stays rejected", apps[dev3["_id"]]["status"] == "rejected")
    check("refund no longer shown on the open project", (await payments.get_project_payment_status(pid, current_user=sales))["escrow_status"] is None)
    await expect_http("cannot reopen twice", 400, projects.reopen_cancelled_project(pid, current_user=sales))

    # ---- second engagement works end to end, on the same invoice link ----
    await projects.accept_application(pid, str(a2), current_user=sales)
    p = raw(proj["_id"])
    check("new developer assigned at their own price", p["assigned_to"] == dev2["_id"] and p["agreed_amount"] == 70000.0 and p["status"] == "in_progress")
    view = await invoices.view_invoice(None, token)
    check("same invoice link is payable again at the new price", view["status"] == "payable" and view["amount"] == 70000.0)
    out = await invoices.pay_invoice(None, token)
    check("a fresh checkout is created", out["authorization_url"].startswith("https://pay/"))
    tx2 = [t for t in db.transactions.docs if t["project_id"] == proj["_id"] and t["status"] == "pending"][0]
    tx2["developer_id"] = dev2["_id"]
    check("old refunded payment does not block the new one", await payments._mark_transaction_successful(db, tx2) is True)
    check("only the new payment counts as paid", len([t for t in db.transactions.docs if t["project_id"] == proj["_id"] and t["status"] == "success"]) == 1)
    await projects.mark_delivered(pid, current_user=dev2)
    await invoices.accept_invoice_delivery(None, token)
    p = raw(proj["_id"])
    d2 = await user(dev2); d1 = await user(dev1)
    check("second engagement completes and pays only the new developer", p["status"] == "completed" and round(d2["pending_balance"], 2) == 31500.0 and d1["pending_balance"] == 0)
    check("history still has exactly one earlier engagement", len(p["previous_engagements"]) == 1)

    # ---- other cases ----
    # cancelled before anyone paid: reopen works and the old unpaid link dies
    sales2 = sales
    p2 = {"_id": ObjectId(), "title": "Unpaid", "salesperson_id": sales["_id"], "status": "open", "assigned_to": None, "budget": 50000.0, "client_email": "c@x.com",
          "applications": [{"application_id": (b1 := ObjectId()), "developer_id": dev1["_id"], "proposed_budget": 50000.0, "status": "pending"}]}
    db.projects.docs.append(p2)
    await projects.accept_application(str(p2["_id"]), str(b1), current_user=sales)
    await payments.create_or_get_payment_link(db, raw(p2["_id"]))
    await projects.update_project(str(p2["_id"]), projects.ProjectUpdate(status="cancelled"), current_user=sales)
    await projects.reopen_cancelled_project(str(p2["_id"]), current_user=sales)
    check("unpaid cancelled project reopens", raw(p2["_id"])["status"] == "open" and raw(p2["_id"]).get("assigned_to") is None)
    check("its old unpaid link is dead", not [t for t in db.transactions.docs if t["project_id"] == p2["_id"] and t["status"] == "pending"])

    # an older refund still recorded as success (before this change) is healed on reopen
    p3 = {"_id": ObjectId(), "title": "Legacy", "salesperson_id": sales["_id"], "status": "cancelled", "assigned_to": dev1["_id"], "budget": 50000.0, "client_email": "c@x.com", "applications": []}
    db.projects.docs.append(p3)
    db.transactions.docs.append({"_id": ObjectId(), "transaction_id": "TXN_LEGACY", "project_id": p3["_id"], "status": "success", "escrow_status": "refunded"})
    await projects.reopen_cancelled_project(str(p3["_id"]), current_user=sales)
    check("legacy refunded payment is healed and the project reopens", raw(p3["_id"])["status"] == "open" and [t for t in db.transactions.docs if t["transaction_id"] == "TXN_LEGACY"][0]["status"] == "refunded")

    # cancelled but money still held (should be impossible) is refused
    p4 = {"_id": ObjectId(), "title": "Held", "salesperson_id": sales["_id"], "status": "cancelled", "assigned_to": dev1["_id"], "budget": 50000.0, "client_email": "c@x.com", "applications": []}
    db.projects.docs.append(p4)
    db.transactions.docs.append({"_id": ObjectId(), "transaction_id": "TXN_HELD", "project_id": p4["_id"], "status": "success", "escrow_status": "held"})
    await expect_http("never reopen while a payment is held", 400, projects.reopen_cancelled_project(str(p4["_id"]), current_user=sales))
    check("and the project is left alone", raw(p4["_id"])["status"] == "cancelled")

    print(f"\n{sum(results)}/{len(results)} passed"); sys.exit(0 if all(results) else 1)
asyncio.run(main())
