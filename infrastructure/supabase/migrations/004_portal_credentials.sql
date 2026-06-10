-- ============================================================
-- CargoIQ Migration 004: Portal Credentials
-- ============================================================

CREATE TABLE portal_credentials (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        UUID NOT NULL REFERENCES organisations(id) ON DELETE CASCADE,
  portal        TEXT NOT NULL,      -- "sars" | "transnet" | "msc" | "maersk" etc.
  username_enc  TEXT NOT NULL,      -- AES-256 encrypted
  password_enc  TEXT NOT NULL,      -- AES-256 encrypted
  extra_enc     TEXT,               -- OTP seed / API key (encrypted)
  last_verified TIMESTAMPTZ,
  is_valid      BOOLEAN DEFAULT NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(org_id, portal)
);

ALTER TABLE portal_credentials ENABLE ROW LEVEL SECURITY;
CREATE POLICY "org_isolation_portal_creds" ON portal_credentials
  FOR ALL USING (org_id = auth_user_org_id());

CREATE TRIGGER update_portal_creds_updated_at
  BEFORE UPDATE ON portal_credentials
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();
