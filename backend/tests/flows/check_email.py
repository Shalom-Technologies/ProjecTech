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
mod("app.security", hash_password=lambda p: "H:" + p, verify_password=lambda p, h: h == "H:" + p, create_access_token=lambda d: "t", generate_reset_token=lambda: "tok123", hash_reset_token=None)
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



import hashlib
from datetime import timedelta
S = sys.modules['app.security']
S.hash_reset_token = lambda t: hashlib.sha256(t.encode()).hexdigest()
_n = itertools.count(1)
S.generate_reset_token = lambda: f"verifytoken{next(_n):04d}"

# ---- a controllable fake mail provider ----
mail = {"fail": False, "sent": []}
async def send_password_reset_email(to, link, name):
    if mail["fail"]: raise RuntimeError("provider rejected the key")
    mail["sent"].append(("reset", to, link))
async def send_verification_email(to, link, name, is_welcome=True):
    if mail["fail"]: raise RuntimeError("provider rejected the key")
    mail["sent"].append(("verify", to, link, is_welcome))
async def send_review_started_email(**kw):
    if mail["fail"]: raise RuntimeError("provider rejected the key")
    mail["sent"].append(("review", kw["to_email"], kw["invoice_url"]))
mod("app.email_client", send_password_reset_email=send_password_reset_email,
    send_verification_email=send_verification_email, send_review_started_email=send_review_started_email)
verification = load("app.verification", "app/verification.py")
auth = load("app.routes.auth", "app/routes/auth.py")
delivery = load("app.delivery", "app/delivery.py")

# real dependency guards, with the web-framework pieces stubbed
fastapi.status = types.SimpleNamespace(HTTP_201_CREATED=201, HTTP_204_NO_CONTENT=204, HTTP_403_FORBIDDEN=403)
fsec = types.ModuleType("fastapi.security")
fsec.HTTPBearer = lambda *a, **k: None; fsec.HTTPAuthorizationCredentials = object
sys.modules["fastapi.security"] = fsec
jwtm = types.ModuleType("jwt")
class _E(Exception): pass
jwtm.ExpiredSignatureError = jwtm.InvalidTokenError = jwtm.PyJWTError = _E
sys.modules["jwt"] = jwtm
mod("app.security", **{**S.__dict__, "decode_access_token": lambda t: {}})
deps = load("app.dependencies_real", "app/dependencies.py")
from app.schemas import UserRegister, ForgotPasswordRequest, VerifyEmailRequest

async def main():
    # ---- registration sends a welcome + confirmation email ----
    r = await auth.register(None, UserRegister(email="new@x.com", password="Passw0rd!!", first_name="Wanjiru", last_name="K", role="salesperson", company_name="Co"))
    user = db.users.docs[0]
    check("new account starts unverified", user["email_verified"] is False and r.user.email_verified is False)
    check("welcome email sent with a confirm link", len(mail["sent"]) == 1 and mail["sent"][0][0] == "verify" and mail["sent"][0][3] is True and "/verify-email?token=verifytoken0001" in mail["sent"][0][2])
    rec = db.email_verifications.docs[0]
    check("confirmation token stored hashed", "token" not in rec and rec["token_hash"] == hashlib.sha256(b"verifytoken0001").hexdigest())

    # ---- gating ----
    await expect_http("unverified user blocked from money actions", 403, deps.require_verified_user(current_user=user))
    await expect_http("unverified salesperson blocked", 403, deps.require_verified_role("salesperson")(current_user=user))

    # ---- confirming ----
    await expect_http("bad token rejected", 400, auth.verify_email(None, VerifyEmailRequest(token="nonsense-token-123")))
    await auth.verify_email(None, VerifyEmailRequest(token="verifytoken0001"))
    check("email now verified", db.users.docs[0]["email_verified"] is True)
    check("verified user passes the guard", (await deps.require_verified_user(current_user=db.users.docs[0])) is not None)
    await expect_http("link cannot be reused", 400, auth.verify_email(None, VerifyEmailRequest(token="verifytoken0001")))
    await expect_http("resend refused when already verified", 400, auth.resend_verification(None, current_user=db.users.docs[0]))

    # ---- resend, cooldown, expiry ----
    db.users.docs[0]["email_verified"] = False
    await auth.resend_verification(None, current_user=db.users.docs[0])
    check("resend emails a new link", mail["sent"][-1][0] == "verify" and mail["sent"][-1][3] is False)
    await expect_http("second resend inside 60 seconds -> 429", 429, auth.resend_verification(None, current_user=db.users.docs[0]))
    db.email_verifications.docs[-1]["expires_at"] = datetime.now(timezone.utc) - timedelta(minutes=1)
    tok = f"verifytoken{next(_n) - 1:04d}"
    await expect_http("expired link rejected", 400, auth.verify_email(None, VerifyEmailRequest(token=tok)))
    check("expired link did not verify", db.users.docs[0]["email_verified"] is False)

    # ---- failures are no longer silent ----
    mail["fail"] = True
    before = len(db.email_failures.docs)
    resp = await auth.forgot_password(None, ForgotPasswordRequest(email="new@x.com"))
    check("reset still answers generically when the email fails", "reset link has been sent" in resp["message"])
    check("reset email failure is recorded", len(db.email_failures.docs) == before + 1 and db.email_failures.docs[-1]["kind"] == "password_reset" and "rejected" in db.email_failures.docs[-1]["error"])
    for d in db.email_verifications.docs: d["created_at"] = datetime.now(timezone.utc) - timedelta(minutes=5)
    await expect_http("resend reports a failed send -> 502", 502, auth.resend_verification(None, current_user=db.users.docs[0]))
    check("verification failure recorded too", db.email_failures.docs[-1]["kind"] == "verification")
    r = await auth.register(None, UserRegister(email="b@x.com", password="Passw0rd!!", first_name="B", last_name="K", role="developer", skills=["py"]))
    check("registration still succeeds when the welcome email fails", r.user.email == "b@x.com" and db.email_failures.docs[-1]["to_email"] == "b@x.com")
    mail["fail"] = False

    # ---- review email failure is visible and can be resent ----
    sales, dev, proj = await make_project(80000.0)
    link = await payments.create_or_get_payment_link(db, await db.projects.find_one({"_id": proj["_id"]})) if False else None
    p = [x for x in db.projects.docs if x["_id"] == proj["_id"]][0]
    p.update({"client_email": "client@x.com", "delivery": {"status": "delivered", "review_deadline": datetime.now(timezone.utc) + timedelta(days=7)}, "salesperson_id": sales["_id"]})
    mail["fail"] = True
    sent = await delivery.send_review_email(db, p, p["delivery"]["review_deadline"])
    await db.projects.update_one({"_id": p["_id"]}, {"$set": {"delivery.client_email_sent": sent, "delivery.client_email_last_attempt": datetime.now(timezone.utc) - timedelta(minutes=5)}})
    p = await db.projects.find_one({"_id": p["_id"]})
    check("failed review email is flagged on the project", delivery.serialize_delivery(p)["client_email_sent"] is False and db.email_failures.docs[-1]["kind"] == "review_started")
    mail["fail"] = False
    out = await delivery.resend_review_email(db, p)
    check("resend delivers it and returns the link", out["sent"] is True and "/pay/" in out["invoice_url"] and mail["sent"][-1][0] == "review")
    p = await db.projects.find_one({"_id": p["_id"]})
    check("flag cleared after a successful resend", delivery.serialize_delivery(p)["client_email_sent"] is True)
    await expect_http("resending again straight away -> 429", 429, delivery.resend_review_email(db, p))

    print(f"\n{sum(results)}/{len(results)} passed"); sys.exit(0 if all(results) else 1)
asyncio.run(main())
