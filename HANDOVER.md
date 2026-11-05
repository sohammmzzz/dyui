# DyUI — Handover for a new session

Paste this whole file into a new Claude Code session (or tell it: "read HANDOVER.md, SPEC.md
and CONTINUE.md in the repo, then continue").

## The project
**DyUI — "Chatbots that answer in interfaces."** A Python framework (think Streamlit/Gradio, but
for chatbots): `pip install dyui`, write one `app.py`, run `dyui run app.py`, get a professional,
calm, animated chat app (frontend + backend). The headline feature: **the LLM renders UI
components** (tables, charts, cards, forms, buttons…) inline in its replies. DyUI auto-generates
a system-prompt section describing the component catalog from pydantic models, parses the model's
streamed output, validates it, and renders it. Developers add their own components in Python
(`@app.component`) and the prompt grows automatically. pip package first; npm package later.

- Repo: `github.com/sohammmzzz/dyui` — branch **`claude/friendly-cerf-om5ed0`** (all work is here, pushed).
- Owner's priorities: **design is everything** (calm, premium, subtle micro-animations everywhere,
  distinctive typography), launch-ready branding, working code that is always committed + pushed.
- Budget-conscious: prefer doing focused work directly; use subagents only with strict file ownership.

## Read these first (in the repo)
1. `SPEC.md` — **source of truth**: brand (§1), repo layout (§2), Python API (§3), HTTP/SSE protocol (§4),
   LLM fence format + structured "tools" mode (§5), 39-component catalog (§6), web app (§7), docs site (§8).
2. `CONTINUE.md` — status table + prioritized backlog.
3. `README.md` — the public pitch (launch-ready, with real screenshots).

## What exists and works (verified)
| Area | Path | State |
|---|---|---|
| Core runtime | `python/dyui/{app,chat,html,cli,demo}.py`, `server/`, `store/` | ✅ App + decorators, Chat (history/session/send/step/ask/set_title), all SPEC §4 routes + SSE, SQLite/memory store, CLI (`run`, `demo`, `new`, `catalog`, `claude\|gemini\|codex init`, `version`) |
| Components + genui | `python/dyui/ui/`, `python/dyui/genui/` | ✅ 38 pydantic component models, catalog → prompt (`fence`/`tools`), strict JSON schemas + `render_*` tool defs, streaming `FenceParser`, validation, history serialization |
| LLM layer | `python/dyui/llm/` | ✅ `dyui.llm.stream` for OpenAI, Anthropic, Ollama, Groq, OpenRouter, Together, DeepSeek, Gemini, Mistral, xAI; `ui_mode="tools"` strict render loop |
| LangGraph | `python/dyui/integrations/langgraph.py` | ✅ `emit()` + `stream()` |
| Templates/examples | `python/dyui/templates/`, `examples/` | ✅ written; LLM examples not run with real keys |
| Web app | `web/` (React 19 + Vite + TS 7, `motion`) | ✅ shell (sidebar, welcome, streaming, composer, uploads, regenerate/edit, feedback, themes, mock mode `?mock=1`) + all 39 components (`web/src/components/dyui/`), fixtures, gallery page |
| Brand | `brand/` | ✅ placeholder logo, Instrument Serif wordmark (+dark), README hero (outlined text), screenshots; `brand/tools/` regenerates SVGs |
| CI | `.github/workflows/` | ✅ written (ci / release→PyPI trusted publishing / docs→GitHub Pages); **never run yet** |

**Tests:** 68 Python (`cd python && pytest -q`) + 31 web (`cd web && npx vitest run`) all pass;
`tsc --noEmit` + `vite build` pass. `dyui demo` was verified end-to-end in Chromium (light + dark,
zero console errors): streaming text, stats, chart, table, callout, custom Flight cards with Book
buttons, timeline, quick replies.

## Backlog (do in this order)
1. **Docs site** — `docs/` with Astro Starlight (not started). SPEC §8 has the full IA. Brand it with
   `web/src/styles/tokens.css` + the three fonts; live demos import `web/src/components/dyui`
   (`NodeView`, `staticContext()`) and `web/src/fixtures/nodes.ts`; API reference via griffe.
   README links to `/components/`, `/changelog/`, `/deploy/production/`; GitHub Pages:
   `site: "https://sohammmzzz.github.io"`, `base: "/dyui"` (make base env-configurable).
   `.github/workflows/docs.yml` expects `cd docs && npm ci && npm run build` → `docs/dist`.
2. **Browser-verify the remaining flows**: `chat.ask()` confirm (demo: Lisbon → Book), form submit
   (demo: "File a support ticket"), rating, regenerate/edit, thread switching, reload persistence,
   mobile width; review `web/gallery.html` (every component) in light/dark. Fix visual issues.
3. **Logo redesign** — current mark is a placeholder the owner dislikes. Research: `brand/LOGO_RESEARCH.md`
   (avoid concentric rings, sparkles, petal "blossoms"; one idea, monochrome-first, works at 16px).
   Swap via `brand/*.svg`, `web/src/styles/logo.svg`, `web/public/favicon.svg` (shell renders it only
   through `web/src/shell/Logo.tsx`), regenerate hero with `python brand/tools/brand_svgs.py`.
4. **First CI run green**, then release: configure the PyPI trusted publisher, tag `v0.2.0`.
5. Polish: remove unused `@fontsource-variable/geist` npm dep; verify provider base URLs in
   `python/dyui/llm/_providers.py`; chart palette slots 5/6 (sky/lavender) fail colour-blind separation;
   main JS chunk ~745 kB — consider code-splitting highlight.js/markdown.
6. Later: auto-repair loop for invalid components (`genui.repair_message` exists), partial streaming of
   tool-call args, `dyui-react` npm package from `web/src/components/dyui`, branching, voice, OAuth.

## Setup & commands
```bash
python3 -m venv .venv && .venv/bin/pip install editables hatchling
cd python && DYUI_SKIP_WEB_BUILD=1 ../.venv/bin/pip install -e ".[all,dev]" --no-build-isolation
../.venv/bin/python -m pytest -q                      # run from python/ (pytest config lives there)
cd ../web && npm install && npm run build:py           # builds web → python/dyui/_static
cd .. && .venv/bin/dyui demo --port 8000               # full app, no API key
cd web && npm run dev                                  # http://localhost:5173/?mock=1 (UI only)
```

## Gotchas learned
- Run pytest from `python/`, not the repo root.
- Editable installs need `editables` + `--no-build-isolation`; set `DYUI_SKIP_WEB_BUILD=1` while iterating.
- httpx `ASGITransport` only stores cookies after a response finishes — hit `/api/config` first in tests
  that run a stream and an action concurrently (browsers are fine).
- Don't `pkill -f "<pattern>"` in the same shell command whose text contains the pattern (it kills itself);
  use `kill $(pgrep -f "[d]yui demo")`.
- Timestamps are milliseconds; the shell accepts seconds or ms.
- New threads are created by `POST /api/chat` with `thread_id: null` (runs `on_chat_start`).
- `ctx.interactive` is true only for the latest assistant message; actions resolve optimistically client-side
  and the server persists `props.__resolved__`.
- Thumbs rating sends `{rating: 1 | -1}`.
- A repo stop-hook asks for commit + push at the end of every turn — commit often.
- Commits end with the session attribution trailers the environment provides; never put model names in commits.
