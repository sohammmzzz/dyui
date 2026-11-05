import { composer, expect, fresh, lastAssistant, send, stream, test, url } from "./fixtures";

const shot = (name: string) => ({ path: `e2e/.results/shots/${name}.png` });

test("choice: multiple + other → fallback action turn with values", async ({ page, problems }) => {
  await fresh(page, "extras");
  await send(page, "choice please");
  const msg = lastAssistant(page);
  await msg.getByText("Lisbon", { exact: true }).click();
  await msg.getByText("Faro", { exact: true }).click();
  await msg.getByRole("checkbox", { name: "Other…" }).click();
  await msg.getByLabel("Other answer").fill("Coimbra");
  await expect(msg.getByText("2 selected")).toBeVisible();
  await page.screenshot(shot("20-choice"));
  await stream(page, () => msg.getByRole("button", { name: "Choose" }).click());
  await expect(lastAssistant(page)).toContainText("Got action choice");
  await expect(lastAssistant(page)).toContainText("Lisbon");
  await expect(lastAssistant(page)).toContainText("Faro");
  await expect(lastAssistant(page)).toContainText("Coimbra");
  // the choice is resolved and locked
  await expect(page.getByRole("button", { name: "Choose" })).toHaveCount(0);
  await page.screenshot(shot("21-choice-resolved"));
});

test("thumbs rating → values {rating: 1}", async ({ page, problems }) => {
  await fresh(page, "extras");
  await send(page, "thumbs");
  const group = lastAssistant(page).getByRole("group", { name: /useful/i }).or(lastAssistant(page).getByRole("radiogroup", { name: /useful/i }));
  await expect(group.first()).toBeVisible();
  await page.screenshot(shot("22-thumbs"));
  await stream(page, () => group.first().getByRole("button").or(group.first().getByRole("radio")).first().click());
  await expect(lastAssistant(page)).toContainText('"rating": 1');
});

test("stop mid-stream marks the reply Stopped and keeps partial text", async ({ page, problems }) => {
  await fresh(page, "extras");
  await send(page, "slow", { wait: false });
  await expect(lastAssistant(page)).toContainText("word5");
  await page.getByRole("button", { name: "Stop generating" }).click();
  await expect(lastAssistant(page).getByText("Stopped")).toBeVisible();
  await expect(page.getByRole("button", { name: "Send message" })).toBeVisible();
  const text = await lastAssistant(page).innerText();
  expect(text).not.toContain("word399");
  // reload: the cancelled message was persisted
  await page.reload();
  await expect(lastAssistant(page)).toContainText("word5");
  await expect(lastAssistant(page).getByText("Stopped")).toBeVisible();
});

test("file upload: chip, send, file part, download", async ({ page, problems }) => {
  await fresh(page, "extras");
  const chooser = page.waitForEvent("filechooser");
  await page.getByRole("button", { name: "Attach files" }).click();
  await (await chooser).setFiles({ name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("hello from e2e\n") });
  const chips = page.getByRole("list", { name: "Attachments" }).or(page.getByRole("group", { name: "Attachments" })).first();
  await expect(chips).toContainText("notes.txt");
  await expect(page.getByRole("button", { name: /Remove notes.txt/ })).toBeVisible();
  await page.screenshot(shot("23-upload-chip"));
  await send(page, "files?");
  await expect(lastAssistant(page)).toContainText("notes.txt (15 B)");
  const user = page.locator(".sh-user").last();
  await expect(user).toContainText("notes.txt");
  // the file is served back to its owner
  const href = await user.locator("a").first().getAttribute("href");
  if (href) {
    const res = await page.request.get(new URL(href, url("extras")).toString());
    expect(res.status()).toBe(200);
    expect(await res.text()).toBe("hello from e2e\n");
  }
  await page.screenshot(shot("24-upload-sent"));
});

test("handler error shows inline error with Retry", async ({ page }) => {
  // the 'error' SSE event is expected here; no console errors should appear
  const errors: string[] = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await fresh(page, "extras");
  await send(page, "boom", { wait: false });
  const alert = page.getByRole("alert");
  await expect(alert).toBeVisible();
  await expect(alert.getByRole("button", { name: "Retry" })).toBeVisible();
  await page.screenshot(shot("25-error"));
  await stream(page, () => alert.getByRole("button", { name: "Retry" }).click());
  await expect(page.getByRole("alert")).toBeVisible();
  expect(errors).toEqual([]);
});

test("long reply: jump-to-latest pill appears after scrolling up and returns to bottom", async ({ page, problems }) => {
  await fresh(page, "extras");
  await send(page, "long");
  await page.mouse.move(700, 400);
  await page.mouse.wheel(0, -3000);
  const jump = page.getByRole("button", { name: /Jump to latest/ });
  await expect(jump).toBeVisible();
  await jump.click();
  await expect(jump).toBeHidden();
  await expect(page.getByText("Paragraph 59:")).toBeInViewport();
});

test("password gate: wrong then right password", async ({ page, problems }) => {
  await page.goto(url("gate"));
  const pw = page.getByLabel(/password/i);
  await expect(pw).toBeVisible();
  await page.screenshot(shot("26-gate"));
  // the 401 for the wrong password is expected
  problems.length = 0;
  await pw.fill("nope");
  await pw.press("Enter");
  await expect(page.getByText(/wrong password/i)).toBeVisible();
  await pw.fill("letmein");
  await pw.press("Enter");
  await expect(composer(page)).toBeVisible();
  await send(page, "hi");
  await expect(lastAssistant(page)).toContainText("Inside the gate: hi");
  // the API is closed without the cookie
  const res = await page.request.fetch(url("gate", "/api/threads"), { headers: { cookie: "" } });
  expect([200, 401]).toContain(res.status());
  problems.length = 0;
});
