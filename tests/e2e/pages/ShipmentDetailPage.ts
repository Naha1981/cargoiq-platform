import { Page, expect, Locator } from "@playwright/test";

export class ShipmentDetailPage {
  readonly reference:       Locator;
  readonly statusBadge:     Locator;
  readonly shieldPanel:     Locator;
  readonly approveButton:   Locator;
  readonly rejectButton:    Locator;
  readonly reAuditButton:   Locator;
  readonly penaltyAlert:    Locator;

  constructor(private page: Page) {
    this.reference      = page.locator("h1").first();
    this.statusBadge    = page.locator(".badge, [class*=badge]").first();
    this.shieldPanel    = page.locator("text=Compliance Shield").locator("..").first();
    this.approveButton  = page.locator('button:has-text("Approve")');
    this.rejectButton   = page.locator('button:has-text("Reject")');
    this.reAuditButton  = page.locator('button:has-text("Re-audit")');
    this.penaltyAlert   = page.locator("text=SARS Penalty Risk Detected");
  }

  async waitForExtraction(timeout = 30000) {
    await this.page.waitForFunction(
      () => !document.body.innerText.includes("extracting"),
      { timeout }
    );
  }

  async assertShieldPasses() {
    await expect(this.shieldPanel.locator("text=COMPLIANT")).toBeVisible({ timeout: 15000 });
  }

  async assertShieldHolds() {
    await expect(this.shieldPanel.locator("text=REVIEW REQUIRED")).toBeVisible({ timeout: 15000 });
  }

  async assertShieldFails() {
    await expect(this.shieldPanel.locator("text=COMPLIANCE FAILURE")).toBeVisible({ timeout: 15000 });
  }

  async assertPenaltyRiskShown() {
    await expect(this.penaltyAlert).toBeVisible();
  }

  async approve(acknowledgeRisk = false) {
    if (acknowledgeRisk) {
      this.page.once("dialog", d => d.accept());
    }
    await this.approveButton.click();
    await this.page.waitForTimeout(2000);
  }

  async reject(reason: string) {
    this.page.once("dialog", d => d.accept(reason));
    await this.rejectButton.click();
    await this.page.waitForTimeout(1000);
  }

  async expandShieldModule(moduleName: string) {
    const module = this.page.locator(`text=${moduleName}`).locator("..");
    await module.click();
  }

  async getExtractedField(label: string): Promise<string> {
    const row = this.page.locator(`.row:has-text("${label}"), div:has-text("${label}")`).first();
    return (await row.locator(".val, .font-mono").textContent()) || "";
  }
}
