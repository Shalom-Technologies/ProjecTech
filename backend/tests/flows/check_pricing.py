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
async def send_review_started_email(**kw): pass
mod("app.email_client", send_review_started_email=send_review_started_email)
load("app.lookups", "app/lookups.py"); load("app.mailer", "app/mailer.py"); load("app.schemas", "app/schemas.py"); load("app.pricing", "app/pricing.py"); load("app.wallet", "app/wallet.py"); load("app.escrow", "app/escrow.py"); load("app.delivery", "app/delivery.py")
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

async def main():
    # 1. agreed price fixed on accept; initialise uses it
    sales, dev, proj = await make_project()
    pid = str(proj["_id"])
    check("agreed_amount set from accepted proposal", proj["agreed_amount"] == 80000.0)
    await expect_http("client-sent wrong amount refused", 400,
        payments.initialize_payment(None, PaymentInitialize(project_id=pid, amount=50000), current_user=sales))
    r1 = await payments.initialize_payment(None, PaymentInitialize(project_id=pid), current_user=sales)
    check("invoice is for the agreed price", r1["amount"] == 80000.0 and paystack_calls[-1]["amount_kobo"] == 8000000)
    r1b = await payments.initialize_payment(None, PaymentInitialize(project_id=pid, amount=80000), current_user=sales)
    check("second request reuses the same unpaid link", r1b["authorization_url"] == r1["authorization_url"] and len(paystack_calls) == 1)

    # 2. proposal validation
    await expect_http("same as agreed refused", 400, projects.propose_price(pid, PriceProposalCreate(amount=80000, reason="no real change"), current_user=sales))
    await expect_http("below minimum refused", 400, projects.propose_price(pid, PriceProposalCreate(amount=50, reason="far too small"), current_user=sales))
    await expect_http("above maximum refused", 400, projects.propose_price(pid, PriceProposalCreate(amount=99_000_000, reason="far too large"), current_user=sales))
    other = {"_id": ObjectId(), "role": "salesperson"}
    await expect_http("another salesperson cannot propose", 403, projects.propose_price(pid, PriceProposalCreate(amount=90000, reason="not my project"), current_user=other))

    # 3. valid proposal blocks invoicing until the developer responds
    await projects.propose_price(pid, PriceProposalCreate(amount=100000, reason="Client added a payment feature"), current_user=sales)
    check("developer notified of the request", any(n["type"] == "price_change_requested" and n["user_id"] == dev["_id"] for n in db.notifications.docs))
    await expect_http("cannot invoice while approval pending", 400, payments.initialize_payment(None, PaymentInitialize(project_id=pid), current_user=sales))
    stranger = {"_id": ObjectId(), "role": "developer"}
    await expect_http("unassigned developer cannot respond", 403, projects.respond_to_price_proposal(pid, PriceProposalDecision(approve=True), current_user=stranger))
    price = await projects.get_price(pid, current_user=dev)
    check("developer can see the pending proposal", price["price_proposal"]["status"] == "pending" and price["agreed_amount"] == 80000.0)
    await expect_http("outsider cannot read the price", 403, projects.get_price(pid, current_user=stranger))

    # 4. approval changes the price, retires the old link, and cannot be applied twice
    await projects.respond_to_price_proposal(pid, PriceProposalDecision(approve=True, note="Fair"), current_user=dev)
    check("agreed price updated after approval", (await projects.get_price(pid, current_user=sales))["agreed_amount"] == 100000.0)
    old_tx = next(t for t in db.transactions.docs if t["paystack_reference"] == "ref1")
    check("old unpaid link cancelled", old_tx["status"] == "cancelled")
    await expect_http("approving twice refused", 400, projects.respond_to_price_proposal(pid, PriceProposalDecision(approve=True), current_user=dev))
    check("salesperson notified of approval", any(n["type"] == "price_change_approved" for n in db.notifications.docs))

    # 5. new invoice at new price; payment on the retired link is flagged, not credited
    r2 = await payments.initialize_payment(None, PaymentInitialize(project_id=pid), current_user=sales)
    check("new invoice uses new price", r2["amount"] == 100000.0 and paystack_calls[-1]["amount_kobo"] == 10000000)
    await webhook("charge.success", {"reference": "ref1"})
    check("payment on retired link flagged for refund", old_tx.get("paid_while_cancelled") is True and old_tx["status"] == "cancelled")
    check("project not marked funded by the retired link", not any(t["status"] == "success" for t in db.transactions.docs))
    await expect_http("verifying a retired link refused", 400, payments.verify_payment(None, types.SimpleNamespace(reference="ref1")))
    await webhook("charge.success", {"reference": "ref2"})
    new_tx = next(t for t in db.transactions.docs if t["paystack_reference"] == "ref2")
    check("payment on current link marks project funded", new_tx["status"] == "success")

    # 6. once funded, the price is locked
    await expect_http("cannot propose after funding", 400, projects.propose_price(pid, PriceProposalCreate(amount=120000, reason="too late to change"), current_user=sales))
    await expect_http("cannot pay twice", 400, payments.initialize_payment(None, PaymentInitialize(project_id=pid), current_user=sales))

    # 7. rejection keeps the price
    sales2, dev2, proj2 = await make_project(proposed=60000.0)
    pid2 = str(proj2["_id"])
    await projects.propose_price(pid2, PriceProposalCreate(amount=30000, reason="Scope reduced a lot"), current_user=sales2)
    await projects.respond_to_price_proposal(pid2, PriceProposalDecision(approve=False, note="Too low"), current_user=dev2)
    pr = await projects.get_price(pid2, current_user=sales2)
    check("rejection keeps agreed price and records note", pr["agreed_amount"] == 60000.0 and pr["price_proposal"]["status"] == "rejected" and pr["price_proposal"]["response_note"] == "Too low")
    r = await payments.initialize_payment(None, PaymentInitialize(project_id=pid2), current_user=sales2)
    check("invoicing opens again after a decline, at the old price", r["amount"] == 60000.0)

    # 8. withdraw
    sales3, dev3, proj3 = await make_project(proposed=70000.0); pid3 = str(proj3["_id"])
    await projects.propose_price(pid3, PriceProposalCreate(amount=75000, reason="Small extra scope"), current_user=sales3)
    await projects.withdraw_price_proposal(pid3, current_user=sales3)
    check("salesperson can withdraw a pending request", (await projects.get_price(pid3, current_user=sales3))["price_proposal"]["status"] == "withdrawn")
    await expect_http("developer cannot answer a withdrawn request", 400, projects.respond_to_price_proposal(pid3, PriceProposalDecision(approve=True), current_user=dev3))
    await expect_http("nothing left to withdraw", 400, projects.withdraw_price_proposal(pid3, current_user=sales3))

    # 9. race: salesperson replaces the proposal after the developer loaded it
    sales4, dev4, proj4 = await make_project(proposed=50000.0); pid4 = str(proj4["_id"])
    await projects.propose_price(pid4, PriceProposalCreate(amount=55000, reason="First figure we discussed"), current_user=sales4)
    db.projects.after_find = lambda d: d["price_proposal"].update(amount=99000)   # replaced mid-request
    await expect_http("stale approval of a replaced proposal refused", 409, projects.respond_to_price_proposal(pid4, PriceProposalDecision(approve=True), current_user=dev4))
    check("price unchanged after the stale approval", (await projects.get_price(pid4, current_user=sales4))["agreed_amount"] == 50000.0)

    # 10. legacy project (accepted before agreed_amount existed)
    legacy = {"_id": ObjectId(), "title": "Old", "salesperson_id": sales["_id"], "status": "in_progress", "assigned_to": dev["_id"], "budget": 40000.0,
              "applications": [{"application_id": ObjectId(), "developer_id": dev["_id"], "proposed_budget": 35000.0, "status": "accepted"}]}
    from app.pricing import get_agreed_amount
    check("legacy project falls back to the accepted proposal", get_agreed_amount(legacy) == 35000.0)


    # 11. notification + idempotency when an outdated link is paid (mismatching amount)
    flagged_notes = [n for n in db.notifications.docs if n["type"] == "payment_needs_refund" and n["user_id"] == sales["_id"]]
    check("salesperson told about the outdated payment", len(flagged_notes) >= 1 and "refunded" in flagged_notes[0]["description"])
    check("flagged payment marked needs_refund", old_tx.get("needs_refund") is True)
    before = len([n for n in db.notifications.docs if n["type"] == "payment_needs_refund"])
    await webhook("charge.success", {"reference": "ref1"})      # Paystack retries the webhook
    after = len([n for n in db.notifications.docs if n["type"] == "payment_needs_refund"])
    check("repeated webhook does not notify twice", before == after)

    # 12. outdated link whose amount equals the CURRENT agreed price is accepted
    s5, d5, p5 = await make_project(proposed=60000.0); pid5 = str(p5["_id"])
    await payments.initialize_payment(None, PaymentInitialize(project_id=pid5), current_user=s5)
    first_ref = paystack_calls and f"ref{len(paystack_calls)}"
    await projects.propose_price(pid5, PriceProposalCreate(amount=70000, reason="Extra pages were added"), current_user=s5)
    await projects.respond_to_price_proposal(pid5, PriceProposalDecision(approve=True), current_user=d5)
    await projects.propose_price(pid5, PriceProposalCreate(amount=60000, reason="Extra pages were dropped"), current_user=s5)
    await projects.respond_to_price_proposal(pid5, PriceProposalDecision(approve=True), current_user=d5)
    await payments.initialize_payment(None, PaymentInitialize(project_id=pid5), current_user=s5)   # a fresh 60k link
    old5 = next(t for t in db.transactions.docs if t["paystack_reference"] == first_ref)
    check("setup: first link retired, fresh link pending", old5["status"] == "cancelled" and
          sum(1 for t in db.transactions.docs if t["project_id"] == p5["_id"] and t["status"] == "pending") == 1)
    notes_before = len(db.notifications.docs)
    await webhook("charge.success", {"reference": first_ref})
    check("matching payment on retired link accepted as funding", old5["status"] == "success" and old5.get("accepted_after_cancel") is True)
    check("other unpaid link for that project retired", not any(t["project_id"] == p5["_id"] and t["status"] == "pending" for t in db.transactions.docs))
    check("no refund notification for an accepted payment", not any(n["type"] == "payment_needs_refund" and n["project_id"] == p5["_id"] for n in db.notifications.docs[notes_before:]))
    check("project now reports funded", (await projects.get_price(pid5, current_user=s5))["is_funded"] is True)

    # 13. same acceptance through the client's return page (verify)
    s6, d6, p6 = await make_project(proposed=45000.0); pid6 = str(p6["_id"])
    await payments.initialize_payment(None, PaymentInitialize(project_id=pid6), current_user=s6)
    ref6 = f"ref{len(paystack_calls)}"
    await projects.propose_price(pid6, PriceProposalCreate(amount=48000, reason="A small addition came up"), current_user=s6)
    await projects.respond_to_price_proposal(pid6, PriceProposalDecision(approve=True), current_user=d6)
    await projects.propose_price(pid6, PriceProposalCreate(amount=45000, reason="Addition was cancelled"), current_user=s6)
    await projects.respond_to_price_proposal(pid6, PriceProposalDecision(approve=True), current_user=d6)
    res = await payments.verify_payment(None, types.SimpleNamespace(reference=ref6))
    check("verify accepts a matching payment on a retired link", res["status"] == "success")
    await expect_http("verify refuses a mismatching payment on a retired link", 400,
                      payments.verify_payment(None, types.SimpleNamespace(reference="ref1")))

    # 14. matching amount but project already funded -> flagged, not double-counted
    s7, d7, p7 = await make_project(proposed=30000.0); pid7 = str(p7["_id"])
    r7 = await payments.initialize_payment(None, PaymentInitialize(project_id=pid7), current_user=s7)
    await webhook("charge.success", {"reference": f"ref{len(paystack_calls)}"})                     # funded properly
    stale = {"_id": ObjectId(), "transaction_id": "TXN_STALE", "project_id": p7["_id"], "status": "cancelled",
             "paystack_reference": "stale-ref", "total_amount": 30000.0}
    db.transactions.docs.append(stale)
    await webhook("charge.success", {"reference": "stale-ref"})
    check("second payment for an already funded project flagged, not counted",
          stale["status"] == "cancelled" and stale.get("needs_refund") is True and
          sum(1 for t in db.transactions.docs if t["project_id"] == p7["_id"] and t["status"] == "success") == 1)
    check("salesperson told the project was already funded", any(
          n["type"] == "payment_needs_refund" and n["project_id"] == p7["_id"] and "already funded" in n["description"] for n in db.notifications.docs))


    # 15. invoice page flow
    s8, d8, p8 = await make_project(proposed=90000.0); pid8 = str(p8["_id"])
    db.users.docs.append({"_id": s8["_id"], "first_name": "Wanjiru", "last_name": "K", "company_name": "Kuza Sales"})
    p8["client_name"] = "Acme Ltd"
    open_proj = {"_id": ObjectId(), "salesperson_id": s8["_id"], "status": "open", "assigned_to": None, "title": "Unassigned project", "budget": 1000.0}
    db.projects.docs.append(open_proj)
    await expect_http("invoice link needs an assigned developer", 400, invoices.get_invoice_link(str(open_proj["_id"]), current_user=s8))
    await expect_http("only the owner can create the invoice link", 403, invoices.get_invoice_link(pid8, current_user=other))
    link = await invoices.get_invoice_link(pid8, current_user=s8)
    link2 = await invoices.get_invoice_link(pid8, current_user=s8)
    token = link["invoice_token"]
    check("invoice link is stable across calls", link2["invoice_token"] == token and link["invoice_url"].endswith(f"/pay/{token}") and len(token) >= 30)

    view = await invoices.view_invoice(None, token)
    check("public view shows agreed price, sender and project", view["amount"] == 90000.0 and view["from_name"] == "Kuza Sales" and view["project_title"] == "Build a shop" and view["status"] == "payable")
    check("public view leaks no emails or ids", not any(k in view for k in ("client_email", "salesperson_id", "assigned_to", "_id", "id")) and "c@x.com" not in json.dumps(view))
    await expect_http("unknown invoice token -> 404", 404, invoices.view_invoice(None, "nope"))
    await expect_http("unknown invoice token cannot be paid -> 404", 404, invoices.pay_invoice(None, "nope"))

    calls_before = len(paystack_calls)
    pay1 = await invoices.pay_invoice(None, token)
    pay1b = await invoices.pay_invoice(None, token)
    check("pay creates a checkout for the agreed price", paystack_calls[-1]["amount_kobo"] == 9000000 and pay1["authorization_url"].startswith("https://pay/"))
    check("pressing pay twice reuses the same checkout", pay1b["authorization_url"] == pay1["authorization_url"] and len(paystack_calls) == calls_before + 1)

    await projects.propose_price(pid8, PriceProposalCreate(amount=95000, reason="Client asked for an extra page"), current_user=s8)
    check("invoice shows 'awaiting approval' during a price change", (await invoices.view_invoice(None, token))["status"] == "awaiting_price_approval")
    await expect_http("cannot pay while the price is awaiting approval", 409, invoices.pay_invoice(None, token))
    await projects.respond_to_price_proposal(pid8, PriceProposalDecision(approve=True), current_user=d8)
    view2 = await invoices.view_invoice(None, token)
    check("same invoice link now shows the new price", view2["amount"] == 95000.0 and view2["status"] == "payable")
    pay2 = await invoices.pay_invoice(None, token)
    check("the old checkout is retired and a new one is made at the new price",
          pay2["authorization_url"] != pay1["authorization_url"] and paystack_calls[-1]["amount_kobo"] == 9500000 and
          next(t for t in db.transactions.docs if t.get("paystack_authorization_url") == pay1["authorization_url"])["status"] == "cancelled")

    # a stray second unpaid checkout (e.g. a double click) is retired once the project is paid
    sibling = {"_id": ObjectId(), "transaction_id": "TXN_SIB", "project_id": p8["_id"], "status": "pending", "paystack_reference": "sib-ref", "total_amount": 95000.0}
    db.transactions.docs.append(sibling)
    cur_ref = next(t for t in db.transactions.docs if t.get("paystack_authorization_url") == pay2["authorization_url"])["paystack_reference"]
    await webhook("charge.success", {"reference": cur_ref})
    check("invoice shows paid", (await invoices.view_invoice(None, token))["status"] == "paid")
    await expect_http("a paid invoice cannot be paid again", 400, invoices.pay_invoice(None, token))
    check("sibling unpaid checkout retired when the project is paid", sibling["status"] == "cancelled")
    await webhook("charge.success", {"reference": "sib-ref"})
    check("payment on the retired sibling is flagged for refund, not double counted",
          sibling.get("needs_refund") is True and sum(1 for t in db.transactions.docs if t["project_id"] == p8["_id"] and t["status"] == "success") == 1)

    # unpaid project that was cancelled
    s9, d9, p9 = await make_project(proposed=20000.0)
    t9 = (await invoices.get_invoice_link(str(p9["_id"]), current_user=s9))["invoice_token"]
    p9["status"] = "cancelled"
    check("cancelled project's invoice is unavailable", (await invoices.view_invoice(None, t9))["status"] == "unavailable")
    await expect_http("cancelled project's invoice cannot be paid", 400, invoices.pay_invoice(None, t9))

    print("\nALL PASS" if all(results) else f"\n{results.count(False)} FAILED")
asyncio.run(main())
