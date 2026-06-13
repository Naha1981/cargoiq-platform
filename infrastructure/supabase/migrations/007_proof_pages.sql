-- ============================================================
-- CargoIQ Migration 007: Shareable Proof Pages
-- ============================================================
-- Lets a founder generate a no-login link to a redacted summary
-- of a prospect's own shadow audit — "text Karel-Jan a link
-- before the call instead of describing it."

ALTER TABLE shadow_audits
  ADD COLUMN share_token   TEXT UNIQUE,
  ADD COLUMN share_enabled BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX idx_shadow_audits_share_token ON shadow_audits(share_token)
  WHERE share_token IS NOT NULL;

-- Note: the public proof-page endpoint reads via the service-role
-- client (bypasses RLS) and only returns rows where share_enabled
-- = true and the token matches exactly — RLS on this table is
-- otherwise unchanged and still protects normal authenticated reads.
