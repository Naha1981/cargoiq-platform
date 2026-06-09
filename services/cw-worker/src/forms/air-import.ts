import { Page } from "playwright";
import { logger } from "../utils/logger";
import { captureScreenshot, CWSession } from "../utils/session";

export interface AirImportFields {
  shipperName?: string; consigneeName?: string; awbNumber?: string;
  originPort?: string; destinationPort?: string; cargoDescription?: string;
  grossWeight?: number; weightUnit?: string; pieces?: number;
  invoiceNumber?: string; invoiceValue?: number; currency?: string;
  incoterms?: string; eta?: string; hsCode?: string;
}

export interface AirImportResult {
  success: boolean; jobNumber?: string; screenshotPath?: string;
  error?: string; fieldsSet: string[]; fieldsFailed: string[];
}

async function fill(page: Page, selectors: string[], value: string): Promise<boolean> {
  for (const sel of selectors) {
    try { await page.fill(sel, value, { timeout: 2500 }); return true; } catch { continue; }
  }
  return false;
}

async function fillOrSelect(page: Page, selectors: string[], value: string): Promise<boolean> {
  for (const sel of selectors) {
    try { await page.fill(sel, value, { timeout: 2000 }); await page.keyboard.press("Tab"); return true; } catch {}
    try { await page.selectOption(sel, { label: value }, { timeout: 2000 }); return true; } catch {}
  }
  return false;
}

async function saveDraft(page: Page): Promise<boolean> {
  for (const sel of ['button:has-text("Save Draft")','button:has-text("Save")','"[data-action=SaveDraft"]','#saveDraftBtn']) {
    try { await page.click(sel, { timeout: 3000 }); await page.waitForTimeout(2000); return true; } catch { continue; }
  }
  try { await page.keyboard.press("Control+s"); await page.waitForTimeout(2000); return true; } catch { return false; }
}

async function getJobNumber(page: Page): Promise<string | null> {
  for (const sel of ['[data-field="JobNumber"]','#JobNumber','.job-number']) {
    try { const t = await page.textContent(sel, { timeout: 3000 }); if (t?.trim()) return t.trim(); } catch { continue; }
  }
  const m = page.url().match(/\/(\d{4,})\/?$/);
  return m ? m[1] : null;
}

export async function createAirImportDraft(session: CWSession, fields: AirImportFields): Promise<AirImportResult> {
  const { page, baseUrl } = session;
  const set: string[] = [], failed: string[] = [];
  try {
    await page.goto(baseUrl + "/CargoWise/FreightForwarding/AirImport/New", { waitUntil: "domcontentloaded", timeout: 20000 });
    logger.info("Air Import form loaded");
    const map: [string | undefined, string[], boolean][] = [
      [fields.shipperName,      ['[data-field="ShipperName"]','#ShipperName'],                         false],
      [fields.consigneeName,    ['[data-field="ConsigneeName"]','#ConsigneeName'],                     false],
      [fields.awbNumber,        ['[data-field="MasterBillNumber"]','#AWBNumber'],                      false],
      [fields.originPort,       ['[data-field="PortOfLoading"]','#PortOfLoading'],                     true],
      [fields.destinationPort,  ['[data-field="PortOfDischarge"]','#PortOfDischarge'],                 true],
      [fields.cargoDescription, ['[data-field="GoodsDescription"]','#GoodsDescription'],               false],
      [fields.grossWeight?.toString(), ['[data-field="TotalWeight"]','#TotalWeight'],                  false],
      [fields.pieces?.toString(),      ['[data-field="Pieces"]','#Pieces'],                            false],
      [fields.incoterms,        ['[data-field="Incoterms"]','#Incoterms'],                             true],
      [fields.eta,              ['[data-field="ETA"]','#ETA','input[type="date"]'],                    false],
    ];
    const fieldNames = ["shipperName","consigneeName","awbNumber","originPort","destinationPort","cargoDescription","grossWeight","pieces","incoterms","eta"];
    for (let i = 0; i < map.length; i++) {
      const [value, selectors, isSelect] = map[i];
      if (!value) continue;
      const ok = isSelect ? await fillOrSelect(page, selectors, value) : await fill(page, selectors, value);
      ok ? set.push(fieldNames[i]) : failed.push(fieldNames[i]);
    }
    await page.waitForTimeout(800);
    const saved = await saveDraft(page);
    if (!saved) throw new Error("Could not save draft — form may not have loaded");
    await page.waitForTimeout(2000);
    const jobNumber     = await getJobNumber(page);
    const screenshotPath = await captureScreenshot(page, "air_import_" + (jobNumber || "unknown"));
    logger.info("Air Import draft created", { jobNumber, fieldsSet: set.length, fieldsFailed: failed.length });
    return { success: true, jobNumber: jobNumber || undefined, screenshotPath, fieldsSet: set, fieldsFailed: failed };
  } catch (err: any) {
    const screenshotPath = await captureScreenshot(page, "air_import_error").catch(() => undefined);
    logger.error("Air Import failed", { error: err.message });
    return { success: false, error: err.message, screenshotPath, fieldsSet: set, fieldsFailed: failed };
  }
}
