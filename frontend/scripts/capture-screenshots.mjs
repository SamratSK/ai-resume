import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { resolve } from "node:path";

const baseURL = process.env.APP_URL ?? "http://127.0.0.1:8000";
const outputDir = resolve(process.cwd(), "../docs/screenshots");
await mkdir(outputDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });

async function capture(name) {
  await page.screenshot({ path: resolve(outputDir, name), fullPage: true });
}

await page.goto(`${baseURL}/#/`);
await page.getByRole("heading", { level: 1 }).waitFor();
await page.waitForTimeout(1200);
await capture("01-home.png");

await page.goto(`${baseURL}/#/jds`);
await page.getByRole("heading", { name: "Job descriptions" }).waitFor();
await capture("02-jobs.png");
await page.getByRole("button", { name: "Paste JD" }).click();
await page.getByRole("dialog").waitFor();
await capture("03-paste-jd.png");
await page.keyboard.press("Escape");

await page.goto(`${baseURL}/#/resumes`);
await page.getByRole("heading", { name: "Resumes" }).waitFor();
await capture("04-resumes.png");

await page.goto(`${baseURL}/#/resumes/res2`);
await page.getByRole("heading", { name: "Ananya Subramanian" }).waitFor();
await page.getByRole("img", { name: "Resume page 1" }).waitFor();
await page.getByRole("button", { name: "Show details for Full name" }).click();
await page.getByRole("button", { name: "Locate on PDF" }).first().click();
await capture("05-resume-evidence.png");

await page.goto(`${baseURL}/#/jds/backend_dev`);
await page.getByRole("heading", { name: "Candidate pool" }).waitFor();
await page.getByText("Ananya Subramanian", { exact: true }).first().waitFor({ timeout: 180_000 });
await capture("06-job-candidate-pool.png");
await page.getByRole("tab", { name: "Chat" }).click();
await capture("07-job-chat.png");

await browser.close();
console.log(`Saved screenshots to ${outputDir}`);
