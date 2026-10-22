# Flow checks

Each `check_*.py` drives the real route functions (payments, delivery, disputes, password
reset, wallet) against a small in-memory fake of MongoDB, with FastAPI, Paystack and the
email sender replaced by stubs. They need no database, network or installed packages, so they
run in a second. `tests/test_flows.py` runs every one of them under pytest.

Limits worth knowing: the fake database implements only the MongoDB features the app uses
(`$set`, `$inc`, `$in`, `$ne`, `$lte`, `$gte`, positional updates, `find_one_and_update`). If
code starts using another operator (for example `$push` in a new place), add it to the fake in
the check files. Unique indexes and real concurrency are simulated, not exercised, so
Paystack test-mode runs are still needed before launch.
