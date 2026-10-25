import { defineConfig } from "@playwright/test";
import { fileURLToPath } from "node:url";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  forbidOnly: Boolean(process.env.CI),
  retries: 0,
  timeout: 60_000,
  globalTimeout: 300_000,
  expect: { timeout: 15_000 },
  reporter: [
    ["list"],
    ["html", { outputFolder: "playwright-report", open: "never" }],
  ],
  use: {
    baseURL: "http://127.0.0.1:4178",
    browserName: "chromium",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    contextOptions: { reducedMotion: "reduce" },
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1280, height: 800 } } },
    {
      name: "mobile",
      use: {
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
  webServer: [
    {
      command:
        "uv run --locked uvicorn tactix.main:app --host 127.0.0.1 --port 8018",
      cwd: fileURLToPath(new URL("../backend", import.meta.url)),
      url: "http://127.0.0.1:8018/health",
      env: { TACTIX_CORS_ORIGINS: "http://127.0.0.1:4178" },
      reuseExistingServer: false,
      timeout: 90_000,
    },
    {
      command:
        "node node_modules/vite/bin/vite.js preview --host 127.0.0.1 --port 4178 --strictPort",
      url: "http://127.0.0.1:4178",
      reuseExistingServer: false,
      timeout: 30_000,
    },
  ],
});
