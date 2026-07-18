import { chromium } from "@playwright/test";
import { copyFile, mkdir, readFile, readdir } from "node:fs/promises";
import { resolve } from "node:path";
import { renderMarkdown } from "./render-markdown.mjs";

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
      ({ heading, content, image }, index) =>
        `<section class="${index ? "new-page" : ""}"><h2 class="file-title">${escapeHtml(heading)}</h2>${
          image ? `<img class="screenshot" src="${image}" alt="${escapeHtml(heading)}">` : `<article>${renderMarkdown(content)}</article>`
        }</section>`,
    )
    .join("\n");
  await page.setContent(`<!doctype html>
    <html><head><meta charset="utf-8"><style>
      @page { size: A4; margin: 16mm; }
      body { color:#172033; font-family:Arial,sans-serif; }
      h1 { font-size:25px; margin:0 0 22px; }
      h2 { color:#342c7d; font-size:17px; margin:18px 0 8px; }
      h3 { color:#27304a; font-size:14px; margin:16px 0 7px; }
      .file-title { margin:0 0 16px; padding-bottom:8px; border-bottom:2px solid #c8c4ff; }
      p, li { font-size:10px; line-height:1.5; }
      ul, ol { padding-left:20px; }
      table { width:100%; border-collapse:collapse; margin:10px 0 16px; font-size:8.5px; }
      th, td { border:1px solid #d9dce7; padding:5px; text-align:left; vertical-align:top; }
      th { background:#efefff; color:#342c7d; }
      code { background:#f0f1f5; border-radius:3px; padding:1px 3px; font:9px "DejaVu Sans Mono",monospace; }
      pre { padding:9px; background:#f5f6f8; white-space:pre-wrap; overflow-wrap:anywhere; font:8.5px/1.45 "DejaVu Sans Mono",monospace; }
      pre code { padding:0; background:transparent; }
      blockquote { margin:10px 0; padding:6px 10px; border-left:3px solid #8e86e8; background:#f5f4ff; }
      .screenshot { display:block; max-width:100%; max-height:238mm; margin:0 auto; object-fit:contain; }
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
const screenshotDir = resolve(root, "docs/screenshots");
const screenshotNames = (await readdir(screenshotDir)).filter((name) => name.endsWith(".png")).sort();
const screenshots = await Promise.all(
  screenshotNames.map(async (name) => ({
    heading: `Interface screenshot: ${name}`,
    image: `data:image/png;base64,${(await readFile(resolve(screenshotDir, name))).toString("base64")}`,
  })),
);
await writePdf(
  resolve(uploadDir, "Sample_Output.pdf"),
  "Sample Shortlisting Output and Interface Screenshots",
  [...outputs, ...screenshots],
);

await copyFile(resolve(root, "requirements.txt"), resolve(uploadDir, "requirements.txt"));
await browser.close();

console.log(uploadDir);
