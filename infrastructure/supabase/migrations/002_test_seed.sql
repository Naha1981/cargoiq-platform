-- ================================================================
-- CargoIQ Test Data Seed
-- Run in Supabase SQL Editor BEFORE running Playwright tests
-- ================================================================

-- Test organisations
INSERT INTO organisations (id, name, slug, plan, monthly_limit) VALUES
  ('00000000-0000-0000-0000-000000000001', 'Demo Freight (Pty) Ltd', 'demo-freight', 'growth', 3000),
  ('00000000-0000-0000-0000-000000000002', 'G Idalene Accounting & Clearing', 'g-idalene', 'starter', 500),
  ('00000000-0000-0000-0000-000000000003', 'Afrigo Global Logistics', 'afrigo', 'enterprise', 10000)
ON CONFLICT (slug) DO NOTHING;

-- After inserting above, create auth users via Supabase Auth dashboard:
-- Go to: Authentication → Users → Add User
-- Create these users with password: TestPass1234!
--   ops@demo-freight.co.za        → org: demo-freight, role: operations_manager
--   ghameeda@gidalene.co.za       → org: g-idalene,   role: admin
--   it@afrigo.co.za               → org: afrigo,      role: admin
--   operator@demo-freight.co.za   → org: demo-freight, role: operator
--   viewer@demo-freight.co.za     → org: demo-freight, role: viewer

-- After creating auth users, insert user profiles:
-- Replace the UUIDs below with the actual IDs from auth.users
-- INSERT INTO users (id, org_id, email, full_name, role) VALUES (...)

-- Sample shipments for testing (optional — tests create via API)
INSERT INTO shipments (
  org_id, status, shield_status, overall_confidence,
  shipper_name, consignee_name, origin_port, destination_port,
  shipment_type, source, hs_code_primary, gross_weight
) VALUES
  -- Clean shipment — should auto-approve
  ('00000000-0000-0000-0000-000000000001',
   'review_required', 'pass', 'high',
   'Shenzhen Electronics Co', 'Demo Freight Imports',
   'CNSHA', 'ZADUR', 'air_import', 'manual_upload',
   '85171100', 245.5),
  -- Compliance failure — invalid HS code
  ('00000000-0000-0000-0000-000000000001',
   'review_required', 'fail', 'medium',
   'Mumbai Textiles Pvt Ltd', 'SA Fashion Imports',
   'INBOM', 'ZACPT', 'fcl_import', 'manual_upload',
   '6205', 180),
  -- SACU shipment — Namibia origin
  ('00000000-0000-0000-0000-000000000002',
   'review_required', 'pass', 'high',
   'Namibia Mining Supplies CC', 'Joburg Industrial (Pty) Ltd',
   'NAWDH', 'ZAJNB', 'road_import', 'manual_upload',
   '84749000', 1250)
ON CONFLICT DO NOTHING;
