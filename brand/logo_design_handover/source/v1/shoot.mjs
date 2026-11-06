// Render HTML boards to PNG:  node shoot.mjs <dir> [file.html ...]
// Needs the `playwright` package resolvable (NODE_PATH or a local install).
import { chromium } from "playwright";
import { readdirSync } from "node:fs";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const dir = resolve(process.argv[2] || ".");
const files = process.argv.slice(3).length ? process.argv.slice(3) : readdirSync(dir).filter((f) => f.startsWith("board-") && f.endsWith(".html"));
const browser = await chromium.launch({ channel: "chromium" });
const page = await browser.newPage({ viewport: { width: 1200, height: 900 }, deviceScaleFactor: 1 });
for (const f of files) {
  await page.goto(pathToFileURL(join(dir, f)).href);
  await page.waitForTimeout(250);
  const el = (await page.$("#board")) || page;
  await el.screenshot({ path: join(dir, f.replace(/\.html$/, ".png")) });
  console.log("shot", f);
}
await browser.close();
