// usage: node shoot.cjs page.html out.png [width] [dpr]
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const [html, out, w = '1600', dpr = '2'] = process.argv.slice(2);
  const b = await chromium.launch();
  const p = await b.newPage({ deviceScaleFactor: +dpr, viewport: { width: +w, height: 900 } });
  await p.goto('file://' + path.resolve(html));
  await p.evaluate(() => document.fonts.ready);
  await p.waitForTimeout(400);
  await p.screenshot({ path: out, fullPage: true });
  await b.close();
})();
