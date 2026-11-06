/**
 * End-to-end suite against real DyUI servers (not part of CI).
 *
 *   cd web && npm run build:py          # bundle the app into the python package
 *   npm run e2e                         # starts `dyui demo` + fixture apps, runs Chromium
 *
 * DYUI_BIN points at the dyui executable (default: `dyui` on PATH, e.g. an activated venv).
 */
import { defineConfig, devices } from "@playwright/test";

const bin = process.env.DYUI_BIN || "dyui";
const server = (cmd: string, port: number) => ({
  command: `${bin} ${cmd} --port ${port}`,
  url: `http://127.0.0.1:${port}/api/config`,
  reuseExistingServer: !process.env.CI,
  timeout: 60_000,
  // the CLI banner prints non-ASCII; Windows pipes default to cp1252
  env: { PYTHONIOENCODING: "utf-8", PYTHONUTF8: "1" },
  stdout: "ignore" as const,
  stderr: "pipe" as const,
});

export const PORTS = { demo: 8011, extras: 8012, gate: 8013 };

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  outputDir: "./e2e/.results",
  use: {
    ...devices["Desktop Chrome"],
    viewport: { width: 1280, height: 860 },
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    permissions: ["clipboard-read", "clipboard-write"],
  },
  webServer: [
    server("demo", PORTS.demo),
    server("run e2e/apps/extras.py --no-reload", PORTS.extras),
    server("run e2e/apps/gate.py --no-reload", PORTS.gate),
  ],
});
