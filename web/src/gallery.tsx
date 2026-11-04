// DyUI component gallery — every component with fixture data (visual QA + docs source).
import { StrictMode, useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { GROUPS, NodeView } from "./components/dyui";
import { FIXTURES } from "./fixtures/nodes";
import type { NodeContext, UINode } from "./lib/types";

const ACCENTS: Record<string, [string, string]> = {
  indigo: ["#5b4fe0", "#8b80ff"], teal: ["#0f8f83", "#3dd6c3"], rose: ["#d6457a", "#ff86ad"],
  amber: ["#b86e0a", "#f5b544"], emerald: ["#178a5c", "#4ade9b"], slate: ["#475569", "#a3b1c6"],
};

/** Tolerant partial-JSON parse (closes open strings/arrays/objects, drops incomplete tokens). */
function partial(src: string): any {
  let i = 0;
  const ws = () => { while (i < src.length && /\s/.test(src[i])) i++; };
  const val = (): any => {
    ws();
    if (i >= src.length) return undefined;
    const c = src[i];
    if (c === "{") { i++; const o: any = {}; for (;;) { ws(); if (i >= src.length) return o; if (src[i] === "}") { i++; return o; } if (src[i] === ",") { i++; continue; } const k = str(); if (k === undefined || k.done === false) return o; ws(); if (src[i] !== ":") return o; i++; const v = val(); if (v === undefined) return o; o[k.s] = v; } }
    if (c === "[") { i++; const a: any[] = []; for (;;) { ws(); if (i >= src.length) return a; if (src[i] === "]") { i++; return a; } if (src[i] === ",") { i++; continue; } const v = val(); if (v === undefined) return a; a.push(v); } }
    if (c === '"') { const s = str(); return s ? s.s : undefined; }
    const m = /^(-?\d+(\.\d+)?([eE][+-]?\d+)?|true|false|null)/.exec(src.slice(i));
    if (!m || i + m[0].length >= src.length) return undefined;
    i += m[0].length;
    return JSON.parse(m[0]);
  };
  const str = (): { s: string; done: boolean } | undefined => {
    if (src[i] !== '"') return undefined;
    let j = i + 1, out = "";
    while (j < src.length) { if (src[j] === "\\") { if (j + 1 >= src.length) break; try { out += JSON.parse(`"${src.slice(j, j + (src[j + 1] === "u" ? 6 : 2))}"`); } catch { break; } j += src[j + 1] === "u" ? 6 : 2; continue; } if (src[j] === '"') { i = j + 1; return { s: out, done: true }; } out += src[j++]; }
    i = src.length;
    return { s: out, done: false };
  };
  return val();
}

const toLLM = (n: UINode): any => ({ ui: n.ui, ...n.props, ...(n.children ? { children: n.children.map(toLLM) } : {}) });

function mapNodes(list: UINode[], id: string, f: (n: UINode) => UINode): UINode[] {
  return list.map((n) => (n.id === id ? f(n) : n.children ? { ...n, children: mapNodes(n.children, id, f) } : n));
}

type Toast = { id: number; title: string; body: string };

function Gallery() {
  const [theme, setTheme] = useState<"system" | "light" | "dark">("system");
  const [accent, setAccent] = useState("indigo");
  const [gen, setGen] = useState(0);
  const [nodes, setNodes] = useState<Record<string, UINode[]>>(FIXTURES);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timer = useRef<number>(0);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "system") root.removeAttribute("data-theme");
    else root.setAttribute("data-theme", theme);
    const dark = theme === "dark" || (theme === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
    root.style.setProperty("--dy-accent", ACCENTS[accent][dark ? 1 : 0]);
  }, [theme, accent]);

  const toast = useCallback((title: string, body: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t.slice(-3), { id, title, body }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4200);
  }, []);

  const ctxFor = (key: string): NodeContext => ({
    messageId: "gallery",
    threadId: null,
    interactive: true,
    onAction: (req) => {
      toast(`action · ${req.action}`, JSON.stringify({ label: req.label, data: req.data, values: req.values }));
      setTimeout(() => setNodes((all) => ({ ...all, [key]: mapNodes(all[key], req.component_id, (n) => ({ ...n, props: { ...n.props, __resolved__: { label: req.label, values: req.values } } })) })), 700);
    },
    onReply: (text) => toast("reply", text),
  });

  const stream = () => {
    cancelAnimationFrame(timer.current);
    const texts = Object.fromEntries(Object.entries(FIXTURES).map(([k, list]) => [k, list.map((n) => JSON.stringify(toLLM(n)))]));
    const start = performance.now();
    const D = 2600;
    const tick = (t: number) => {
      const f = Math.min(1, (t - start) / D);
      setNodes(Object.fromEntries(Object.entries(FIXTURES).map(([k, list]) => [k, list.map((n, i) => {
        if (f >= 1) return n;
        const s = texts[k][i];
        const obj = partial(s.slice(0, Math.floor(s.length * f))) ?? {};
        const { ui: _u, children, ...props } = obj;
        return { id: n.id, ui: n.ui, props, children, status: "streaming" } as UINode;
      })])));
      if (f < 1) timer.current = requestAnimationFrame(tick);
      else setGen((g) => g + 1);
    };
    timer.current = requestAnimationFrame(tick);
  };

  return (
    <div className="dy-root g-page">
      <header className="g-bar">
        <div className="g-brand"><span className="g-dot" /> DyUI <em>components</em></div>
        <div className="g-controls">
          <div className="g-seg">{(["light", "dark", "system"] as const).map((t) => <button key={t} aria-pressed={theme === t} onClick={() => setTheme(t)}>{t}</button>)}</div>
          <div className="g-swatches">{Object.keys(ACCENTS).map((a) => <button key={a} title={a} aria-label={`Accent ${a}`} aria-pressed={accent === a} style={{ background: ACCENTS[a][0] }} onClick={() => setAccent(a)} />)}</div>
          <button className="dy-btn dy-btn--secondary dy-btn--sm" onClick={() => { setNodes(FIXTURES); setGen((g) => g + 1); }}>Replay</button>
          <button className="dy-btn dy-btn--primary dy-btn--sm" onClick={stream}>Simulate streaming</button>
        </div>
      </header>
      <main className="g-main" key={gen}>
        {Object.entries(GROUPS).map(([group, names]) => (
          <section key={group} id={`group-${group}`} className="g-group">
            <h2 className="g-h2">{group}</h2>
            {names.map((name) => (
              <div key={name} className="g-item" id={`c-${name}`}>
                <div className="g-name">{name}</div>
                <div className="dy-stack" style={{ gap: 14 }}>
                  {(nodes[name] ?? []).map((n) => <NodeView key={n.id} node={n} ctx={ctxFor(name)} />)}
                </div>
              </div>
            ))}
          </section>
        ))}
      </main>
      <div className="g-toasts" aria-live="polite">
        {toasts.map((t) => <div key={t.id} className="g-toast"><b>{t.title}</b><code>{t.body}</code></div>)}
      </div>
    </div>
  );
}

const css = `
body{margin:0;background:var(--dy-bg);color:var(--dy-text)}
.g-page{min-height:100vh}
.g-bar{position:sticky;top:0;z-index:20;display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;justify-content:space-between;padding:12px max(16px,4vw);background:color-mix(in oklab,var(--dy-bg) 86%,transparent);backdrop-filter:blur(12px);border-bottom:1px solid var(--dy-border)}
.g-brand{display:flex;align-items:center;gap:8px;font-weight:600;font-size:15px}.g-brand em{font-family:var(--dy-font-display);font-weight:400;font-size:19px;color:var(--dy-text-muted)}
.g-dot{width:14px;height:14px;border-radius:50% 50% 50% 0;transform:rotate(-45deg);background:var(--dy-bloom)}
.g-controls{display:flex;flex-wrap:wrap;align-items:center;gap:10px}
.g-seg{display:inline-flex;padding:2px;border:1px solid var(--dy-border);border-radius:10px;background:var(--dy-surface)}
.g-seg button{border:0;background:transparent;color:var(--dy-text-muted);font:500 12.5px var(--dy-font);padding:5px 10px;border-radius:8px;cursor:pointer;text-transform:capitalize}
.g-seg button[aria-pressed=true]{background:var(--dy-accent-soft);color:var(--dy-accent-strong)}
.g-swatches{display:flex;gap:5px}.g-swatches button{width:18px;height:18px;border-radius:50%;border:2px solid var(--dy-surface);box-shadow:0 0 0 1px var(--dy-border);cursor:pointer}
.g-swatches button[aria-pressed=true]{box-shadow:0 0 0 2px var(--dy-text)}
.g-main{max-width:760px;margin:0 auto;padding:24px 16px 120px}
.g-group{padding-top:28px}
.g-h2{font-family:var(--dy-font-display);font-weight:400;font-size:40px;letter-spacing:var(--dy-tracking-display);text-transform:capitalize;margin:0 0 8px}
.g-item{padding:18px 0 22px;border-top:1px solid var(--dy-border)}
.g-name{font-family:var(--dy-font-mono);font-size:12px;color:var(--dy-text-faint);margin-bottom:12px}
.g-toasts{position:fixed;right:16px;bottom:16px;display:flex;flex-direction:column;gap:8px;z-index:50;max-width:min(380px,calc(100vw - 32px))}
.g-toast{padding:10px 12px;border-radius:12px;background:var(--dy-surface);border:1px solid var(--dy-border);box-shadow:var(--dy-shadow-lg);font-size:12.5px;display:flex;flex-direction:column;gap:4px;animation:dy-rise .3s var(--dy-ease)}
.g-toast code{font-family:var(--dy-font-mono);font-size:11.5px;color:var(--dy-text-muted);word-break:break-all}
`;
const style = document.createElement("style");
style.textContent = css;
document.head.appendChild(style);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Gallery />
  </StrictMode>,
);
