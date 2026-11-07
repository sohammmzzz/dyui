/**
 * The SPA runs under the server's Content-Security-Policy (python/dyui/server: strict
 * script-src with a per-page nonce, see security/vapt-frontend.md) with zero violations.
 */
import { test, expect } from "./fixtures";
import { send, stream, url } from "./fixtures";
import type { Page } from "@playwright/test";

async function watchCsp(page: Page) {
  await page.addInitScript(() => {
    (window as any).__csp = [];
    document.addEventListener("securitypolicyviolation", (e) =>
      (window as any).__csp.push(`${e.violatedDirective} ${e.blockedURI} ${e.sourceFile}:${e.lineNumber}`),
    );
  });
}
const violations = (page: Page): Promise<string[]> => page.evaluate(() => (window as any).__csp);

test("the app runs under the server CSP with zero violations", async ({ page, problems }) => {
  await watchCsp(page);
  const res = await page.goto(url("demo"));
  const policy = (await res!.headerValue("content-security-policy")) ?? "";
  expect(policy).toMatch(/script-src 'self'[^;]*'nonce-/);
  expect(policy).not.toMatch(/unsafe-eval|script-src[^;]*unsafe-inline/);

  const starters = page.getByRole("list", { name: "Suggestions" }).getByRole("button");
  await stream(page, () => starters.first().click()); // the component tour: charts, tables, motion, code
  await send(page, "show me");
  await page.waitForTimeout(1000);
  expect(await violations(page)).toEqual([]);

  // control: the policy really is in force (DevTools-evaluated eval is exempt, so use the DOM)
  const control = await page.evaluate(async () => {
    const s = document.createElement("script");
    s.textContent = "window.__inlineRan = true";
    document.body.append(s);
    await new Promise((r) => setTimeout(r, 200));
    return { ran: !!(window as any).__inlineRan, violations: (window as any).__csp.length };
  });
  expect(control).toEqual({ ran: false, violations: 1 });
  const keep = problems.filter((p) => !/Executing inline script violates/.test(p));
  problems.splice(0, problems.length, ...keep);
});

test("the gallery renders every component under the server CSP", async ({ page, problems }) => {
  // Expected to fail until the server serves gallery.html with a nonce (backend follow-up,
  // security/vapt-frontend.md §6). Playwright reports it once that lands, so the gap can't rot.
  test.fail(true, "gallery.html is served without <meta name=dyui-csp-nonce>");
  await watchCsp(page);
  await page.goto(url("demo", "/gallery.html"));
  await page.waitForTimeout(2500);
  // violations inside srcdoc iframes fire on the iframe's document: check the console too
  const csp = problems.filter((p) => /Content Security Policy/i.test(p));
  problems.splice(0, problems.length);
  expect([...(await violations(page)), ...csp]).toEqual([]);
});

test("developer html scripts run (nonce) and auto-height works under the server CSP", async ({ page, problems }) => {
  await watchCsp(page);
  await page.goto("http://127.0.0.1:8014/");
  await send(page, "devhtml-clean");
  const frame = page.locator("iframe").first();
  await expect(frame).toHaveAttribute("sandbox", "allow-scripts");
  await expect(page.frameLocator("iframe").first().locator("#ok")).toHaveText("script ran");
  await expect.poll(async () => frame.evaluate((el) => el.getBoundingClientRect().height)).toBeGreaterThan(300);
  expect(await violations(page)).toEqual([]);
  expect(problems.filter((p) => /Content Security Policy/i.test(p))).toEqual([]);
});
