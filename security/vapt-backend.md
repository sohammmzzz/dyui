# DyUI 1.0 — backend VAPT report

**Scope:** the Python package `python/dyui/**`:
- `server/` (HTTP, SSE, auth, static), `app.py`, `chat.py`
- `store/`, `genui/` (parser, partial JSON, validation)
- `ui/`, `html.py`, `cli.py`, `llm/`, `integrations/`

The web client was in scope only where it interacts with server behaviour (CSP, CSRF, headers).

**Baseline:** commit `2f399ae`. That release-branch tip already included the 1.0 hardening commit `5b75224`, which covered:
- the `html` component being blocked from LLM output,
- body and upload limits,
- the login throttle,
- action data taken from the server's copy,
- the 409 replay check,
- NaN scrubbing,
- serving uploads as attachments,
- id validation.

This assessment builds on that commit and doesn't repeat it.

**Result:** 12 security findings were fixed (2 High, 2 Medium, 8 Low/Info). Each has a regression test. The final black-box run was **86 checks, 0 findings**. Several functional bugs reported by the code review and web QA were fixed alongside them (§4).

## 1. Method and environment

| | |
|---|---|
| OS / runtimes | Windows 11, CPython 3.11.7. The full suite was also run on CPython 3.10, and with the **minimum** dependency versions (`uv --resolution lowest-direct`). |
| Stack | fastapi 0.162.0, starlette 1.10.0, uvicorn 0.54.0, pydantic 2.14.3, python-multipart 0.0.33, h11 0.16.0 |
| Black box | Real uvicorn servers on 127.0.0.1, using two test apps:<br>• open: SQLite, uploads, a custom component with a `book_flight` action handler, `chat.ask()`, a developer `ui.Html`, and an "echo LLM" that streams the user's text through the fence parser, simulating a fully prompt-injected model;<br>• password-gated: started with untrusted proxy headers.<br>Attacked with scripted `httpx` clients (86 checks), plus `dyui demo` for the UI. |
| Browser | Headless Chromium (Playwright 1.64.1) loading the built web app under the new CSP. Probes covered nonce'd vs. injected scripts and the inheritance of `srcdoc` iframes. |
| White box | Code review of every module in scope; `cProfile` of the parser; in-process probes for recursion depth. |
| Supply chain | `pip-audit` on the resolved environment, and a review of the `pyproject.toml` minimum versions against published advisories. |

## 2. Findings

Severity is CVSS-style: impact on a default deployment, weighed against how easily it can be triggered.
- "LLM-triggerable" means a prompt-injected or misbehaving model can cause it. Anything the user, a web page or a document can put into the model's context counts.
- "Remote" means any visitor can trigger it.

| ID | Severity | Finding | Status | Regression tests |
|---|---|---|---|---|
| V-01 | **High** | **Event-loop DoS from one component line (quadratic streaming parser).** For every chunk, `FenceParser` re-ran `parse_partial`, re-validated the whole node and re-sent it. It also re-scanned the whole unit for every line and re-copied and searched the growing partial line. One reply with a ~20 kB component line (7-character chunks) blocked the event loop for minutes: a concurrent `GET /api/config` timed out after 60 s for every user. The 8 kB case took 8 s and 80 kB was estimated at hours. SSE traffic was also quadratic. LLM-triggerable. | **Fixed.** Incremental depth/string scanner; pending chunks held in a list; partial re-parses throttled geometrically (≥25% growth, or a quiet period of at least 4× the last parse's cost), so total work is linear; previews stop above 64 KiB; components over 512 KiB fail as "too large" and the rest of the block is skipped. A fenceless candidate line is held for at most 64 KiB. **1 MB line: 0.76 s.** Server stays responsive. | `test_vapt.py::test_long_component_line_parses_in_linear_time`, `…partial_previews…`, `…over_size_cap…`, `…ui_key_last…`, `…multiline…`, `…huge_bare_line…`, `…server_stays_responsive…` |
| V-02 | **High** | **Deep nesting → uncaught `RecursionError` or a process crash.** The parser (`json.loads`, `parse_partial`) and validation (pydantic, `has_nonfinite`, `to_json_text`) all recurse. About 200 levels of `card.children` raised an uncaught `RecursionError` that aborted the reply, and `end_message()` re-raised it. With more stack already in use, it was a **fatal C-stack overflow that killed the Python process** on Windows (reproduced under pytest). That's a full outage from one model reply. It also hit `catalog.validate` for dict yields, tools mode and LangGraph `emit`. LLM-triggerable. | **Fixed.** A nesting limit (`MAX_DEPTH = 48` JSON levels) is enforced iteratively, in the streaming scanner and in `validate_instance` before anything recurses. Over-deep components become `invalid` chips with a short, non-recursive `raw`. `RecursionError` is also caught on every decode path. | `test_deep_nesting_in_fence…[30/200/5000]`, `…unterminated_and_bare…`, `…catalog_validate_rejects_deep…`, `…too_deep_is_iterative`, `…dict_yield_and_tools_mode…` |
| V-03 | **Medium** | **CSRF from same-site origins.** The API parsed JSON regardless of `Content-Type`, and relied on `SameSite=Lax`. Lax blocks cross-*site* POSTs but still sends cookies for same-site ones: another port on `localhost` (very common in development) or a sibling subdomain. A `text/plain` POST from `http://localhost:3000` to `/api/chat`, `/api/upload`, `/api/action` or `/api/login` succeeded with the victim's cookies, including on password-protected apps. That let an attacker drive the victim's conversations, spend LLM budget and fire declared actions. Remote, needs a same-site page. | **Fixed** (`_SecurityMiddleware`). Requests with `Sec-Fetch-Site: cross-site` or `same-site` on state-changing `/api` methods get **403**; without fetch metadata, a mismatching `Origin` (or `null`) gets 403. JSON routes require `application/json` (415 otherwise), which forces a CORS preflight that DyUI never grants. Reads are unaffected. | `test_cross_origin_writes_are_refused` (18 cases), `…mismatching_origin…`, `…same_origin_writes_allowed`, `…json_routes_require_json…` |
| V-04 | **Medium** | **Concurrent duplicate actions (TOCTOU).** The 409 "already answered" check read `__resolved__`, then wrote it after several awaits. With the SQLite store, whose operations really yield, concurrent clicks on one *Book* button ran the handler several times (code review: 3 requests gave 200/200/200). Two concurrent answers to `chat.ask()` could also overwrite each other. Remote, against the user's own components; the business impact is double bookings or payments. | **Fixed.** A synchronous check-and-claim per (thread, component) runs right after `check_action`, with no await in between. It's released once `__resolved__` is persisted, and expires after 120 s. The `ask()` path refuses a future that's already done. The losing request gets 409, or an `error` event if it lost inside the stream. | `test_review_fixes.py::test_concurrent_clicks_run_the_action_once[False/sqlite]`, `…concurrent_answers_to_ask…`, `…stale_claims_expire`; black box: 8 concurrent → `[200, 409×7]` |
| V-05 | Low | **No security headers.** There was no CSP, no `X-Frame-Options`/`frame-ancestors` (so interactive *Book*/*Approve* buttons could be clickjacked), no `nosniff` on HTML/API, no `Referrer-Policy`, `COOP` or `Permissions-Policy`, and API responses had no `Cache-Control`. | **Fixed.**<br>• **CSP on `index.html`:** `script-src 'self' 'nonce-<per-response>'`, `object-src 'none'`, `base-uri 'self'`, `form-action 'self'`, `connect-src 'self'`, `frame-src 'self'` plus the YouTube-nocookie and Vimeo embeds, `frame-ancestors 'self'`, and images/media from any http(s) host. Inline scripts carry the nonce, which is exposed as `<meta name="dyui-csp-nonce">`.<br>• **Other HTML responses:** a hash-based CSP.<br>• **All responses:** `X-Frame-Options: SAMEORIGIN`, `nosniff`, `Referrer-Policy: same-origin`, COOP `same-origin`, and a restrictive `Permissions-Policy`.<br>• **`/api` responses:** `Cache-Control: no-store`.<br>• **New options:** `App(embed_origins=[...])` (validated) and `App(csp=True/str/False)`. In Chromium, nothing in the app violates the policy apart from the `html` component scripts that need the frontend nonce follow-up (§5); an injected script without the nonce is blocked. | `test_html_gets_nonce_csp_and_hardening_headers`, `test_api_headers`, `test_csp_options`, `test_embed_origins_validated`, `test_csp_option_rejects_header_injection`, `test_inline_script_hashes` |
| V-06 | Low | **Weak handling of the session-signing secret.** `.dyui/secret` was written non-atomically with default permissions (0644 on POSIX, so readable by other local users). Concurrent workers could each generate a different secret, which made auth cookies valid on only some workers. | **Fixed.** Created with `O_CREAT\|O_EXCL`, mode `0600`, the winner's value re-read on a race, and a short or corrupt secret replaced. `DYUI_SECRET` is still preferred. | `test_secret_created_once_owner_only_and_shared` |
| V-07 | Low | **Password-length timing side channel.** `hmac.compare_digest` was called on inputs of different lengths. | **Fixed:** fixed-length SHA-256 digests are compared instead. | `test_login_compares_fixed_length_digests` |
| V-08 | Low | **Dependency floors allowed known-vulnerable releases:**<br>• starlette < 0.49.1 (CVE-2025-62727: Range-header DoS in `FileResponse`, which DyUI uses for `/api/files`; also CVE-2024-47874 and CVE-2025-54121);<br>• python-multipart < 0.0.27 (CVE-2024-53981, CVE-2026-40347, CVE-2026-42561);<br>• h11 < 0.16 (CVE-2025-43859).<br>Separately, `pydantic>=2.6` was below what the code needs (the import fails before 2.10). | **Fixed:** direct floors `starlette>=0.49.1`, `python-multipart>=0.0.27`, `h11>=0.16.0`, `fastapi>=0.120.1`, `pydantic>=2.10`; dev floors `pytest>=8.3` and `pytest-asyncio>=0.24`. The suite passes on Python 3.10 at these minimum runtime versions, apart from 2 tests that need the optional `openai` extra, which that environment didn't install. `pip-audit`: no known vulnerabilities in runtime dependencies (only the venv's own pip/setuptools are flagged). | lowest-direct run (§1) |
| V-09 | Low | **`on_chat_start` session lost** (integrity). `POST /api/chat` with `thread_id: null` ran `on_chat_start`, which saved the session. `on_message` then got a Chat built from the stale thread dict, saw `{}`, and overwrote the stored session. | **Fixed:** `Chat._save_session` keeps the shared thread dict current. | `test_session_from_on_chat_start_reaches_on_message_and_persists[False/sqlite]` |
| V-10 | Low | **Feedback handler robustness.** An exception in `on_feedback` returned a bare 500, the session it changed was never saved, and `chat.send()` there went to a queue nothing reads. | **Fixed:** the exception is logged and the response is 200; the session is saved; a warning is logged if the handler tries to send. | `test_feedback_handler_session_saved_and_send_warned`, `test_failing_feedback_handler_is_not_a_500` |
| V-11 | Info | **Orphaned "streaming" messages.** `chat.ask()` persists the message mid-stream. After a crash or restart, it reloaded as streaming forever. | **Fixed:** live message ids are tracked, and `GET /api/threads/{id}` reports persisted `streaming` messages that aren't live as `cancelled`. | `test_orphaned_streaming_message_shows_cancelled`, `test_streaming_status_rewrite_only_for_orphans` |
| V-12 | Info | **Server banner.** `Server: uvicorn` was sent on every response. | **Fixed** for `dyui run`/`dyui demo` (`server_header=False`). People who run `uvicorn app:app` directly should pass `--no-server-header`. | `test_serve_uses_drive_aware_split_for_reload` (checks the flag) |

## 3. Tested and found OK (no change needed)

- **AuthZ / IDOR**, using two separate `dyui_uid` identities on every route:
  - read, rename and delete a thread;
  - read a file; attach another user's file id to a message;
  - edit another thread's message; feedback; action.

  All return 404, 400 or a silent drop. Messages are scoped by thread in both stores.
- **Password gate:**
  - All 10 protected `/api` routes return 401 without the cookie.
  - Forged cookies and non-ASCII cookies return 401, not 500.
  - The throttle locks out after 10 failures, and spoofed `X-Forwarded-For` doesn't help when the proxy isn't trusted.
- **Injection:**
  - SQL injection through titles and ids: all queries are parameterised, and dynamic SQL uses only whitelisted fragments.
  - CR/LF in titles and upload filenames: Starlette percent-encodes `filename*`.
  - Title escaping in the served HTML.
- **Traversal:** static routes (`..`, `%2f`, `%2e%2e`, backslashes), `/api/files`, `/api/logo` (developer-configured). Upload ids are random, and stored paths are never taken from the client.
- **Uploads:**
  - Over-limit uploads (`max_upload_mb`) get 413, as do JSON bodies over 1 MiB, before buffering; chunked bodies too.
  - HTML/SVG/JS are served as `attachment` with a sandboxing CSP.
  - Mislabelled content gets `nosniff`.
- **LLM trust boundary** (fence mode, dict yields, nesting through card/grid/tabs/accordion):
  - `html`/`invalid` can't be produced.
  - `javascript:`, `JaVaScRiPt:`, whitespace-prefixed, `data:`, `vbscript:`, protocol-relative, backslash-host and `file:` URLs are all rejected.
  - Model-supplied `__resolved__` and `__component__` are stripped.
  - `invalid` chips carry `raw` as text, capped at 4000 characters.
  - The model can only declare actions on its own components, and those route to `on_message` or to the handler for that name with the server's own data. Values are user input by design.
- **Information disclosure:**
  - Handler exceptions return `"<ExceptionClass>: something went wrong while replying."`. No message, path or traceback reaches the client; it's logged server-side.
  - API 404s are clean, and there are no directory listings.
  - A missing upload field returns FastAPI's 422, which names only the field.
- **Lifecycle:**
  - An abandoned `chat.ask()` stream cleans up `app._pending`.
  - Replaying an answered component returns 409.
  - No CORS headers are sent.
- **`ui.Html(template=...)` path safety:** see F-01.

## 4. Functional bugs fixed in the same pass (code review and QA)

| ID | Bug | Fix | Tests |
|---|---|---|---|
| F-01 | `ui.Html(template="cards/x.html")` rendered the *path text*, because `_finish_node` passed the path to `render_template` as template source. | New `dyui.html.load_template()`:<br>• **Where it looks:** `<root>/templates/` and then `<root>/`, where root is `template_root=` if given, else the app's own directory (registered by `App()`), else the working directory.<br>• **What it refuses:** absolute paths, drive paths, `..`/backslash escapes, null bytes, non-`.html`/`.htm` files, and symlinks resolving outside the root.<br>`html_template()` uses the same loader. The docstring is corrected, and `template`/`props`/`template_root` never reach the client. | `test_vapt.py::test_html_template_*` (12 traversal variants + symlink) |
| F-02 | Parser fences:<br>(A) `Hi ```dyui` (opener not on its own line), then a lone ```` ``` ````, opened a code block that swallowed the rest of the message;<br>(B) `~~~dyui … ~~~` leaked the fences;<br>(C) any ```` ``` ```` closed a ```` ```` ```` code block. | CommonMark fence model (char + length + info); only a matching fence closes. `~~~` is supported for `dyui`/`json` and code. Inline ```` ```dyui ```` openers are recognised, with the partial tail held back mid-line so it never leaks. A lone fence right after a fenceless component line is swallowed. | 6 new fixtures in the every-split-point fuzz test, plus `test_inline_opener…`, `test_tilde_fences…`, `test_only_a_matching_fence…`, `test_stray_fence…`, `test_backticks_in_prose_still_stream` |
| F-03 | `dyui run C:\proj\app.py:app` split on the drive colon, which silently disabled reload and picked the wrong reload dir. | Shared, drive-aware `split_target()`. | `test_split_target`, `test_serve_uses_drive_aware_split_for_reload` |
| F-04 | `hatch_build.py` skipped the web build whenever any `_static/index.html` existed, so local builds could ship a stale UI. | Rebuilds when `_static` is missing or older than any web input; `DYUI_SKIP_WEB_BUILD` and `DYUI_FORCE_WEB_BUILD` are still honoured. | `test_hatch_rebuilds_stale_static` |
| F-05 | AppConfig lacked the upload limit that the web client shows. | `max_upload_mb` added (`null` when uploads are disabled). | `test_config_reports_upload_limit` |
| F-06 | A demo star rating fell through to the "I only know a few tricks" reply. | `@app.on_action("rating")` thank-you handler. | `test_demo_rating_gets_a_thank_you` |

## 5. Frontend follow-ups (outside this agent's files)

1. **Required: `web/src/components/dyui/developer/Html.tsx` must use the CSP nonce.** `srcdoc` iframes inherit the page's CSP (verified in Chromium). So under the new default policy, the component's own height-reporter script and any `<script>` in developer HTML are blocked. Static HTML still renders.
   - Read the nonce with `document.querySelector('meta[name="dyui-csp-nonce"]')?.content`.
   - Add `nonce="…"` to the reporter `<script>`.
   - Rewrite developer HTML with `html.replace(/<script\b/gi, '<script nonce="…"')`. This is safe because the HTML is developer-authored.

   I verified this exact approach in Chromium: the nonce'd script inside the `srcdoc` ran, and an injected script without the nonce was blocked. Until it lands, apps that need scripts in `html` components can pass `App(csp=False)`.
2. Handle `403 Cross-origin requests are not allowed` and `415` gracefully in `api.ts`. The app itself never triggers them, because it sends JSON from its own origin; a misconfigured reverse proxy that rewrites `Origin` could.
3. Keep `invalid` chips rendering `props.raw` as text (React already escapes it). Keep `react-markdown`'s default `urlTransform`, which drops `javascript:` links in prose. Highlight.js output fed to `dangerouslySetInnerHTML` (`shell/Markdown.tsx`) must stay escaped (highlight.js escapes by default).
4. SPEC/docs:
   - §3.2: add `embed_origins` and `csp`.
   - §4: add the 403/409/413/415/429 responses and `AppConfig.max_upload_mb`.
   - §5.1: describe the component limits (512 KiB, 48 levels, 64 KiB previews).
   - §3.5: describe the template lookup order.
   - Document `SECURITY.md`.

## 6. Residual risks (accepted / documented in SECURITY.md)

- **No per-user quotas or rate limits.** Anyone who can reach the app can start conversations (spending LLM budget), create threads and upload files up to `max_upload_mb` each, with no total quota. Uploads aren't deleted when a thread is. Use `password=`, an auth proxy and/or reverse-proxy rate limits for public deployments.
- **Identity is an anonymous bearer cookie** (`dyui_uid`, HttpOnly, 1 year). Whoever holds it can read that browser's conversations.
  - Password mode is a single shared password; the auth cookie is valid until the password or secret changes, and there's no per-user logout.
  - The login throttle is per process, in memory, and keyed on the client IP. Behind a proxy without `--proxy-headers` every user shares the proxy's IP, so one attacker can lock everyone out for 5 minutes.
- **CSP leaves some room.** It allows `style-src 'unsafe-inline'` and images/media from any http(s) host, which the product needs because models show web images and favicons. A future HTML-injection bug could therefore exfiltrate data via CSS or image requests, though not run script. No such injection was found.
- **Limit side effects.** Fenceless (no ```` ```dyui ````) component lines over 64 KiB now stream as prose. Components over 512 KiB, or nested deeper than 48 JSON levels, render as `invalid` chips.
- **Error events name the exception class** (e.g. `RuntimeError`); this is low value to an attacker. Running `uvicorn app:app` directly still sends the `Server` banner unless `--no-server-header` is passed.
