/** Flows of the built-in `dyui demo` bot. */
import { composer, expect, fresh, lastAssistant, send, settled, stream, test, url } from "./fixtures";

const shot = (name: string, fullPage = false) => ({ path: `e2e/.results/shots/${name}.png`, fullPage });

test("welcome screen, starters and the tour stream components", async ({ page, problems }) => {
  await fresh(page);
  await expect(page.getByRole("heading", { level: 2 })).toContainText("interfaces");
  const starters = page.getByRole("list", { name: "Suggestions" }).getByRole("button");
  await expect(starters).toHaveCount(4);
  await page.waitForTimeout(900); // let the entrance settle before the screenshot
  await page.screenshot(shot("01-welcome"));

  await stream(page, () => starters.first().click());
  const msg = lastAssistant(page);
  await expect(msg.locator("[data-dy-ui='stats']")).toBeVisible();
  await expect(msg.locator("[data-dy-ui='chart'] svg").first()).toBeVisible();
  await expect(msg.locator("[data-dy-ui='plan']")).toBeVisible();
  await expect(msg.getByRole("group", { name: "Suggested replies" })).toBeVisible();
  await page.screenshot(shot("02-tour"));
});

test("quick reply → sales: step, reasoning, stats, chart, table, callout", async ({ page, problems }) => {
  await fresh(page);
  await send(page, "show me");
  await stream(page, () =>
    lastAssistant(page).getByRole("group", { name: "Suggested replies" }).getByRole("button", { name: "Analyze Q3 sales" }).click(),
  );
  const msg = lastAssistant(page);
  await expect(msg.getByRole("table")).toBeVisible();
  await expect(msg).toContainText("Orbit is the only product that shrank");
  await expect(msg).toContainText("Querying the sales warehouse");
  // numeric columns: header text is right-aligned over right-aligned values
  const units = msg.getByRole("columnheader", { name: /Units/ });
  const head = await units.locator("button").boundingBox();
  const label = await units.getByText("Units").boundingBox();
  expect(head && label && head.x + head.width - (label.x + label.width)).toBeLessThan(40);
  // sorting
  await units.locator("button").click();
  await expect(units).toHaveAttribute("aria-sort", /descending|ascending/);
  await page.waitForTimeout(700);
  await page.screenshot(shot("03-sales"));
});

test("Lisbon → Book → chat.ask() confirm → booked, view follows the reply", async ({ page, problems }) => {
  await fresh(page);
  await send(page, "Plan a weekend in Lisbon");
  const msg = lastAssistant(page);
  await expect(msg.getByRole("button", { name: "Book" })).toHaveCount(2);
  // the action stream stays open while chat.ask() waits for the confirm
  await msg.getByRole("button", { name: "Book" }).first().click();
  const confirm = page.getByRole("button", { name: "Book flight" });
  await expect(confirm).toBeVisible();
  await page.waitForTimeout(700);
  await page.screenshot(shot("04-confirm"));
  await confirm.click();
  await expect(page.getByText("You're going to Lisbon")).toBeVisible();
  await settled(page);
  await expect(page.getByText("LX7Q2D is on its way")).toBeInViewport();
  await expect(page.getByRole("button", { name: /Jump to latest/ })).toBeHidden();
  await page.screenshot(shot("05-booked"));
  // the confirm is resolved and can't be used again
  await expect(page.getByRole("button", { name: "Book flight" })).toHaveCount(0);
  // reload keeps the resolved state
  await page.reload();
  await expect(page.getByText("You're going to Lisbon")).toBeVisible();
  await expect(page.getByRole("button", { name: "Book flight" })).toHaveCount(0);
});

test("confirm → cancel path", async ({ page, problems }) => {
  await fresh(page);
  await send(page, "Plan a weekend in Lisbon");
  await lastAssistant(page).getByRole("button", { name: "Book" }).nth(1).click();
  await page.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByText("nothing was booked")).toBeVisible();
  await settled(page);
});

test("support ticket form submit → plan + stars rating", async ({ page, problems }) => {
  await fresh(page);
  await send(page, "File a support ticket");
  const form = lastAssistant(page);
  const submit = form.getByRole("button", { name: "Create ticket" });
  // required field is enforced client-side (no request)
  await submit.click();
  await expect(page.getByText("Routed to Exports")).toHaveCount(0);
  await form.getByLabel("Subject").fill("Exports time out");
  await form.getByLabel("Area").selectOption("Exports");
  await form.getByLabel("Details").fill("CSV export spins forever.");
  await page.screenshot(shot("06-form"));
  await stream(page, () => submit.click());
  await expect(page.getByText("Routed to Exports")).toBeVisible();
  const reply = lastAssistant(page);
  await expect(reply.locator("[data-dy-ui='rating']")).toBeVisible();
  await stream(page, () => reply.getByRole("radio", { name: /^4/ }).click());
  await expect(reply.locator("[data-dy-ui='rating']")).toContainText(/thanks/i);
  await page.screenshot(shot("07-ticket"));
});

test("regenerate, feedback, copy", async ({ page, problems }) => {
  await fresh(page);
  await send(page, "hello");
  const good = lastAssistant(page).getByRole("button", { name: "Good response" });
  const fb = page.waitForResponse((r) => r.url().endsWith("/api/feedback"));
  await good.click();
  expect((await fb).status()).toBe(200);
  await expect(good).toHaveAttribute("aria-pressed", "true");
  await lastAssistant(page).getByRole("button", { name: "Copy" }).click();
  await expect(lastAssistant(page).getByRole("button", { name: "Copied" })).toBeVisible();
  const clip = await page.evaluate(() => navigator.clipboard.readText());
  expect(clip).toContain("Here's the idea");
  await stream(page, () => lastAssistant(page).getByRole("button", { name: "Regenerate" }).click());
  await expect(page.getByRole("article", { name: "Assistant message" })).toHaveCount(1);
  await expect(lastAssistant(page)).toContainText("Here's the idea");
  // feedback survives a reload
  await page.reload();
  await expect(page.getByRole("article", { name: "Assistant message" })).toHaveCount(1);
});

test("edit last user message re-runs the turn", async ({ page, problems }) => {
  await fresh(page);
  await send(page, "hello");
  const user = page.locator(".sh-user").last();
  await user.hover();
  await user.getByRole("button", { name: "Edit" }).click();
  const box = page.getByLabel("Edit message");
  await box.fill("Analyze Q3 sales");
  await stream(page, () => box.press("Enter"));
  await expect(lastAssistant(page).getByRole("table")).toBeVisible();
  await expect(page.locator(".sh-user")).toHaveCount(1);
  await expect(page.locator(".sh-user")).toContainText("Analyze Q3 sales");
  await page.reload();
  await expect(page.locator(".sh-user")).toContainText("Analyze Q3 sales");
  await expect(page.getByRole("article", { name: "Assistant message" })).toHaveCount(1);
});

test("threads: create, switch, rename, delete, reload persistence", async ({ page, problems }) => {
  await fresh(page);
  await send(page, "Plan a weekend in Lisbon");
  const list = page.getByRole("list", { name: "Conversations" }).first();
  const thread = (name: string) => list.getByRole("button", { name, exact: true });
  await expect(thread("Plan a weekend in Lisbon")).toBeVisible();

  await page.getByRole("button", { name: "New chat" }).first().click();
  await expect(page.getByRole("list", { name: "Suggestions" })).toBeVisible();
  await send(page, "Analyze Q3 sales");
  await expect(thread("Analyze Q3 sales")).toBeVisible();

  // switch back
  await thread("Plan a weekend in Lisbon").click();
  await expect(lastAssistant(page)).toContainText("Lisbon in early autumn");

  // reload persists the open thread (URL hash)
  await page.reload();
  await expect(lastAssistant(page)).toContainText("Lisbon in early autumn");
  await expect(lastAssistant(page).getByRole("button", { name: "Book" })).toHaveCount(2);

  // rename
  const item = list.getByRole("listitem").filter({ hasText: "Plan a weekend" });
  await item.hover();
  await item.getByRole("button", { name: /^Rename/ }).click();
  const input = page.getByLabel("Rename chat");
  await input.fill("Lisbon trip");
  await input.press("Enter");
  await expect(thread("Lisbon trip")).toBeVisible();
  await page.reload();
  await expect(thread("Lisbon trip")).toBeVisible();

  // delete
  const renamed = list.getByRole("listitem").filter({ hasText: "Lisbon trip" });
  await renamed.hover();
  await renamed.getByRole("button", { name: /^Delete/ }).click();
  await renamed.getByRole("button", { name: "Delete", exact: true }).click();
  await expect(thread("Lisbon trip")).toHaveCount(0);
  await expect(thread("Analyze Q3 sales")).toBeVisible();
  await page.reload();
  await expect(thread("Lisbon trip")).toHaveCount(0);
  await page.screenshot(shot("08-threads"));
});

test("theme toggle switches and persists", async ({ page, problems }) => {
  await fresh(page);
  const html = page.locator("html");
  await page.getByRole("radio", { name: /Dark/ }).click();
  await expect(html).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(html).toHaveAttribute("data-theme", "dark");
  await send(page, "Analyze Q3 sales");
  await page.waitForTimeout(800);
  await page.screenshot(shot("09-dark-sales"));
  await page.getByRole("radio", { name: /Light/ }).click();
  await expect(html).toHaveAttribute("data-theme", "light");
});

test("mobile width: sidebar becomes a drawer", async ({ page, problems }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fresh(page);
  await page.waitForTimeout(900);
  await page.screenshot(shot("10-mobile-welcome"));
  await send(page, "Plan a weekend in Lisbon");
  await page.screenshot(shot("11-mobile-lisbon"));
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, "no horizontal overflow").toBeLessThanOrEqual(0);
  await page.getByRole("button", { name: "Open sidebar" }).click();
  await expect(page.getByRole("button", { name: "Close sidebar" })).toBeVisible();
  await page.waitForTimeout(600);
  await page.screenshot(shot("12-mobile-drawer"));
  await page.keyboard.press("Escape");
  await expect(page.getByRole("button", { name: "Close sidebar" })).toBeHidden();
});

test("keyboard only: send, Tab to Book, confirm with Enter", async ({ page, problems }) => {
  await fresh(page);
  await composer(page).focus();
  await page.keyboard.type("Plan a weekend in Lisbon");
  await stream(page, () => page.keyboard.press("Enter"));
  let found = false;
  for (let i = 0; i < 80 && !found; i++) {
    await page.keyboard.press("Tab");
    found = await page.evaluate(() => (document.activeElement as HTMLElement | null)?.innerText?.trim() === "Book");
  }
  expect(found, "Book reachable with Tab").toBe(true);
  const ring = await page.evaluate(() => getComputedStyle(document.activeElement as Element).outlineStyle);
  expect(ring, "visible focus ring").not.toBe("none");
  await page.keyboard.press("Enter");
  await expect(page.getByRole("button", { name: "Book flight" })).toBeVisible();
  await page.getByRole("button", { name: "Book flight" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByText("You're going to Lisbon")).toBeVisible();
  await settled(page);
});

test("reduced motion: no blur/transform entrances", async ({ browser }) => {
  const ctx = await browser.newContext({ reducedMotion: "reduce" });
  const page = await ctx.newPage();
  const errors: string[] = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await page.goto(url("demo"));
  await send(page, "show me");
  await expect(lastAssistant(page).getByRole("group", { name: "Suggested replies" })).toBeVisible();
  const moving = await page.evaluate(() =>
    [...document.querySelectorAll<HTMLElement>(".sh-main *")].filter((el) => {
      const cs = getComputedStyle(el);
      return /blur\((?!0)/.test(cs.filter);
    }).length,
  );
  expect(moving).toBe(0);
  expect(errors).toEqual([]);
  await ctx.close();
});
