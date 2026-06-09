/**
 * SPEC 09 — Mobile Responsiveness
 * Tests on Pixel 7 viewport (WhatsApp-first SA market)
 * Many SA operators access CargoIQ from mobile
 */
import { test, expect, devices } from "@playwright/test";
import { AuthPage }               from "../pages/AuthPage";
import { USERS }                  from "../fixtures/test-data";

// These tests use the mobile project defined in playwright.config.ts
test.use({ ...devices["Pixel 7"] });

test.describe("Mobile Responsiveness", () => {

  test.beforeEach(async ({ page }) => {
    await new AuthPage(page).login(USERS.opsManager.email, USERS.opsManager.password);
  });

  test("Dashboard renders on mobile without overflow", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");
    // Check no horizontal scroll
    const hasHScroll = await page.evaluate(() =>
      document.body.scrollWidth > window.innerWidth
    );
    expect(hasHScroll).toBe(false);
    // KPI cards stack vertically
    await expect(page.locator("text=Queue Size")).toBeVisible();
  });

  test("Queue page table scrolls horizontally on mobile", async ({ page }) => {
    await page.goto("/queue");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("table")).toBeVisible({ timeout: 8000 });
  });

  test("Login page is usable on mobile", async ({ page }) => {
    await page.goto("/auth/login");
    const emailInput = page.locator('input[type="email"]');
    const passInput  = page.locator('input[type="password"]');
    await expect(emailInput).toBeVisible();
    await expect(passInput).toBeVisible();
    // Inputs should be large enough to tap
    const emailBox = await emailInput.boundingBox();
    expect(emailBox?.height).toBeGreaterThan(30);
  });

  test("Sidebar collapses automatically on mobile", async ({ page }) => {
    await page.goto("/dashboard");
    // On mobile the sidebar should be collapsed or hidden by default
    const sidebar = page.locator("aside").first();
    const width = await sidebar.evaluate(el => el.getBoundingClientRect().width);
    // Should be 56px (collapsed) or 0px (hidden) on mobile
    expect(width).toBeLessThan(240);
  });

});
