-- ============================================================
-- CargoIQ Migration 010: Security Audit Fixes
-- ============================================================
-- Found during a full-platform RLS audit: two tables created in
-- migrations 008/009 were missing Row Level Security. Both are
-- low-risk (all application access goes through the service-role
-- admin client, which bypasses RLS entirely) but RLS should be
-- enabled on every table as defense-in-depth, in case a future
-- feature ever exposes these via the anon/authenticated key
-- directly (e.g. a Supabase client-side query).

-- ── invoice_sequences ────────────────────────────────────────
-- Has org_id as primary key — needs standard tenant isolation,
-- same pattern as every other org-scoped table.

ALTER TABLE invoice_sequences ENABLE ROW LEVEL SECURITY;

CREATE POLICY "org_isolation_invoice_sequences" ON invoice_sequences
  FOR ALL USING (org_id = auth_user_org_id());


-- ── diesel_price_history ─────────────────────────────────────
-- This table has NO org_id — it's global reference data (public
-- DMPR fuel prices), not tenant-specific. RLS is enabled with a
-- read-only policy for any authenticated user; writes remain
-- restricted to the service-role client (the scheduler reminder
-- + manual SQL Editor inserts), since no INSERT/UPDATE policy
-- is granted to authenticated/anon roles.

ALTER TABLE diesel_price_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "authenticated_read_diesel_prices" ON diesel_price_history
  FOR SELECT
  USING (auth.role() = 'authenticated');
