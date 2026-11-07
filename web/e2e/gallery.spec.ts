/** Every component in gallery.html renders without errors, in light and dark. */
import { expect, test, url } from "./fixtures";

// registry.ts GROUPS, in order (36 LLM components + developer-only html/invalid)
const ALL = [
  "markdown", "callout", "code", "quote", "sources", "badges", "divider",
  "table", "stat", "stats", "keyvalue", "chart", "progress", "timeline", "json",
  "image", "gallery", "video", "audio", "file", "link_preview",
  "buttons", "quick_replies", "choice", "form", "confirm", "rating",
  "card", "grid", "tabs", "accordion", "carousel", "list",
  "step", "reasoning", "plan",
  "html", "invalid",
];

// A 1200×800 stand-in for any third-party image the fixtures reference: the test
// stays hermetic and isn't at the mercy of remote CORP headers or the network.
const IMG = Buffer.from(
  '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800"><defs><linearGradient id="g" x2="1" y2="1">' +
    '<stop stop-color="#5B4FE0"/><stop offset="1" stop-color="#14A394"/></linearGradient></defs><rect width="1200" height="800" fill="url(#g)"/></svg>',
);

for (const theme of ["light", "dark"] as const) {
  test(`gallery renders every component (${theme})`, async ({ page, problems }) => {
    test.setTimeout(150_000);
    await page.route(/^https?:\/\/(?!127\.0\.0\.1|localhost)/, (route) => {
      const type = route.request().resourceType();
      if (type === "image") return route.fulfill({ status: 200, contentType: "image/svg+xml", body: IMG });
      return route.fulfill({ status: 204, body: "" });
    });
    await page.goto(url("demo", "/gallery.html"));
    await page.getByRole("button", { name: theme, exact: true }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    const items = page.locator(".g-item");
    await expect(items.first()).toBeVisible();
    const names = await items.locator(".g-name").allInnerTexts();
    expect(names).toEqual(ALL);
    for (let i = 0; i < names.length; i++) {
      const item = items.nth(i);
      await item.scrollIntoViewIfNeeded();
      await page.waitForTimeout(450); // entrance + count-up animations
      const box = await item.boundingBox();
      expect(box && box.height, `${names[i]} has height`).toBeGreaterThan(20);
      const overflow = await item.evaluate((el) => el.scrollWidth - el.clientWidth);
      expect(overflow, `${names[i]} horizontal overflow`).toBeLessThanOrEqual(1);
      await item.screenshot({ path: `e2e/.results/gallery/${theme}/${String(i).padStart(2, "0")}-${names[i]}.png` });
    }
    // a loaded image keeps a real frame (regression: the frame collapsed to 3×2 px)
    const frame = page.locator("#c-image .dy-image-frame");
    await expect(frame).toHaveAttribute("data-loaded", "");
    const fb = await frame.boundingBox();
    expect(fb && fb.width, "image frame width").toBeGreaterThan(300);
    expect(fb && fb.height, "image frame height").toBeGreaterThan(150);
    const invalid = await page.locator(".g-item:not(#c-invalid) [data-dy-ui='invalid']").count();
    expect(invalid, "no built-in fixture falls back to invalid").toBe(0);

    expect(await page.locator('meta[name="dyui-csp-nonce"]').count()).toBe(1);
  });
}
