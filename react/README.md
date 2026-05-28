# @dyui/react

The React runtime for [**DyUI**](../python) — render live, pluggable UI cards
emitted by any LangGraph agent. Zero runtime dependencies (React is a peer),
themeable via CSS variables, and works in Next.js, Vite, or any React app.

## Install

```bash
npm install @dyui/react
```

```tsx
import { useDyUIAgent, DyUISurface, createRegistry } from "@dyui/react";
import "@dyui/react/styles.css";
```

## Use

```tsx
function MyCard({ props }) {
  return <div>{props.expression} = {props.result}</div>;
}

export default function App() {
  // Add/override cards by `component` key; built-ins stay available.
  const registry = createRegistry({ calc_result: MyCard });

  const { cards, tokens, status, run, dismiss } = useDyUIAgent({
    url: "http://localhost:8008/dyui/stream",
  });

  return (
    <>
      <button onClick={() => run("what is 2+2")}>Ask</button>
      <DyUISurface cards={cards} registry={registry} onDismiss={dismiss} />
      <pre>{tokens}</pre>
    </>
  );
}
```

## API

| Export | What it does |
|---|---|
| `useDyUIAgent({ url, headers?, autoRunInput?, collectTokens? })` | Connects to the agent's SSE endpoint and returns `{ cards, bySurface, surfaces, tokens, status, error, run, stop, dismiss, reset }`. |
| `<DyUISurface cards registry? onDismiss? empty? />` | Lays out a list of cards. |
| `<DyUICard card registry? onDismiss? bare? />` | Renders a single card (header + lifecycle body). |
| `createRegistry(overrides)` | Merge custom components over the built-ins. |
| `defaultRegistry` | The built-in cards map. |
| `streamAgent(opts, onFrame)` | Low-level SSE-over-fetch client (no React). |
| `reducer`, `selectCards`, … | The pure store, if you want your own state wiring. |
| `sanitizeHtml` | The default sanitizer used by the `html` card. |

## Built-in cards

`text` · `markdown` · `table` · `stat` · `progress` · `list` · `keyvalue` ·
`json` · `alert` · `image` · `html` (sanitized custom markup).

## Card component contract

```tsx
interface CardComponentProps<P> {
  card: DyUICardData;   // full card (id, status, title, accent, …)
  props: P;             // the emitted props
  status: CardStatus;   // "pending" | "active" | "done" | "error"
}
```

`pending` cards render a skeleton automatically; `error` cards render the error
message. Your component only handles the resolved/active content.

## Theming

Override CSS variables (`--dyui-accent`, `--dyui-surface-bg`, `--dyui-border`,
`--dyui-text`, …) or target `.dyui-*` classes. Add `class="dyui-light"` on an
ancestor for the light theme. Per-card `accent` set on the agent side maps to
`--dyui-accent`.

## Dev

```bash
npm install
npm run typecheck && npm run build && npm test
```
