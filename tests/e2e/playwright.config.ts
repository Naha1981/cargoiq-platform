import { defineConfig, devices } from "@playwright/test";
import dotenv from "dotenv";
dotenv.config({ path: "../../.env" });

export default defineConfig({
  testDir:   "./specs",
  timeout:   60_000,
  retries:   process.env.CI ? 2 : 1,
  workers:   process.env.CI ? 1 : 2,
  reporter:  [
    ["html", { outputFolder: "../../test-results/html", open: "never" }],
    ["list"],
    ["json", { outputFile: "../../test-results/results.json" }],
  ],
  use: {
    baseURL:        process.env.BASE_URL || "http://localhost:3000",
    screenshot:     "only-on-failure",
    video:          "on-first-retry",
    trace:          "on-first-retry",
    actionTimeout:  15_000,
    navigationTimeout: 30_000,
  },
  projects: [
    {
      name:  "chromium",
      use:   { ...devices["Desktop Chrome"] },
    },
    {
      name:  "mobile-chrome",
      use:   { ...devices["Pixel 7"] },
      testMatch: ["**/09-mobile*.spec.ts"],
    },
  ],
  webServer: process.env.CI ? undefined : [
    {
      command: "cd ../../apps/api && uvicorn main:app --port 8000",
      url:     "http://localhost:8000/health",
      reuseExistingServer: true,
      timeout: 30_000,
    },
    {
      command: "cd ../../apps/web && npm run dev",
      url:     "http://localhost:3000",
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
});
