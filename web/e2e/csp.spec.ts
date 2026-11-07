/**
 * The SPA must run under the recommended Content-Security-Policy (security/vapt-frontend.md).
 * The policy is injected into HTML responses here, so this guards the frontend's
 * CSP-readiness whether or not the server sends one yet.
 */
import { test, expect } from "./fixtures";
import { send, stream, url } from "./fixtures";

export const RECOMMENDED_CSP = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' https: data: blob:",
  "media-src 'self' https: blob:",
  "font-src 'self' data:",
  "connect-src 'self'",
  "frame-src https://www.youtube-nocookie.com https://player.vimeo.com",
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

test("the app runs under the recommended CSP with zero violations", async ({ page, problems }) => {
  await page.route("**/*", async (route) => {
    const req = route.request();
    if (req.resourceType() !== "document") return route.continue();
    const res = await route.fetch();
    await route.fulfill({ response: res, headers: { ...res.headers(), "content-security-policy": RECOMMENDED_CSP } });
  });
  await page.addInitScript(() => {
    (window as any).__csp = [];
    document.addEventListener("securitypolicyviolation", (e) =>
      (window as any).__csp.push(`${e.violatedDirective} ${e.blockedURI} ${e.sourceFile}:${e.lineNumber}`),
    );
  });
  await page.goto(url("demo"));
  const starters = page.getByRole("list", { name: "Suggestions" }).getByRole("button");
  await stream(page, () => starters.first().click()); // the component tour: charts, tables, motion, code
  await send(page, "show me");
  await page.waitForTimeout(1000);
  const violations: string[] = await page.evaluate(() => (window as any).__csp);
  expect(violations).toEqual([]);
  expect(problems.filter((p) => /Content Security Policy/i.test(p))).toEqual([]);
  // control: the policy really is in force (DevTools-evaluated eval is exempt, so use the DOM)
  const ran = await page.evaluate(async () => {
    const s = document.createElement("script");
    s.textContent = "window.__inlineRan = true";
    document.body.append(s);
    await new Promise((r) => setTimeout(r, 200));
    return { ran: !!(window as any).__inlineRan, violations: (window as any).__csp.length };
  });
  expect(ran).toEqual({ ran: false, violations: 1 });
  // the control's own (expected) console report is not a problem
  const keep = problems.filter((p) => !/Executing inline script violates/.test(p));
  problems.splice(0, problems.length, ...keep);
});

test("developer html (srcdoc) under the recommended CSP", async ({ page }) => {
  await page.route("**/*", async (route) => {
    if (route.request().resourceType() !== "document" || !route.request().isNavigationRequest()) return route.continue();
    const res = await route.fetch();
    await route.fulfill({ response: res, headers: { ...res.headers(), "content-security-policy": RECOMMENDED_CSP } });
  });
  await page.goto("http://127.0.0.1:8014/");
  await page.locator("#dy-composer").fill("devhtml");
  await page.locator("#dy-composer").press("Enter");
  const probe = page.frameLocator("iframe").first().locator("#probe");
  await expect(probe).toBeVisible();
  await page.waitForTimeout(1500);
  // srcdoc documents inherit the page's CSP, so developer scripts are blocked unless the
  // server relaxes script-src; record the behaviour for the report.
  test.info().annotations.push({ type: "srcdoc-scripts", description: (await probe.textContent()) ?? "" });
});
