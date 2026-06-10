/**
 * CargoIQ — Base Portal Adapter
 * All portal adapters extend this class.
 * Provides: login, screenshot, self-healing selectors, retry logic.
 */
import { Browser, BrowserContext, Page, chromium } from "playwright";
import { logger } from "../utils/logger";
import * as fs from "fs";
import * as path from "path";

export interface PortalResult {
  success:       boolean;
  data?:         Record<string, any>;
  screenshotPath?: string;
  error?:        string;
  portal:        string;
  timestamp:     string;
}

export interface PortalCredentials {
  username:  string;
  password:  string;
  secondFactor?: string;   // OTP / PIN for 2FA portals
  extraData?: Record<string, string>;  // portal-specific extra fields
}

const HEADLESS = process.env.BROWSER_HEADLESS !== "false";
const TIMEOUT  = parseInt(process.env.BROWSER_TIMEOUT_MS || "45000");
const SHOT_DIR = process.env.SCREENSHOT_PATH || "/tmp/cargoiq-screenshots";

export abstract class BasePortalAdapter {
  protected browser?:  Browser;
  protected context?:  BrowserContext;
  protected page?:     Page;
  protected portalName: string;

  constructor(portalName: string) {
    this.portalName = portalName;
    if (!fs.existsSync(SHOT_DIR)) {
      fs.mkdirSync(SHOT_DIR, { recursive: true });
    }
  }

  // ── Browser lifecycle ─────────────────────────────────────

  protected async launch(): Promise<Page> {
    this.browser = await chromium.launch({
      headless: HEADLESS,
      args: [
        "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu",
        "--disable-blink-features=AutomationControlled",
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
      ],
    });
    this.context = await this.browser.newContext({
      viewport:  { width: 1366, height: 768 },
      ignoreHTTPSErrors: true,
      javaScriptEnabled: true,
    });
    this.page = await this.context.newPage();
    this.page.setDefaultTimeout(TIMEOUT);
    return this.page;
  }

  protected async close(): Promise<void> {
    try { await this.browser?.close(); } catch { /* ignore */ }
  }

  // ── Screenshot ────────────────────────────────────────────

  protected async screenshot(label: string): Promise<string> {
    const filename = `${this.portalName}_${label}_${Date.now()}.png`;
    const filepath = path.join(SHOT_DIR, filename);
    try {
      await this.page?.screenshot({ path: filepath, fullPage: false });
      return filepath;
    } catch {
      return "";
    }
  }

  // ── Self-healing selector ────────────────────────────────
  // Tries multiple selectors; if all fail, returns null
  // and logs a warning for human review.

  protected async findElement(selectors: string[], timeout = 5000) {
    for (const sel of selectors) {
      try {
        const el = this.page!.locator(sel).first();
        await el.waitFor({ timeout, state: "visible" });
        return el;
      } catch { continue; }
    }
    logger.warn(`[${this.portalName}] Could not find element`, { selectors });
    return null;
  }

  protected async fillField(selectors: string[], value: string): Promise<boolean> {
    for (const sel of selectors) {
      try {
        await this.page!.fill(sel, value, { timeout: 5000 });
        return true;
      } catch { continue; }
    }
    return false;
  }

  protected async clickElement(selectors: string[]): Promise<boolean> {
    for (const sel of selectors) {
      try {
        await this.page!.click(sel, { timeout: 5000 });
        return true;
      } catch { continue; }
    }
    return false;
  }

  protected async getText(selectors: string[]): Promise<string> {
    for (const sel of selectors) {
      try {
        const text = await this.page!.textContent(sel, { timeout: 3000 });
        if (text?.trim()) return text.trim();
      } catch { continue; }
    }
    return "";
  }

  // ── Wait helpers ──────────────────────────────────────────

  protected async waitForAny(selectors: string[], timeout = 15000): Promise<string | null> {
    try {
      const result = await this.page!.waitForSelector(
        selectors.join(", "),
        { timeout, state: "visible" }
      );
      if (result) return await result.evaluate(el => el.tagName);
    } catch { }
    return null;
  }

  // ── Abstract interface ────────────────────────────────────

  abstract login(creds: PortalCredentials): Promise<boolean>;
  abstract execute(params: Record<string, any>): Promise<PortalResult>;
}
