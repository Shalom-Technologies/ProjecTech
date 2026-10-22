# ProjecTech

Are you a developer who has been looking for work for a very long time and landing no clients? Or maybe you're a marketer who's been job hunting or wondering how you can monetize your skills without entering the rat race.

Introducing [ProjecTech](https://projectech.dev/), a platform that connects developers and marketers.

On [ProjecTech](https://projectech.dev/) marketers do what they do best, find a client who is looking for a software developer. You can narrow down your niche or diversify as much as you can. It doesn't matter, just find a client. Then, connect with a developer who is the best fit for that project right on [ProjecTech](https://projectech.dev/). You get paid a commission from your work, so the more clients you land the more you get paid.

Are you a developer who's tired of the hell that is finding your own clients? Well, on [ProjecTech](https://projectech.dev/) we already have projects ready that are looking for a developer to complete them. You don't need to pay to land a client or create a gig that sits at the last page where no one will see it. It doesn't matter if you are a junior developer or a more advanced one. You can land a project in a few clicks and start working then get paid based on the work you do.

So what are you waiting for? Signup for [ProjecTech](https://projectech.dev/) and start working today.


---

## For developers

ProjecTech is a FastAPI + MongoDB backend (`backend/`, deployed on Fly.io) and a React + Vite frontend (`frontend/`, deployed on Render). Payments run through Paystack in KES, with M-Pesa payouts.

### How the money moves

1. A salesperson accepts a developer's application, which fixes the agreed price. A price change needs the developer's approval.
2. The client opens the project's invoice link (`/pay/<token>`) and pays through Paystack. The money is held, not paid out.
3. The developer marks the work delivered. The client then has `REVIEW_WINDOW_DAYS` (7) to accept it or report a problem. With no objection, the payment is released automatically.
4. Released earnings wait `PAYOUT_HOLD_DAYS` (7) as pending, then become withdrawable to M-Pesa.
5. A reported problem freezes the release until an admin resolves it (see Operations).

### Run it locally

Backend (Python 3.12):

```
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # then fill it in; SECRET_KEY is required (openssl rand -hex 32)
uvicorn app.main:app --reload --port 8000
```

Frontend:

```
cd frontend
npm install
echo "VITE_API_BASE_URL=http://localhost:8000" > .env.local
npm run dev
```

### Tests

```
cd backend && pytest -q          # fast flow checks against an in-memory database, plus an import check
cd frontend && npm run lint && npm run build
```

CI (`.github/workflows/ci.yml`) runs both on every pull request. See `backend/tests/flows/README.md` for what the flow checks do and do not cover.

### Deploy

Backend on Fly.io:

```
cd backend
fly secrets set \
  MONGODB_URL='mongodb+srv://...' \
  SECRET_KEY="$(openssl rand -hex 32)" \
  CORS_ORIGINS=https://projectech.dev \
  FRONTEND_URL=https://projectech.dev \
  PAYSTACK_PUBLIC_KEY=... PAYSTACK_SECRET_KEY=... \
  SMTP_USERNAME=... SMTP_PASSWORD=... EMAIL_FROM=...
fly deploy
```

The app refuses to start without a strong `SECRET_KEY`. Changing it later logs everyone out.

Frontend on Render (Static Site): root directory `frontend`, build command `npm install && npm run build`, publish directory `dist`, environment variable `VITE_API_BASE_URL` set to the Fly API address, and one rewrite rule: source `/*`, destination `/index.html`, action Rewrite. Without that rule, refreshing a page or following an email or Paystack link returns a 404.

Paystack dashboard: set the webhook URL to `https://<your-fly-app>.fly.dev/api/payments/webhook`, subscribe it to `charge.success` and the `transfer.*` events, and turn off "Confirm transfers before sending" so M-Pesa withdrawals go out without manual approval.

### Operations

- **Disputes.** A problem report freezes the payment. Review it, then (from `backend/`, or on Fly with `fly ssh console -C "python -m scripts.resolve_dispute list"`):
  `python -m scripts.resolve_dispute list`, `show <project_id>`, and `resolve <project_id> release|refund|split --refund-amount N --note "..."`.
  For a refund or split, issue the refund to the client in the Paystack dashboard first. The script only records the outcome and pays out what remains.
- **Payments that need a refund.** If a client pays a retired link at an old price, the transaction is flagged `needs_refund: true` and the salesperson is notified. Refund it in Paystack.
- **Background job.** Every `BACKGROUND_JOB_INTERVAL_SECONDS` (15 minutes) each server releases deliveries whose review window ended and payouts whose hold ended. It is safe with several servers running.
- **Backups.** Atlas free (M0) clusters have no backups; use `mongodump --uri "$MONGODB_URL" --gzip --archive=projectech-$(date +%F).gz` on a schedule and keep copies off the machine. Flex clusters take daily snapshots automatically, and M10 and above have Cloud Backup. Because this database holds money records, use a tier with backups before launch, and test a restore once.
- **Region.** The Fly machine is in Johannesburg (`jnb`). Choose the Atlas region closest to it so database calls stay fast.
- **Size.** The machine has 512 MB of memory. If Fly reports out-of-memory restarts, raise `memory` in `backend/fly.toml`.
