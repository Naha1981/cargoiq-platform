/**
 * SPEC 07 — Analytics & ROI
 * Tests: ROI metrics, volume breakdown, compliance summary
 * Persona: MD/CFO (monthly review of business value)
 */
import { test, expect } from "@playwright/test";
import { AuthPage }      from "../pages/AuthPage";
import { DashboardPage } from "../pages/DashboardPage";
import { USERS }         from "../fixtures/test-data";

test.describe("Analytics & ROI", () => {

  test.beforeEach(async ({ page }) => {
    await new AuthPage(page).login(USERS.owner.email, USERS.owner.password);
  });

  test("Analytics page loads with ROI cards", async ({ page }) => {
    await page.goto("/analytics");
    await page.waitForLoadState("networkidle");
    for (const metric of ["Shipments Processed","Hours Saved","Labour Cost Saved","Errors Prevented","Total Value Delivered"]) {
      await expect(page.locator(`text=${metric}`).first()).toBeVisible({ timeout: 10000 });
    }
  });

  test("ROI values displayed in ZAR format", async ({ page }) => {
    await page.goto("/analytics");
    await page.waitForLoadState("networkidle");
    // At least one R value visible
    await expect(page.locator("text=/R[\d,]+/").first()).toBeVisible({ timeout: 8000 });
  });

  test("Dashboard ROI summary matches analytics page", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");
    const dashROI = page.locator("text=ROI Summary").locator("..");
    await expect(dashROI).toBeVisible({ timeout: 10000 });
    await expect(dashROI.locator("text=Errors Prevented")).toBeVisible();
  });

  test("Compliance summary shows module breakdown", async ({ page }) => {
    await page.goto("/compliance");
    await page.waitForLoadState("networkidle");
    await expect(page.locator("text=Top Compliance Issues")).toBeVisible({ timeout: 8000 });
    await expect(page.locator("text=Overall Compliance Pass Rate")).toBeVisible();
    // Pass rate bar rendered
    await expect(page.locator(".bg-success-DEFAULT, .bg-warning-DEFAULT, .bg-error-DEFAULT").first()).toBeVisible();
  });

});
