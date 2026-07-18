import { chromium } from "@playwright/test";
import { readFile, readdir } from "node:fs/promises";
import { resolve } from "node:path";
import { renderMarkdown } from "./render-markdown.mjs";

const root = resolve(process.cwd(), "..");
const outputDir = resolve(root, "output");
const screenshotDir = resolve(root, "docs/screenshots");
const pdfPath = resolve(root, "docs/InternLoom_Submission_Outputs.pdf");

const escapeHtml = (value) =>
  value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");

const outputNames = (await readdir(outputDir))
  .filter((name) => name === "summary.md" || name.endsWith("_shortlist.md"))
  .sort((a, b) => (a === "summary.md" ? -1 : b === "summary.md" ? 1 : a.localeCompare(b)));
const screenshotNames = (await readdir(screenshotDir))
  .filter((name) => name.endsWith(".png"))
  .sort();

const outputSections = await Promise.all(
  outputNames.map(async (name) => {
    const content = await readFile(resolve(outputDir, name), "utf8");
    return `<section class="document"><h2 class="file-title">${escapeHtml(name)}</h2><article>${renderMarkdown(content)}</article></section>`;
  }),
);

const screenshotSections = await Promise.all(
  screenshotNames.map(async (name) => {
    const image = await readFile(resolve(screenshotDir, name));
    const source = `data:image/png;base64,${image.toString("base64")}`;
    return `<section class="screenshot"><h2>${escapeHtml(name)}</h2><img src="${source}" alt="${escapeHtml(name)}"></section>`;
  }),
);

const parseReport = await readFile(resolve(root, "parse_quality_report.md"), "utf8");
const html = `<!doctype html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page { size: A4; margin: 14mm; }
  * { box-sizing: border-box; }
  body { margin: 0; color: #172033; font-family: Arial, sans-serif; }
  .cover { min-height: 250mm; display: flex; flex-direction: column; justify-content: center; text-align: center; page-break-after: always; }
  h1 { margin: 0; font-size: 34px; }
  h2 { margin: 0 0 12px; color: #342c7d; font-size: 18px; }
  .subtitle { margin-top: 12px; color: #596174; font-size: 16px; }
  .document { page-break-before: always; }
  article h1 { font-size:22px; margin:0 0 14px; }
  article h2 { font-size:17px; margin:18px 0 8px; }
  article h3 { font-size:14px; margin:15px 0 7px; }
  .file-title { padding-bottom:8px; border-bottom:2px solid #c8c4ff; }
  p, li { font-size:9.5px; line-height:1.45; }
  ul, ol { padding-left:19px; }
  table { width:100%; border-collapse:collapse; margin:10px 0 15px; font-size:8px; }
  th, td { border:1px solid #d9dce7; padding:4px; text-align:left; vertical-align:top; }
  th { background:#efefff; color:#342c7d; }
  code { background:#f0f1f5; border-radius:3px; padding:1px 3px; font:8.5px "DejaVu Sans Mono",monospace; }
  pre { padding:8px; background:#f5f6f8; white-space:pre-wrap; overflow-wrap:anywhere; font:8px/1.4 "DejaVu Sans Mono",monospace; }
  pre code { padding:0; background:transparent; }
  blockquote { margin:10px 0; padding:6px 10px; border-left:3px solid #8e86e8; background:#f5f4ff; }
  .screenshot { page-break-before: always; }
  .screenshot img { display: block; max-width: 100%; max-height: 245mm; margin: 0 auto; object-fit: contain; }
</style>
</head>
<body>
  <section class="cover">
    <h1>InternLoom Resume Shortlisting Engine</h1>
    <p class="subtitle">Current outputs, parse report, and interface screenshots</p>
    <p class="subtitle">Generated 18 July 2026</p>
  </section>
  <section class="document"><h2>parse_quality_report.md</h2><pre>${escapeHtml(parseReport)}</pre></section>
  ${outputSections.join("\n")}
  ${screenshotSections.join("\n")}
</body>
</html>`;

const browser = await chromium.launch();
const page = await browser.newPage();
await page.setContent(html, { waitUntil: "load" });
await page.pdf({
  path: pdfPath,
  format: "A4",
  printBackground: true,
  displayHeaderFooter: true,
  headerTemplate: "<span></span>",
  footerTemplate: '<div style="width:100%;font:8px Arial;color:#777;text-align:center"><span class="pageNumber"></span> / <span class="totalPages"></span></div>',
  margin: { top: "14mm", right: "14mm", bottom: "16mm", left: "14mm" },
});
await browser.close();
console.log(pdfPath);
