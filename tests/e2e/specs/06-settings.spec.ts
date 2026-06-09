/**
 * SPEC 06 — Settings
 * Tests: CargoWise config, email connection, WiseLayer setup
 * Persona: IT Director / Admin (configures the system once)
 */
import { test, expect } from "@playwright/test";
import { AuthPage }     from "../pages/AuthPage";
import { USERS }        from "../fixtures/test-data";

test.describe("Settings", () => {

  test.beforeEach(async ({ page }) => {
    await new AuthPage(page).login(USERS.itDirector.email, USERS.itDirector.password);
  });

  test("Settings page loads with all tab sections", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");
    for (const tab of ["General","Email Connection","CargoWise","WiseLayer","Security"]) {
      await expect(page.locator(`text=${tab}`).first()).toBeVisible();
    }
  });

  test("General tab: confidence threshold selector works", async ({ page }) => {
    await page.goto("/settings");
    await page.click('button:has-text("General")');
    await expect(page.locator("text=Auto-Approve Threshold")).toBeVisible();
    // Select a different threshold
    await page.selectOption("select", { label: "80% — Medium-high confidence" });
    await page.click('button:has-text("Save Changes")');
    await expect(page.locator("text=Settings saved")).toBeVisible({ timeout: 5000 });
  });

  test("CargoWise tab: server URL input accepts value", async ({ page }) => {
    await page.goto("/settings");
    await page.click('button:has-text("CargoWise")');
    const urlInput = page.locator('input[placeholder*="cargowise"]');
    await expect(urlInput).toBeVisible();
    await urlInput.fill("https://mycompany.cargowise.com");
    await expect(urlInput).toHaveValue("https://mycompany.cargowise.com");
  });

  test("CargoWise tab: test connection button fires", async ({ page }) => {
    await page.goto("/settings");
    await page.click('button:has-text("CargoWise")');
    await page.fill('input[placeholder*="cargowise"]', "https://test.cargowise.com");
    await page.click('button:has-text("Test Connection")');
    // Shows testing state or result
    await expect(page.locator("text=Testing, text=verified, text=failed")).toBeVisible({ timeout: 8000 });
  });

  test("Email tab: Gmail connect button present", async ({ page }) => {
    await page.goto("/settings");
    await page.click('button:has-text("Email Connection")');
    await expect(page.locator("text=Gmail / Google Workspace")).toBeVisible();
    await expect(page.locator('button:has-text("Connect Gmail")')).toBeVisible();
  });

  test("WiseLayer tab: eFiling credentials form present", async ({ page }) => {
    await page.goto("/settings");
    await page.click('button:has-text("WiseLayer")');
    await expect(page.locator("text=eFiling Username")).toBeVisible();
    await expect(page.locator("text=RLA Sentinel")).toBeVisible();
    await expect(page.locator("text=R2,000")).toBeVisible(); // storage cost warning
  });

  test("Security tab: change password form renders", async ({ page }) => {
    await page.goto("/settings");
    await page.click('button:has-text("Security")');
    await expect(page.locator('input[placeholder*="Current password"]')).toBeVisible();
    await expect(page.locator('button:has-text("Update Password")')).toBeVisible();
    await expect(page.locator("text=POPIA, text=South Africa")).toBeVisible();
  });

});
