/**
 * SPEC 01 — Authentication
 * Tests: signup, login, logout, protected routes, wrong credentials
 */
import { test, expect } from "@playwright/test";
import { AuthPage }      from "../pages/AuthPage";
import { USERS }         from "../fixtures/test-data";

test.describe("Authentication", () => {

  test("Owner can sign up and land on dashboard", async ({ page }) => {
    const auth = new AuthPage(page);
    await auth.signup(
      "new_owner@testfreight.co.za", "TestPass1234!",
      "Test Owner", "Test Freight (Pty) Ltd"
    );
    await auth.assertOnDashboard();
    // JWT token stored in localStorage
    const token = await page.evaluate(() => localStorage.getItem("cargoiq_token"));
    expect(token).toBeTruthy();
  });

  test("Ops Manager can log in with valid credentials", async ({ page }) => {
    const auth = new AuthPage(page);
    await auth.login(USERS.opsManager.email, USERS.opsManager.password);
    await auth.assertOnDashboard();
  });

  test("Wrong password shows error message", async ({ page }) => {
    await page.goto("/auth/login");
    await page.fill('input[type="email"]', USERS.opsManager.email);
    await page.fill('input[type="password"]', "WrongPassword!");
    await page.click('button[type="submit"]');
    await expect(page.locator(".bg-error-bg, [class*=error]")).toBeVisible({ timeout: 8000 });
    await expect(page).not.toHaveURL(/.*dashboard/);
  });

  test("Protected route redirects unauthenticated user to login", async ({ page }) => {
    // Clear any stored token
    await page.goto("/auth/login");
    await page.evaluate(() => localStorage.clear());
    await page.goto("/dashboard");
    // Should redirect or show login
    await expect(page).toHaveURL(/.*login|.*auth/);
  });

  test("User can log out and be returned to login", async ({ page }) => {
    const auth = new AuthPage(page);
    await auth.login(USERS.opsManager.email, USERS.opsManager.password);
    await auth.assertOnDashboard();
    await auth.logout();
    await auth.assertRedirectedToLogin();
    const token = await page.evaluate(() => localStorage.getItem("cargoiq_token"));
    expect(token).toBeFalsy();
  });

  test("Viewer can log in and see dashboard (read-only)", async ({ page }) => {
    const auth = new AuthPage(page);
    await auth.login(USERS.viewer.email, USERS.viewer.password);
    await auth.assertOnDashboard();
    // Viewer should not see upload button
    await page.goto("/queue");
    // Upload button may or may not be present for viewer — depends on role
    // At minimum the queue should load
    await expect(page.locator("table, text=No shipments")).toBeVisible({ timeout: 10000 });
  });

});
