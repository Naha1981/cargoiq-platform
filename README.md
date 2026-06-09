# CargoIQ Platform

South Africa's AI compliance and cost containment layer for freight forwarders.

## Products
- **CargoFlow AI** — Email/PDF/WhatsApp ingestion → AI extraction → SARS Compliance Shield → CargoWise execution
- **WiseLayer** — XML Compactor, RLA Sentinel, Configuration AI, BI Co-Pilot

## Tech Stack
- **Backend:** Python 3.12 + FastAPI + Supabase
- **Frontend:** Next.js 14 App Router + Tailwind CSS + ShadCN
- **AI:** LangChain + Instructor + Claude API (Anthropic)
- **Queue:** Redis + RabbitMQ
- **Deployment:** Railway (API) + Vercel (Web)

## Quick Start

```bash
# 1. Clone and install
git clone https://github.com/cargoiq-za/cargoiq-platform
cd cargoiq-platform

# 2. Copy environment files
cp .env.example .env
cp apps/api/.env.example apps/api/.env
cp apps/web/.env.example apps/web/.env.local

# 3. Fill in your Supabase + Anthropic credentials in .env files

# 4. Start with Docker
docker-compose up --build

# OR run individually:
# Backend: cd apps/api && pip install -r requirements.txt && uvicorn main:app --reload
# Frontend: cd apps/web && npm install && npm run dev
```

## Database Setup
```bash
# Run migrations against your Supabase project
cd infrastructure/supabase
# Copy migrations to Supabase dashboard SQL editor and run in order
```

## Project Structure
```
cargoiq-platform/
├── apps/
│   ├── api/          # FastAPI backend (Python)
│   └── web/          # Next.js 14 frontend (TypeScript)
├── packages/
│   ├── extraction/   # AI extraction engine
│   ├── compliance/   # Compliance Shield modules
│   └── cargowise/    # CargoWise integration
└── infrastructure/
    ├── supabase/     # Database migrations
    └── docker/       # Docker configs
```

## Environment Variables
See `.env.example` for all required variables.

## Deployment
- **API:** Push to Railway. `railway up` from `apps/api/`
- **Web:** Push to Vercel. Connect GitHub repo, set `apps/web` as root.

---
*CargoIQ (Pty) Ltd · Johannesburg, South Africa*
