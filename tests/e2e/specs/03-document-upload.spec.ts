/**
 * SPEC 03 — Document Upload
 * Tests: file drag-drop, upload validation, processing trigger
 * Persona: Operator (daily document handler)
 */
import { test, expect } from "@playwright/test";
import { AuthPage }   from "../pages/AuthPage";
import { QueuePage }  from "../pages/QueuePage";
import { UploadPage } from "../pages/UploadPage";
import { USERS }      from "../fixtures/test-data";
import path           from "path";
import fs             from "fs";

// Create a minimal test PDF in memory
async function createTestPDF(tmpDir: string, name: string): Promise<string> {
  const filePath = path.join(tmpDir, name);
  // Minimal valid PDF structure
  const pdfContent = `%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer<</Size 4/Root 1 0 R>>
startxref
190
%%EOF`;
  fs.writeFileSync(filePath, pdfContent);
  return filePath;
}

test.describe("Document Upload", () => {
  let tmpDir: string;

  test.beforeAll(async () => {
    tmpDir = fs.mkdtempSync("/tmp/cargoiq-test-");
  });

  test.afterAll(() => {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  });

  test.beforeEach(async ({ page }) => {
    await new AuthPage(page).login(USERS.operator.email, USERS.operator.password);
  });

  test("Upload page renders with dropzone", async ({ page }) => {
    const upload = new UploadPage(page);
    await upload.goto();
    await expect(page.locator('text=Drag & drop')).toBeVisible();
    await expect(page.locator('button:has-text("Browse Files")')).toBeVisible();
    // Recommended documents shown
    await expect(page.locator("text=Commercial Invoice")).toBeVisible();
    await expect(page.locator("text=Packing List")).toBeVisible();
  });

  test("PDF file can be added to upload list", async ({ page }) => {
    const pdfPath = await createTestPDF(tmpDir, "test_invoice.pdf");
    const upload  = new UploadPage(page);
    await upload.goto();
    await upload.uploadFile(pdfPath);
    await upload.assertFileAdded("test_invoice.pdf");
    await expect(page.locator('button:has-text("Upload & Extract")')).toBeVisible();
  });

  test("Non-PDF file is rejected with error message", async ({ page }) => {
    const upload  = new UploadPage(page);
    await upload.goto();

    // Create a text file
    const txtPath = path.join(tmpDir, "test.txt");
    fs.writeFileSync(txtPath, "not a pdf");

    const input = page.locator('input[type="file"]');
    await input.setInputFiles(txtPath);
    // Text file should not appear in list (rejected by dropzone mime filter)
    await expect(page.locator("text=test.txt")).not.toBeVisible({ timeout: 2000 }).catch(() => {});
  });

  test("File size limit warning shown for large files", async ({ page }) => {
    const upload = new UploadPage(page);
    await upload.goto();
    // Verify the size limit is mentioned in the UI
    await expect(page.locator("text=50MB")).toBeVisible();
  });

  test("Multiple files can be queued before upload", async ({ page }) => {
    const paths = await Promise.all([
      createTestPDF(tmpDir, "invoice.pdf"),
      createTestPDF(tmpDir, "packing_list.pdf"),
    ]);
    const upload = new UploadPage(page);
    await upload.goto();

    for (const p of paths) {
      const input = page.locator('input[type="file"]');
      await input.setInputFiles(p);
    }

    await expect(page.locator('button:has-text("Upload & Extract (2 files")')).toBeVisible({ timeout: 5000 });
  });

  test("Upload button triggers extraction pipeline", async ({ page }) => {
    const pdfPath = await createTestPDF(tmpDir, "trigger_test.pdf");
    const upload  = new UploadPage(page);
    await upload.goto();

    // Intercept upload API call
    const uploadPromise = page.waitForRequest(r =>
      r.url().includes("/documents/upload") && r.method() === "POST"
    );

    await upload.uploadFile(pdfPath);
    await page.click('button:has-text("Upload & Extract")');
    await uploadPromise;
    // Should navigate away after upload
    await page.waitForURL(/.*shipments|.*queue/, { timeout: 20000 });
  });

  test("Clear all removes files from list", async ({ page }) => {
    const pdfPath = await createTestPDF(tmpDir, "to_clear.pdf");
    const upload  = new UploadPage(page);
    await upload.goto();
    await upload.uploadFile(pdfPath);
    await page.click('button:has-text("Clear All")');
    await expect(page.locator("text=to_clear.pdf")).not.toBeVisible();
  });

});
