/**
 * The landing hero: a scripted conversation streamed into the real DyUI
 * component library — text arrives in chunks, a step runs, a table fills in row
 * by row, then buttons and quick replies bloom in. Interactions work.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { NodeView, Prose, staticContext } from "@/components/dyui";
import { FIXTURES } from "@/fixtures/nodes";
import type { UINode } from "@/lib/types";

type Part = { kind: "text"; text: string } | { kind: "node"; node: UINode };
type Turn = { role: "user" | "assistant"; parts: Part[] };

const QUESTION = "Find me a flight to Lisbon on Friday evening.";
const ANSWER =
  "Five flights land in Lisbon on Friday. **TAP at 18:05** is the best balance of price and timing — direct, and you're in the city by 20:40.";
const FOLLOW = "I'd hold the TAP seat now; fares on this route usually rise on Thursdays.";

const table = FIXTURES.table[0];
const buttons = FIXTURES.buttons[0];
const replies = FIXTURES.quick_replies[0];
const step = (status: "running" | "done"): UINode => ({
  id: "lc_step",
  ui: "step",
  status: "done",
  props: { title: "Search flights LHR → LIS", type: "search", status, ...(status === "done" ? { duration_ms: 1240 } : {}) },
});
const withRows = (n: number): UINode => ({
  ...table,
  id: "lc_table",
  status: n < table.props.rows.length ? "streaming" : "done",
  props: { ...table.props, rows: table.props.rows.slice(0, n) },
});

// what the reply demonstrates, in the order it happens
const PHASES: Array<[string, string]> = [
  ["A step runs", "The agent's work shows as a step while it happens."],
  ["Prose streams", "Text arrives in chunks, rendered as Markdown."],
  ["A table fills in", "Components render while the model is still writing them."],
  ["Buttons answer back", "Clicks reach your Python handlers. Try one."],
];

function chunks(text: string): string[] {
  return text.match(/\S+\s*/g) ?? [text];
}

export default function LiveChat() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [phase, setPhase] = useState(-1);
  const timers = useRef<number[]>([]);
  const root = useRef<HTMLDivElement>(null);
  const body = useRef<HTMLDivElement>(null);
  const started = useRef(false);

  // keep the newest content in view while the reply streams (like the real app)
  useEffect(() => {
    const el = body.current;
    if (!el) return;
    const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    el.scrollTo({ top: el.scrollHeight, behavior: reduced ? "auto" : "smooth" });
  }, [turns]);

  const clear = () => {
    timers.current.forEach((t) => clearTimeout(t));
    timers.current = [];
  };

  const play = useCallback(() => {
    clear();
    setDone(false);
    setBusy(true);
    setPhase(-1);
    const reduced = typeof matchMedia !== "undefined" && matchMedia("(prefers-reduced-motion: reduce)").matches;
    const answer: Turn = { role: "assistant", parts: [] };
    const frames: Array<[number, () => void]> = [];
    let t = 0;
    const at = (delay: number, f: () => void) => {
      t += delay;
      frames.push([t, f]);
    };
    const push = () => setTurns([{ role: "user", parts: [{ kind: "text", text: QUESTION }] }, { ...answer, parts: [...answer.parts] }]);

    at(250, () => push());
    at(500, () => {
      answer.parts.push({ kind: "node", node: step("running") });
      setPhase(0);
      push();
    });
    at(1300, () => {
      answer.parts[0] = { kind: "node", node: step("done") };
      answer.parts.push({ kind: "text", text: "" });
      setPhase(1);
      push();
    });
    for (const c of chunks(ANSWER)) {
      at(45, () => {
        const p = answer.parts[1] as { kind: "text"; text: string };
        p.text += c;
        push();
      });
    }
    const rows = table.props.rows.length;
    for (let i = 1; i <= rows; i++) {
      at(i === 1 ? 260 : 170, () => {
        if (i === 1) setPhase(2);
        answer.parts[2] = { kind: "node", node: withRows(i) };
        push();
      });
    }
    at(260, () => {
      answer.parts.push({ kind: "text", text: "" });
      push();
    });
    for (const c of chunks(FOLLOW)) {
      at(40, () => {
        const p = answer.parts[3] as { kind: "text"; text: string };
        p.text += c;
        push();
      });
    }
    at(220, () => {
      answer.parts.push({ kind: "node", node: { ...buttons, id: "lc_buttons" } });
      setPhase(3);
      push();
    });
    at(260, () => {
      answer.parts.push({ kind: "node", node: { ...replies, id: "lc_replies" } });
      push();
      setBusy(false);
      setDone(true);
    });

    if (reduced) {
      frames.forEach(([, f]) => f());
      return;
    }
    timers.current = frames.map(([ms, f]) => window.setTimeout(f, ms));
  }, []);

  // start when the hero scrolls into view (it usually is on load)
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting) && !started.current) {
        started.current = true;
        play();
      }
    }, { threshold: 0.2 });
    io.observe(el);
    return () => {
      io.disconnect();
      clear();
    };
  }, [play]);

  const resolve = (id: string, label?: string, values?: Record<string, unknown>) =>
    setTurns((all) =>
      all.map((turn) => ({
        ...turn,
        parts: turn.parts.map((p) =>
          p.kind === "node" && p.node.id === id ? { kind: "node", node: { ...p.node, props: { ...p.node.props, __resolved__: { label, values } } } } : p,
        ),
      })),
    );

  const ctx = staticContext({
    messageId: "landing",
    interactive: done,
    onAction: (req) => {
      resolve(req.component_id, req.label, req.values);
      setTurns((all) => [
        ...all,
        { role: "assistant", parts: [{ kind: "text", text: `That click arrived in Python as \`${req.action}\` — your \`@app.on_action("${req.action}")\` handler takes it from here.` }] },
      ]);
    },
    onReply: (text) =>
      setTurns((all) => [
        ...all.map((turn) => ({ ...turn, parts: turn.parts.filter((p) => !(p.kind === "node" && p.node.ui === "quick_replies")) })),
        { role: "user", parts: [{ kind: "text", text }] },
        { role: "assistant", parts: [{ kind: "text", text: "This demo stops here. Run `dyui demo` to keep the conversation going — no API key needed." }] },
      ]),
  });

  return (
    <div className="lc-stage not-content" ref={root}>
      <div className="lc-legend">
        <p className="lp-eyebrow">Live demo</p>
        <p className="lc-legend-title">One reply, as it streams.</p>
        <ol className="lc-phases">
          {PHASES.map(([title, body], i) => (
            <li key={title} data-state={done || phase > i ? "done" : phase === i ? "active" : "idle"}>
              <span className="lc-phase-n" aria-hidden="true">
                0{i + 1}
              </span>
              <span className="lc-phase-copy">
                <strong>{title}</strong>
                <span>{body}</span>
              </span>
            </li>
          ))}
        </ol>
        <button type="button" className="lc-replay" onClick={play} disabled={busy}>
          <svg aria-hidden="true" viewBox="0 0 16 16" width="12" height="12">
            <path d="M2.5 8a5.5 5.5 0 1 0 1.7-4M2.5 2.5V5H5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          {busy ? "Streaming…" : "Replay"}
        </button>
      </div>
      <div className="lc dy-root">
      <div className="lc-chrome" aria-hidden="true">
        <span className="lc-dot" />
        <span className="lc-dot" />
        <span className="lc-dot" />
        <span className="lc-title">Travel Bot</span>
        <span className="lc-addr">localhost:8000</span>
      </div>
      <div className="lc-body" ref={body} aria-live="polite" aria-busy={busy}>
        {turns.map((turn, i) =>
          turn.role === "user" ? (
            <div key={i} className="lc-user">
              {turn.parts.map((p, j) => (p.kind === "text" ? <span key={j}>{p.text}</span> : null))}
            </div>
          ) : (
            <div key={i} className="lc-assistant">
              {turn.parts.map((p, j) =>
                p.kind === "text" ? (p.text ? <Prose key={j} text={p.text} /> : null) : <NodeView key={p.node.id} node={p.node} ctx={ctx} />,
              )}
            </div>
          ),
        )}
        {busy && turns.length < 2 && <div className="lc-thinking" aria-label="Thinking" />}
      </div>
      <div className="lc-foot" aria-hidden="true">
        <span className="lc-composer">Message Travel Bot…</span>
        <span className="lc-send">
          <svg viewBox="0 0 16 16" width="14" height="14">
            <path d="M8 12.5v-9M4 7.5l4-4 4 4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </span>
      </div>
      </div>
    </div>
  );
}
