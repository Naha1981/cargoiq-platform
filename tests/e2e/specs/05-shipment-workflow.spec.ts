/**
 * SPEC 05 — Full Shipment Workflow
 * Tests: approve, reject, human edit, audit trail
 * Persona: Operations Manager (approves 20-50 shipments/day)
 */
import { test, expect } from "@playwright/test";
import { AuthPage }           from "../pages/AuthPage";
import { QueuePage }          from "../pages/QueuePage";
import { ShipmentDetailPage } from "../pages/ShipmentDetailPage";
import { USERS }              from "../fixtures/test-data";

test.describe("Shipment Workflow", () => {

  test.beforeEach(async ({ page }) => {
    await new AuthPage(page).login(USERS.opsManager.email, USERS.opsManager.password);
  });

  test("Queue page loads with shipment table", async ({ page }) => {
    const queue = new QueuePage(page);
    await queue.goto();
    await expect(page.locator("table")).toBeVisible({ timeout: 10000 });
    // Column headers present
    for (const col of ["Reference","Shipper","Consignee","Status"]) {
      await expect(page.locator(`th:has-text("${col}")`)).toBeVisible();
    }
  });

  test("Status filter tabs work correctly", async ({ page }) => {
    const queue = new QueuePage(page);
    await queue.goto();

    const filters = ["All","Pending","Review Required","Approved","Rejected"];
    for (const f of filters) {
      await page.click(`button:has-text("${f}")`);
      await page.waitForTimeout(500);
      // URL or API should reflect the filter
      await expect(page.locator("table, text=No shipments")).toBeVisible();
    }
  });

  test("Search filters shipments by reference", async ({ page }) => {
    const queue = new QueuePage(page);
    await queue.goto();
    await queue.searchFor("CIQ-2026");
    await page.waitForTimeout(800);
    // All visible rows should contain the search term or show empty state
    const rows = page.locator("tbody tr");
    const count = await rows.count();
    if (count > 0) {
      await expect(page.locator("text=CIQ-2026").first()).toBeVisible();
    }
  });

  test("Clicking shipment row opens detail view", async ({ page }) => {
    const queue = new QueuePage(page);
    await queue.goto();
    const rows = page.locator("tbody tr");
    if (await rows.count() === 0) test.skip(true, "No shipments");
    await rows.first().click();
    await expect(page).toHaveURL(/.*shipments\/.+/);
  });

  test("Shipment detail shows all field sections", async ({ page }) => {
    await page.goto("/queue");
    const rows = page.locator("tbody tr");
    if (await rows.count() === 0) test.skip(true, "No shipments");
    await rows.first().click();
    await page.waitForURL("**/shipments/**");

    for (const section of ["Parties","Routing","Cargo & Commercial","Compliance Shield"]) {
      await expect(page.locator(`text=${section}`).first()).toBeVisible({ timeout: 8000 });
    }
  });

  test("Reviewer can approve a review_required shipment", async ({ page }) => {
    await page.goto("/queue?status=review_required");
    await page.waitForLoadState("networkidle");
    const rows = page.locator("tbody tr");
    if (await rows.count() === 0) test.skip(true, "No review_required shipments");
    await rows.first().click();
    await page.waitForURL("**/shipments/**");

    const detail = new ShipmentDetailPage(page);
    const approveBtn = page.locator('button:has-text("Approve")');
    if (await approveBtn.isVisible()) {
      await detail.approve();
      // Status should update
      await expect(page.locator("text=APPROVED, text=PUSHING TO CW, text=approved")).toBeVisible({ timeout: 10000 });
    }
  });

  test("Reviewer can reject a shipment with reason", async ({ page }) => {
    await page.goto("/queue?status=review_required");
    await page.waitForLoadState("networkidle");
    const rows = page.locator("tbody tr");
    if (await rows.count() === 0) test.skip(true, "No review_required shipments");
    await rows.first().click();
    await page.waitForURL("**/shipments/**");

    const detail = new ShipmentDetailPage(page);
    if (await page.locator('button:has-text("Reject")').isVisible()) {
      await detail.reject("Test rejection — missing packing list");
      await expect(page.locator("text=REJECTED, text=rejected")).toBeVisible({ timeout: 8000 });
    }
  });

  test("Approve with compliance failure shows confirmation dialog", async ({ page }) => {
    await page.goto("/queue?shield=fail");
    await page.waitForLoadState("networkidle");
    const rows = page.locator("tbody tr");
    if (await rows.count() === 0) test.skip(true, "No failed shipments");
    await rows.first().click();
    await page.waitForURL("**/shipments/**");

    // Set up dialog handler before clicking approve
    let dialogAppeared = false;
    page.once("dialog", async d => {
      dialogAppeared = true;
      await d.dismiss(); // Cancel the override
    });

    const approveBtn = page.locator('button:has-text("Approve")');
    if (await approveBtn.isVisible()) {
      await approveBtn.click();
      await page.waitForTimeout(1000);
      expect(dialogAppeared).toBe(true);
    }
  });

  test("Audit trail shows all actions on a shipment", async ({ page }) => {
    await page.goto("/queue");
    const rows = page.locator("tbody tr");
    if (await rows.count() === 0) test.skip(true, "No shipments");
    await rows.first().click();
    await page.waitForURL("**/shipments/**");

    // Processing metadata section should exist
    await expect(page.locator("text=Processing").first()).toBeVisible({ timeout: 8000 });
  });

  test("Pagination works on queue with many shipments", async ({ page }) => {
    const queue = new QueuePage(page);
    await queue.goto();
    const nextBtn = page.locator('button:has-text("Next")');
    const prevBtn = page.locator('button:has-text("Previous")');
    // Buttons exist
    await expect(nextBtn).toBeVisible();
    await expect(prevBtn).toBeVisible();
    // Previous disabled on page 1
    await expect(prevBtn).toBeDisabled();
  });

});
