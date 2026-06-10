/**
 * CargoIQ — SARS eFiling Portal Adapter
 *
 * Handles:
 *   1. RLA status checks (importer registration/licensing/accreditation)
 *   2. SAD500 customs declaration submission
 *   3. VOC (Voucher of Correction) filing
 *   4. Container release status polling
 *
 * Portal: https://efiling.sars.gov.za
 * Auth: username + password (+ OTP for 2FA accounts)
 */
import { BasePortalAdapter, PortalCredentials, PortalResult } from "./base-adapter";
import { logger } from "../utils/logger";

export type SARSAction =
  | "check_rla"
  | "submit_sad500"
  | "check_release"
  | "submit_voc"
  | "check_account_balance";

export interface SARSParams {
  action:         SARSAction;
  importerCode?:  string;   // e.g. "ZA12345678"
  sad500Data?:    Record<string, any>;
  mrn?:           string;   // Customs reference number
  vodData?:       Record<string, any>;
}

export class SARSEFilingAdapter extends BasePortalAdapter {
  private static BASE_URL = "https://efiling.sars.gov.za";

  constructor() {
    super("sars_efiling");
  }

  // ── Login ──────────────────────────────────────────────────

  async login(creds: PortalCredentials): Promise<boolean> {
    const page = await this.launch();

    try {
      logger.info("[SARS] Navigating to eFiling login");
      await page.goto(`${SARSEFilingAdapter.BASE_URL}/eFiling/portal`, {
        waitUntil: "domcontentloaded", timeout: 30000
      });

      // Username
      const usernameOk = await this.fillField([
        '#txtUsername', 'input[name="txtUsername"]',
        'input[placeholder*="Username"]', 'input[placeholder*="username"]',
        '#Username', 'input[type="text"]:first-of-type',
      ], creds.username);

      if (!usernameOk) {
        logger.error("[SARS] Could not find username field");
        await this.screenshot("login_failed_no_username");
        return false;
      }

      // Password
      await this.fillField([
        '#txtPassword', 'input[name="txtPassword"]',
        'input[type="password"]', '#Password',
      ], creds.password);

      // Submit
      const submitted = await this.clickElement([
        '#btnLogin', 'button[type="submit"]',
        'input[type="submit"]', 'button:has-text("Login")',
        'button:has-text("Sign In")', '.login-btn',
      ]);

      if (!submitted) {
        await this.screenshot("login_no_submit_btn");
        return false;
      }

      // Wait for redirect away from login page
      await page.waitForTimeout(3000);

      // Handle OTP / 2FA if present
      if (creds.secondFactor) {
        const otpField = await this.findElement([
          'input[name*="otp"]', 'input[placeholder*="OTP"]',
          'input[placeholder*="PIN"]', '#txtOTP',
        ]);
        if (otpField) {
          logger.info("[SARS] OTP field detected — entering second factor");
          await otpField.fill(creds.secondFactor);
          await this.clickElement([
            'button:has-text("Verify")', 'button:has-text("Submit")',
            '#btnVerify', 'button[type="submit"]',
          ]);
          await page.waitForTimeout(3000);
        }
      }

      // Verify login success — check we are NOT on login page
      const currentUrl = page.url();
      const loginFailed = currentUrl.includes("login") ||
        await page.locator("text=Invalid username or password").isVisible().catch(() => false);

      if (loginFailed) {
        await this.screenshot("login_rejected");
        logger.error("[SARS] Login rejected — check credentials");
        return false;
      }

      await this.screenshot("login_success");
      logger.info("[SARS] Login successful");
      return true;

    } catch (err: any) {
      logger.error("[SARS] Login error", { error: err.message });
      await this.screenshot("login_error");
      return false;
    }
  }

  // ── Main execute dispatcher ────────────────────────────────

  async execute(params: SARSParams): Promise<PortalResult> {
    try {
      switch (params.action) {
        case "check_rla":
          return await this._checkRLA(params.importerCode!);
        case "submit_sad500":
          return await this._submitSAD500(params.sad500Data!);
        case "check_release":
          return await this._checkRelease(params.mrn!);
        default:
          return {
            success: false, portal: this.portalName,
            timestamp: new Date().toISOString(),
            error: `Unknown action: ${params.action}`,
          };
      }
    } finally {
      await this.close();
    }
  }

  // ── RLA Status Check ───────────────────────────────────────
  // Called by RLA Sentinel every morning at 06:00 SAST

  private async _checkRLA(importerCode: string): Promise<PortalResult> {
    const page = this.page!;
    logger.info(`[SARS] Checking RLA status for ${importerCode}`);

    try {
      // Navigate to RLA section
      const navigated = await this.clickElement([
        'a:has-text("RLA")',
        'a:has-text("Registration, Licensing")',
        'a[href*="rla"]',
        'a[href*="RLA"]',
        'span:has-text("RLA")',
      ]);

      if (!navigated) {
        // Try direct URL
        await page.goto(
          `${SARSEFilingAdapter.BASE_URL}/eFiling/portal#/rla`,
          { waitUntil: "domcontentloaded", timeout: 15000 }
        );
      }

      await page.waitForTimeout(2000);

      // Search for importer
      await this.fillField([
        'input[placeholder*="Importer"]', 'input[placeholder*="Search"]',
        '#importerSearch', 'input[name*="search"]',
      ], importerCode);

      await this.clickElement([
        'button:has-text("Search")', '#btnSearch',
        'button[type="submit"]',
      ]);

      await page.waitForTimeout(2000);

      // Extract status
      const statusText = await this.getText([
        '.rla-status', '[class*="status"]', 'td:nth-child(3)',
        '.badge', '[data-field="status"]',
      ]);

      const screenshotPath = await this.screenshot(`rla_${importerCode}`);

      const isActive    = /active|registered|approved/i.test(statusText);
      const isSuspended = /suspended|blocked|revoked|inactive/i.test(statusText);

      logger.info(`[SARS] RLA status for ${importerCode}: ${statusText || "unknown"}`);

      return {
        success: true,
        portal:  this.portalName,
        timestamp: new Date().toISOString(),
        screenshotPath,
        data: {
          importerCode,
          rlaStatus:    isSuspended ? "suspended" : isActive ? "active" : "unverified",
          rawStatus:    statusText,
          checkedAt:    new Date().toISOString(),
          screenshotPath,
        },
      };

    } catch (err: any) {
      const screenshotPath = await this.screenshot("rla_error");
      return {
        success: false, portal: this.portalName,
        timestamp: new Date().toISOString(),
        screenshotPath, error: err.message,
        data: { importerCode, rlaStatus: "check_failed" },
      };
    }
  }

  // ── SAD500 Submission ─────────────────────────────────────
  // Fills and submits a customs declaration

  private async _submitSAD500(sad500: Record<string, any>): Promise<PortalResult> {
    const page = this.page!;
    logger.info("[SARS] Starting SAD500 submission");

    try {
      // Navigate to new declaration
      await this.clickElement([
        'a:has-text("Customs")', 'a[href*="customs"]',
        'a:has-text("Declaration")', 'a[href*="declaration"]',
      ]);
      await page.waitForTimeout(1500);

      // New entry
      await this.clickElement([
        'button:has-text("New")', 'a:has-text("New Declaration")',
        '#btnNew', 'button:has-text("Create")',
      ]);
      await page.waitForTimeout(2000);

      const fields: [string, string[]][] = [
        // [value, [selectors]]
        [sad500.declarantCode,   ['#declarantCode', '[data-field="declarantCode"]']],
        [sad500.importerCode,    ['#importerCode',  '[data-field="importerCode"]']],
        [sad500.hsCode,          ['#hsCode', '#tariffCode', '[data-field="hsCode"]']],
        [sad500.statisticalValue, ['#statisticalValue', '[data-field="value"]']],
        [sad500.netMass,         ['#netMass', '[data-field="netMass"]']],
        [sad500.procedureCode,   ['#procedureCode', '[data-field="cpc"]']],
        [sad500.countryOfOrigin, ['#countryOfOrigin', '[data-field="origin"]']],
      ];

      for (const [value, selectors] of fields) {
        if (value) await this.fillField(selectors, String(value));
      }

      const screenshotBefore = await this.screenshot("sad500_before_submit");

      // Submit
      await this.clickElement([
        'button:has-text("Submit")', '#btnSubmit',
        'button:has-text("File")', 'input[value="Submit"]',
      ]);
      await page.waitForTimeout(4000);

      // Get MRN / reference number
      const mrn = await this.getText([
        '.mrn', '#mrnNumber', '[class*="mrn"]',
        'text=/MRN:?\s*[A-Z0-9]+/',
      ]);

      const screenshotAfter = await this.screenshot("sad500_submitted");
      logger.info(`[SARS] SAD500 submitted — MRN: ${mrn}`);

      return {
        success: !!mrn,
        portal:  this.portalName,
        timestamp: new Date().toISOString(),
        screenshotPath: screenshotAfter,
        data: {
          mrn,
          submittedAt: new Date().toISOString(),
          screenshotBefore,
          screenshotAfter,
        },
      };

    } catch (err: any) {
      const screenshotPath = await this.screenshot("sad500_error");
      return {
        success: false, portal: this.portalName,
        timestamp: new Date().toISOString(),
        screenshotPath, error: err.message,
      };
    }
  }

  // ── Release Status Check ──────────────────────────────────

  private async _checkRelease(mrn: string): Promise<PortalResult> {
    const page = this.page!;
    logger.info(`[SARS] Checking release status for MRN ${mrn}`);

    try {
      await this.fillField([
        '#searchMRN', 'input[placeholder*="MRN"]',
        'input[placeholder*="Reference"]',
      ], mrn);

      await this.clickElement(['button:has-text("Search")', '#btnSearch']);
      await page.waitForTimeout(2000);

      const status = await this.getText([
        '.release-status', '[class*="release"]',
        'td:has-text("Released")', '[data-field="releaseStatus"]',
      ]);

      const isReleased = /released|cleared|free/i.test(status);
      const screenshotPath = await this.screenshot(`release_${mrn}`);

      return {
        success: true,
        portal:  this.portalName,
        timestamp: new Date().toISOString(),
        screenshotPath,
        data: {
          mrn, releaseStatus: isReleased ? "released" : "not_released",
          rawStatus: status, checkedAt: new Date().toISOString(),
        },
      };

    } catch (err: any) {
      const screenshotPath = await this.screenshot("release_error");
      return {
        success: false, portal: this.portalName,
        timestamp: new Date().toISOString(),
        screenshotPath, error: err.message,
      };
    }
  }
}
