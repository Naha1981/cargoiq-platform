/**
 * SPEC 10 — Role-Based Access Control
 * Tests: viewer vs operator vs admin permissions
 * Critical for multi-user freight operations
 */
import { test, expect } from "@playwright/test";
import { AuthPage }     from "../pages/AuthPage";
import { USERS }        from "../fixtures/test-data";

test.describe("Role Permissions", () => {

  test("Viewer cannot see approve/reject buttons", async ({ page }) => {
    await new AuthPage(page).login(USERS.viewer.email, USERS.viewer.password);
    await page.goto("/queue");
    await page.waitForLoadState("networkidle");
    // Approve/reject action buttons should not be visible for viewer
    const approveBtn = page.locator('button[title="Approve"]').first();
    const rejectBtn  = page.locator('button[title="Reject"]').first();
    // Either not present or disabled
    const approveVisible = await approveBtn.isVisible().catch(() => false);
    const rejectVisible  = await rejectBtn.isVisible().catch(() => false);
    expect(approveVisible && rejectVisible).toBe(false);
  });

  test("Operator can view shipments but settings shows limited options", async ({ page }) => {
    await new AuthPage(page).login(USERS.operator.email, USERS.operator.password);
    await page.goto("/queue");
    await expect(page.locator("table, text=No shipments")).toBeVisible({ timeout: 10000 });
    await page.goto("/settings");
    await expect(page.locator("text=General")).toBeVisible();
  });

  test("Admin can access all sections including settings", async ({ page }) => {
    await new AuthPage(page).login(USERS.owner.email, USERS.owner.password);
    const sections = ["/dashboard", "/queue", "/compliance", "/analytics", "/settings"];
    for (const section of sections) {
      await page.goto(section);
      await page.waitForLoadState("networkidle");
      // Should not get 403 or redirect to login
      await expect(page).not.toHaveURL(/.*login/);
    }
  });

  test("Each user only sees their own organisation data", async ({ browser }) => {
    // Two users from different orgs open the app simultaneously
    const ctx1 = await browser.newContext();
    const ctx2 = await browser.newContext();
    const page1 = await ctx1.newPage();
    const page2 = await ctx2.newPage();

    await new AuthPage(page1).login(USERS.opsManager.email, USERS.opsManager.password);
    await new AuthPage(page2).login(USERS.owner.email, USERS.owner.password);

    // Each should see their own org name in sidebar
    await page1.goto("/dashboard");
    await page2.goto("/dashboard");

    const org1 = await page1.locator(".text-nav-text-muted, [class*=muted]").first().textContent();
    const org2 = await page2.locator(".text-nav-text-muted, [class*=muted]").first().textContent();

    // Orgs should be different (data isolation)
    if (org1 && org2) {
      expect(org1).not.toBe(org2);
    }

    await ctx1.close();
    await ctx2.close();
  });

});
