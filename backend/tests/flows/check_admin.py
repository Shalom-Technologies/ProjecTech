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
        if "$exists" in v: ok &= (bool(actual_list) == v["$exists"])
        if "$nin" in v: ok &= not any(a in v["$nin"] for a in actual_list)
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
    def find(self, q=None, sort=None):
        docs = [d for d in self.docs if match(d, q or {})]
        class _C:
            async def to_list(self_, length=None): return docs[:length] if length else docs
        return _C()
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
            if match(d, q): self._apply(d, u, q, array_filters); return types.SimpleNamespace(modified_count=1, matched_count=1)
        return types.SimpleNamespace(modified_count=0, matched_count=0)
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
    def __getitem__(self, n): return self.c.setdefault(n, Coll())
db = DB()

# ---------- app package stubs + real modules ----------
def mod(name, **attrs):
    m = types.ModuleType(name); m.__dict__.update(attrs); sys.modules[name] = m; return m
app = mod("app"); app.__path__ = []
mod("app.routes").__path__ = []
mod("app.config", settings=types.SimpleNamespace(
    CURRENCY="KES", REVIEW_WINDOW_DAYS=7, PAYOUT_HOLD_DAYS=7, MIN_PAYMENT_AMOUNT=100.0, MAX_PAYMENT_AMOUNT=5_000_000.0, FRONTEND_URL="http://x", ADMIN_EMAIL="admin@x.com",
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
admin_mails = []; admin_mail_down = [False]
async def send_admin_alert_email(to, subject, lines):
    if admin_mail_down[0]: raise RuntimeError("provider down")
    admin_mails.append((to, subject, lines))
mod("app.email_client", send_review_started_email=send_review_started_email, send_admin_alert_email=send_admin_alert_email)
load("app.lookups", "app/lookups.py"); load("app.mailer", "app/mailer.py"); load("app.schemas", "app/schemas.py"); load("app.pricing", "app/pricing.py"); load("app.wallet", "app/wallet.py")
load("app.escrow", "app/escrow.py"); load("app.admin_alerts", "app/admin_alerts.py"); load("app.refunds", "app/refunds.py"); delivery = load("app.delivery", "app/delivery.py")
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

async def make_held(title="Build a shop"):
    sales = {"_id": ObjectId(), "role": "salesperson", "first_name": "S", "last_name": "P", "email": "s@x.com"}
    dev = {"_id": ObjectId(), "role": "developer", "first_name": "D", "last_name": "D", "email": "d@x.com"}
    for u in (sales, dev): db.users.docs.append({**u, "wallet_balance": 0.0, "pending_balance": 0.0, "total_earned": 0.0})
    a = ObjectId()
    proj = {"_id": ObjectId(), "title": title, "salesperson_id": sales["_id"], "status": "open", "assigned_to": None,
            "budget": 90000.0, "client_email": "c@x.com", "client_name": "Client",
            "applications": [{"application_id": a, "developer_id": dev["_id"], "proposed_budget": 80000.0, "status": "pending"}]}
    db.projects.docs.append(proj)
    await projects.accept_application(str(proj["_id"]), str(a), current_user=sales)
    tx = await fund(proj, dev)
    return sales, dev, proj, tx

def tx_of(tx): return [t for t in db.transactions.docs if t["_id"] == tx["_id"]][0]

async def main():
    # ---- refund messages from Paystack ----
    sales, dev, proj, tx = await make_held()
    ref = tx["paystack_reference"]
    check("an unrelated refund event is ignored", await webhook("refund.processed", {"transaction_reference": "nope"}) == {"status": "received"})
    t = tx_of(tx); t["needs_refund"] = True; t["admin_alerted_at"] = datetime.now(timezone.utc)
    await webhook("refund.pending", {"transaction_reference": ref, "refund_reference": "r1"})
    check("pending recorded", tx_of(tx)["refund_status"] == "pending" and tx_of(tx)["needs_refund"] is True)
    await webhook("refund.processed", {"transaction_reference": ref, "refund_reference": "r1"})
    check("processed recorded and no longer waiting", tx_of(tx)["refund_status"] == "processed" and tx_of(tx)["needs_refund"] is False)
    await webhook("refund.processing", {"transaction_reference": ref})
    check("a late 'processing' does not undo a finished refund", tx_of(tx)["refund_status"] == "processed")
    await webhook("refund.failed", {"transaction_reference": ref})
    check("failed recorded", tx_of(tx)["refund_status"] == "failed")
    check("failure re-arms the admin alert", "admin_alerted_at" not in tx_of(tx))
    await webhook("refund.processed", {"transaction": {"reference": ref}})
    check("reference can come nested", tx_of(tx)["refund_status"] == "processed")

    # ---- refund without a problem report ----
    sales, dev, proj, tx = await make_held("Second")
    await delivery.refund_project(db, proj["_id"], "client emailed us")
    t = tx_of(tx)
    check("payment recorded as refunded", t["status"] == "refunded" and t["escrow_status"] == "refunded" and t["refunded_amount"] == t["total_amount"])
    p = raw(proj["_id"])
    check("project cancelled with a note", p["status"] == "cancelled" and p["admin_refund"]["note"] == "client emailed us")
    check("nobody is paid out", (await user(dev))["wallet_balance"] == 0 and (await user(dev))["pending_balance"] == 0)
    kinds = [n["type"] for n in db.notifications.docs if n["project_id"] == proj["_id"]]
    check("salesperson and developer told", kinds.count("project_refunded") == 2)
    try: await delivery.refund_project(db, proj["_id"]); check("second refund refused", False)
    except ValueError: check("second refund refused", True)

    sales, dev, proj, tx = await make_held("Disputed")
    await projects.mark_delivered(str(proj["_id"]), current_user=dev)
    from app.schemas import ProblemReport
    await projects.report_problem(str(proj["_id"]), ProblemReport(reason="not what we agreed on at all"), current_user=sales)
    try: await delivery.refund_project(db, proj["_id"]); check("open problem report must go through resolve", False)
    except ValueError as e: check("open problem report must go through resolve", "open problem report" in str(e))
    check("and the payment is still held", tx_of(tx)["escrow_status"] == "held")

    # ---- admin email digest ----
    db.email_failures.docs.append({"_id": ObjectId(), "kind": "verification", "to_email": "x@y.com", "error": "bad key"})
    tx_due = {"_id": ObjectId(), "project_id": ObjectId(), "paystack_reference": "late1", "total_amount": 5000.0, "needs_refund": True, "status": "cancelled"}
    db.transactions.docs.append(tx_due)
    n = await delivery.send_admin_digest(db)
    check("one email with every item", len(admin_mails) == 1 and n == len(admin_mails[0][2]) and n >= 3)
    text = "\n".join(admin_mails[0][2])
    check("mentions the problem report, the refund due and the failed email",
          "Disputed" in text and "late1" in text and "verification" in text)
    check("sent to the admin", admin_mails[0][0] == "admin@x.com")
    check("nothing new -> no second email", await delivery.send_admin_digest(db) == 0 and len(admin_mails) == 1)

    # a refund that fails is announced even though the payment was alerted before
    await webhook("refund.failed", {"transaction_reference": "late1"})
    await delivery.send_admin_digest(db)
    check("failed refund announced again", len(admin_mails) == 2 and "FAILED" in "\n".join(admin_mails[1][2]))

    # provider down: items kept for the next cycle, no endless loop of failure records
    failures_before = len(db.email_failures.docs)
    db.email_failures.docs.append({"_id": ObjectId(), "kind": "reset", "to_email": "z@y.com", "error": "x"})
    admin_mail_down[0] = True
    check("alert failure does not raise", await delivery.send_admin_digest(db) == 0)
    check("alert failure is not recorded as an email failure", len(db.email_failures.docs) == failures_before + 1)
    admin_mail_down[0] = False
    check("retried next cycle", await delivery.send_admin_digest(db) == 1 and "reset" in "\n".join(admin_mails[-1][2]))

    # not configured: nothing is sent and nothing is marked
    from app.config import settings
    settings.ADMIN_EMAIL = ""
    db.email_failures.docs.append({"_id": ObjectId(), "kind": "welcome", "to_email": "q@y.com", "error": "x"})
    sent_before = len(admin_mails)
    check("no admin address -> nothing sent", await delivery.send_admin_digest(db) == 0 and len(admin_mails) == sent_before)
    check("and the item stays unannounced", "admin_alerted_at" not in db.email_failures.docs[-1])
    settings.ADMIN_EMAIL = "admin@x.com"
    check("sent once an address is set", await delivery.send_admin_digest(db) == 1)

    # ---- the client's contact details are not shown to other users ----
    sales, dev, proj, tx = await make_held("Privacy")
    stranger = {"_id": ObjectId(), "role": "developer"}
    pid = str(proj["_id"])
    raw(proj["_id"]).update(description="d", category="web", deadline=None, created_at=datetime.now(timezone.utc))
    view = await projects.get_project(pid, current_user=sales)
    check("the salesperson sees the client's name and email", view["client_name"] == "Client" and view["client_email"] == "c@x.com")
    view = await projects.get_project(pid, current_user=dev)
    check("the assigned developer sees the name only", view["client_name"] == "Client" and view["client_email"] is None)
    view = await projects.get_project(pid, current_user=stranger)
    check("another developer sees neither", view["client_name"] is None and view["client_email"] is None)

    print(f"\n{sum(results)}/{len(results)} passed"); sys.exit(0 if all(results) else 1)
asyncio.run(main())
