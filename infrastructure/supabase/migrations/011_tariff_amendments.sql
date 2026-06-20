-- ============================================================
-- CargoIQ Migration 011: Tariff Amendments (Firecrawl Alternative)
-- ============================================================
-- Zero ongoing cost replacement for a paid scraping service.
-- When SARS publishes a tariff change, add one row here — via
-- the API endpoint or directly in SQL Editor — and the HS
-- Classifier automatically starts flagging matching shipments.
-- No redeploy, no scraping credits, no new infrastructure.
--
-- Global reference data — same pattern as diesel_price_history.
-- No org_id: applies to every CargoIQ client equally.

CREATE TABLE IF NOT EXISTS tariff_amendments (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  effective_date    DATE NOT NULL,
  category          TEXT NOT NULL,           -- e.g. "steel", "polyethylene"
  keywords          TEXT[] NOT NULL,         -- matched against cargo descriptions
  hs_chapters       TEXT[] NOT NULL DEFAULT '{}',  -- 2-digit chapters, e.g. {'72','73'}
  change_description TEXT NOT NULL,
  source            TEXT,                     -- e.g. "SARS.gov.za tariff amendment, 12 June 2026"
  added_by          TEXT,                     -- who logged it (founder, ops, etc.)
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tariff_amendments_date ON tariff_amendments(effective_date DESC);

ALTER TABLE tariff_amendments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated_read_tariff_amendments" ON tariff_amendments
  FOR SELECT
  USING (auth.role() = 'authenticated');

-- Seed with the 3 amendments already known (12 June 2026)
INSERT INTO tariff_amendments (effective_date, category, keywords, hs_chapters, change_description, source) VALUES
  ('2026-06-12', 'steel',
   ARRAY['steel','flat-rolled','hot-rolled','cold-rolled','steel coil','steel sheet'],
   ARRAY['72','73'],
   'Safeguard duty introduced — 15%+ depending on product, 3-year protection period',
   'SARS.gov.za tariff amendment, 12 June 2026'),
  ('2026-06-12', 'polyethylene',
   ARRAY['polyethylene','PE film','PE bags','PE containers','plastic film','plastic packaging'],
   ARRAY['39'],
   'Anti-dumping duty structure changed on polyethylene products',
   'SARS.gov.za tariff amendment, 12 June 2026'),
  ('2026-06-12', 'machinery',
   ARRAY['industrial machinery','industrial equipment','machinery parts'],
   ARRAY['84','85'],
   'Tariff relief — select industrial machinery reduced from 20% to 15%',
   'SARS.gov.za tariff amendment, 12 June 2026')
ON CONFLICT DO NOTHING;
