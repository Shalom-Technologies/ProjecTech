import asyncio, importlib.util, sys, types
import os
BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
fa = types.ModuleType("fastapi")
class HTTPException(Exception): pass
class R:
    def _d(self,*a,**k): return lambda f: f
    get=post=put=delete=_d
    def __init__(self,*a,**k): pass
fa.APIRouter, fa.HTTPException, fa.Depends, fa.Query, fa.Request = R, HTTPException, (lambda x=None: x), (lambda d=None,**k: d), object
sys.modules["fastapi"] = fa
httpx = types.ModuleType("httpx"); httpx.HTTPStatusError = httpx.RequestError = Exception; sys.modules["httpx"] = httpx
def mod(n, **a): m = types.ModuleType(n); m.__dict__.update(a); sys.modules[n] = m; return m
mod("app").__path__ = []
mod("app.config", settings=types.SimpleNamespace(CURRENCY="KES"))
class Projects:
    docs = [{"assigned_to": "dev1", "salesperson_id": "s1", "status": "completed"},
            {"assigned_to": "dev1", "salesperson_id": "s1", "status": "in_progress"},
            {"assigned_to": "dev1", "salesperson_id": "s2", "status": "completed"},
            {"assigned_to": "dev2", "salesperson_id": "s1", "status": "completed"}]
    async def count_documents(self, q):
        return sum(all(d.get(k) == v for k, v in q.items()) for d in self.docs)
mod("app.database", get_database=lambda: types.SimpleNamespace(projects=Projects()))
mod("app.dependencies", get_current_user=lambda: None)
mod("app.schemas", UserProfileUpdate=object, PayoutAccountAdd=object, WithdrawRequest=object)
mod("app.paystack_client", paystack=None); mod("app.rate_limit", limiter=types.SimpleNamespace(limit=lambda s: (lambda f: f)))
mod("app.wallet", refund_withdrawal=None)
spec = importlib.util.spec_from_file_location("app.routes.users", f"{BACKEND}/app/routes/users.py")
users = importlib.util.module_from_spec(spec); spec.loader.exec_module(users)
def user(role, _id): return {"_id": _id, "role": role, "email": "e", "first_name": "A", "last_name": "B", "created_at": 0}
async def main():
    a = await users.get_profile(current_user=user("developer", "dev1"))
    b = await users.get_profile(current_user=user("salesperson", "s1"))
    c = await users.get_profile(current_user=user("developer", "nobody"))
    print("developer dev1 ->", a["completed_projects"], "(expect 2)")
    print("salesperson s1 ->", b["completed_projects"], "(expect 2)")
    print("no projects    ->", c["completed_projects"], "(expect 0)")
    assert (a["completed_projects"], b["completed_projects"], c["completed_projects"]) == (2, 2, 0)
    print("ALL PASS")
asyncio.run(main())
