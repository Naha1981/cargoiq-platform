-- ============================================================
-- CargoIQ — Initial Database Schema
-- Migration: 001_initial_schema.sql
-- Run this in your Supabase SQL Editor
-- ============================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- ORGANISATIONS (tenants)
-- ============================================================
CREATE TABLE organisations (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name                  TEXT NOT NULL,
  slug                  TEXT UNIQUE NOT NULL,
  plan                  TEXT NOT NULL DEFAULT 'pilot' CHECK (plan IN ('pilot', 'starter', 'growth', 'enterprise')),
  status                TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'cancelled')),
  cw_server_url         TEXT,
  cw_credentials_enc    TEXT,  -- AES-256 encrypted CargoWise credentials
  confidence_thresholds JSONB NOT NULL DEFAULT '{
    "auto_approve": 0.90,
    "review_required": 0.75,
    "human_only": 0.0
  }',
  settings              JSONB NOT NULL DEFAULT '{}',
  shipments_this_month  INTEGER NOT NULL DEFAULT 0,
  monthly_limit         INTEGER NOT NULL DEFAULT 200,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- USERS
-- ============================================================
CREATE TABLE users (
  id           UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  org_id       UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  email        TEXT NOT NULL,
  full_name    TEXT,
  role         TEXT NOT NULL DEFAULT 'operator' CHECK (role IN ('admin', 'operations_manager', 'operator', 'viewer')),
  is_active    BOOLEAN NOT NULL DEFAULT TRUE,
  avatar_url   TEXT,
  last_login_at TIMESTAMPTZ,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- EMAIL CONNECTIONS
-- ============================================================
CREATE TABLE email_connections (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  type            TEXT NOT NULL CHECK (type IN ('gmail', 'outlook', 'imap')),
  email_address   TEXT NOT NULL,
  credentials_enc TEXT,  -- encrypted OAuth tokens or IMAP password
  status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'disconnected', 'error', 'pending')),
  last_synced_at  TIMESTAMPTZ,
  error_message   TEXT,
  created_by      UUID REFERENCES users(id),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(org_id, email_address)
);

-- ============================================================
-- INBOUND EMAILS
-- ============================================================
CREATE TABLE inbound_emails (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id         UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  connection_id  UUID REFERENCES email_connections(id),
  message_id     TEXT UNIQUE,  -- email message-id header (prevents duplicates)
  from_address   TEXT,
  from_name      TEXT,
  subject        TEXT,
  body_preview   TEXT,
  received_at    TIMESTAMPTZ,
  classification TEXT CHECK (classification IN ('freight', 'non_freight', 'unknown')),
  status         TEXT NOT NULL DEFAULT 'received' CHECK (status IN ('received', 'processing', 'processed', 'ignored', 'error')),
  raw_headers    JSONB DEFAULT '{}',
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- DOCUMENTS
-- ============================================================
CREATE TABLE documents (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id       UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  email_id     UUID REFERENCES inbound_emails(id),
  storage_path TEXT NOT NULL,  -- Supabase Storage path: org_id/documents/filename
  filename     TEXT,
  file_size    INTEGER,
  mime_type    TEXT,
  doc_type     TEXT CHECK (doc_type IN (
    'commercial_invoice', 'packing_list', 'air_waybill', 'bill_of_lading',
    'certificate_of_origin', 'customs_declaration', 'delivery_note',
    'insurance_cert', 'other', 'unknown'
  )),
  page_count   INTEGER,
  raw_text     TEXT,  -- extracted text from Marker/OCR
  status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'processed', 'failed')),
  ocr_method   TEXT,  -- 'marker', 'tesseract', 'digital_pdf'
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- SHIPMENTS (core entity)
-- ============================================================
CREATE TABLE shipments (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                   UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  reference                TEXT UNIQUE,  -- e.g. CIQ-2026-00001

  -- Core extracted fields
  shipper_name             TEXT,
  shipper_address          TEXT,
  consignee_name           TEXT,
  consignee_address        TEXT,
  notify_party             TEXT,
  origin_port              TEXT,
  origin_country           TEXT,
  destination_port         TEXT,
  destination_country      TEXT,
  cargo_description        TEXT,
  hs_code_primary          TEXT,
  gross_weight             NUMERIC(12,3),
  net_weight               NUMERIC(12,3),
  weight_unit              TEXT DEFAULT 'KGS',
  volume_cbm               NUMERIC(10,3),
  number_of_packages       INTEGER,
  incoterms                TEXT,
  invoice_number           TEXT,
  invoice_value            NUMERIC(15,2),
  currency                 TEXT DEFAULT 'USD',
  awb_or_bl_number         TEXT,
  vessel_or_flight         TEXT,
  eta                      DATE,
  etd                      DATE,
  shipment_type            TEXT CHECK (shipment_type IN (
    'air_import', 'air_export', 'fcl_import', 'fcl_export',
    'lcl_import', 'lcl_export', 'road_import', 'road_export',
    'customs_only', 'unknown'
  )),

  -- All extracted fields as flexible JSONB (100+ fields)
  extracted_fields         JSONB DEFAULT '{}',

  -- Confidence scoring
  confidence_scores        JSONB DEFAULT '{}',  -- per-field confidence
  overall_confidence       TEXT CHECK (overall_confidence IN ('high', 'medium', 'low')),
  confidence_percentage    NUMERIC(5,2),

  -- AI flags (detected during extraction, before shield)
  ai_flags                 JSONB DEFAULT '{}',  -- {sars_query: bool, description_change: bool, etc}

  -- Compliance Shield results
  shield_status            TEXT CHECK (shield_status IN ('pass', 'hold', 'fail', 'pending', 'skipped')),
  shield_results           JSONB DEFAULT '{}',  -- per-module results
  shield_run_at            TIMESTAMPTZ,

  -- Workflow status
  status                   TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
    'pending', 'extracting', 'extracted', 'shield_running',
    'review_required', 'approved', 'rejected', 'pushing_to_cw',
    'in_cargowise', 'error'
  )),
  cargowise_job_id         TEXT,
  cargowise_draft_url      TEXT,

  -- People
  reviewed_by              UUID REFERENCES users(id),
  reviewed_at              TIMESTAMPTZ,
  review_notes             TEXT,

  -- Source
  source                   TEXT CHECK (source IN ('email', 'whatsapp', 'manual_upload', 'api')),
  source_email_id          UUID REFERENCES inbound_emails(id),

  -- Timing
  processing_started_at    TIMESTAMPTZ,
  processing_completed_at  TIMESTAMPTZ,
  processing_duration_ms   INTEGER,

  created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- SHIPMENT DOCUMENTS (junction)
-- ============================================================
CREATE TABLE shipment_documents (
  shipment_id UUID NOT NULL REFERENCES shipments(id) ON DELETE CASCADE,
  document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  role        TEXT,  -- 'primary_invoice', 'packing_list', 'transport_doc', etc.
  PRIMARY KEY (shipment_id, document_id)
);

-- ============================================================
-- CARGO LINE ITEMS
-- ============================================================
CREATE TABLE cargo_line_items (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shipment_id  UUID NOT NULL REFERENCES shipments(id) ON DELETE CASCADE,
  line_number  INTEGER,
  hs_code      TEXT,
  description  TEXT,
  quantity     NUMERIC(12,3),
  unit         TEXT,
  unit_weight  NUMERIC(12,3),
  total_weight NUMERIC(12,3),
  unit_value   NUMERIC(15,4),
  total_value  NUMERIC(15,2),
  currency     TEXT,
  country_of_origin TEXT,
  confidence   TEXT CHECK (confidence IN ('high', 'medium', 'low')),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- COMPLIANCE EVENTS
-- ============================================================
CREATE TABLE compliance_events (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  shipment_id     UUID NOT NULL REFERENCES shipments(id) ON DELETE CASCADE,
  org_id          UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  module          TEXT NOT NULL CHECK (module IN (
    'invoice_pl_xref', 'hs_code_validator', 'vat_engine',
    'rla_sentinel', 'da65_detector', 'da179_calculator', 'rcg_matcher'
  )),
  result          TEXT NOT NULL CHECK (result IN ('pass', 'hold', 'fail')),
  detail          JSONB NOT NULL DEFAULT '{}',
  penalty_risk    BOOLEAN NOT NULL DEFAULT FALSE,
  resolution      TEXT,  -- suggested fix
  auto_resolved   BOOLEAN NOT NULL DEFAULT FALSE,
  resolved_by     UUID REFERENCES users(id),
  resolved_at     TIMESTAMPTZ,
  resolution_note TEXT,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- AUDIT LOG (append-only — no UPDATE/DELETE via RLS)
-- ============================================================
CREATE TABLE audit_log (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  entity_type   TEXT,
  entity_id     UUID,
  action        TEXT NOT NULL,
  actor_type    TEXT NOT NULL CHECK (actor_type IN ('ai_system', 'user', 'system')),
  actor_id      UUID,
  before_state  JSONB,
  after_state   JSONB,
  metadata      JSONB DEFAULT '{}',
  ip_address    INET,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- CARGOWISE EXECUTIONS
-- ============================================================
CREATE TABLE cw_executions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  shipment_id     UUID NOT NULL REFERENCES shipments(id) ON DELETE CASCADE,
  execution_type  TEXT NOT NULL CHECK (execution_type IN ('playwright', 'eadaptor_xml')),
  status          TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'success', 'failed', 'cancelled')),
  xml_payload     TEXT,
  screenshot_path TEXT,
  cw_response     JSONB,
  duration_ms     INTEGER,
  attempt_number  INTEGER NOT NULL DEFAULT 1,
  error_message   TEXT,
  started_at      TIMESTAMPTZ,
  completed_at    TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- WISELAYER: RLA STATUS RECORDS
-- ============================================================
CREATE TABLE rla_statuses (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  importer_code    TEXT NOT NULL,
  importer_name    TEXT,
  rla_status       TEXT NOT NULL DEFAULT 'unverified' CHECK (rla_status IN ('active', 'suspended', 'inactive', 'unverified')),
  last_checked_at  TIMESTAMPTZ,
  suspended_since  TIMESTAMPTZ,
  alert_sent       BOOLEAN NOT NULL DEFAULT FALSE,
  alert_sent_at    TIMESTAMPTZ,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(org_id, importer_code)
);

-- ============================================================
-- WISELAYER: TRANSACTION COMPACTION LOG
-- ============================================================
CREATE TABLE wisetech_transactions (
  id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                 UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  date                   DATE NOT NULL,
  original_count         INTEGER NOT NULL DEFAULT 0,
  compacted_count        INTEGER NOT NULL DEFAULT 0,
  saved_count            INTEGER GENERATED ALWAYS AS (original_count - compacted_count) STORED,
  estimated_saving_usd   NUMERIC(10,2),
  estimated_saving_zar   NUMERIC(10,2),
  created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(org_id, date)
);

-- ============================================================
-- AUTO-GENERATE SHIPMENT REFERENCES
-- ============================================================
CREATE SEQUENCE shipment_reference_seq START 1;

CREATE OR REPLACE FUNCTION generate_shipment_reference()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.reference IS NULL THEN
    NEW.reference := 'CIQ-' || TO_CHAR(NOW(), 'YYYY') || '-' || LPAD(nextval('shipment_reference_seq')::TEXT, 5, '0');
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_shipment_reference
  BEFORE INSERT ON shipments
  FOR EACH ROW EXECUTE FUNCTION generate_shipment_reference();

-- ============================================================
-- AUTO-UPDATE updated_at TIMESTAMPS
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_organisations_updated_at BEFORE UPDATE ON organisations FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_email_connections_updated_at BEFORE UPDATE ON email_connections FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_shipments_updated_at BEFORE UPDATE ON shipments FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER update_rla_statuses_updated_at BEFORE UPDATE ON rla_statuses FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- INDEXES (performance)
-- ============================================================
CREATE INDEX idx_shipments_org_id ON shipments(org_id);
CREATE INDEX idx_shipments_status ON shipments(status);
CREATE INDEX idx_shipments_created_at ON shipments(created_at DESC);
CREATE INDEX idx_shipments_org_status ON shipments(org_id, status);
CREATE INDEX idx_documents_org_id ON documents(org_id);
CREATE INDEX idx_documents_shipment ON shipment_documents(shipment_id);
CREATE INDEX idx_compliance_events_shipment ON compliance_events(shipment_id);
CREATE INDEX idx_audit_log_org_entity ON audit_log(org_id, entity_type, entity_id);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at DESC);
CREATE INDEX idx_inbound_emails_org ON inbound_emails(org_id);

-- ============================================================
-- ROW LEVEL SECURITY
-- ============================================================
ALTER TABLE organisations     ENABLE ROW LEVEL SECURITY;
ALTER TABLE users             ENABLE ROW LEVEL SECURITY;
ALTER TABLE email_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE inbound_emails    ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents         ENABLE ROW LEVEL SECURITY;
ALTER TABLE shipments         ENABLE ROW LEVEL SECURITY;
ALTER TABLE shipment_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE cargo_line_items  ENABLE ROW LEVEL SECURITY;
ALTER TABLE compliance_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_log         ENABLE ROW LEVEL SECURITY;
ALTER TABLE cw_executions     ENABLE ROW LEVEL SECURITY;
ALTER TABLE rla_statuses      ENABLE ROW LEVEL SECURITY;
ALTER TABLE wisetech_transactions ENABLE ROW LEVEL SECURITY;

-- Helper function: get current user's org_id
CREATE OR REPLACE FUNCTION auth_user_org_id()
RETURNS UUID AS $$
  SELECT org_id FROM users WHERE id = auth.uid()
$$ LANGUAGE SQL SECURITY DEFINER STABLE;

-- RLS Policies
CREATE POLICY "org_isolation_organisations" ON organisations
  FOR ALL USING (id = auth_user_org_id());

CREATE POLICY "org_isolation_users" ON users
  FOR ALL USING (org_id = auth_user_org_id());

CREATE POLICY "org_isolation_email_connections" ON email_connections
  FOR ALL USING (org_id = auth_user_org_id());

CREATE POLICY "org_isolation_inbound_emails" ON inbound_emails
  FOR ALL USING (org_id = auth_user_org_id());

CREATE POLICY "org_isolation_documents" ON documents
  FOR ALL USING (org_id = auth_user_org_id());

CREATE POLICY "org_isolation_shipments" ON shipments
  FOR ALL USING (org_id = auth_user_org_id());

CREATE POLICY "org_isolation_shipment_documents" ON shipment_documents
  FOR ALL USING (
    shipment_id IN (SELECT id FROM shipments WHERE org_id = auth_user_org_id())
  );

CREATE POLICY "org_isolation_cargo_line_items" ON cargo_line_items
  FOR ALL USING (
    shipment_id IN (SELECT id FROM shipments WHERE org_id = auth_user_org_id())
  );

CREATE POLICY "org_isolation_compliance_events" ON compliance_events
  FOR ALL USING (org_id = auth_user_org_id());

-- Audit log: read-only for users, no delete
CREATE POLICY "org_isolation_audit_log_read" ON audit_log
  FOR SELECT USING (org_id = auth_user_org_id());

CREATE POLICY "org_isolation_audit_log_insert" ON audit_log
  FOR INSERT WITH CHECK (org_id = auth_user_org_id());

CREATE POLICY "org_isolation_cw_executions" ON cw_executions
  FOR ALL USING (org_id = auth_user_org_id());

CREATE POLICY "org_isolation_rla_statuses" ON rla_statuses
  FOR ALL USING (org_id = auth_user_org_id());

CREATE POLICY "org_isolation_wisetech_transactions" ON wisetech_transactions
  FOR ALL USING (org_id = auth_user_org_id());

-- ============================================================
-- SEED: Demo organisation for development
-- ============================================================
-- NOTE: Run this only in development. Comment out for production.
-- INSERT INTO organisations (id, name, slug, plan, monthly_limit)
-- VALUES ('00000000-0000-0000-0000-000000000001', 'Demo Freight Co', 'demo-freight', 'growth', 3000);
