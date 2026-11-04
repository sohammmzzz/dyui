# CONTINUE — DyUI 0.2 rewrite: status & backlog

> Hand-off notes for picking the rewrite back up. **`SPEC.md` is the source of truth** for the
> product, Python API, HTTP/SSE protocol, LLM fence format, component catalog and brand.
> Branch: `claude/friendly-cerf-om5ed0`.

## Where things stand

| Area | Path | Status |
|---|---|---|
| Spec | `SPEC.md` | ✅ complete (brand, API, protocol §4, fence format §5, structured "tools" mode §5.0, 39 components §6) |
| Brand | `brand/` | ✅ placeholder logo, wordmark (+dark), README hero (light/dark, outlined text). `brand/tools/` regenerates them. Logo redesign **paused** — see `brand/LOGO_RESEARCH.md` |
| README | `README.md` | ✅ launch-ready copy. ⏳ needs real app screenshots + code samples verified against the final API |
| CI | `.github/workflows/` | ✅ written (ci, release → PyPI trusted publishing, docs → GitHub Pages). ⚠️ see "CI fixes" |
| LLM layer | `python/dyui/llm/` | ✅ `dyui.llm.stream` (OpenAI, Anthropic, Ollama, Groq, OpenRouter, Together, DeepSeek, Gemini, Mistral, xAI), fence + `ui_mode="tools"` strict render loop. 24 offline tests pass |
| LangGraph | `python/dyui/integrations/langgraph.py` | ✅ `emit()` + `stream()`; tested with a real tiny graph |
| Templates / examples | `python/dyui/templates/`, `examples/` | ✅ written against SPEC; **not yet run** (core app missing) |
| Components (Python) | `python/dyui/ui/` | ✅ 38 pydantic models, positional ctors, `to_node()`, prompt signatures, strict `json_schema()`. ⏳ no tests yet |
| genui | `python/dyui/genui/` | ✅ `Catalog` (`prompt(mode)`, `only/without`, `tool_schemas(provider)`, `validate`), streaming `FenceParser` (smoke-tested char-by-char), partial JSON, history serialization. ⏳ no tests yet |
| Store | `python/dyui/store/` | ✅ `Store` protocol, `SQLiteStore`, `MemoryStore`. ⏳ no tests yet |
| **Core runtime** | `python/dyui/` | ❌ **not written**: `__init__.py`, `app.py`, `chat.py`, `server/`, `html.py`, `cli.py`, `demo.py`, `pyproject.toml`, `hatch_build.py`, core tests |
| Web shell | `web/src/{App,main}.tsx`, `web/src/shell/`, `web/src/lib/` | ✅ all SPEC §7 shell features, mock transport (`?mock=1`, 5 scripted demos), 31 vitest tests pass. ⏳ never visually verified in a browser |
| Web components | `web/src/components/dyui/`, `web/src/fixtures/`, `web/src/gallery.tsx` | 🟡 written for all groups; at hand-off the build had errors (`NodeView.tsx` imports a missing `./registry`; type errors in `interactive/Choice.tsx`, `interactive/Form.tsx` — passing a `(v, fallback?)` helper straight to `.map`). Check `npx tsc --noEmit` first |
| Docs site | `docs/` | ❌ not started (Astro Starlight, SPEC §8) |

## Backlog (in order)

### P0 — make it run
1. **Web build green**: `cd web && npx tsc --noEmit && npx vite build`. Fix the component-library errors above (add `components/dyui/registry.ts(x)` mapping every `ui` name → component; fix the `.map` helper calls).
2. **Finish py-core** (SPEC §3, §4, §9):
   - `dyui/__init__.py`: public re-exports (`App`, `Chat`, `Message`, `Action`, `Feedback`, `File`, `Starter`, `Component`, `Reasoning`, `ui`, `catalog`), `dyui.llm` exposed lazily via module `__getattr__`.
   - `chat.py`: `Message`, `File`, `Action`, `Feedback`, `Chat` (`history`, `messages`, `session`, `send`, `step`, `ask`, `set_title`), `Step` context manager.
   - `app.py`: `App(...)` options, decorators (`on_message`, `on_chat_start`, `on_action`, `on_feedback`, `component`), all handler shapes (async gen / sync gen / coroutine / sync), yield types (str → `FenceParser`, components, `Reasoning`, `{"ui":…}` dicts), live `app.catalog`, ASGI `__call__`.
   - `server/`: every route + SSE event in SPEC §4. The shell already speaks it: new threads arrive via `POST /api/chat` with `thread_id: null` (run `on_chat_start` there); `ctx.interactive` is only true for the latest assistant message; actions resolve optimistically client-side, server persists `props.__resolved__` and emits a `ui` upsert; timestamps in **seconds**. Heartbeat, disconnect → cancel → `cancelled`, regenerate/edit, auto-title, `dyui_uid` cookie, password gate, uploads, SPA static serving from `dyui/_static` with a friendly fallback page.
   - `html.py` (traversal-safe templates → sandboxed `html` node), `cli.py` (`run`, `new`, `demo`, `catalog`, `claude|gemini|codex init`, `version`), `demo.py` (no-API-key showcase streaming fenced text through the real parser).
   - `pyproject.toml` (hatchling, extras `openai`/`anthropic`/`langgraph`/`all`/`dev`, script `dyui`, wheel artifacts `dyui/_static/**`) + `hatch_build.py` (skip with `DYUI_SKIP_WEB_BUILD`; build `../web` and copy `dist` → `dyui/_static`).
   - Contracts other code already relies on: `catalog.tool_schemas("openai"|"anthropic")` and `catalog.prompt(mode="fence"|"tools")` (exist), tool names prefixed `render_`; examples/templates assume `ui.Stats(items=[…])`, `ui.Plan(title=, items=[…])`, `ui.Sources(items=[…])`, `ui.Form(fields=[…])`, `ui.Choice(question, options)`, `ui.Callout(text, level=, title=)`, `ui.Confirm(title, text=, confirm_label=)`, `ui.Chart(kind=, labels=, series=)`, `ui.Card(…, subtitle=, actions=[…])`, `ui.Button(…, style=)`.
   - Tests: ui/genui (chunk-boundary fuzz for the parser), store, server routes via httpx ASGITransport (SSE, ask round-trip, forged action → 400, regenerate/edit, auth, upload), CLI.
3. **Integrate & verify**: `cd web && npm run build:py` → `pip install -e "python[all,dev]"` → `dyui demo` → Playwright E2E (send, components stream, action, regenerate, threads, reload persists, light/dark, mobile). Run every example/template once.

### P1 — launch
4. **Docs site** (`docs/`, Astro Starlight, SPEC §8): brand theme (Instrument Serif/Sans, tokens from `web/src/styles/tokens.css`), landing page with a live mock chat, one page per component using `web/src/fixtures/nodes.ts` + `NodeView`, API reference generated with griffe. Slugs the README links to: `/components/`, `/changelog/`, `/deploy/production/`. For GitHub Pages: `site: "https://sohammmzzz.github.io"`, `base: "/dyui"` (make base env-configurable for other hosts).
5. **README**: add real screenshots (light/dark `<picture>`) under the hero; re-check every code sample against the final API.
6. **CI fixes**: `pytest` from the repo root fails collection — run `cd python && pytest -q` in `ci.yml`, or set `[tool.pytest.ini_options] pythonpath = ["."]`, `asyncio_mode = "auto"` in `pyproject.toml`.
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
cd python && ../.venv/bin/python -m pytest -q # LLM + LangGraph tests today
```

Suggested approach: one agent per area with strict file ownership (as in this run), all building
against `SPEC.md`; integrate with a real browser before polishing.
