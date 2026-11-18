import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  testMatch: "**/*.spec.mjs",
  timeout: 30_000,
  expect: { timeout: 10_000 },
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["list"], ["html", { outputFolder: "playwright-report", open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:4319",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command: "node serve.mjs",
      url: "http://127.0.0.1:4319/health",
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      command: "python -m vibe.playground --port 4320",
      url: "http://127.0.0.1:4320/health",
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
  ],
});
