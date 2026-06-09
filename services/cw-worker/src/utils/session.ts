import { Browser, BrowserContext, Page, chromium } from "playwright";
import { logger } from "./logger";
import { decrypt } from "./crypto";

export interface CWCredentials { serverUrl: string; username: string; password: string; }
export interface CWSession { browser: Browser; context: BrowserContext; page: Page; baseUrl: string; }

const TIMEOUT  = parseInt(process.env.BROWSER_TIMEOUT_MS || "30000");
const HEADLESS = process.env.BROWSER_HEADLESS !== "false";

export function parseCWCredentials(serverUrl: string, credentialsEnc: string): CWCredentials {
  const dec = decrypt(credentialsEnc);
  try {
    const p = JSON.parse(dec);
    return { serverUrl, ...p };
  } catch {
    const [username, password] = dec.split(":");
    return { serverUrl, username, password };
  }
}

export async function createCWSession(creds: CWCredentials): Promise<CWSession> {
  logger.info("Launching browser", { url: creds.serverUrl });
  const browser = await chromium.launch({
    headless: HEADLESS,
    args: ["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
  });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    ignoreHTTPSErrors: true,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(TIMEOUT);
  await page.goto(creds.serverUrl, { waitUntil: "domcontentloaded" });

  const uSelectors = ['input[name="username"]','input[id="username"]','#UserName','input[type="text"]'];
  const pSelectors = ['input[name="password"]','input[id="password"]','#Password','input[type="password"]'];
  const sSelectors = ['button[type="submit"]','input[type="submit"]','#loginBtn','button:has-text("Log In")'];

  let loggedIn = false;
  for (const u of uSelectors) {
    try {
      await page.fill(u, creds.username, { timeout: 3000 });
      for (const p of pSelectors) {
        try {
          await page.fill(p, creds.password, { timeout: 2000 });
          for (const s of sSelectors) {
            try { await page.click(s, { timeout: 2000 }); await page.waitForNavigation({ timeout: 15000 }); loggedIn = true; break; } catch { continue; }
          }
          if (loggedIn) break;
        } catch { continue; }
      }
      if (loggedIn) break;
    } catch { continue; }
  }

  if (!loggedIn) { await browser.close(); throw new Error("CargoWise login failed — check credentials"); }
  logger.info("CW session established", { url: page.url() });
  return { browser, context, page, baseUrl: creds.serverUrl };
}

export async function closeCWSession(session: CWSession): Promise<void> {
  try { await session.browser.close(); } catch { /* ignore */ }
}

export async function captureScreenshot(page: Page, label: string): Promise<string> {
  const dir  = process.env.SCREENSHOT_PATH || "/tmp/cargoiq-screenshots";
  const path = dir + "/" + label + "_" + Date.now() + ".png";
  await page.screenshot({ path, fullPage: false });
  return path;
}
