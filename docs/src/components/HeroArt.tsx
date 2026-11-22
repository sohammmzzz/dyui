/**
 * The landing hero's art: "dye in still water — interfaces emerge from text, calmly" (brand/BRAND.md).
 *
 * A field of the model's own fine print is written line by line, exactly what a model writes for
 * DyUI: a sentence, then a ```dyui fence with one JSON object. As each fence closes, a drop of
 * indigo dye spreads through the text there, the text clears, and the real component resolves
 * out of it (rendered by the DyUI component library itself), with the mark's bloom easing.
 * Three replies, a hold, a quiet dissolve, and it begins again.
 *
 * Calm by design: one slow loop, opacity / transform / blur only, paused off-screen and in
 * background tabs. With reduced motion it shows the finished composition, still.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { NodeView, staticContext } from "@/components/dyui";
import type { UINode } from "@/lib/types";

const node = (id: string, ui: string, props: Record<string, unknown>): UINode => ({ id, ui, props, status: "done" } as UINode);

const STAT = { label: "Monthly recurring revenue", value: "$48.2k", delta: "+12.4%", trend: "up", help: "vs. October" };
const CHART = {
  kind: "area",
  title: "Revenue",
  unit: "$",
  labels: ["Jun", "Jul", "Aug", "Sep", "Oct", "Nov"],
  series: [{ name: "Revenue", data: [31200, 33800, 36100, 39400, 42900, 48200] }],
};
const BUTTONS = {
  items: [
    { label: "Send the board update", action: "send_update", style: "primary" },
    { label: "Edit first", action: "edit", style: "secondary" },
  ],
};

/** One reply = a sentence + its fence; `pool` is where its component surfaces. */
const REPLIES = [
  { id: "stat", text: "Revenue is up 12.4% since October.", ui: "stat", props: STAT },
  { id: "chart", text: "It has grown every month since June:", ui: "chart", props: CHART },
  { id: "buttons", text: "Shall I send the board update?", ui: "buttons", props: BUTTONS },
] as const;

const FENCE = "```";
const LINES: Array<{ text: string; closes?: string }> = REPLIES.flatMap((r) => [
  { text: r.text },
  { text: FENCE + "dyui" },
  { text: JSON.stringify({ ui: r.ui, ...r.props }) },
  { text: FENCE, closes: r.id },
]);
const TOTAL = LINES.reduce((n, l) => n + l.text.length, 0);

const CPS = 150; // characters per second — a quick, even model
const HOLD_MS = 4200; // the finished composition rests
const FADE_MS = 1100; // then everything dissolves back to paper

type Phase = "write" | "hold" | "fade";

export default function HeroArt() {
  const [chars, setChars] = useState(0); // characters written so far
  const [shown, setShown] = useState<string[]>([]); // components that have surfaced
  const [phase, setPhase] = useState<Phase>("write");
  const [still, setStill] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const ctx = useMemo(() => staticContext({ messageId: "hero" }) /* looks live; the art takes no pointer input */, []);

  useEffect(() => {
    const reduced = matchMedia("(prefers-reduced-motion: reduce)");
    if (reduced.matches) {
      setStill(true);
      setChars(TOTAL);
      setShown(REPLIES.map((r) => r.id));
      setPhase("hold");
      return;
    }
    let raf = 0;
    let visible = true;
    let t0 = 0; // start of the current loop, in "running" time
    let run = 0; // running time (ms), frozen while hidden
    let last = 0;
    const io = new IntersectionObserver(([e]) => (visible = e.isIntersecting), { threshold: 0.05 });
    if (root.current) io.observe(root.current);

    const writeMs = (TOTAL / CPS) * 1000;
    const loopMs = writeMs + HOLD_MS + FADE_MS + 500;
    let prevChars = -1;
    let prevPhase: Phase | null = null;
    const tick = (now: number) => {
      raf = requestAnimationFrame(tick);
      const dt = last ? Math.min(64, now - last) : 0;
      last = now;
      if (!visible || document.hidden) return;
      run += dt;
      const t = (run - t0) % loopMs;
      const c = Math.min(TOTAL, Math.floor((t / 1000) * CPS));
      const p: Phase = t < writeMs ? "write" : t < writeMs + HOLD_MS ? "hold" : "fade";
      if (c !== prevChars) {
        prevChars = c;
        setChars(c);
        // a component surfaces once its closing fence has been written
        let n = 0;
        const done: string[] = [];
        for (const l of LINES) {
          n += l.text.length;
          if (l.closes && c >= n) done.push(l.closes);
        }
        setShown((s) => (s.length === done.length ? s : done));
      }
      if (p !== prevPhase) {
        prevPhase = p;
        setPhase(p);
      }
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      io.disconnect();
    };
  }, []);

  // split the written characters over the lines; the caret sits on the line being written
  let left = chars;
  let caretLine = -1;
  const lines = LINES.map((l, i) => {
    const n = Math.max(0, Math.min(l.text.length, left));
    left -= l.text.length;
    if (caretLine < 0 && (n < l.text.length || i === LINES.length - 1)) caretLine = i;
    return { ...l, shown: l.text.slice(0, n), fence: l.text.startsWith(FENCE), json: l.text.startsWith("{") };
  });

  return (
    <div className="ha" ref={root} data-phase={phase} data-still={still || undefined} aria-hidden="true">
      <div className="ha-field">
        {lines.map((l, i) => (
          <p key={i} className={l.json ? "ha-line is-json" : l.fence ? "ha-line is-fence" : "ha-line is-prose"}>
            {l.shown}
            {i === caretLine && phase === "write" && <span className="ha-caret" />}
          </p>
        ))}
      </div>
      {REPLIES.map((r) => {
        const on = shown.includes(r.id);
        return (
          <div key={r.id} className={`ha-pool ha-pool--${r.id}`} data-on={on || undefined}>
            <span className="ha-clear" />
            <span className="ha-dye" />
            <div className="ha-comp dy-root">{on && <NodeView node={node(`hero_${r.id}`, r.ui, r.props as Record<string, unknown>)} ctx={ctx} />}</div>
          </div>
        );
      })}
    </div>
  );
}
