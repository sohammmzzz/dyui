// Render SVG/HTML files to PNG with headless Chromium (Playwright).
//
//   NODE_PATH=<dir with playwright>/node_modules node brand/tools/render.cjs jobs.json
//
// jobs.json: [{ "src": "a.svg", "out": "a.png", "width": 1200, "height": 630,
//               "scale": 1, "bg": "transparent" }, ...]   (paths relative to jobs.json)
// An .svg is shown as an <img> at width x height (exactly how GitHub and browsers use it);
// an .html page is shot at its #board element.
const { chromium } = require("playwright");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");

(async () => {
  const jobsFile = path.resolve(process.argv[2]);
  const base = path.dirname(jobsFile);
  const jobs = JSON.parse(fs.readFileSync(jobsFile, "utf8"));
  let browser;
  try {
    browser = await chromium.launch();
  } catch {
    browser = await chromium.launch({ channel: "chrome" });
  }
  for (const j of jobs) {
    const src = path.resolve(base, j.src);
    const out = path.resolve(base, j.out);
    fs.mkdirSync(path.dirname(out), { recursive: true });
    const ctx = await browser.newContext({
      viewport: { width: Math.ceil(j.width || 1200), height: Math.ceil(j.height || 800) },
      deviceScaleFactor: j.scale || 1,
      colorScheme: j.scheme || "light",
    });
    const page = await ctx.newPage();
    if (src.endsWith(".html")) {
      await page.goto(pathToFileURL(src).href);
      await page.evaluate(() => document.fonts && document.fonts.ready);
      await page.waitForTimeout(200);
      const el = (await page.$("#board")) || page;
      await el.screenshot({ path: out });
    } else {
      const bg = j.bg || "transparent";
      // a temp page on the file origin, so the <img> may load a file: URL
      const tmp = out + ".tmp.html";
      fs.writeFileSync(
        tmp,
        `<html><body style="margin:0;background:${bg}"><img src="${pathToFileURL(src).href}" ` +
          `style="display:block;width:${j.width}px;height:${j.height}px"></body></html>`,
      );
      await page.goto(pathToFileURL(tmp).href);
      fs.unlinkSync(tmp);
      await page.waitForFunction(() => {
        const i = document.images[0];
        return i && i.complete && i.naturalWidth > 0;
      });
      await page.screenshot({
        path: out,
        omitBackground: bg === "transparent",
        clip: { x: 0, y: 0, width: j.width, height: j.height },
      });
    }
    await ctx.close();
    console.log("rendered", path.relative(base, out));
  }
  await browser.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
