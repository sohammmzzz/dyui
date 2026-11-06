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

function chunks(text: string): string[] {
  return text.match(/\S+\s*/g) ?? [text];
}

export default function LiveChat() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
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
      push();
    });
    at(1300, () => {
      answer.parts[0] = { kind: "node", node: step("done") };
      answer.parts.push({ kind: "text", text: "" });
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
    <div className="lc dy-root not-content" ref={root}>
      <div className="lc-chrome" aria-hidden="true">
        <span className="lc-dot" />
        <span className="lc-dot" />
        <span className="lc-dot" />
        <span className="lc-title">Travel Bot</span>
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
      <div className="lc-foot">
        <span className="lc-composer">Message Travel Bot…</span>
        <button type="button" className="lc-replay" onClick={play} disabled={busy}>
          {busy ? "Streaming…" : "Replay"}
        </button>
      </div>
    </div>
  );
}
