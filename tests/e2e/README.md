# CargoIQ E2E Test Suite

Playwright tests covering all user roles and critical workflows.

## Quick Start

```bash
cd tests/e2e
npm install
npx playwright install chromium

# Run all tests (requires running app)
npm test

# Smoke tests only (fast — 3 specs)
npm run test:smoke

# API contract tests only (no browser needed)
npm run test:api

# Run with visible browser
npm run test:headed

# Debug a specific test
npm run test:debug
```

## Test Coverage

| Spec | What it tests | Persona |
|---|---|---|
| 01-auth | Signup, login, logout, protected routes | All users |
| 02-dashboard | KPI cards, charts, navigation | Ops Manager |
| 03-document-upload | File upload, validation, processing | Operator |
| 04-compliance-shield | All 6 modules, penalty alerts | Owner/MD |
| 05-shipment-workflow | Approve, reject, audit trail | Ops Manager |
| 06-settings | CargoWise config, email, WiseLayer | IT Director |
| 07-analytics-roi | ROI metrics, ZAR values | MD/CFO |
| 08-api-health | All API endpoints, auth contracts | CI/CD |
| 09-mobile | Responsive layout, mobile usability | Operator |
| 10-role-permissions | Viewer/operator/admin access | All roles |

## Test Users (seed in Supabase before running)

| User | Email | Role | Use case |
|---|---|---|---|
| Owner | ghameeda@gidalene.co.za | admin | Personal liability, compliance focus |
| Ops Manager | ops@demo-freight.co.za | operations_manager | Daily approvals |
| IT Director | it@afrigo.co.za | admin | CW config, WiseLayer |
| Operator | operator@demo-freight.co.za | operator | Document upload |
| Viewer | viewer@demo-freight.co.za | viewer | Read-only access |

## Seed Test Users

Run this SQL in your Supabase SQL Editor before testing:

```sql
-- Insert test organisation
INSERT INTO organisations (id, name, slug, plan)
VALUES
  ('00000000-0000-0000-0000-000000000001', 'Demo Freight (Pty) Ltd', 'demo-freight', 'growth'),
  ('00000000-0000-0000-0000-000000000002', 'G Idalene Accounting & Clearing', 'g-idalene', 'starter'),
  ('00000000-0000-0000-0000-000000000003', 'Afrigo Global Logistics', 'afrigo', 'enterprise')
ON CONFLICT (slug) DO NOTHING;
-- Then create auth users via Supabase Auth dashboard or signup API
-- Use the emails and password: TestPass1234!
```

## CI/CD Integration

Tests run automatically on every push to main via GitHub Actions.
See `.github/workflows/ci.yml` for the full pipeline.

## Environment Variables

```
BASE_URL=http://localhost:3000     # Web app URL
API_URL=http://localhost:8000      # API URL
```
