import { Page, expect, Locator } from "@playwright/test";

export class CompliancePage {
  readonly passRate:        Locator;
  readonly penaltyCount:    Locator;
  readonly topModules:      Locator;
  readonly rlaTable:        Locator;

  constructor(private page: Page) {
    this.passRate     = page.locator("text=Overall Compliance Pass Rate").locator("..").locator(".text-5xl");
    this.penaltyCount = page.locator("text=Penalty Risk Events").locator("..").locator(".text-3xl");
    this.topModules   = page.locator("text=Top Compliance Issues").locator("..").locator("table, [class*=divide]");
    this.rlaTable     = page.locator("text=RLA Status Monitor").locator("..");
  }

  async goto() {
    await this.page.goto("/compliance");
    await this.page.waitForLoadState("networkidle");
  }

  async assertPassRateVisible() {
    await expect(this.passRate).toBeVisible({ timeout: 10000 });
  }

  async assertRLATableVisible() {
    await expect(this.rlaTable).toBeVisible();
  }
}
