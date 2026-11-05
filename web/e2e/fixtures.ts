import { test as base, expect, type Page } from "@playwright/test";

export const PORTS = { demo: 8011, extras: 8012, gate: 8013 } as const;
export const url = (app: keyof typeof PORTS, path = "/") => `http://127.0.0.1:${PORTS[app]}${path}`;

type Problems = { problems: string[] };

/**
 * Every test fails on console errors, uncaught page errors and failed requests
 * (aborted streams from Stop / navigation are expected and ignored).
 */
export const test = base.extend<Problems>({
  problems: async ({ page }, use) => {
    const problems: string[] = [];
    page.on("console", (m) => {
      if (m.type() === "error") problems.push(`console: ${m.text()}`);
    });
    page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
    page.on("requestfailed", (r) => {
      const err = r.failure()?.errorText ?? "";
      if (/ERR_ABORTED|NS_BINDING_ABORTED|cancelled/i.test(err)) return;
      problems.push(`requestfailed: ${r.method()} ${r.url()} ${err}`);
    });
    page.on("response", (r) => {
      if (r.status() >= 500) problems.push(`http ${r.status()}: ${r.url()}`);
    });
    await use(problems);
    expect(problems, "console errors / failed requests").toEqual([]);
  },
});
export { expect };

export const composer = (page: Page) => page.locator("#dy-composer");

const isStream = (u: string, m: string) => m === "POST" && /\/api\/(chat|action|threads)(\?|$)/.test(u);

/**
 * Run `trigger` and wait for the SSE stream it starts (POST /api/chat|action) to
 * finish, then for the UI to settle. Racing on DOM state alone is flaky: replies
 * from a local server can start and end between two polls.
 */
export async function stream(page: Page, trigger: () => Promise<unknown>) {
  const res = page.waitForResponse((r) => isStream(r.url(), r.request().method()), { timeout: 30_000 });
  await trigger();
  await (await res).finished();
  await settled(page);
}

/** Type a message and send it; by default waits for the full reply. */
export async function send(page: Page, text: string, { wait = true }: { wait?: boolean } = {}) {
  await composer(page).fill(text);
  if (wait) await stream(page, () => composer(page).press("Enter"));
  else await composer(page).press("Enter");
}

/** The latest assistant message. */
export const lastAssistant = (page: Page) => page.getByRole("article", { name: "Assistant message" }).last();

/** Wait until no assistant message is streaming. */
export async function settled(page: Page) {
  // the thread view mounts after the welcome screen's exit animation (AnimatePresence mode="wait")
  await expect(page.locator(".sh-welcome-wrap")).toHaveCount(0);
  await expect(page.locator(".sh-assistant.is-streaming")).toHaveCount(0, { timeout: 30_000 });
  await expect(page.getByRole("button", { name: "Send message" })).toBeVisible();
}

export async function fresh(page: Page, app: keyof typeof PORTS = "demo") {
  await page.goto(url(app));
  await expect(composer(page)).toBeVisible();
}
