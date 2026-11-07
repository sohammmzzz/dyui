/**
 * Frontend security suite: renders hostile model output (e2e/apps/hostile.py) and asserts
 * that nothing executes and no dangerous URL / handler / spoofed state reaches the DOM.
 * Not part of CI — see e2e/README.md.
 */
import { test as base, expect, type Page } from "@playwright/test";
import { composer, settled } from "./fixtures";

const ORIGIN = "http://127.0.0.1:8014";

const test = base.extend<{ dialogs: string[] }>({
  dialogs: async ({ page }, use) => {
    const dialogs: string[] = [];
    page.on("dialog", async (d) => {
      dialogs.push(d.message());
      await d.dismiss();
    });
    await use(dialogs);
    expect(dialogs, "a payload executed (dialog opened)").toEqual([]);
  },
});

/** Everything in the DOM that could execute or leave the app. */
async function audit(page: Page) {
  return page.evaluate(() => {
    const bad: string[] = [];
    const all = Array.from(document.querySelectorAll("*"));
    for (const el of all) {
      for (const a of Array.from(el.attributes)) {
        const n = a.name.toLowerCase();
        const v = a.value.trim();
        if (n.startsWith("on")) bad.push(`handler ${el.tagName}[${n}]`);
        if (["href", "src", "poster", "action", "formaction", "xlink:href", "data"].includes(n)) {
          if (/^\s*(javascript|data|vbscript|file|blob):/i.test(v)) bad.push(`scheme ${el.tagName}[${n}]=${v.slice(0, 60)}`);
          if (/^\s*(\/\/|\/\\|\\)/.test(v)) bad.push(`protocol-relative ${el.tagName}[${n}]=${v.slice(0, 60)}`);
        }
        if (["href", "src", "poster"].includes(n) && v) {
          // what the browser would actually load / navigate to
          let host = "";
          try {
            host = new URL(v, document.baseURI).hostname;
          } catch {
            /* unparsable: browsers ignore it */
          }
          if (/evil\.example/.test(host)) bad.push(`offsite ${el.tagName}[${n}]=${v.slice(0, 60)}`);
        }
        if (n === "srcdoc") bad.push(`srcdoc ${el.tagName}`);
      }
      if (el.tagName === "A") {
        const a = el as HTMLAnchorElement;
        if (a.target === "_blank" && !/noopener/.test(a.rel)) bad.push(`tabnabbing ${a.href}`);
        if (a.href && !/^(https?:|mailto:)/.test(a.protocol + "")) bad.push(`link protocol ${a.protocol}`);
      }
    }
    for (const s of Array.from(document.querySelectorAll("body script, iframe, object, embed, base, meta[http-equiv], form[action]"))) {
      bad.push(`element ${s.tagName}`);
    }
    if (({} as Record<string, unknown>).polluted !== undefined) bad.push("prototype polluted");
    return bad;
  });
}

async function ask(page: Page, text: string) {
  const res = page.waitForResponse((r) => r.url().includes("/api/chat") && r.request().method() === "POST");
  await composer(page).fill(text);
  await composer(page).press("Enter");
  await (await res).finished();
  await settled(page);
  await page.waitForTimeout(800); // let lazy highlighters / images settle
}

test.describe("hostile content", () => {
  test("control: the harness detects execution and bad attributes", async ({ page, dialogs }) => {
    await page.goto(ORIGIN + "/");
    await page.evaluate(() => {
      setTimeout(() => alert("control"), 0);
      const a = document.createElement("a");
      a.href = "javascript:void(0)";
      a.setAttribute("onclick", "x()");
      document.body.append(a);
    });
    await expect.poll(() => dialogs.length).toBe(1);
    expect(await audit(page)).toEqual(expect.arrayContaining(["handler A[onclick]", "scheme A[href]=javascript:void(0)"]));
    dialogs.length = 0;
  });

  test("config, starters and thread titles render as text", async ({ page, dialogs }) => {
    await page.goto(ORIGIN + "/");
    await expect(page.getByText("desc <img src=x onerror=alert('cfg')>")).toBeVisible();
    expect(await audit(page)).toEqual([]);
    await ask(page, "hello <img src=x onerror=alert('user')>");
    await expect(page.getByText("echo: hello <img src=x onerror=alert('user')>")).toBeVisible();
    expect(await page.title()).toContain("</title>");
    expect(await audit(page)).toEqual([]);
    expect(dialogs).toEqual([]);
  });

  for (const mode of ["md", "fence", "dict"]) {
    test(`model output via ${mode} cannot execute or smuggle URLs`, async ({ page, dialogs }) => {
      await page.goto(ORIGIN + "/");
      await ask(page, mode);
      const findings = await audit(page);
      expect(findings).toEqual([]);
      // a model can't pre-resolve an interactive component
      await expect(page.getByText("Approved (spoofed)")).toHaveCount(0);
      // look-alike hosts are not treated as YouTube embeds
      await expect(page.getByText(/loads from youtube-nocookie\.com/)).toHaveCount(0);
      // hover everything: lazy handlers / tooltips must not execute either
      for (const el of await page.locator(".dy-chart svg path, .dy-chart svg rect").all()) await el.hover({ force: true }).catch(() => {});
      expect(dialogs).toEqual([]);
      await page.screenshot({ path: `e2e/.results/shots/security-${mode}.png`, fullPage: true });
    });
  }

  test("developer html stays inside its sandbox", async ({ page, dialogs, context }) => {
    const popups: string[] = [];
    context.on("page", (p) => popups.push(p.url()));
    const navs: string[] = [];
    page.on("framenavigated", (f) => f === page.mainFrame() && navs.push(f.url()));
    await page.goto(ORIGIN + "/");
    await ask(page, "devhtml");
    const frame = page.locator("iframe").first();
    await expect(frame).toHaveAttribute("sandbox", "allow-scripts");
    const probe = page.frameLocator("iframe").first().locator("#probe");
    await expect(probe).toContainText("alert:");
    const report = await probe.textContent();
    // every escape hatch is closed (alert is silently ignored without allow-modals)
    for (const k of ["parentDom:blocked", "cookie:blocked", "storage:blocked"]) expect(report).toContain(k);
    await page.waitForTimeout(1500);
    expect(popups, "popups opened").toEqual([]);
    expect(navs.every((u) => u.startsWith(ORIGIN)), `top navigated: ${navs.join(", ")}`).toBe(true);
    expect(page.url().startsWith(ORIGIN)).toBe(true);
    // the auto-height channel ignores spoofed / out-of-range messages
    const h = await frame.evaluate((el) => el.getBoundingClientRect().height);
    expect(h).toBeGreaterThanOrEqual(24);
    expect(h).toBeLessThan(400);
    expect(dialogs).toEqual([]);
  });

  test("uploaded file names render as text", async ({ page, dialogs, request }) => {
    await page.goto(ORIGIN + "/");
    await page.locator('input[type="file"]').setInputFiles({
      name: `"><img src=x onerror=alert('fname')>.png`,
      mimeType: "image/png",
      buffer: Buffer.from("89504e470d0a1a0a", "hex"),
    });
    await ask(page, "file");
    expect(await audit(page)).toEqual([]);
    expect(dialogs).toEqual([]);
    void request;
  });
});
