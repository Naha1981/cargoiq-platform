-- ============================================================
-- CargoIQ Migration 006: Carrier Invoice Auditor + Driver Check-Ins
-- ============================================================
-- Both features run on plain Postgres (Supabase) — no PostGIS,
-- no Temporal, no GPS hardware required. Driver waiting-time is
-- captured via two WhatsApp text messages (ARRIVED / DEPARTED),
-- not GPS geofencing.

-- ── Carrier Rate Cards ──────────────────────────────────────
-- The org's negotiated rates per carrier, per charge type.
-- Used to detect overcharges on incoming carrier invoices.

CREATE TABLE carrier_rate_cards (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  carrier_name  TEXT NOT NULL,          -- "Maersk", "MSC", "Bidvest Panalpina", etc.
  charge_type   TEXT NOT NULL,          -- "ocean_freight" | "baf" | "thc" | "documentation" | "demurrage" | other
  lane          TEXT,                   -- e.g. "CNSHA-ZADUR" — optional, NULL = applies to all lanes
  unit          TEXT NOT NULL DEFAULT 'per_shipment',  -- "per_container" | "per_kg" | "per_cbm" | "per_shipment" | "flat"
  agreed_rate   NUMERIC(12,2) NOT NULL,
  currency      TEXT NOT NULL DEFAULT 'USD',
  valid_from    DATE NOT NULL DEFAULT CURRENT_DATE,
  valid_to      DATE,
  notes         TEXT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_rate_cards_org_carrier ON carrier_rate_cards(org_id, carrier_name);

ALTER TABLE carrier_rate_cards ENABLE ROW LEVEL SECURITY;
CREATE POLICY "org_isolation_rate_cards" ON carrier_rate_cards
  FOR ALL USING (org_id = auth_user_org_id());

CREATE TRIGGER update_rate_cards_updated_at
  BEFORE UPDATE ON carrier_rate_cards
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- ── Carrier Invoice Audits ──────────────────────────────────
-- Result of running an uploaded carrier invoice through the
-- CarrierInvoice Auditor (Overcharge Hunter).

CREATE TABLE carrier_invoice_audits (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  shipment_id     UUID REFERENCES shipments(id),
  document_id     UUID REFERENCES documents(id),
  carrier_name    TEXT NOT NULL,
  invoice_number  TEXT,
  invoice_currency TEXT DEFAULT 'USD',
  invoice_total   NUMERIC(12,2),
  agreed_total    NUMERIC(12,2),
  variance_total  NUMERIC(12,2) GENERATED ALWAYS AS (
                    COALESCE(invoice_total,0) - COALESCE(agreed_total,0)
                  ) STORED,
  variance_zar    NUMERIC(12,2),         -- variance converted to ZAR for reporting
  line_items      JSONB NOT NULL DEFAULT '[]',  -- [{description, billed, agreed, variance, matched_rate_card_id}]
  status          TEXT NOT NULL DEFAULT 'clean'
                  CHECK (status IN ('clean','overcharge_detected','no_rate_card','review_required')),
  dispute_generated BOOLEAN NOT NULL DEFAULT FALSE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_carrier_audits_org ON carrier_invoice_audits(org_id, status);

ALTER TABLE carrier_invoice_audits ENABLE ROW LEVEL SECURITY;
CREATE POLICY "org_isolation_carrier_audits" ON carrier_invoice_audits
  FOR ALL USING (org_id = auth_user_org_id());


-- ── Driver Check-Ins (Waiting Time, no GPS) ─────────────────
-- A driver replies "ARRIVED <ref>" or "DEPARTED <ref>" on WhatsApp.
-- Two timestamps per shipment = wait duration. No GPS/Traccar needed.

CREATE TABLE driver_checkins (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  shipment_id   UUID REFERENCES shipments(id),
  reference     TEXT,                  -- shipment reference as typed by driver, e.g. "CIQ-2026-00247"
  driver_phone  TEXT NOT NULL,
  driver_name   TEXT,
  location_name TEXT,                  -- "Durban Pier 2", "City Deep", free text from driver
  event_type    TEXT NOT NULL CHECK (event_type IN ('arrived','departed')),
  raw_message   TEXT,                  -- original WhatsApp text, for audit
  event_time    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_checkins_org_ref ON driver_checkins(org_id, reference, event_time);

ALTER TABLE driver_checkins ENABLE ROW LEVEL SECURITY;
CREATE POLICY "org_isolation_driver_checkins" ON driver_checkins
  FOR ALL USING (org_id = auth_user_org_id());


-- ── Waiting Time Findings ───────────────────────────────────
-- Computed result: arrived → departed pairs that exceed free time,
-- representing unbilled accessorial revenue.

CREATE TABLE waiting_time_findings (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  shipment_id     UUID REFERENCES shipments(id),
  reference       TEXT,
  driver_phone    TEXT,
  location_name   TEXT,
  arrived_at      TIMESTAMPTZ NOT NULL,
  departed_at     TIMESTAMPTZ NOT NULL,
  total_minutes   INTEGER GENERATED ALWAYS AS (
                    EXTRACT(EPOCH FROM (departed_at - arrived_at)) / 60
                  ) STORED,
  free_minutes    INTEGER NOT NULL DEFAULT 120,   -- 2 hours free, configurable later
  billable_minutes INTEGER,
  rate_per_hour_zar NUMERIC(8,2) NOT NULL DEFAULT 350.00,
  unbilled_revenue_zar NUMERIC(12,2),
  status          TEXT NOT NULL DEFAULT 'identified'
                  CHECK (status IN ('identified','invoiced','dismissed')),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_waiting_findings_org ON waiting_time_findings(org_id, status);

ALTER TABLE waiting_time_findings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "org_isolation_waiting_findings" ON waiting_time_findings
  FOR ALL USING (org_id = auth_user_org_id());
