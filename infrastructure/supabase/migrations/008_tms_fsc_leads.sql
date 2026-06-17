-- ============================================================
-- CargoIQ Migration 008: TMS compliance + FSC rate cards + Leads CRM
-- ============================================================

-- ── TMS declaration field on shipments ──────────────────────
-- Stores the SARS TMS permit number once the driver completes
-- the online declaration (sars.gov.za/travellerdeclaration).
-- Compliance Shield Module 7 checks this before flagging a hold.

ALTER TABLE shipments
  ADD COLUMN IF NOT EXISTS tms_declaration_number   TEXT,
  ADD COLUMN IF NOT EXISTS vehicle_registration_country TEXT,
  ADD COLUMN IF NOT EXISTS origin_country_code       TEXT DEFAULT 'ZA',
  ADD COLUMN IF NOT EXISTS destination_country_code  TEXT DEFAULT 'ZA';

COMMENT ON COLUMN shipments.tms_declaration_number IS
  'SARS TMS permit number — mandatory for foreign-registered vehicles from 1 June 2026';


-- ── FSC (Fuel Surcharge Clause) support on rate cards ───────
-- When diesel price drops, carriers are slow to reduce FSC.
-- These fields let CargoIQ calculate the correct FSC and flag
-- overcharges when the carrier hasn't passed on price reductions.

ALTER TABLE carrier_rate_cards
  ADD COLUMN IF NOT EXISTS diesel_base_rate_zar     NUMERIC(8,2),
  -- Base diesel price above which FSC kicks in (e.g. R22.00)
  ADD COLUMN IF NOT EXISTS fsc_percent_per_50c      NUMERIC(5,3),
  -- FSC % added per R0.50/litre above the base (typical: 1.0 = 1%)
  ADD COLUMN IF NOT EXISTS current_diesel_price_zar NUMERIC(8,2),
  -- Most recent diesel price captured (updated by scheduler)
  ADD COLUMN IF NOT EXISTS diesel_price_updated_at  TIMESTAMPTZ;

COMMENT ON COLUMN carrier_rate_cards.fsc_percent_per_50c IS
  'FSC formula: for every R0.50/litre above diesel_base_rate_zar, add this % to base freight. '
  'Standard SA FSC clause: 1% per R0.50/litre. Source: DMPR published prices.';


-- ── Leads CRM — Deal Hunter output ──────────────────────────
-- The Base44 Super Agent generates 10 leads per night. This table
-- stores them so you can track status, schedule follow-ups, and
-- correlate which leads converted to paying clients.

CREATE TABLE IF NOT EXISTS leads (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           UUID REFERENCES organisations(id),  -- NULL = internal CRM

  -- Company
  company_name     TEXT NOT NULL,
  company_website  TEXT,
  company_type     TEXT CHECK (company_type IN (
                     '3pl_fleet', 'importer_wholesaler',
                     'cross_border_trucker', 'clearing_agent', 'other'
                   )),
  location         TEXT,

  -- Contact
  contact_name     TEXT,
  contact_title    TEXT,
  linkedin_url     TEXT,
  email            TEXT,
  phone            TEXT,

  -- Pain & fit
  primary_pain     TEXT,                   -- e.g. "SARS TMS non-compliance"
  pain_estimate_zar_low  NUMERIC(12,2),
  pain_estimate_zar_high NUMERIC(12,2),
  cargoiq_modules  TEXT[],                 -- e.g. ARRAY['tms_checker','carrier_invoice_auditor']
  hook             TEXT,                   -- personalisation angle

  -- Outreach
  dm_draft         TEXT,                   -- LinkedIn DM ready to send
  status           TEXT NOT NULL DEFAULT 'new'
                   CHECK (status IN (
                     'new', 'messaged', 'replied', 'call_booked',
                     'audit_running', 'proposal_sent', 'won', 'lost', 'not_qualified'
                   )),
  source           TEXT DEFAULT 'deal_hunter',  -- 'deal_hunter' | 'manual' | 'referral'
  messaged_at      TIMESTAMPTZ,
  replied_at       TIMESTAMPTZ,
  call_booked_at   TIMESTAMPTZ,
  notes            TEXT,

  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_leads_status   ON leads(status);
CREATE INDEX idx_leads_type     ON leads(company_type);
CREATE INDEX idx_leads_created  ON leads(created_at DESC);

ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
-- Leads are internal to CargoIQ the company — not tenant-isolated.
-- Only service role can read/write. No user-facing RLS policy needed.

CREATE TRIGGER update_leads_updated_at
  BEFORE UPDATE ON leads
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- ── Diesel price history ─────────────────────────────────────
-- Stores daily diesel prices for FSC auditing.
-- Updated by the scheduler's new diesel_price_updater job.

CREATE TABLE IF NOT EXISTS diesel_price_history (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  price_zar     NUMERIC(8,2) NOT NULL,
  region        TEXT NOT NULL DEFAULT 'gauteng'
                CHECK (region IN ('gauteng', 'coast')),
  effective_date DATE NOT NULL,
  source        TEXT DEFAULT 'dmpr',   -- Dept of Mineral & Petroleum Resources
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(effective_date, region)
);

-- Seed: verified prices from constants.py
INSERT INTO diesel_price_history (price_zar, region, effective_date, source) VALUES
  (26.11, 'gauteng', '2026-04-01', 'dmpr'),   -- April spike
  (22.86, 'gauteng', '2026-06-03', 'dmpr'),   -- June drop (R3.25 reduction)
  (25.35, 'coast',   '2026-04-01', 'dmpr'),
  (22.11, 'coast',   '2026-06-03', 'dmpr')
ON CONFLICT (effective_date, region) DO NOTHING;
