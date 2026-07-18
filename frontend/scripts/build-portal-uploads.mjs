import { chromium } from "@playwright/test";
import { copyFile, mkdir, readFile, readdir } from "node:fs/promises";
import { resolve } from "node:path";

const root = resolve(process.cwd(), "..");
const uploadDir = resolve(root, "docs/portal-uploads");
await mkdir(uploadDir, { recursive: true });

const escapeHtml = (value) =>
  value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");

const browser = await chromium.launch();

async function writePdf(path, title, sections) {
  const page = await browser.newPage();
  const body = sections
    .map(
      ({ heading, content }, index) =>
        `<section class="${index ? "new-page" : ""}"><h2>${escapeHtml(heading)}</h2><pre>${escapeHtml(content)}</pre></section>`,
    )
    .join("\n");
  await page.setContent(`<!doctype html>
    <html><head><meta charset="utf-8"><style>
      @page { size: A4; margin: 16mm; }
      body { color:#172033; font-family:Arial,sans-serif; }
      h1 { font-size:25px; margin:0 0 22px; }
      h2 { color:#342c7d; font-size:17px; margin:0 0 12px; }
      pre { white-space:pre-wrap; overflow-wrap:anywhere; font:9px/1.45 "DejaVu Sans Mono",monospace; }
      .new-page { page-break-before:always; }
    </style></head><body><h1>${escapeHtml(title)}</h1>${body}</body></html>`);
  await page.pdf({
    path,
    format: "A4",
    printBackground: true,
    displayHeaderFooter: true,
    headerTemplate: "<span></span>",
    footerTemplate: '<div style="width:100%;font:8px Arial;color:#777;text-align:center"><span class="pageNumber"></span> / <span class="totalPages"></span></div>',
    margin: { top: "16mm", right: "16mm", bottom: "17mm", left: "16mm" },
  });
  await page.close();
}

const design = await readFile(resolve(root, "DESIGN_DECISIONS.md"), "utf8");
await writePdf(resolve(uploadDir, "Design_Decisions.pdf"), "Design Decisions Document", [
  { heading: "Four Tricky Parts", content: design },
]);

const report = await readFile(resolve(root, "parse_quality_report.md"), "utf8");
await writePdf(resolve(uploadDir, "Parse_Quality_Report.pdf"), "Parse Quality Report", [
  { heading: "Parse Evaluation", content: report },
]);

const outputDir = resolve(root, "output");
const outputNames = (await readdir(outputDir))
  .filter((name) => name === "summary.md" || name.endsWith("_shortlist.md"))
  .sort((a, b) => (a === "summary.md" ? -1 : b === "summary.md" ? 1 : a.localeCompare(b)));
const outputs = await Promise.all(
  outputNames.map(async (name) => ({
    heading: name,
    content: await readFile(resolve(outputDir, name), "utf8"),
  })),
);
await writePdf(resolve(uploadDir, "Sample_Output.pdf"), "Sample Shortlisting Output", outputs);

await copyFile(resolve(root, "requirements.txt"), resolve(uploadDir, "requirements.txt"));
await browser.close();

console.log(uploadDir);
