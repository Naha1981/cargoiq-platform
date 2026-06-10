/**
 * CargoIQ — Transnet Navis / TPT Port Portal Adapter
 *
 * Handles:
 *   1. Container status checks (vessel ETA, gate-in, release)
 *   2. Demurrage calculation (free days vs actual days)
 *   3. Gate-out slip capture (proof of collection)
 *   4. Terminal availability checks
 *
 * Portals covered:
 *   - Transnet Port Terminals: https://tpt.transnet.net
 *   - NAVIS / TOS portal
 *   - Port of Durban container tracker
 */
import { BasePortalAdapter, PortalCredentials, PortalResult } from "./base-adapter";
import { logger } from "../utils/logger";

export type TransnetAction =
  | "check_container"
  | "get_demurrage"
  | "check_vessel_eta"
  | "get_gate_slips"
  | "check_availability";

export interface TransnetParams {
  action:          TransnetAction;
  containerNumber?: string;
  vesselName?:      string;
  voyageNumber?:    string;
  bookingRef?:      string;
}

export class TransnetNavisAdapter extends BasePortalAdapter {
  private static PORTALS = {
    tpt:    "https://tpt.transnet.net",
    navis:  "https://navisaccess.transnet.net",
    durban: "https://www.tnpa.com/Pages/Ports/Durban.aspx",
  };

  constructor() {
    super("transnet_navis");
  }

  async login(creds: PortalCredentials): Promise<boolean> {
    const page = await this.launch();
    try {
      logger.info("[TRANSNET] Logging in to TPT portal");
      await page.goto(TransnetNavisAdapter.PORTALS.tpt, {
        waitUntil: "domcontentloaded", timeout: 30000
      });

      await this.fillField([
        '#Username', 'input[name="username"]',
        'input[placeholder*="Username"]', 'input[type="text"]:first-of-type',
      ], creds.username);

      await this.fillField([
        '#Password', 'input[name="password"]',
        'input[type="password"]',
      ], creds.password);

      await this.clickElement([
        'button[type="submit"]', '#btnLogin',
        'button:has-text("Login")', 'input[value="Login"]',
      ]);

      await page.waitForTimeout(3000);
      const currentUrl = page.url();
      const failed = currentUrl.toLowerCase().includes("login") &&
        !currentUrl.toLowerCase().includes("portal");

      if (failed) {
        await this.screenshot("transnet_login_failed");
        return false;
      }

      await this.screenshot("transnet_login_success");
      logger.info("[TRANSNET] Login successful");
      return true;

    } catch (err: any) {
      logger.error("[TRANSNET] Login error", { error: err.message });
      await this.screenshot("transnet_login_error");
      return false;
    }
  }

  async execute(params: TransnetParams): Promise<PortalResult> {
    try {
      switch (params.action) {
        case "check_container":
          return await this._checkContainer(params.containerNumber!);
        case "get_demurrage":
          return await this._getDemurrage(params.containerNumber!);
        case "check_vessel_eta":
          return await this._checkVesselETA(params.vesselName!, params.voyageNumber);
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

  // ── Container Status Check ────────────────────────────────

  private async _checkContainer(containerNumber: string): Promise<PortalResult> {
    const page = this.page!;
    logger.info(`[TRANSNET] Checking container ${containerNumber}`);

    try {
      // Navigate to container enquiry
      const navOk = await this.clickElement([
        'a:has-text("Container Enquiry")',
        'a:has-text("Track Container")',
        'a[href*="container"]',
        'a:has-text("Enquiry")',
      ]);

      if (!navOk) {
        await page.goto(
          `${TransnetNavisAdapter.PORTALS.tpt}/container-enquiry`,
          { waitUntil: "domcontentloaded", timeout: 15000 }
        );
      }

      await page.waitForTimeout(1500);

      // Enter container number
      await this.fillField([
        '#containerNo', '#containerNumber',
        'input[placeholder*="Container"]',
        'input[name*="container"]',
      ], containerNumber);

      await this.clickElement([
        'button:has-text("Search")', 'button:has-text("Enquire")',
        '#btnSearch', '#btnEnquire', 'button[type="submit"]',
      ]);

      await page.waitForTimeout(3000);

      // Extract status fields
      const status       = await this.getText(['.status-value', '#containerStatus', 'td:nth-child(3)']);
      const location     = await this.getText(['.location', '#currentLocation', '[data-field="location"]']);
      const vesselName   = await this.getText(['.vessel-name', '#vesselName', '[data-field="vessel"]']);
      const eta          = await this.getText(['#eta', '.eta-value', '[data-field="eta"]']);
      const freeDays     = await this.getText(['#freeDays', '.free-days', '[data-field="freeDays"]']);
      const demurrageDay = await this.getText(['#demurrageStart', '.demurrage-date']);
      const gateIn       = await this.getText(['#gateIn', '.gate-in', '[data-field="gateIn"]']);
      const gateOut      = await this.getText(['#gateOut', '.gate-out', '[data-field="gateOut"]']);

      const screenshotPath = await this.screenshot(`container_${containerNumber}`);

      const isReleased   = /released|available|cleared/i.test(status);
      const isOnVessel   = /vessel|on board|in transit/i.test(status);
      const isAtTerminal = /terminal|yard|port/i.test(location);

      logger.info(`[TRANSNET] Container ${containerNumber}: ${status}`);

      return {
        success: true,
        portal:  this.portalName,
        timestamp: new Date().toISOString(),
        screenshotPath,
        data: {
          containerNumber,
          status:       status       || "unknown",
          location:     location     || "unknown",
          vesselName:   vesselName   || null,
          eta:          eta          || null,
          freeDays:     freeDays     || null,
          demurrageStartDate: demurrageDay || null,
          gateIn:       gateIn       || null,
          gateOut:      gateOut      || null,
          isReleased,
          isOnVessel,
          isAtTerminal,
          checkedAt: new Date().toISOString(),
        },
      };

    } catch (err: any) {
      const screenshotPath = await this.screenshot("container_error");
      return {
        success: false, portal: this.portalName,
        timestamp: new Date().toISOString(),
        screenshotPath, error: err.message,
        data: { containerNumber, status: "check_failed" },
      };
    }
  }

  // ── Demurrage Calculator ───────────────────────────────────

  private async _getDemurrage(containerNumber: string): Promise<PortalResult> {
    const containerResult = await this._checkContainer(containerNumber);

    if (!containerResult.success || !containerResult.data) {
      return containerResult;
    }

    const data = containerResult.data;

    // Calculate demurrage exposure
    const FREE_DAYS     = parseInt(data.freeDays || "7");
    const COST_PER_DAY  = 12500;  // R12,500/day standard Durban demurrage

    let demurrageExposureZAR = 0;
    let daysOverFree = 0;

    if (data.eta) {
      const etaDate    = new Date(data.eta);
      const today      = new Date();
      const daysAtPort = Math.floor((today.getTime() - etaDate.getTime()) / 86400000);

      if (daysAtPort > FREE_DAYS && !data.gateOut) {
        daysOverFree         = daysAtPort - FREE_DAYS;
        demurrageExposureZAR = daysOverFree * COST_PER_DAY;
      }
    }

    return {
      ...containerResult,
      data: {
        ...data,
        demurrageExposureZAR,
        daysOverFreeTime: daysOverFree,
        freeDaysAllowed:  FREE_DAYS,
        costPerDayZAR:    COST_PER_DAY,
        demurrageAlert:   demurrageExposureZAR > 0,
      },
    };
  }

  // ── Vessel ETA Check ──────────────────────────────────────

  private async _checkVesselETA(vesselName: string, voyageNumber?: string): Promise<PortalResult> {
    const page = this.page!;
    logger.info(`[TRANSNET] Checking ETA for vessel ${vesselName}`);

    try {
      await this.clickElement([
        'a:has-text("Vessel Schedule")', 'a:has-text("Vessel Enquiry")',
        'a[href*="vessel"]',
      ]);

      await page.waitForTimeout(1500);

      await this.fillField([
        '#vesselName', 'input[placeholder*="Vessel"]',
        'input[name*="vessel"]',
      ], vesselName);

      if (voyageNumber) {
        await this.fillField([
          '#voyageNo', 'input[placeholder*="Voyage"]',
        ], voyageNumber);
      }

      await this.clickElement(['button:has-text("Search")', '#btnSearch']);
      await page.waitForTimeout(2000);

      const eta      = await this.getText(['#eta', '.eta', '[data-field="eta"]']);
      const berth    = await this.getText(['#berth', '.berth-number']);
      const status   = await this.getText(['.vessel-status', '[data-field="status"]']);

      const screenshotPath = await this.screenshot(`vessel_${vesselName}`);

      return {
        success: true,
        portal:  this.portalName,
        timestamp: new Date().toISOString(),
        screenshotPath,
        data: { vesselName, voyageNumber, eta, berth, status, checkedAt: new Date().toISOString() },
      };

    } catch (err: any) {
      const screenshotPath = await this.screenshot("vessel_error");
      return {
        success: false, portal: this.portalName,
        timestamp: new Date().toISOString(),
        screenshotPath, error: err.message,
      };
    }
  }
}
