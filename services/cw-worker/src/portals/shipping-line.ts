/**
 * CargoIQ — Shipping Line Adapter
 * Covers: MSC, Maersk, Hapag-Lloyd, CMA CGM, Evergreen
 *
 * All shipping lines expose a public container tracking page.
 * This adapter scrapes real-time container status, vessel ETA,
 * and container release status from each line's website.
 *
 * No login required for tracking — uses public tracking portals.
 * For full container release: uses authenticated agent portals.
 */
import { BasePortalAdapter, PortalCredentials, PortalResult } from "./base-adapter";
import { logger } from "../utils/logger";

export type ShippingLine = "msc" | "maersk" | "hapag" | "cma" | "evergreen" | "one" | "cosco";

export interface ShippingLineParams {
  action:          "track_container" | "check_release" | "get_bl_status";
  containerNumber: string;
  line:            ShippingLine;
  billOfLading?:   string;
}

const LINE_URLS: Record<ShippingLine, string> = {
  msc:      "https://www.msc.com/en/track-a-shipment",
  maersk:   "https://www.maersk.com/tracking",
  hapag:    "https://www.hapag-lloyd.com/en/online-business/track/track-by-container-solution.html",
  cma:      "https://www.cma-cgm.com/ebusiness/tracking/search",
  evergreen: "https://www.evergreen-line.com/ecom/CUP_INQUERY.DO",
  one:      "https://ecomm.one-line.com/ecom/CUP_HOM_3301.do",
  cosco:    "https://elines.coscoshipping.com/ebtracking/public",
};

const LINE_NAMES: Record<ShippingLine, string> = {
  msc:      "MSC Mediterranean Shipping",
  maersk:   "Maersk",
  hapag:    "Hapag-Lloyd",
  cma:      "CMA CGM",
  evergreen: "Evergreen Line",
  one:      "Ocean Network Express",
  cosco:    "COSCO Shipping",
};

export class ShippingLineAdapter extends BasePortalAdapter {
  private line: ShippingLine;

  constructor(line: ShippingLine) {
    super(`shipping_${line}`);
    this.line = line;
  }

  async login(_creds: PortalCredentials): Promise<boolean> {
    // Public tracking — no login needed
    await this.launch();
    return true;
  }

  async execute(params: ShippingLineParams): Promise<PortalResult> {
    try {
      await this.launch();
      switch (params.action) {
        case "track_container":
          return await this._trackContainer(params.containerNumber);
        case "check_release":
          return await this._checkRelease(params.containerNumber, params.billOfLading);
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

  private async _trackContainer(containerNumber: string): Promise<PortalResult> {
    const page = this.page!;
    const url  = LINE_URLS[this.line];

    logger.info(`[${this.line.toUpperCase()}] Tracking container ${containerNumber}`);

    try {
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
      await page.waitForTimeout(2000);

      // Handle cookie banners (common on European shipping sites)
      await this.clickElement([
        'button:has-text("Accept")', 'button:has-text("Accept All")',
        'button:has-text("I Accept")', '#onetrust-accept-btn-handler',
        '.cookie-accept', '[class*="accept-cookie"]',
      ]);
      await page.waitForTimeout(500);

      // Enter container number in search box
      const inputOk = await this.fillField([
        'input[placeholder*="Container"]', 'input[placeholder*="container"]',
        'input[placeholder*="B/L"]', 'input[placeholder*="tracking"]',
        '#containerSearchInput', '#trackingInput',
        'input[name*="container"]', 'input[name*="tracking"]',
        'input[type="text"]:first-of-type',
      ], containerNumber);

      if (!inputOk) {
        await this.screenshot(`${this.line}_no_input`);
        return {
          success: false, portal: this.portalName,
          timestamp: new Date().toISOString(),
          error: "Could not find search input",
        };
      }

      // Submit search
      await this.clickElement([
        'button:has-text("Track")', 'button:has-text("Search")',
        'button:has-text("GO")', 'button[type="submit"]',
        '#btnTrack', '#searchBtn',
      ]);

      await page.waitForTimeout(4000);

      // Extract tracking results (structure varies by line)
      const data = await this._extractTrackingData(containerNumber);
      const screenshotPath = await this.screenshot(`track_${containerNumber}`);

      logger.info(`[${this.line.toUpperCase()}] Container ${containerNumber}: ${data.status}`);

      return {
        success: true, portal: this.portalName,
        timestamp: new Date().toISOString(),
        screenshotPath,
        data: {
          ...data,
          shippingLine: LINE_NAMES[this.line],
          containerNumber,
          checkedAt: new Date().toISOString(),
        },
      };

    } catch (err: any) {
      const screenshotPath = await this.screenshot(`${this.line}_error`);
      return {
        success: false, portal: this.portalName,
        timestamp: new Date().toISOString(),
        screenshotPath, error: err.message,
      };
    }
  }

  private async _extractTrackingData(containerNumber: string): Promise<Record<string, any>> {
    const page = this.page!;

    // Common selectors across multiple shipping lines
    // Each line uses different class names — we try them all
    const getAny = async (selectors: string[]) => this.getText(selectors);

    const status   = await getAny([
      '.status', '.event-status', '.tracking-status',
      '[class*="status"]', 'td:nth-child(2)', '.leg-status',
      '.container-status', '.shipment-status',
    ]);

    const location = await getAny([
      '.location', '.event-location', '.port-name',
      '[class*="location"]', 'td:nth-child(3)',
      '.current-location', '.last-event-location',
    ]);

    const vesselName = await getAny([
      '.vessel', '.vessel-name', '[class*="vessel"]',
      'td:has-text("Vessel"):nth-child(2)',
    ]);

    const eta = await getAny([
      '.eta', '.arrival', '[class*="eta"]',
      '.estimated-arrival', '.expected-arrival',
      'td:has-text("ETA")', '[data-label="ETA"]',
    ]);

    const pod = await getAny([
      '.pod', '.destination', '.port-of-discharge',
      '[class*="discharge"]', '[data-label="Destination"]',
    ]);

    const pol = await getAny([
      '.pol', '.origin', '.port-of-loading',
      '[class*="loading"]', '[data-label="Origin"]',
    ]);

    // Events table (last 3 events)
    let events: string[] = [];
    try {
      const eventRows = page.locator('.event-row, .tracking-event, tr.event, [class*="event-item"]');
      const count = Math.min(await eventRows.count(), 3);
      for (let i = 0; i < count; i++) {
        const text = await eventRows.nth(i).textContent();
        if (text) events.push(text.trim().replace(/\s+/g, " ").slice(0, 100));
      }
    } catch { }

    const isSADurban = /durban|south africa|dbn/i.test(location + pod);
    const isReleased = /released|available|delivery/i.test(status);
    const isInTransit = /transit|on board|vessel|sailing/i.test(status);

    return {
      status:     status   || "unknown",
      location:   location || "unknown",
      vesselName: vesselName || null,
      eta:        eta        || null,
      portOfDischarge: pod   || null,
      portOfLoading:   pol   || null,
      recentEvents: events,
      isReleased,
      isInTransit,
      isAtDurban: isSADurban,
    };
  }

  private async _checkRelease(containerNumber: string, billOfLading?: string): Promise<PortalResult> {
    // Track and add release-specific logic
    const trackResult = await this._trackContainer(containerNumber);
    if (!trackResult.success) return trackResult;

    const isReleased = trackResult.data?.isReleased || false;
    const eta        = trackResult.data?.eta;

    return {
      ...trackResult,
      data: {
        ...trackResult.data,
        releaseStatus: isReleased ? "released" : "not_released",
        billOfLading: billOfLading || null,
      },
    };
  }
}

// ── Factory function ──────────────────────────────────────────

export function createShippingAdapter(line: ShippingLine): ShippingLineAdapter {
  return new ShippingLineAdapter(line);
}

export function detectShippingLine(containerNumber: string): ShippingLine | null {
  // Container prefixes identify the line
  const prefix = containerNumber.substring(0, 4).toUpperCase();
  const prefixMap: Record<string, ShippingLine> = {
    "MSCU": "msc", "MEDU": "msc", "MSDU": "msc",
    "MAEU": "maersk", "MRKU": "maersk", "MSKU": "maersk",
    "HLCU": "hapag", "HLXU": "hapag",
    "CMAU": "cma", "CGMU": "cma",
    "EITU": "evergreen", "EMCU": "evergreen",
    "ONEY": "one", "ONEU": "one",
    "CSNU": "cosco", "CCLU": "cosco",
  };
  return prefixMap[prefix] || null;
}
