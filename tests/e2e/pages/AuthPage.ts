import { Page, expect } from "@playwright/test";

export class AuthPage {
  constructor(private page: Page) {}

  async signup(email: string, password: string, name: string, org: string) {
    await this.page.goto("/auth/signup");
    await this.page.fill('input[type="text"]:first-of-type', org);
    await this.page.fill('input:nth-of-type(2)', name);
    await this.page.fill('input[type="email"]', email);
    await this.page.fill('input[type="password"]', password);
    await this.page.click('button[type="submit"]');
    await this.page.waitForURL("**/dashboard", { timeout: 15000 });
  }

  async login(email: string, password: string) {
    await this.page.goto("/auth/login");
    await this.page.fill('input[type="email"]', email);
    await this.page.fill('input[type="password"]', password);
    await this.page.click('button[type="submit"]');
    await this.page.waitForURL("**/dashboard", { timeout: 15000 });
  }

  async logout() {
    await this.page.click('a[href="/auth/login"]');
    await this.page.waitForURL("**/auth/login");
  }

  async assertOnDashboard() {
    await expect(this.page).toHaveURL(/.*dashboard/);
    await expect(this.page.locator(".logo, text=CargoIQ")).toBeVisible();
  }

  async assertRedirectedToLogin() {
    await expect(this.page).toHaveURL(/.*login/);
  }
}
