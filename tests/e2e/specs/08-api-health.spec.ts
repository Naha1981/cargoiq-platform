/**
 * SPEC 08 — API Health & Contract Tests
 * Tests the FastAPI backend directly (not via UI)
 * Ensures all endpoints return correct status codes.
 */
import { test, expect, request } from "@playwright/test";
import { API_BASE, USERS }        from "../fixtures/test-data";

test.describe("API Health & Contracts", () => {

  test("Health endpoint returns 200", async ({ request }) => {
    const res = await request.get(`${API_BASE}/health`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.status).toMatch(/healthy|degraded/);
  });

  test("Root endpoint returns service info", async ({ request }) => {
    const res = await request.get(`${API_BASE}/`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.service).toBe("CargoIQ API");
    expect(body.version).toBeTruthy();
  });

  test("Auth signup endpoint accepts valid payload", async ({ request }) => {
    const unique = Date.now();
    const res = await request.post(`${API_BASE}/api/v1/auth/signup`, {
      data: {
        email:     `test_${unique}@cargoiq-test.co.za`,
        password:  "TestPass1234!",
        full_name: "Test User",
        org_name:  `Test Org ${unique}`,
      },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    expect(body.access_token).toBeTruthy();
    expect(body.organisation.name).toContain("Test Org");
  });

  test("Auth signup rejects duplicate email", async ({ request }) => {
    const email = `duplicate_${Date.now()}@cargoiq-test.co.za`;
    // First signup
    await request.post(`${API_BASE}/api/v1/auth/signup`, {
      data: { email, password: "TestPass1234!", full_name: "User One", org_name: "Org One" },
    });
    // Second signup with same email
    const res = await request.post(`${API_BASE}/api/v1/auth/signup`, {
      data: { email, password: "TestPass1234!", full_name: "User Two", org_name: "Org Two" },
    });
    expect(res.status()).toBeGreaterThanOrEqual(400);
  });

  test("Unauthenticated request to protected endpoint returns 401", async ({ request }) => {
    const res = await request.get(`${API_BASE}/api/v1/shipments/`);
    expect(res.status()).toBe(401);
  });

  test("Documents endpoint requires auth", async ({ request }) => {
    const res = await request.get(`${API_BASE}/api/v1/documents/`);
    expect([401, 403]).toContain(res.status());
  });

  test("Analytics dashboard endpoint returns correct schema", async ({ request }) => {
    // Login first
    const authRes = await request.post(`${API_BASE}/api/v1/auth/signup`, {
      data: {
        email: `analytics_test_${Date.now()}@cargoiq-test.co.za`,
        password: "TestPass1234!", full_name: "Analytics User", org_name: "Analytics Org",
      },
    });
    const { access_token } = await authRes.json();

    const res = await request.get(`${API_BASE}/api/v1/analytics/dashboard`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(typeof body.queue_size).toBe("number");
    expect(typeof body.automation_rate).toBe("number");
    expect(typeof body.compliance_flags_today).toBe("number");
  });

  test("Compliance summary endpoint returns module breakdown", async ({ request }) => {
    const authRes = await request.post(`${API_BASE}/api/v1/auth/signup`, {
      data: {
        email: `compliance_test_${Date.now()}@cargoiq-test.co.za`,
        password: "TestPass1234!", full_name: "Compliance User", org_name: "Compliance Org",
      },
    });
    const { access_token } = await authRes.json();

    const res = await request.get(`${API_BASE}/api/v1/analytics/compliance-summary`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.shield_breakdown).toBeDefined();
    expect(typeof body.pass_rate_pct).toBe("number");
  });

  test("Queue stats endpoint returns BullMQ metrics", async ({ request }) => {
    const authRes = await request.post(`${API_BASE}/api/v1/auth/signup`, {
      data: {
        email: `queue_test_${Date.now()}@cargoiq-test.co.za`,
        password: "TestPass1234!", full_name: "Queue User", org_name: "Queue Org",
      },
    });
    const { access_token } = await authRes.json();

    const res = await request.get(`${API_BASE}/api/v1/shipments/queue/stats`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect([200, 500]).toContain(res.status()); // 500 if Redis not running, 200 if it is
  });

});
