# CONTINUE — DyUI 0.2 rewrite: status & backlog

> Hand-off notes for picking the rewrite back up. **`SPEC.md` is the source of truth** for the
> product, Python API, HTTP/SSE protocol, LLM fence format, component catalog and brand.
> Branch: `claude/friendly-cerf-om5ed0`.

## Where things stand

| Area | Path | Status |
|---|---|---|
| Spec | `SPEC.md` | ✅ complete (brand, API, protocol §4, fence format §5, structured "tools" mode §5.0, 39 components §6) |
| Brand | `brand/` | ✅ placeholder logo, wordmark (+dark), README hero (light/dark, outlined text). `brand/tools/` regenerates them. Logo redesign **paused** — see `brand/LOGO_RESEARCH.md` |
| README | `README.md` | ✅ launch-ready copy + real app screenshots (light/dark). ⏳ re-check code samples against the final API |
| CI | `.github/workflows/` | ✅ written (ci, release → PyPI trusted publishing, docs → GitHub Pages). ⚠️ see "CI fixes" |
| LLM layer | `python/dyui/llm/` | ✅ `dyui.llm.stream` (OpenAI, Anthropic, Ollama, Groq, OpenRouter, Together, DeepSeek, Gemini, Mistral, xAI), fence + `ui_mode="tools"` strict render loop. 24 offline tests pass |
| LangGraph | `python/dyui/integrations/langgraph.py` | ✅ `emit()` + `stream()`; tested with a real tiny graph |
| Templates / examples | `python/dyui/templates/`, `examples/` | ✅ written against SPEC; `dyui new --template basic` tested; LLM examples not run (need API keys) |
| Components (Python) | `python/dyui/ui/` | ✅ 38 pydantic models, positional ctors, `to_node()`, prompt signatures, strict `json_schema()`. ⏳ no tests yet |
| genui | `python/dyui/genui/` | ✅ `Catalog` (`prompt(mode)`, `only/without`, `tool_schemas(provider)`, `validate`), streaming `FenceParser` (smoke-tested char-by-char), partial JSON, history serialization. ⏳ no tests yet |
| Store | `python/dyui/store/` | ✅ `Store` protocol, `SQLiteStore`, `MemoryStore`. ⏳ no tests yet |
| **Core runtime** | `python/dyui/` | ✅ `App`, `Chat` (history/session/send/step/ask/set_title), server (all SPEC §4 routes + SSE), `html.py`, CLI (`run`/`demo`/`new`/`catalog`/`init`/`version`), `demo.py`, `pyproject.toml`, `hatch_build.py`. 44 tests pass (`cd python && pytest -q`) |
| Web shell | `web/src/{App,main}.tsx`, `web/src/shell/`, `web/src/lib/` | ✅ all SPEC §7 shell features, mock transport (`?mock=1`), 31 vitest tests pass. E2E-verified against `dyui demo` in Chromium (light + dark, zero console errors) |
| Web components | `web/src/components/dyui/`, `web/src/fixtures/`, `web/src/gallery.tsx` | ✅ all 39 + `invalid`; `tsc` + `vite build` pass; stats/chart/table/callout/card/keyvalue/buttons/timeline/quick_replies verified in the E2E run. ⏳ gallery + remaining components not visually reviewed |
| Docs site | `docs/` | ❌ not started (Astro Starlight, SPEC §8) |

## Backlog (in order)

### P0 — done in this run
Web build green · core runtime written and tested (44 tests) · `dyui demo` verified end to end in a browser.
Remaining checks: run each `examples/*.py` with a real API key; click through `ask()`/form/rating flows in
the browser (covered by API tests, not yet by Playwright); review `web/gallery.html` visually.

### P1 — launch
4. **Docs site** (`docs/`, Astro Starlight, SPEC §8): brand theme (Instrument Serif/Sans, tokens from `web/src/styles/tokens.css`), landing page with a live mock chat, one page per component using `web/src/fixtures/nodes.ts` + `NodeView`, API reference generated with griffe. Slugs the README links to: `/components/`, `/changelog/`, `/deploy/production/`. For GitHub Pages: `site: "https://sohammmzzz.github.io"`, `base: "/dyui"` (make base env-configurable for other hosts).
5. **README**: add real screenshots (light/dark `<picture>`) under the hero; re-check every code sample against the final API.
6. **CI**: `ci.yml` now runs `cd python && pytest -q` (pytest config lives in `python/pyproject.toml`). Confirm the first CI run is green.
7. **Release 0.2.0**: tag `v0.2.0` after configuring the PyPI trusted publisher for `release.yml`.

### P2 — polish
8. **Logo redesign** per `brand/LOGO_RESEARCH.md` (the designer's notes so far: "Speech Drop" read as a generic list/notes icon; the "D-Card" monogram had a construction bug and its header bar looked like a trash can; "Quarter-circle bloom" and "Layered emergence" were unreviewed). Swap in via `brand/*.svg`, `web/src/styles/logo.svg`, `web/public/favicon.svg` (the shell renders it only through `shell/Logo.tsx`), and regenerate the README hero with `python brand/tools/brand_svgs.py` (update its `mark()` function).
9. Remove the now-unused `@fontsource-variable/geist` npm dependency (UI font is Instrument Sans).
10. Verify the provider base URLs in `python/dyui/llm/_providers.py` against current provider docs (written from memory).
11. Visual polish pass on shell + components with Playwright screenshots (`web/gallery.html` shows every component).

### Later (roadmap)
Auto-repair loop for invalid fenced components (`genui.repair_message` helper exists), partial streaming of tool-call args in tools mode, `dyui-react` npm package from `web/src/components/dyui`, conversation branching, voice, artifacts side panel, OAuth.

## How to resume

```bash
python3 -m venv .venv && .venv/bin/pip install fastapi "uvicorn[standard]" pydantic watchfiles python-multipart pytest pytest-asyncio httpx openai anthropic langgraph griffe
cd web && npm install && npm run dev          # http://localhost:5173/?mock=1 (shell with mock backend)
#                                    gallery:  http://localhost:5173/gallery.html
cd python && pip install -e ".[all,dev]" && pytest -q   # 44 tests
cd web && npm run build:py && cd .. && dyui demo    # full app at http://localhost:8000
```

Suggested approach: one agent per area with strict file ownership (as in this run), all building
against `SPEC.md`; integrate with a real browser before polishing.
