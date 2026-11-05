# End-to-end tests

Playwright drives Chromium against real DyUI servers: `dyui demo` (port 8011) plus two fixture
apps in `apps/` (`extras.py` on 8012, `gate.py` on 8013). Not part of CI.

```bash
cd web
npm run build:py                      # bundle the app into python/dyui/_static
npx playwright install chromium       # once
DYUI_BIN=../.venv/bin/dyui npm run e2e   # Windows: ../.venv/Scripts/dyui
```

`DYUI_BIN` defaults to `dyui` on your PATH. Servers already running on those ports are reused.
Every test fails on console errors, uncaught page errors, failed requests or 5xx responses.
Screenshots land in `e2e/.results/shots/` and `e2e/.results/gallery/{light,dark}/` (gitignored).
