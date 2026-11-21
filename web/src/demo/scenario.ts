/**
 * `dyui demo` (python/dyui/demo.py), ported to the in-browser mock transport for the
 * docs-site embed. Keep it in step with demo.py: same config, starters, routing, reply
 * texts, components (including the custom Flight card), actions and follow-ups.
 *
 * Replies are written the way demo.py writes them — prose with ```dyui blocks, one JSON
 * object per line — and split here the way the server's parser splits them, so the text
 * and components are identical to the Python demo. Content is deterministic; only the
 * token pacing varies. Nothing is persisted (demo.py uses persist=False): every page load
 * starts fresh.
 */
import { ASK, N, S, T, U, W, R, type ActionOutcome, type Op, type Scenario, type Script } from "@/lib/mock";
import type { ActionRequest, AppConfig, UINode } from "@/lib/types";

const STARTERS = [
  { label: "Show me what you can do", icon: "sparkles" },
  { label: "Analyze Q3 sales", icon: "chart" },
  { label: "Plan a weekend in Lisbon", icon: "plane" },
  { label: "File a support ticket", icon: "life-buoy" },
];

function config(p: URLSearchParams): Omit<AppConfig, "authenticated"> {
  const theme = p.get("theme");
  return {
    title: "DyUI",
    description: "A short tour of chat that answers in interfaces.",
    welcome: "Ask me anything — I answer in interfaces.",
    placeholder: "Message DyUI…",
    logo: null,
    theme: theme === "light" || theme === "dark" ? theme : "system",
    accent: "indigo",
    starters: STARTERS.map((s) => ({ label: s.label, message: s.label, icon: s.icon })),
    features: { history: true, uploads: true, feedback: true, auth: false },
    version: (import.meta.env.VITE_DYUI_VERSION as string | undefined) || "dev",
    max_upload_mb: 20,
  };
}

/* ------------------------------------------------- replies, as demo.py writes them */

type Spec = Record<string, any> & { ui: string };

/** demo.py's block(): a ```dyui fence, one component per line. */
const block = (...components: Spec[]) => "\n```dyui\n" + components.map((c) => JSON.stringify(c)).join("\n") + "\n```\n";

/** The props the server's validation fills in for components demo.py writes sparsely. */
const DEFAULTS: Record<string, Record<string, any>> = {
  confirm: { cancel_label: "Cancel" },
  rating: { max: 5, action: "rating" },
};

/** `@app.component class Flight` — render() returns a card with a key/value list and a Book button. */
function flight(f: Spec, id: string): UINode {
  const data = { airline: f.airline, route: f.route, depart: f.depart, duration: f.duration, price: f.price };
  return {
    id,
    ui: "card",
    props: {
      title: f.airline,
      subtitle: `${f.route} · ${f.depart}`,
      actions: [{ label: "Book", action: "book_flight", data, style: "primary" }],
      __component__: "flight",
    },
    children: [
      {
        id: `${id}-0`,
        ui: "keyvalue",
        props: { items: [{ key: "Duration", value: f.duration }, { key: "Price", value: `€${Number(f.price).toFixed(0)}` }] },
        status: "done",
      },
    ],
    status: "done",
  };
}

/** One component spec → a ui op, streamed in the way the shell shows a component arriving. */
function component(spec: Spec): Op {
  const { ui, ...props } = spec;
  if (ui === "flight") {
    const node = N("card", {});
    return U(flight(spec, node.id), { skeletonMs: 260 });
  }
  const node = N(ui, { ...props, ...Object.fromEntries(Object.entries(DEFAULTS[ui] ?? {}).filter(([k]) => !(k in props))) });
  if (ui === "table") return U(node, { progressive: "rows" });
  if (ui === "stats" || ui === "plan" || ui === "timeline") return U(node, { progressive: "items" });
  if (ui === "chart") return U(node, { skeletonMs: 420 });
  return U(node);
}

const FENCE = /```dyui\n([\s\S]*?)\n```\n?/g;

/** Split a demo.py reply the way the server's stream parser does: prose → text, fence lines → components. */
export function parseReply(text: string): Op[] {
  const ops: Op[] = [];
  let last = 0;
  for (const m of text.matchAll(FENCE)) {
    if (m.index! > last) ops.push(T(text.slice(last, m.index)));
    for (const line of m[1].split("\n")) if (line.trim()) ops.push(component(JSON.parse(line)));
    last = m.index! + m[0].length;
  }
  if (last < text.length) ops.push(T(text.slice(last)));
  return ops;
}

/* --------------------------------------------------------------------- the flows */

function tour(): Op[] {
  return [
    R("The user wants a tour. Show a few component families, briefly, then offer next steps."),
    W(400),
    ...parseReply(
      "Here's the idea: instead of describing things, I **show** them. A few examples —\n" +
        block({
          ui: "stats",
          items: [
            { label: "Components", value: 39 },
            { label: "Providers", value: 10 },
            { label: "Frontend code", value: "0 lines" },
          ],
        }) +
        "Data becomes charts:\n" +
        block({
          ui: "chart",
          kind: "area",
          title: "Weekly active users",
          labels: ["W1", "W2", "W3", "W4", "W5", "W6"],
          series: [{ name: "Users", data: [120, 180, 260, 310, 420, 515] }],
        }) +
        "and steps become live plans:\n" +
        block({
          ui: "plan",
          title: "Launch checklist",
          items: [
            { title: "Write app.py", status: "done" },
            { title: "Teach the LLM your components", status: "done" },
            { title: "dyui run app.py", status: "active" },
            { title: "Ship it", status: "pending" },
          ],
        }) +
        "Where to next?\n" +
        block({ ui: "quick_replies", options: ["Analyze Q3 sales", "Plan a weekend in Lisbon", "File a support ticket"] }),
    ),
  ];
}

function sales(): Op[] {
  return [
    S({ title: "Querying the sales warehouse", type: "search", ms: 900, input: { quarter: "Q3", regions: 4 }, output: "4 regions · 12,480 orders" }),
    R("EMEA grew fastest; lead with the headline numbers, then the regional chart and table."),
    W(300),
    ...parseReply(
      "Q3 closed strong — revenue is up **14%** quarter over quarter, led by EMEA.\n" +
        block({
          ui: "stats",
          items: [
            { label: "Revenue", value: "$4.82M", delta: "+14%", trend: "up" },
            { label: "Orders", value: "12,480", delta: "+9%", trend: "up" },
            { label: "Refund rate", value: "1.8%", delta: "-0.4pt", trend: "down" },
          ],
        }) +
        block({
          ui: "chart",
          kind: "bar",
          title: "Revenue by region ($k)",
          labels: ["NA", "EMEA", "APAC", "LATAM"],
          series: [
            { name: "Q2", data: [1620, 1180, 980, 450] },
            { name: "Q3", data: [1710, 1460, 1090, 560] },
          ],
        }) +
        block({
          ui: "table",
          caption: "Top products",
          columns: ["Product", "Units", "Revenue", "QoQ"],
          rows: [
            ["Atlas Pro", 3120, "$1.21M", "+18%"],
            ["Atlas Lite", 4410, "$0.88M", "+7%"],
            ["Nimbus", 1980, "$0.74M", "+22%"],
            ["Orbit", 1270, "$0.41M", "-3%"],
          ],
        }) +
        block({
          ui: "callout",
          level: "info",
          title: "Worth a look",
          text: "Orbit is the only product that shrank. Its refunds doubled after the July price change.",
        }),
    ),
  ];
}

function lisbon(): Op[] {
  return [
    S({ title: "Searching flights · LHR → LIS", type: "search", ms: 1000, output: "14 options · 3 shown" }),
    ...parseReply(
      "Lisbon in early autumn is lovely — warm, quieter, golden light. Here are the best flights for Friday:\n" +
        block(
          { ui: "flight", airline: "TAP Air Portugal", route: "LHR → LIS", depart: "Fri 18:05", duration: "2h 45m", price: 189 },
          { ui: "flight", airline: "British Airways", route: "LHR → LIS", depart: "Fri 07:20", duration: "2h 50m", price: 214 },
        ) +
        "And a rough shape for the weekend:\n" +
        block({
          ui: "timeline",
          items: [
            { time: "Fri evening", title: "Arrive · dinner in Alfama", status: "pending" },
            { time: "Sat", title: "Belém, pastéis, LX Factory", status: "pending" },
            { time: "Sun", title: "Sintra day trip", status: "pending" },
          ],
        }) +
        block({ ui: "quick_replies", options: ["Show hotels in Alfama", "Make it cheaper"] }),
    ),
  ];
}

function support(): Op[] {
  return parseReply(
    "Sorry you're having trouble. Tell me a little more and I'll route it to the right team:\n" +
      block({
        ui: "form",
        title: "New support ticket",
        action: "submit_ticket",
        submit_label: "Create ticket",
        fields: [
          { name: "subject", label: "Subject", type: "text", required: true, placeholder: "Can't export reports" },
          { name: "area", label: "Area", type: "select", options: ["Billing", "Exports", "Login", "Other"] },
          { name: "urgency", label: "Urgency", type: "slider", min: 1, max: 5, default: 3 },
          { name: "details", label: "Details", type: "textarea" },
        ],
      }),
  );
}

function fallback(): Op[] {
  return parseReply(
    "I'm the DyUI demo, so I only know a few tricks — but each one answers in an interface. Try one:\n" +
      block({
        ui: "quick_replies",
        options: ["Show me what you can do", "Analyze Q3 sales", "Plan a weekend in Lisbon", "File a support ticket"],
      }),
  );
}

const ROUTES: [string[], () => Op[]][] = [
  [["what can you do", "show me", "tour", "hello", "hi"], tour],
  [["sales", "revenue", "q3", "analy"], sales],
  [["lisbon", "flight", "trip", "travel", "weekend", "hotel", "cheaper"], lisbon],
  [["support", "ticket", "help", "issue", "problem"], support],
];

/** `@app.on_message reply` — the first route with a matching keyword, else the fallback. */
function route(text: string): Op[] {
  const t = text.toLowerCase();
  for (const [keys, flow] of ROUTES) if (keys.some((k) => t.includes(k))) return flow();
  return fallback();
}

/** The server's auto-title: the first six words, trimmed of punctuation. */
export function autoTitle(text: string): string {
  const words = text.split(/\s+/).filter(Boolean);
  const title = words.slice(0, 6).join(" ").replace(/^[ .,:;!?]+|[ .,:;!?]+$/g, "").slice(0, 60) || "New chat";
  return words.length > 6 ? title + "…" : title;
}

function scriptFor(text: string): Script {
  return { title: autoTitle(text), ops: route(text) };
}

/* ------------------------------------------------------------------- the actions */

const fmt0 = (n: unknown) => Number(n || 0).toFixed(0);

function book(req: ActionRequest): Op[] {
  const f = req.data ?? {};
  return [
    T(`Great choice — **${f.airline}**, ${f.depart}. One last check:`),
    ASK(
      N("confirm", {
        title: `Book ${f.airline} for €${fmt0(f.price)}?`,
        text: "Your card on file will be charged.",
        confirm_label: "Book flight",
        cancel_label: "Cancel",
        action: "confirm_booking",
      }),
      (answer) =>
        answer?.values?.confirmed ?? true
          ? [
              S({ title: "Booking", type: "tool", ms: 800, output: "PNR · LX7Q2D" }),
              U(N("callout", { text: "Booked. Confirmation LX7Q2D is on its way to your inbox.", level: "success", title: "You're going to Lisbon" })),
            ]
          : [U(N("callout", { text: "No problem — nothing was booked.", level: "info" }))],
    ),
  ];
}

function ticket(req: ActionRequest): Op[] {
  const v = req.values ?? {};
  return [
    S({ title: "Creating ticket", type: "tool", ms: 700, output: "#4821" }),
    ...parseReply(
      `Ticket **#4821** is open: *${v.subject || "Untitled"}*. Here's what happens next:\n` +
        block({
          ui: "plan",
          items: [
            { title: "Ticket created", status: "done" },
            { title: `Routed to ${v.area || "Support"}`, status: "done" },
            { title: "First response (usually < 2h)", status: "active" },
            { title: "Resolution", status: "pending" },
          ],
        }) +
        block({ ui: "rating", label: "How was this experience?", style: "stars" }),
    ),
  ];
}

function rated(req: ActionRequest): Op[] {
  const n = Number(req.values?.rating ?? 0);
  const score = Number.isFinite(n) ? n : 0;
  if (score >= 4) return [T(`Thank you for the ${fmt0(score)}/5 — glad that helped. I've passed it on to the team.`)];
  if (score > 0) return [T(`Thanks for the honest ${fmt0(score)}/5. I've flagged this ticket so a teammate follows up personally.`)];
  return [T("Thanks for the feedback — it goes straight to the support team.")];
}

function actionOutcome(req: ActionRequest): ActionOutcome {
  switch (req.action) {
    case "book_flight":
      return { mode: "reply", ops: book(req) };
    case "submit_ticket":
      return { mode: "reply", ops: ticket(req) };
    case "rating":
      return { mode: "reply", ops: rated(req) };
    default:
      // no @app.on_action handler: the action becomes a user message for on_message
      return { mode: "message", ops: route(`${req.action} ${req.label ?? ""}`) };
  }
}

export const demoScenario: Scenario = { config, scriptFor, actionOutcome, persist: false };
