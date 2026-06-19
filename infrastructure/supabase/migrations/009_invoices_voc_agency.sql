-- ============================================================
-- CargoIQ Migration 009: Invoice Generator + VOC Tracker
-- ============================================================

-- ── Sequential invoice numbering ────────────────────────────
-- One sequence per organisation, resets never (avoids gaps
-- that would concern SARS on a VAT audit).

CREATE TABLE IF NOT EXISTS invoice_sequences (
  org_id      UUID PRIMARY KEY REFERENCES organisations(id) ON DELETE CASCADE,
  last_number INTEGER NOT NULL DEFAULT 0
);


-- ── Invoices ─────────────────────────────────────────────────
-- Covers: waiting-time charge notices, carrier dispute invoices,
-- and any future billable CargoIQ finding. Single table, typed
-- by invoice_type.

CREATE TABLE IF NOT EXISTS invoices (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  invoice_number  TEXT NOT NULL,           -- e.g. "CIQ-INV-2026-0042"
  invoice_type    TEXT NOT NULL DEFAULT 'waiting_time'
                  CHECK (invoice_type IN (
                    'waiting_time', 'carrier_dispute',
                    'demurrage_recovery', 'other'
                  )),
  shipment_id     UUID REFERENCES shipments(id),
  finding_id      UUID,                    -- waiting_time_findings.id or carrier_invoice_audits.id
  client_name     TEXT NOT NULL,           -- Billed to (importer / shipper)
  client_address  TEXT,
  vat_number      TEXT,                    -- Client VAT number if registered
  line_items      JSONB NOT NULL DEFAULT '[]',
  -- [{description, quantity, unit_price_zar, total_zar}]
  subtotal_zar    NUMERIC(12,2) NOT NULL,
  vat_rate        NUMERIC(5,4) NOT NULL DEFAULT 0.15,
  vat_zar         NUMERIC(12,2) GENERATED ALWAYS AS (
                    ROUND(subtotal_zar * vat_rate, 2)
                  ) STORED,
  total_zar       NUMERIC(12,2) GENERATED ALWAYS AS (
                    ROUND(subtotal_zar * (1 + vat_rate), 2)
                  ) STORED,
  status          TEXT NOT NULL DEFAULT 'draft'
                  CHECK (status IN ('draft','sent','paid','cancelled')),
  due_date        DATE,
  bank_account    TEXT,                    -- org's bank details (encrypted optional)
  notes           TEXT,
  sent_at         TIMESTAMPTZ,
  paid_at         TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(org_id, invoice_number)
);

CREATE INDEX idx_invoices_org    ON invoices(org_id, status);
CREATE INDEX idx_invoices_client ON invoices(org_id, client_name);

ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
CREATE POLICY "org_isolation_invoices" ON invoices
  FOR ALL USING (org_id = auth_user_org_id());

CREATE TRIGGER update_invoices_updated_at
  BEFORE UPDATE ON invoices
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- ── VOC (Voucher of Correction) Tracker ─────────────────────
-- SARS issues a VOC when a customs declaration needs to be
-- amended after acceptance. The agent must pay additional duty
-- within a deadline. Untracked VOCs = silent liability growth.

CREATE TABLE IF NOT EXISTS vouchers_of_correction (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  shipment_id           UUID REFERENCES shipments(id),
  voc_reference         TEXT NOT NULL,        -- SARS VOC reference number
  mrn                   TEXT,                  -- Master Reference Number of the original declaration
  customs_value_original  NUMERIC(14,2),       -- Original declared value
  customs_value_corrected NUMERIC(14,2),       -- SARS-corrected value
  duty_original_zar     NUMERIC(12,2),
  duty_corrected_zar    NUMERIC(12,2),
  duty_difference_zar   NUMERIC(12,2) GENERATED ALWAYS AS (
                          COALESCE(duty_corrected_zar, 0) - COALESCE(duty_original_zar, 0)
                        ) STORED,
  vat_difference_zar    NUMERIC(12,2),
  total_liability_zar   NUMERIC(12,2) GENERATED ALWAYS AS (
                          COALESCE(duty_corrected_zar, 0) - COALESCE(duty_original_zar, 0) +
                          COALESCE(vat_difference_zar, 0)
                        ) STORED,
  reason_code           TEXT,                  -- SARS reason code for amendment
  reason_description    TEXT,
  status                TEXT NOT NULL DEFAULT 'outstanding'
                        CHECK (status IN (
                          'outstanding', 'paid', 'disputed', 'written_off'
                        )),
  payment_deadline      DATE,
  paid_at               TIMESTAMPTZ,
  agent_liable          BOOLEAN NOT NULL DEFAULT FALSE,
  -- True if agent may be personally liable (Section 99(2))
  notes                 TEXT,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_voc_org_status ON vouchers_of_correction(org_id, status);
CREATE INDEX idx_voc_deadline   ON vouchers_of_correction(payment_deadline)
  WHERE status = 'outstanding';

ALTER TABLE vouchers_of_correction ENABLE ROW LEVEL SECURITY;
CREATE POLICY "org_isolation_voc" ON vouchers_of_correction
  FOR ALL USING (org_id = auth_user_org_id());

CREATE TRIGGER update_voc_updated_at
  BEFORE UPDATE ON vouchers_of_correction
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();


-- ── Agency Mode: importer client on shipments ───────────────
-- Lets a clearing agent (like G Idalene) filter their shipment
-- queue by the specific importer client the shipment belongs to.
-- Separate from consignee_name — this is the agent's client name.

ALTER TABLE shipments
  ADD COLUMN IF NOT EXISTS importer_client_name TEXT,
  ADD COLUMN IF NOT EXISTS tms_declaration_number TEXT;

CREATE INDEX IF NOT EXISTS idx_shipments_importer_client
  ON shipments(org_id, importer_client_name)
  WHERE importer_client_name IS NOT NULL;
