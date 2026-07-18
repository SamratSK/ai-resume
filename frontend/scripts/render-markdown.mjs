import { spawnSync } from "node:child_process";
import { resolve } from "node:path";

export function renderMarkdown(markdown) {
  const python = process.env.PYTHON ?? resolve(process.cwd(), "../.venv/bin/python");
  const script = [
    "import sys",
    "from markdown_it import MarkdownIt",
    "renderer = MarkdownIt('commonmark', {'html': False, 'linkify': False}).enable('table')",
    "sys.stdout.write(renderer.render(sys.stdin.read()))",
  ].join("\n");
  const result = spawnSync(python, ["-c", script], {
    input: markdown,
    encoding: "utf8",
    maxBuffer: 10 * 1024 * 1024,
  });
  if (result.status !== 0) {
    throw new Error(result.stderr || "Markdown rendering failed");
  }
  return result.stdout;
}
