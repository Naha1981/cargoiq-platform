import { Page, expect, Locator } from "@playwright/test";

export class DashboardPage {
  readonly queueSize:        Locator;
  readonly automationRate:   Locator;
  readonly complianceFlags:  Locator;
  readonly processedToday:   Locator;
  readonly volumeChart:      Locator;
  readonly roiSummary:       Locator;

  constructor(private page: Page) {
    this.queueSize       = page.locator("text=Queue Size").locator("..").locator(".font-mono, .text-3xl").first();
    this.automationRate  = page.locator("text=Automation Rate").locator("..").locator(".font-mono, .text-3xl").first();
    this.complianceFlags = page.locator("text=Compliance Flags").locator("..").locator(".font-mono, .text-3xl").first();
    this.processedToday  = page.locator("text=Processed Today").locator("..").locator(".font-mono, .text-3xl").first();
    this.volumeChart     = page.locator(".recharts-wrapper, [class*=recharts]").first();
    this.roiSummary      = page.locator("text=ROI Summary").first();
  }

  async goto() {
    await this.page.goto("/dashboard");
    await this.page.waitForLoadState("networkidle");
  }

  async assertKPIsVisible() {
    await expect(this.queueSize).toBeVisible({ timeout: 10000 });
    await expect(this.automationRate).toBeVisible();
    await expect(this.complianceFlags).toBeVisible();
  }

  async assertVolumeChartLoaded() {
    await expect(this.volumeChart).toBeVisible({ timeout: 10000 });
  }

  async navigateTo(section: "queue" | "compliance" | "analytics" | "settings") {
    await this.page.click(`a[href="/${section}"]`);
    await this.page.waitForURL(`**/${section}*`);
  }
}
