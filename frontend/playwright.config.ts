import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 30_000 },
  use: {
    baseURL: "http://127.0.0.1:8000",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  reporter: "line",
});
