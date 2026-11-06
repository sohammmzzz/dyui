# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 1.x | ✅ security fixes |
| 0.x | ❌ please upgrade to 1.x |

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Report privately through GitHub: **Security → Report a vulnerability** on
[sohammmzzz/dyui](https://github.com/sohammmzzz/dyui/security/advisories/new)
(GitHub private vulnerability reporting / security advisories). Include:

- the DyUI version (`dyui version`) and Python version,
- a minimal app or request sequence that reproduces it,
- the impact you observed.

You'll get an acknowledgement within a few days. Fixes are released as a patch
version with a GitHub security advisory, and you'll be credited unless you ask
not to be.

## Threat model

DyUI serves a chat UI whose content partly comes from a language model. The
trust boundaries it is built around:

| Source | Trust | What DyUI does |
|---|---|---|
| **Your Python code** (handlers, custom components, `ui.Html`, templates) | Trusted | Runs as-is. Developer-only components (`html`) render in a sandboxed iframe (`allow-scripts`, never same-origin). |
| **The LLM's output** (fenced ```` ```dyui ```` blocks, `render_*` tool calls, LangGraph `emit`) | **Untrusted** — assume prompt injection | Parsed with size, depth and time limits; validated against the component schemas; only built-in, LLM-allowed components; never HTML; URLs restricted to `http(s):`, `mailto:` and the app's own `api/files/…`; invalid output becomes a quiet "couldn't display" chip. The model can't pre-resolve interactive components or declare actions that reach handlers it wasn't given. |
| **The browser / end user** | Untrusted | Anonymous per-browser identity (`dyui_uid`, HttpOnly, SameSite=Lax) scopes every thread, message, file and action. Optional shared password with a signed cookie and a failed-login throttle. Action payloads are taken from the server's copy of the component, not the client. |
| **Other websites** | Untrusted | No CORS. State-changing API calls from other origins (cross-site *and* same-site, e.g. another port on localhost) are refused; JSON routes require `Content-Type: application/json`. A strict Content-Security-Policy (per-response nonce), `X-Frame-Options`/`frame-ancestors`, `nosniff`, `Referrer-Policy` and COOP are sent by default. |
| **Uploaded files** | Untrusted | Size-limited; stored under random ids; served only to their uploader; anything a browser could execute (HTML, SVG, JS…) is served as a download with a sandboxing CSP and `nosniff`. |

### Deployment notes

- **TLS:** put DyUI behind HTTPS in production. Cookies get the `Secure` flag
  when the request scheme is `https` — behind a TLS-terminating proxy run uvicorn
  with `--proxy-headers` and `--forwarded-allow-ips=<proxy ip>` so it sees the
  real scheme and client address (the login throttle keys on the client address).
- **Secret:** set `DYUI_SECRET` (32+ random bytes) when running several
  processes or hosts; otherwise one is generated once in `.dyui/secret`
  (owner-only permissions).
- **Rate limits & quotas:** DyUI bounds request and component sizes but does not
  meter LLM usage or upload volume per user. Anyone who can reach the app can
  start conversations (and spend your LLM budget); use `password=`, an auth
  proxy, and/or rate limiting at your reverse proxy for public deployments.
- **Embedding:** to show the app in an `<iframe>` on another site, list that
  site in `App(embed_origins=[...])`. `App(csp=...)` lets you replace or (not
  recommended) disable the Content-Security-Policy.
