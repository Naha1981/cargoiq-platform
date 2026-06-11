-- ============================================================
-- CargoIQ Migration 005: Shadow Audits
-- ============================================================

CREATE TABLE shadow_audits (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id       UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  status       TEXT NOT NULL DEFAULT 'completed'
               CHECK (status IN ('running', 'completed', 'failed')),
  summary      JSONB NOT NULL DEFAULT '{}',
  findings     JSONB NOT NULL DEFAULT '[]',
  period_days  INTEGER,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

ALTER TABLE shadow_audits ENABLE ROW LEVEL SECURITY;
CREATE POLICY "org_isolation_shadow_audits" ON shadow_audits
  FOR ALL USING (org_id = auth_user_org_id());

CREATE INDEX idx_shadow_audits_org ON shadow_audits(org_id, created_at DESC);
