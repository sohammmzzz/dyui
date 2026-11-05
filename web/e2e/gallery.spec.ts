/** Every component in gallery.html renders without errors, in light and dark. */
import { expect, test, url } from "./fixtures";

for (const theme of ["light", "dark"] as const) {
  test(`gallery renders every component (${theme})`, async ({ page, problems }) => {
    test.setTimeout(120_000);
    await page.goto(url("demo", "/gallery.html"));
    await page.getByRole("button", { name: theme, exact: true }).click();
    await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
    const items = page.locator(".g-item");
    await expect(items.first()).toBeVisible();
    const count = await items.count();
    expect(count).toBeGreaterThanOrEqual(39);
    // the fallback renderer must not appear for any built-in fixture
    const names = await items.locator(".g-name").allInnerTexts();
    for (let i = 0; i < count; i++) {
      const item = items.nth(i);
      await item.scrollIntoViewIfNeeded();
      await page.waitForTimeout(450); // entrance + count-up animations
      const box = await item.boundingBox();
      expect(box && box.height, `${names[i]} has height`).toBeGreaterThan(20);
      // nothing overflows the item horizontally
      const overflow = await item.evaluate((el) => el.scrollWidth - el.clientWidth);
      expect(overflow, `${names[i]} horizontal overflow`).toBeLessThanOrEqual(1);
      await item.screenshot({ path: `e2e/.results/gallery/${theme}/${String(i).padStart(2, "0")}-${names[i]}.png` });
    }
    const invalid = await page.locator(".g-item:not(#c-invalid) [data-dy-ui='invalid']").count();
    expect(invalid, "no built-in fixture falls back to invalid").toBe(0);
  });
}
