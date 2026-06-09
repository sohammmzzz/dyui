"""Generate an editable React project that consumes ``dyui-react``.

Used by ``dyui export <name>``. Everything is emitted from string templates so
the package ships no extra data files. The result is a standard Vite + React +
TypeScript app pre-wired to a DyUI stream endpoint, with a sample custom card to
extend.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

_PACKAGE_JSON = """{{
  "name": "{name}",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {{
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  }},
  "dependencies": {{
    "dyui-react": "{dyui_dep}",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  }},
  "devDependencies": {{
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "typescript": "^5.6.0",
    "vite": "^6.0.0"
  }}
}}
"""

_VITE_CONFIG = """import {{ defineConfig }} from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({{
  plugins: [react()],
  server: {{ port: 5173 }},
}});
"""

_TSCONFIG = """{{
  "compilerOptions": {{
    "target": "ES2020",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "noEmit": true
  }},
  "include": ["src"]
}}
"""

_INDEX_HTML = """<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{name}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
"""

_MAIN_TSX = """import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "dyui-react/styles.css";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
"""

_ENV = """# Point at your running `dyui serve` (or FastAPI) endpoint.
VITE_DYUI_URL={stream_url}
"""

_APP_TSX = '''import {{ useMemo, useState }} from "react";
import {{ useDyUIAgent, DyUISurface, createRegistry }} from "dyui-react";
import {{ ExampleCard }} from "./cards/ExampleCard";

const STREAM_URL = import.meta.env.VITE_DYUI_URL ?? "{stream_url}";

export default function App() {{
  const [query, setQuery] = useState("");

  // Register custom cards by the `component` key your agent emits.
  // Built-in cards (text, table, stat, progress, markdown, html, ...) stay available.
  const registry = useMemo(
    () => createRegistry({{ /* my_card: ExampleCard */ }}),
    []
  );

  const {{ cards, tokens, status, error, run, stop, dismiss }} = useDyUIAgent({{
    url: STREAM_URL,
  }});
  const streaming = status === "streaming";

  return (
    <div className="page">
      <header>
        <h1>{name}</h1>
        <p>Dynamic UI streamed from your LangGraph agent via DyUI.</p>
      </header>

      <form
        className="ask"
        onSubmit={{(e) => {{ e.preventDefault(); streaming ? stop() : run(query); }}}}
      >
        <input
          value={{query}}
          onChange={{(e) => setQuery(e.target.value)}}
          placeholder="Message the agent…"
        />
        <button type="submit" className={{streaming ? "stop" : ""}}>
          {{streaming ? "Stop" : "Send"}}
        </button>
      </form>

      {{error ? <div className="error">⚠ {{error}}</div> : null}}

      <main>
        <section>
          <h2>Cards</h2>
          <DyUISurface
            cards={{cards}}
            registry={{registry}}
            onDismiss={{dismiss}}
            empty={{<span>Ask something to see cards appear.</span>}}
          />
        </section>
        {{tokens ? (
          <section>
            <h2>Agent</h2>
            <div className="prose">{{tokens}}</div>
          </section>
        ) : null}}
      </main>
    </div>
  );
}}
'''

_EXAMPLE_CARD = '''import type {{ CardComponentProps }} from "dyui-react";

/**
 * A sample CUSTOM card. Register it in App.tsx:
 *   createRegistry({{ my_card: ExampleCard }})
 * Then emit from your agent:  emit("my_card", {{ title, body }})
 */
export function ExampleCard({{ props }}: CardComponentProps<{{ title?: string; body?: string }}>) {{
  return (
    <div style={{{{ display: "flex", flexDirection: "column", gap: 4 }}}}>
      <strong>{{props.title}}</strong>
      <span style={{{{ color: "var(--dyui-muted)" }}}}>{{props.body}}</span>
    </div>
  );
}}
'''

_INDEX_CSS = """:root { color-scheme: dark; }
* { box-sizing: border-box; }
body {
  margin: 0;
  background: #0a0b0e;
  color: #eef1f5;
  font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
}
.page { max-width: 820px; margin: 0 auto; padding: 40px 20px 80px; }
header h1 { margin: 0 0 4px; font-size: 26px; }
header p { margin: 0 0 24px; color: #9aa3b0; }
.ask { display: flex; gap: 8px; margin-bottom: 24px; }
.ask input {
  flex: 1; background: #16191f; border: 1px solid #2d333b; border-radius: 12px;
  padding: 12px 16px; color: inherit; font-size: 15px;
}
.ask button {
  background: linear-gradient(135deg, #f5b544, #ff8a6b); color: #1a1206;
  border: none; border-radius: 12px; padding: 12px 20px; font-weight: 700; cursor: pointer;
}
.ask button.stop { background: linear-gradient(135deg, #ff8a6b, #ef5a5a); color: #fff; }
.error { color: #ff8a6b; margin-bottom: 16px; }
main { display: flex; flex-direction: column; gap: 28px; }
h2 { font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; color: #9aa3b0; }
.prose { background: #16191f; border: 1px solid #2d333b; border-radius: 14px; padding: 16px; white-space: pre-wrap; }
"""

_VITE_ENV_DTS = """/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DYUI_URL?: string;
}
interface ImportMeta {
  readonly env: ImportMetaEnv;
}
"""

_GITIGNORE = "node_modules/\ndist/\n*.tsbuildinfo\n.env.local\n"

_README = """# {name}

A DyUI dynamic-UI frontend (exported with `dyui export`). It connects to your
LangGraph agent's stream endpoint and renders live cards.

## Run

```bash
npm install
npm run dev      # http://localhost:5173
```

Set the endpoint in `.env` (`VITE_DYUI_URL`), and make sure your agent is
serving (e.g. `dyui serve agent.py`).

## Custom cards

1. Add a component in `src/cards/`.
2. Register it in `src/App.tsx`: `createRegistry({{ my_card: MyCard }})`.
3. Emit it from your agent: `emit("my_card", {{ ... }})`.

Built-in cards (`text, markdown, table, stat, progress, list, keyvalue, json,
alert, image, html`) work with no extra code.
"""


def write_react_project(
    dest: Path,
    *,
    project_name: str,
    stream_url: str,
    local_react: "str | None" = None,
) -> list[str]:
    """Write the project files under ``dest``; return the relative paths written.

    ``local_react`` points the ``dyui-react`` dependency at a local build
    (``file:<path>``) instead of the published npm package -- useful before the
    package is published, or for working against a checkout.
    """
    dyui_dep = f"file:{local_react}" if local_react else "^0.1.0"
    files: dict[str, str] = {
        "package.json": _PACKAGE_JSON.format(name=project_name, dyui_dep=dyui_dep),
        "vite.config.ts": _VITE_CONFIG.format(),
        "tsconfig.json": _TSCONFIG.format(),
        "index.html": _INDEX_HTML.format(name=project_name),
        ".env": _ENV.format(stream_url=stream_url),
        ".gitignore": _GITIGNORE,
        "README.md": _README.format(name=project_name),
        "src/main.tsx": _MAIN_TSX,
        "src/App.tsx": _APP_TSX.format(name=project_name, stream_url=stream_url),
        "src/index.css": _INDEX_CSS,
        "src/cards/ExampleCard.tsx": _EXAMPLE_CARD.format(),
        "src/vite-env.d.ts": _VITE_ENV_DTS,
    }
    written: list[str] = []
    for rel, content in files.items():
        path = dest / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        written.append(rel)
    return sorted(written)
