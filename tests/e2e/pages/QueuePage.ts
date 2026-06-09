import { Page, expect, Locator } from "@playwright/test";

export class QueuePage {
  readonly uploadButton:     Locator;
  readonly refreshButton:    Locator;
  readonly searchInput:      Locator;
  readonly shipmentTable:    Locator;
  readonly totalCount:       Locator;

  constructor(private page: Page) {
    this.uploadButton   = page.locator('button:has-text("Upload Document")');
    this.refreshButton  = page.locator('button:has-text("Refresh")');
    this.searchInput    = page.locator('input[placeholder*="Search"]').first();
    this.shipmentTable  = page.locator("table").first();
    this.totalCount     = page.locator("text=/\d+ record/").first();
  }

  async goto() {
    await this.page.goto("/queue");
    await this.page.waitForLoadState("networkidle");
  }

  async clickUpload() {
    await this.uploadButton.click();
    await this.page.waitForURL("**/queue/upload");
  }

  async searchFor(term: string) {
    await this.searchInput.fill(term);
    await this.page.waitForResponse(r => r.url().includes("/shipments"));
  }

  async filterByStatus(status: string) {
    await this.page.click(`button:has-text("${status}")`);
    await this.page.waitForTimeout(500);
  }

  async getShipmentRows() {
    return this.page.locator("tbody tr");
  }

  async clickFirstShipment() {
    const rows = await this.getShipmentRows();
    await rows.first().click();
    await this.page.waitForURL("**/shipments/**");
  }

  async approveFirstShipment() {
    const approveBtn = this.page.locator('button[title="Approve"]').first();
    await approveBtn.click();
    await this.page.waitForTimeout(1000);
  }

  async rejectFirstShipment(reason: string) {
    const rejectBtn = this.page.locator('button[title="Reject"]').first();
    this.page.once("dialog", d => d.accept(reason));
    await rejectBtn.click();
    await this.page.waitForTimeout(1000);
  }

  async assertEmptyState() {
    await expect(this.page.locator("text=No shipments found")).toBeVisible();
  }
}
