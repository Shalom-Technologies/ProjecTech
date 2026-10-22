import os
BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
import asyncio, re, sys, types

# Stub app.config so wallet.py imports without pydantic_settings
cfg = types.ModuleType("app.config")
cfg.settings = types.SimpleNamespace(CURRENCY="KES")
app = types.ModuleType("app"); app.__path__ = []
sys.modules["app"] = app; sys.modules["app.config"] = cfg

class HTTPStatusError(Exception):
    def __init__(self, status): super().__init__(status); self.response = types.SimpleNamespace(status_code=status)
class RequestError(Exception): pass
httpx = types.ModuleType("httpx"); httpx.HTTPStatusError, httpx.RequestError = HTTPStatusError, RequestError
sys.modules["httpx"] = httpx

import importlib.util
spec = importlib.util.spec_from_file_location("app.wallet", os.path.join(BACKEND, "app", "wallet.py"))
wallet = importlib.util.module_from_spec(spec); sys.modules["app.wallet"] = wallet; spec.loader.exec_module(wallet)

async def _aw(x): return x

class Coll:
    def __init__(self): self.docs = []
    def _match(self, d, q):
        for k, v in q.items():
            if isinstance(v, dict) and "$in" in v:
                if d.get(k) not in v["$in"]: return False
            elif isinstance(v, dict) and "$lte" in v:
                if d.get(k) is None or d.get(k) > v["$lte"]: return False
            elif d.get(k) != v: return False
        return True
    async def find_one_and_update(self, q, u):
        for d in self.docs:
            if self._match(d, q):
                before = dict(d); d.update(u["$set"]); return before
        return None
    async def insert_one(self, d): self.docs.append(d)
    def find(self, q):
        rows = [d for d in self.docs if self._match(d, q)]
        return types.SimpleNamespace(to_list=lambda length=None: _aw(rows))
    async def update_one(self, q, u):
        for d in self.docs:
            if self._match(d, q):
                d.update(u.get("$set", {}))
                for k, v in u.get("$inc", {}).items(): d[k] = d.get(k, 0) + v
                return
class DB:
    def __init__(self):
        self.wallet_transactions, self.users, self.notifications = Coll(), Coll(), Coll()

async def scenario(name, events, expect_balance, expect_status):
    db = DB()
    db.users.docs.append({"_id": 1, "wallet_balance": 900})   # 1000 withdrawn, 100 left? -> balance after deduction
    db.users.docs[0]["wallet_balance"] = 0
    db.wallet_transactions.docs.append({"user_id": 1, "transaction_type": "withdrawal", "amount": -1000, "status": "pending", "paystack_reference": "wd_x"})
    for new_status, allowed in events:
        await wallet.refund_withdrawal(db, "wd_x", new_status, allowed)
    bal = db.users.docs[0]["wallet_balance"]; st = db.wallet_transactions.docs[0]["status"]
    refunds = [d for d in db.wallet_transactions.docs if d.get("transaction_type") == "refund"]
    ok = bal == expect_balance and st == expect_status
    print(("PASS" if ok else "FAIL"), name, f"balance={bal} status={st} refunds={len(refunds)}")
    return ok

async def main():
    F = ("failed", ["pending"]); R = ("reversed", ["pending", "success"])
    res = [
        await scenario("failed once", [F], 1000, "failed"),
        await scenario("failed delivered twice", [F, F], 1000, "failed"),
        await scenario("failed then reversed (no double refund)", [F, R], 1000, "failed"),
        await scenario("reversed twice", [R, R], 1000, "reversed"),
    ]
    # success first: failed must NOT refund
    db = DB(); db.users.docs.append({"_id": 1, "wallet_balance": 0})
    db.wallet_transactions.docs.append({"user_id": 1, "transaction_type": "withdrawal", "amount": -1000, "status": "success", "paystack_reference": "wd_x"})
    await wallet.refund_withdrawal(db, "wd_x", *F)
    ok = db.users.docs[0]["wallet_balance"] == 0; res.append(ok); print("PASS" if ok else "FAIL", "failed after success is ignored")
    # success then reversed refunds
    await wallet.refund_withdrawal(db, "wd_x", *R)
    ok = db.users.docs[0]["wallet_balance"] == 1000; res.append(ok); print("PASS" if ok else "FAIL", "reversed after success refunds once")
    # unknown reference
    ok = (await wallet.refund_withdrawal(db, "nope", *F)) is False; res.append(ok); print("PASS" if ok else "FAIL", "unknown reference ignored")

    # ---- immediate / checked outcomes ----
    from datetime import datetime, timedelta, timezone
    def fresh(status="pending", age_min=0, ref="wd_x"):
        db = DB(); db.users.docs.append({"_id": 1, "wallet_balance": 0})
        db.wallet_transactions.docs.append({"user_id": 1, "transaction_type": "withdrawal", "amount": -1000, "status": status,
            "paystack_reference": ref, "created_at": datetime.now(timezone.utc) - timedelta(minutes=age_min)})
        return db
    def chk(name, ok): res.append(ok); print("PASS" if ok else "FAIL", name)

    db = fresh(); await wallet.settle_withdrawal_from_status(db, "wd_x", "success"); await wallet.settle_withdrawal_from_status(db, "wd_x", "success")
    chk("immediate success marks it complete", db.wallet_transactions.docs[0]["status"] == "success" and db.users.docs[0]["wallet_balance"] == 0)
    db = fresh(); await wallet.settle_withdrawal_from_status(db, "wd_x", "failed"); await wallet.settle_withdrawal_from_status(db, "wd_x", "failed")
    chk("immediate failure refunds exactly once", db.users.docs[0]["wallet_balance"] == 1000)
    db = fresh(); chk("a non-final status changes nothing", await wallet.settle_withdrawal_from_status(db, "wd_x", "pending") == "pending" and db.wallet_transactions.docs[0]["status"] == "pending")

    class FakePaystack:
        def __init__(self, answers): self.answers = answers; self.calls = 0
        async def verify_transfer(self, ref):
            self.calls += 1; a = self.answers
            if isinstance(a, Exception): raise a
            return {"data": {"status": a}}

    db = fresh(age_min=30); n = await wallet.reconcile_pending_withdrawals(db, FakePaystack("success"))
    chk("old pending withdrawal confirmed by Paystack completes", n == 1 and db.wallet_transactions.docs[0]["status"] == "success")
    db = fresh(age_min=30); n = await wallet.reconcile_pending_withdrawals(db, FakePaystack("failed"))
    chk("old pending withdrawal Paystack says failed is refunded", n == 1 and db.users.docs[0]["wallet_balance"] == 1000)
    db = fresh(age_min=5); ps = FakePaystack("success"); n = await wallet.reconcile_pending_withdrawals(db, ps)
    chk("recent withdrawals are left for the webhook", n == 0 and ps.calls == 0)
    db = fresh(age_min=30); n = await wallet.reconcile_pending_withdrawals(db, FakePaystack("pending"))
    chk("still processing stays pending", n == 0 and db.wallet_transactions.docs[0]["status"] == "pending")
    db = fresh(age_min=30); n = await wallet.reconcile_pending_withdrawals(db, FakePaystack(HTTPStatusError(404)))
    chk("unknown to Paystack but recent: wait", n == 0 and db.users.docs[0]["wallet_balance"] == 0)
    db = fresh(age_min=300); n = await wallet.reconcile_pending_withdrawals(db, FakePaystack(HTTPStatusError(404)))
    chk("unknown to Paystack for hours: money returned", n == 1 and db.users.docs[0]["wallet_balance"] == 1000)
    db = fresh(age_min=300); n = await wallet.reconcile_pending_withdrawals(db, FakePaystack(RequestError("down")))
    chk("Paystack unreachable: nothing is changed", n == 0 and db.users.docs[0]["wallet_balance"] == 0)
    db = fresh(age_min=300); n = await wallet.reconcile_pending_withdrawals(db, FakePaystack(HTTPStatusError(500)))
    chk("Paystack error: nothing is changed", n == 0 and db.users.docs[0]["wallet_balance"] == 0)

    # phone normalisation (same regex as schemas.PayoutAccountAdd)
    def norm(v):
        digits = re.sub(r"[\s\-()]", "", v)
        m = re.fullmatch(r"(?:\+?254|0)?([71]\d{8})", digits)
        return "0" + m.group(1) if m else None
    cases = {"0712345678": "0712345678", "+254712345678": "0712345678", "254 712 345 678": "0712345678",
             "712345678": "0712345678", "0112345678": "0112345678", "07123": None, "0812345678": None, "abc": None}
    for k, v in cases.items():
        ok = norm(k) == v; res.append(ok); print("PASS" if ok else "FAIL", f"phone {k!r} -> {norm(k)!r}")
    print("\nALL PASS" if all(res) else "\nSOME FAILED")
asyncio.run(main())
