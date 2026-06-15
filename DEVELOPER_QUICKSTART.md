# CargoIQ — Deployment Quickstart
## From a fresh machine to a live, client-demo-ready platform

**Repo:** https://github.com/Naha1981/cargoiq-platform  
**Stack:** FastAPI · Supabase · Next.js 14 · Playwright · Evolution API · Redis · APScheduler  
**Deploy targets:** Railway (API + cw-worker) · Vercel (web) · Supabase (database)

---

## Prerequisites
- Python 3.12+
- Node.js 20+
- Docker Desktop (for local dev / Evolution API)
- Supabase account (free tier works for pilots)
- Anthropic API key — console.anthropic.com
- Railway account — railway.app
- Vercel account — vercel.com

---

## Step 1 — Clone and configure environment

```bash
git clone https://github.com/Naha1981/cargoiq-platform
cd cargoiq-platform

# Generate your two secret keys — run each separately, use different outputs
openssl rand -hex 32   # → paste as SECRET_KEY
openssl rand -hex 32   # → paste as ENCRYPTION_KEY

# Root env (used by docker-compose / Evolution API)
cp .env.example .env

# API env
cp apps/api/.env.example apps/api/.env

# Web env
cp apps/web/.env.example apps/web/.env.local

# CW Worker env
cp services/cw-worker/.env.example services/cw-worker/.env
```

Fill in all four files. Minimum required values to get the API running:

| Variable | Where to get it |
|---|---|
| `SUPABASE_URL` | Supabase → Project Settings → API |
| `SUPABASE_ANON_KEY` | Supabase → Project Settings → API |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Project Settings → API |
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `SECRET_KEY` | `openssl rand -hex 32` |
| `ENCRYPTION_KEY` | `openssl rand -hex 32` (different value) |

---

## Step 2 — Create Supabase project and run all migrations

1. Go to supabase.com → New project → choose **af-south-1** (Cape Town) for POPIA
2. Once created, open **SQL Editor**
3. Run each migration **in order** — paste and click Run one at a time:

```
infrastructure/supabase/migrations/001_initial_schema.sql   ← core tables + RLS
infrastructure/supabase/migrations/002_test_seed.sql        ← test org + shipments
infrastructure/supabase/migrations/003_portal_jobs.sql      ← portal jobs + container tracking
infrastructure/supabase/migrations/004_portal_credentials.sql ← encrypted portal credentials
infrastructure/supabase/migrations/005_shadow_audits.sql    ← shadow audit table
infrastructure/supabase/migrations/006_carrier_audit_and_checkins.sql ← carrier audit + driver check-ins
infrastructure/supabase/migrations/007_proof_pages.sql      ← shareable proof page tokens
```

4. Create a Storage bucket:
   - Supabase → Storage → New bucket
   - Name: `documents` · Public: **NO**

---

## Step 3 — Start the API locally

```bash
cd apps/api
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Expected startup output:
```
INFO  🚀 CargoIQ API starting — development
INFO  Supabase: https://your-project.supabase.co...
INFO  Claude API: ✓ configured
INFO  ✅ Scheduler started — 4 jobs registered
INFO  [1] Daily RLA check        — 06:00 SAST daily
INFO  [2] Container tracker      — every 30 min
INFO  [3] Notification processor — every 2 min
INFO  [4] Shadow audit sweep     — Mon 07:00 SAST
```

Verify it's healthy:
```bash
curl http://localhost:8000/health
# {"status": "healthy", "checks": {...}}

curl http://localhost:8000/scheduler/status
# {"scheduler": "running", "job_count": 4, "jobs": [...]}
```

---

## Step 4 — Create your first account

```bash
curl -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "you@cargoiq.co.za",
    "password": "changeme123",
    "full_name": "Thabiso",
    "org_name": "CargoIQ Demo"
  }'
# Returns: {"access_token": "...", "user": {...}, "organisation": {...}}
```

Save the `access_token` — you need it for all subsequent API calls.

---

## Step 5 — Start Redis (required for queue)

```bash
docker-compose up redis -d
```

Or use Railway's managed Redis (add a Redis plugin to your Railway project).

---

## Step 6 — Start the web frontend

```bash
cd apps/web
npm install
npm run dev
# → http://localhost:3000
```

---

## Step 7 — Start Evolution API (WhatsApp)

```bash
docker-compose up evolution-api -d
```

Then configure it:
1. Open http://localhost:8080/manager
2. Create an instance named `cargoiq`
3. Scan the QR code with your WhatsApp Business number
4. Set webhook URL to: `http://your-api-url/api/v1/internal/webhooks/whatsapp-checkin/{org_id}`

---

## Step 8 — Deploy to production

### API → Railway

```bash
# Install Railway CLI
npm install -g @railway/cli
railway login

# From project root
railway init
railway link

# Set all env vars from apps/api/.env in Railway dashboard:
# Project → Variables → add each one
# Then deploy:
railway up --service api
```

Or connect GitHub repo in Railway UI:
1. New project → Deploy from GitHub repo → select `Naha1981/cargoiq-platform`
2. Set root directory: `apps/api`
3. Add all variables from `apps/api/.env.example`
4. Railway auto-detects the Dockerfile

### Web → Vercel

```bash
cd apps/web
vercel --prod
```

Or connect in Vercel UI:
1. New project → Import from GitHub → `Naha1981/cargoiq-platform`
2. Root directory: `apps/web`
3. Add all variables from `apps/web/.env.example`

### CW Worker → Railway (separate service)

Same as API but root directory: `services/cw-worker`
```
Start command: npm start
```

---

## Step 9 — Generate the internal n8n token (NOT needed — replaced)

The three n8n workflows have been replaced by `apps/api/scheduler.py` which starts
automatically with the API. No n8n, no Zapier, no Make required.

To confirm jobs are running after deployment:
```bash
curl https://your-api.railway.app/scheduler/status
```

---

## Step 10 — Run your first Shadow Audit (the demo)

```bash
# Upload 20 of a prospect's shipment PDFs via the web UI:
# → /queue/upload

# Then trigger the Shadow Audit:
curl -X POST "https://your-api.railway.app/api/v1/audit/shadow?days_back=30" \
  -H "Authorization: Bearer $TOKEN"

# Generate a shareable proof-page link:
curl -X POST "https://your-api.railway.app/api/v1/audit/shadow/{audit_id}/share" \
  -H "Authorization: Bearer $TOKEN"
# Returns: {"share_path": "/api/v1/public/proof/aB3xY..."}
# Text THIS link to the prospect before your call.
```

---

## Complete feature inventory (what's built)

| Feature | Endpoint | Status |
|---|---|---|
| Auth (signup/login/me) | `/auth/*` | ✅ |
| PDF extraction (Claude AI) | `/documents/upload` | ✅ |
| Shipment queue | `/shipments/*` | ✅ |
| Compliance Shield (6 modules) | runs on upload | ✅ |
| CustomsStop risk score (1–5) | `shield_results.risk_score` | ✅ |
| Email Inbox AI Agent | `/inbox/*` | ✅ |
| SARS eFiling portal adapter | via cw-worker | ✅ |
| Transnet Navis portal adapter | via cw-worker | ✅ |
| Shipping line trackers (7 lines) | via cw-worker | ✅ |
| RLA Sentinel (daily 06:00) | scheduler job 1 | ✅ |
| Container tracker (30-min) | scheduler job 2 | ✅ |
| Notification sender (2-min) | scheduler job 3 | ✅ |
| Weekly shadow audit sweep | scheduler job 4 | ✅ |
| CarrierInvoice Auditor | `/carrier-audit/*` | ✅ |
| Driver WhatsApp check-ins | `/internal/webhooks/whatsapp-checkin/{org}` | ✅ |
| Waiting-time charge notice | `/analytics/waiting-time/findings/{id}/charge-notice` | ✅ |
| Shadow Audit | `/audit/shadow` | ✅ |
| Shareable Proof Page | `/public/proof/{token}` | ✅ |
| Savings Certificate (print-to-PDF) | `/audit/certificate` | ✅ |
| Client Success Story | `/audit/success-story` | ✅ |
| Sentinel dashboard | `/sentinel` (frontend) | ✅ |
| Onboarding checklist | `/onboarding/status` | ✅ |
| Portal credentials vault | `/portals/credentials` | ✅ |
| Analytics & ROI | `/analytics/*` | ✅ |

---

## Migrations reference

| File | What it creates |
|---|---|
| `001_initial_schema.sql` | organisations, users, shipments, documents, compliance_events, audit_log, rla_statuses |
| `002_test_seed.sql` | Demo org + 10 sample shipments for development |
| `003_portal_jobs.sql` | portal_jobs, container_tracking, notification_queue |
| `004_portal_credentials.sql` | portal_credentials (AES-256 encrypted) |
| `005_shadow_audits.sql` | shadow_audits |
| `006_carrier_audit_and_checkins.sql` | carrier_rate_cards, carrier_invoice_audits, driver_checkins, waiting_time_findings |
| `007_proof_pages.sql` | Adds share_token + share_enabled to shadow_audits |

---

## Security notes

1. **Repo is currently public.** Set to private in GitHub → Settings → Danger Zone before client work.
2. **Never commit `.env` files** — `.gitignore` excludes them but double-check.
3. **SECRET_KEY and ENCRYPTION_KEY** must be identical across API and CW Worker.
4. **SUPABASE_SERVICE_ROLE_KEY** bypasses all RLS — only use in server-side code, never in the browser.
5. **Proof page links** (`/public/proof/{token}`) are public to anyone with the link. Disable via `DELETE /audit/shadow/{id}/share`.

---

## Quick wins after deployment

In order of business value:

1. Upload 20 of Ghameeda Idalene's recent shipment PDFs → run Shadow Audit → generate Proof Page link → text it to her
2. Add Maersk / MSC rate cards in `/carrier-audit` → upload one carrier invoice → show the overcharge finding live
3. Ask Clearing Shipment's drivers to WhatsApp "ARRIVED [ref]" and "DEPARTED [ref]" → show the waiting-time charge notice generating automatically
4. Open `/sentinel` in a large browser window during the Karel-Jan meeting — let the live counters run
