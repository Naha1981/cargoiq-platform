import { Page, expect, Locator } from "@playwright/test";
import path from "path";

export class UploadPage {
  readonly dropzone:      Locator;
  readonly uploadButton:  Locator;
  readonly fileList:      Locator;

  constructor(private page: Page) {
    this.dropzone     = page.locator('[class*="border-dashed"]').first();
    this.uploadButton = page.locator('button:has-text("Upload & Extract")');
    this.fileList     = page.locator('[class*="divide-y"] > div');
  }

  async goto() {
    await this.page.goto("/queue/upload");
    await this.page.waitForLoadState("domcontentloaded");
  }

  async uploadFile(filePath: string) {
    const input = this.page.locator('input[type="file"]');
    await input.setInputFiles(filePath);
    await this.page.waitForTimeout(500);
  }

  async uploadAndProcess(filePath: string) {
    await this.uploadFile(filePath);
    await expect(this.uploadButton).toBeVisible({ timeout: 5000 });
    await this.uploadButton.click();
  }

  async assertFileAdded(filename: string) {
    await expect(this.page.locator(`text=${filename}`)).toBeVisible();
  }

  async assertProcessingStarted() {
    const processing = this.page.locator("text=Processing, text=Extracting, text=processing");
    // Either navigates to shipment or shows processing state
    const navigated = this.page.waitForURL("**/shipments/**", { timeout: 30000 });
    const queueNav  = this.page.waitForURL("**/queue", { timeout: 30000 });
    await Promise.race([navigated, queueNav]);
  }
}
