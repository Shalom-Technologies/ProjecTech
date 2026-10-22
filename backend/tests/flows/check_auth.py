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
    async def delete_many(self, q):
        self.docs[:] = [d for d in self.docs if not match(d, q)]
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
    CURRENCY="KES", REVIEW_WINDOW_DAYS=7, PAYOUT_HOLD_DAYS=7, PASSWORD_RESET_TOKEN_EXPIRE_MINUTES=30, MIN_PAYMENT_AMOUNT=100.0, MAX_PAYMENT_AMOUNT=5_000_000.0, FRONTEND_URL="http://x",
    PAYSTACK_SECRET_KEY="sk_test", DEVELOPER_COMMISSION=0.45, SALESPERSON_COMMISSION=0.35))
mod("app.database", get_database=lambda: db)
mod("app.dependencies", get_current_user=lambda: None, require_role=lambda *r: (lambda: None), require_verified_role=lambda *r: (lambda: None), require_verified_user=lambda: None)
mod("app.rate_limit", limiter=types.SimpleNamespace(limit=lambda s: (lambda f: f)))
mod("app.dependencies", get_current_user=lambda: None, require_role=lambda *r: (lambda: None), require_verified_role=lambda *r: (lambda: None), require_verified_user=lambda: None)
sent = []
async def send_password_reset_email(email, link, name): sent.append(link)
mod("app.email_client", send_password_reset_email=send_password_reset_email, send_review_started_email=None)
mod("app.security", hash_password=lambda p: "H:" + p, verify_password=lambda p, h: h == "H:" + p, create_access_token=lambda d: "t", token_for_user=lambda u: "t:%s" % u.get("password_version", 0), token_matches_password_version=lambda p, u: p.get("pv", 0) == u.get("password_version", 0), generate_reset_token=lambda: "tok123", hash_reset_token=None)
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



import hashlib
sec = load("app.security_real_hash", "app/security.py") if False else None
import app.security as S
S = sys.modules['app.security']
S.hash_reset_token = lambda t: hashlib.sha256(t.encode()).hexdigest()
S.ResetDummy = None
sent = []
async def _spre(email, link, name): sent.append(link)
async def _sver(*a, **k): pass
mod("app.email_client", send_password_reset_email=_spre, send_verification_email=_sver)
load("app.verification", "app/verification.py")
auth = load("app.routes.auth", "app/routes/auth.py")
from app.schemas import ForgotPasswordRequest, ResetPasswordRequest, ChangePasswordRequest

async def main():
    from datetime import timedelta
    uid = ObjectId()
    db.users.docs.append({"_id": uid, "email": "a@b.com", "first_name": "A", "password_hash": "H:old"})
    await auth.forgot_password(None, ForgotPasswordRequest(email="a@b.com"))
    rec = db.password_resets.docs[0]
    check("token is not stored in plain text", "token" not in rec and "tok123" not in json.dumps(rec, default=str))
    check("hash is stored", rec["token_hash"] == hashlib.sha256(b"tok123").hexdigest())
    check("email link carries the real token", sent[0].endswith("token=tok123"))
    await expect_http("wrong token rejected", 400, auth.reset_password(None, ResetPasswordRequest(token="nope", new_password="NewPassw0rd!")))
    await auth.reset_password(None, ResetPasswordRequest(token="tok123", new_password="NewPassw0rd!"))
    check("password changed", db.users.docs[0]["password_hash"] == "H:NewPassw0rd!")
    check("reset raises the password version (signs out old devices)", db.users.docs[0].get("password_version") == 1)
    await expect_http("token cannot be reused", 400, auth.reset_password(None, ResetPasswordRequest(token="tok123", new_password="Another1Pass!")))
    db.users.docs[0]["password_hash"] = "H:keep"
    db.password_resets.docs.append({"_id": ObjectId(), "user_id": uid, "token_hash": hashlib.sha256(b"old").hexdigest(), "used": False, "expires_at": datetime.now(timezone.utc) - timedelta(minutes=1)})
    await expect_http("expired token rejected", 400, auth.reset_password(None, ResetPasswordRequest(token="old", new_password="Another1Pass!")))
    check("expired token did not change password", db.users.docs[0]["password_hash"] == "H:keep")
    # changing the password while logged in: other devices out, this one gets a fresh token
    db.users.docs[0]["password_hash"] = "H:cur"
    res = await auth.change_password(None, ChangePasswordRequest(current_password="cur", new_password="Brand9NewPass!"), current_user=db.users.docs[0])
    check("change raises the version again", db.users.docs[0].get("password_version") == 2)
    check("change returns a token for the new version", res["access_token"] == "t:2")
    print(f"\n{sum(results)}/{len(results)} passed"); sys.exit(0 if all(results) else 1)
asyncio.run(main())
