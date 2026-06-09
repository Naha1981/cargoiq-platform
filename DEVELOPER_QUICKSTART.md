# CargoIQ — Developer Quickstart
## Week 1 Build Guide

---

## Prerequisites
- Python 3.12+
- Node.js 20+
- Docker & Docker Compose
- A Supabase project (free tier works)
- Anthropic API key (Claude)

---

## Day 1 — Foundation (Environment + Database)

### Step 1: Clone and configure
```bash
git clone https://github.com/cargoiq-za/cargoiq-platform
cd cargoiq-platform
cp .env.example .env
# Fill in SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY, ANTHROPIC_API_KEY
```

### Step 2: Run database migration
1. Open your Supabase project → SQL Editor
2. Paste the contents of `infrastructure/supabase/migrations/001_initial_schema.sql`
3. Click Run
4. Verify tables created: organisations, users, shipments, documents, etc.

### Step 3: Create Supabase Storage bucket
1. Supabase → Storage → New bucket
2. Name: `documents`
3. Public: NO (private bucket)

### Step 4: Start the API
```bash
cd apps/api
cp .env.example .env
# Fill in your env values
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Step 5: Verify auth works
```bash
# Sign up a test user
curl -X POST http://localhost:8000/api/v1/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123","full_name":"Test User","org_name":"Test Freight Co"}'

# Should return: {"access_token": "...", "user": {...}, "organisation": {...}}
```

✅ **Day 1 complete** when: API starts, migration runs, signup returns a JWT.

---

## Day 2 — Document Upload

### Step 1: Start with Docker (includes Redis)
```bash
docker-compose up redis -d
cd apps/api && uvicorn main:app --reload
```

### Step 2: Test document upload
```bash
# Get a token first (from Day 1 signup)
TOKEN="your_jwt_token_here"

# Upload a test PDF
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/test_invoice.pdf"

# Should return: {"id": "...", "status": "pending", ...}
```

### Step 3: Check processing started
```bash
DOC_ID="the_id_from_upload"

# Poll every 2 seconds until status = "processed"
curl http://localhost:8000/api/v1/documents/$DOC_ID \
  -H "Authorization: Bearer $TOKEN"
```

✅ **Day 2 complete** when: PDF uploads, OCR runs, `raw_text` column populated.

---

## Day 3 — Text Extraction Quality Check

After uploading 5 real freight PDFs, check extraction quality:
```bash
# Get document with raw text
curl "http://localhost:8000/api/v1/documents/$DOC_ID?include_text=true" \
  -H "Authorization: Bearer $TOKEN" | python -m json.tool | grep raw_text
```

Check:
- [ ] Digital PDFs: text should be clean and complete
- [ ] Scanned PDFs: OCR should recognise key fields
- [ ] Invoice numbers, weights, addresses visible in raw_text
- [ ] No major garbage characters or encoding issues

If text quality is poor on scanned docs, Marker OCR may need GPU or fallback to pdfplumber.

✅ **Day 3 complete** when: text extraction works on 5 sample freight documents.

---

## Day 4 — First AI Extraction Test

### Step 1: Add sample PDFs to test directory
```bash
cp your_invoice.pdf apps/api/tests/extraction/samples/
```

### Step 2: Update expected values
Edit `apps/api/tests/extraction/expected.json` with the known correct values from your sample PDFs.

### Step 3: Run accuracy test
```bash
cd apps/api
ANTHROPIC_API_KEY=sk-ant-your-key python -m tests.extraction.accuracy_test
```

### Expected output (first run):
```
OVERALL ACCURACY: 72.3% (47/65 fields)
🟡 Good progress. Focus prompt engineering on failing fields.
```

Common first-run failures:
- `hs_code_primary`: Model extracts with dots (e.g. "8471.30.00") — needs cleaning
- `gross_weight`: Unit included in value (e.g. "1250 KGS") — needs split
- `shipment_type`: Not always determinable from invoice alone

✅ **Day 4 complete** when: accuracy test runs and produces a score.

---

## Day 5 — Prompt Engineering

### Iterating on the extraction prompt

The extraction system prompt is in:
`apps/api/services/extraction_service.py` → `EXTRACTION_SYSTEM_PROMPT`

For each failing field from Day 4, add a specific rule. Examples:

**If HS codes include dots:**
```
SARS requires HS codes as exactly 8 numeric digits with no punctuation.
If you see "8471.30.00", extract as "84713000".
```

**If weights include units:**
```
Extract gross_weight as a NUMBER ONLY (e.g. "1250.5" not "1250.5 KGS").
Put the unit in gross_weight_unit separately.
```

**If shipment type is wrong:**
```
Determine shipment_type from: bill of lading = ocean (fcl/lcl),
air waybill = air, road waybill = road. If both invoice and BL,
use the transport document to determine type.
```

### Re-run and compare
```bash
# After editing the prompt, re-run:
python -m tests.extraction.accuracy_test

# Compare new score vs Day 4 baseline in results.json
```

Target: ≥85% by end of Day 5.

✅ **Week 1 complete** when:
- [ ] Supabase running with all tables
- [ ] File upload stores PDFs in storage
- [ ] OCR extracts readable text from freight documents
- [ ] AI extraction achieves ≥75% field accuracy
- [ ] At least one end-to-end test: upload PDF → extracted fields visible in API response

---

## Starting the Frontend

```bash
cd apps/web
cp .env.example .env.local
# Set NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, NEXT_PUBLIC_API_URL

npm install
npm run dev
# Visit http://localhost:3000
```

### Test flow:
1. Go to http://localhost:3000/auth/signup
2. Create an account
3. Navigate to /queue/upload
4. Drop a PDF file
5. Watch it process and appear in /queue
6. Click the shipment to see extracted fields

---

## Deployment

### Deploy API to Railway
```bash
npm install -g @railway/cli
railway login
cd apps/api
railway init
railway up
```

### Deploy Web to Vercel
```bash
npm install -g vercel
cd apps/web
vercel
# Follow prompts, set environment variables in Vercel dashboard
```

### Deploy to custom domain
1. cargoiq.co.za → point to Vercel (web)
2. api.cargoiq.co.za → point to Railway (API)
3. Set CORS in API .env: `ALLOWED_ORIGINS=https://app.cargoiq.co.za`

---

## Environment Variables Checklist

Before first pilot client:
- [ ] `SUPABASE_URL` — your Supabase project URL
- [ ] `SUPABASE_ANON_KEY` — Supabase anon key
- [ ] `SUPABASE_SERVICE_ROLE_KEY` — Supabase service role key
- [ ] `ANTHROPIC_API_KEY` — Claude API key
- [ ] `SECRET_KEY` — random 32+ char string
- [ ] `ENCRYPTION_KEY` — 32 bytes hex for CW credential encryption
- [ ] `ALLOWED_ORIGINS` — your web app URL

---

## Getting Help

- FastAPI docs: http://localhost:8000/docs (dev mode)
- Supabase dashboard: your Supabase project URL
- n8n: http://localhost:5678 (docker compose)

*CargoIQ (Pty) Ltd · Johannesburg, South Africa*
