# DyUI 1.0 — frontend VAPT report

**Scope:** everything that runs in the browser:
- `web/src/**` (shell, `lib/`, `components/dyui/`),
- the built SPA as served by the Python server (`python/dyui/_static`),
- the gallery page,
- `docs/` (the static docs site, which embeds the same components).

**Baseline:** `28f3459` (release branch after the web QA merge), re-run after merging the backend VAPT work (`0f12840`: CSP with per-page nonce, CSRF 403/415, limits).

**Result:**
- 4 frontend findings fixed (1 Medium, 2 Low, 1 Info) plus 1 correctness bug.
- 1 integration fix required by the new server CSP.
- Nothing executed in any test.
- Everything else listed in §3 was tested and found OK.

## 1. Method and environment

| | |
|---|---|
| OS / runtime | Windows 11, Node 24, Python 3.11, Chromium (Playwright 1.5x, headless). |
| Black box | Real `dyui` servers: `dyui demo` (8011), fixture apps `extras.py` / `gate.py`, and a new **hostile app** `web/e2e/apps/hostile.py` (8014). In the hostile app, the app config (title, description, welcome, placeholder, starters and icons), the thread title, user text, uploaded file names, and **every component** carry XSS / URL-smuggling payloads. Components are delivered three ways: raw markdown, the LLM fence path (streaming parser + validation) and handler-yielded dicts. |
| Detection | `web/e2e/security.spec.ts`:<br>• fails on **any dialog** (every payload calls `alert`);<br>• audits the whole DOM for `on*` attributes;<br>• flags `javascript:` / `data:` / `vbscript:` / `file:` / `blob:` URLs and protocol-relative or backslash URLs in `href` / `src` / `poster` / `action`;<br>• flags any resolved host that is off-site (`evil.example`);<br>• flags `target=_blank` without `noopener`, stray `script` / `iframe` / `object` / `embed` / `base` / `meta[http-equiv]` / `form[action]` elements, and prototype pollution.<br>A **positive control** proves that the harness catches a real dialog and bad attributes. |
| CSP | `web/e2e/csp.spec.ts` runs under the **server's real policy**, counting violations on the page and (through the console) inside iframes:<br>• the component tour plus chart / table / code flows produce zero violations;<br>• the gallery: one known violation, a backend gap (§6.1), tracked as an expected failure;<br>• developer `html` scripts run with the nonce and auto-height works;<br>• **enforcement control:** a DOM-injected inline script is blocked and reported. Playwright-evaluated `eval` is exempt from CSP, so it can't serve as a control. |
| White box | Every `dangerouslySetInnerHTML`, `href` / `src` / `poster` sink, `style` binding, `className` interpolation, `postMessage` listener, storage use and action-firing path in `web/src`; docs `set:html` uses. |
| Supply chain | `npm audit` (prod and dev) on `web/` and `docs/` lockfiles. |

## 2. Findings

| ID | Severity | Finding | Status | Regression tests |
|---|---|---|---|---|
| W-01 | **Medium** | **Mock transport reachable in production.** `?mock=1` switched any deployed app to the scripted demo transport. A crafted link such as `https://bot.company.com/?mock=1` showed a fake conversation and fake config on the company's genuine origin, past the password gate. That makes it a UI-spoofing / phishing aid. No real data is exposed, but the content is shown on a trusted origin. | **Fixed.** `?mock=1` is honoured only in dev builds (`import.meta.env.DEV`); the mock transport is tree-shaken out of the production bundle (−27 kB). | `src/lib/errors.test.ts › wantsMock` |
| W-02 | Low | **Look-alike hosts became video embeds.** `toEmbed` matched `host.endsWith("youtube.com")`, so `evilyoutube.com/watch?v=…` rendered the "YouTube · loads from youtube-nocookie.com" facade. The embed URL is rebuilt from a fixed host and a validated id, so this misleads but doesn't inject. | **Fixed.** Exact hosts only (`youtube.com`, `m.`/`www.`, `music.youtube.com`, `youtu.be`, `youtube-nocookie.com`, `vimeo.com`, `player.vimeo.com`) and http(s) only. | `src/components/dyui/media/Video.test.ts`, `e2e/security.spec.ts` |
| W-03 | Low | **Inline script / style in `index.html`** (theme bootstrap) forced a hash or `'unsafe-inline'` into any CSP. | **Fixed.** Moved to `public/boot.js` and `public/boot.css`; the shipped HTML has no inline script or style. | `e2e/csp.spec.ts` |
| W-04 | Info | **Upload thumbnails used the raw `file.url`** while the link used the vetted URL. The URL is server-generated, so this was defence in depth. | **Fixed.** The thumbnail uses the vetted `safeLink` URL, resolved against the app base. | `e2e/security.spec.ts › uploaded file names` |
| W-05 | Integration (required) | **Developer `html` scripts blocked by the new server CSP.** `srcdoc` iframes inherit the page policy, so the height reporter and developer `<script>`s didn't run. | **Fixed.** `Html.tsx` reads `<meta name="dyui-csp-nonce">` (validated `[A-Za-z0-9+/_=-]`) and stamps the nonce on every `<script>` in the srcdoc, replacing any existing nonce. Sandbox is unchanged (`allow-scripts` only). | `src/components/dyui/developer/Html.test.ts`, `e2e/csp.spec.ts › developer html` |
| B-01 | Bug (correctness) | `appendReasoning` merged a second thinking round into the first reasoning block above the text. The server, and a reload, show two blocks. | **Fixed.** Extends only when the last part is reasoning. | `src/lib/store.test.ts` |
| — | Robustness | Friendly copy for the server's new **403** (cross-origin write refused / uploads disabled) and **415** (non-JSON body). | Added. Every JSON write already sends `Content-Type: application/json`, and a test pins it. | `src/lib/errors.test.ts`, `src/lib/api.test.ts` |

## 3. Tested and found OK

- **Markdown (chat prose and the `markdown` component):**
  - raw HTML is skipped (`<script>`, `<img onerror>`, `<iframe>`, raw `<a href=javascript:>`);
  - `urlTransform` drops `javascript:` in every tested form: upper-case, tab-split, entity-encoded (`&#106;`, `&colon;`), percent-encoded and leading-space;
  - also dropped: `data:` (incl. base64), `vbscript:`, `//host`, `\\host`, reference-style links and autolinks;
  - `/\host` is percent-encoded by the parser to a same-origin path.
- **Code blocks:**
  - highlight.js output is escaped;
  - a hostile fence info string (`js" onmouseover=…`) stays inside `className`.
- **URL props at every nesting depth:** image, gallery, video and poster, audio, file, `link_preview` (url and image), sources and favicons, card image, list image, quote source, table / keyvalue cells, and tabs / accordion children. All pass through `lib/url.ts`. The server applies the same policy, so the client check is defence in depth.
- **Text sinks:** chart titles, labels and series names (SVG text), JSON keys and values, table cells and headers, form labels / placeholders / defaults / field names, badges (colour is allow-listed), timeline, stat, callout, toasts, thread titles (sidebar and `document.title`), user text, file names, app title / description / welcome / placeholder, starter labels and icons. All are React-escaped. Chart colours come from a fixed palette by index.
- **Developer `html` iframe:**
  - `sandbox="allow-scripts"` with no same-origin;
  - the probe couldn't read `parent.document`, cookies or storage, couldn't open popups, submit a form to another origin or navigate top, and didn't raise dialogs;
  - the height channel checks `event.source` plus a random key, and clamps to 24–4000px;
  - spoofed and malformed messages are ignored;
  - the model can't produce `html` by any path (verified on fence and dict paths).
- **Client-side trust:**
  - actions fire only on user gestures;
  - they're disabled while a component is streaming and on non-latest messages;
  - `__resolved__` / `__component__` from the model are stripped server-side, including in partial previews, so "Approved (spoofed)" never renders;
  - quick replies send only on click; no form auto-submits.
- **Links:** every `target=_blank` carries `rel="noopener noreferrer"` (DOM audit over all hostile content). App files resolve under the app base and can't reach another origin (`//`, backslashes, `..`, encoded slashes).
- **Prototype pollution** via `json` (`__proto__`, `constructor.prototype`): none.
- **Storage:** `localStorage` holds only `dyui:theme` and the sidebar state (mock data only in dev). No secrets or PII.
- **Platform:** no service worker; no sourcemaps shipped.
- **Docs:** `set:html` is used only with `inline()`, which escapes every segment of build-time docstrings. The landing demo uses static fixtures.
- **Supply chain:** `npm audit` reports **0 vulnerabilities** for `web/` and `docs/` (production and dev).

## 4. Content-Security-Policy

The SPA needs no `unsafe-eval` and no inline script. Below is the minimal policy it needs, which is what the server now sends. It was verified with zero violations across the demo flows and nonce'd developer HTML; the gallery has one known violation, see §6.1.

```
default-src 'self';
script-src 'self' 'nonce-<per page>';      # nonce only for developer ui.Html scripts
style-src 'self' 'unsafe-inline';          # motion's popLayout <style> + React style attributes
img-src 'self' https: data: blob:;          # model-supplied images/favicons
media-src 'self' https: blob:;
font-src 'self' data:;
connect-src 'self';
frame-src https://www.youtube-nocookie.com https://player.vimeo.com;   # (+ 'self')
object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'self'
```

Developer `ui.Html` can't use inline event-handler attributes (`onclick="…"`) under this policy; `addEventListener` inside a `<script>` works. This is documented in the docs.

## 5. Residual risks

- **Third-party requests from model output.** `img-src https:` is required, so images, favicons and media from model-chosen hosts can leak the viewer's IP and timing to that host. This is by design for a generative-UI chat, and the same applies to any markdown image.
- **`style-src 'unsafe-inline'`** (needed by motion) would let a future HTML-injection bug style the page, but not run script. No injection was found.
- **Developer HTML is trusted.** It runs scripts in an opaque-origin sandbox with the page nonce. Templates must escape untrusted values: `{{ key }}` does, `{{{ key }}}` doesn't.

## 6. Backend follow-ups

1. **`gallery.html` is served without a nonce** (functional, no security impact). The `static` route sends every file other than `index.html` as a plain `FileResponse` with the hash-only CSP and no `<meta name="dyui-csp-nonce">`. On `/gallery.html`, the `html` example's srcdoc height reporter is therefore blocked: one console CSP violation, and the iframe keeps its fallback height. **Fix (python/dyui/server):** run any shipped `*.html` through the same nonce injection as `index.html`, or leave `gallery.html` out of the wheel. Until then, `e2e/gallery.spec.ts` tolerates exactly that message while no nonce meta is present, and `e2e/csp.spec.ts › gallery` is marked `test.fail`, so Playwright flags it as soon as the fix lands.
2. `python/README.md` (the PyPI page) doesn't link to `SECURITY.md`.

Everything else from the backend (CSP with nonce, CSRF 403/415, limits) is consumed as specified.
