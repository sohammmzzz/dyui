/**
 * Mock transport — the whole DyUI protocol (SPEC §4) in the browser, no Python needed.
 *
 * `npm run dev` + `?mock=1` (or no backend reachable in dev) streams a scripted
 * showcase: realistic token timing, live steps, reasoning, and `ui` nodes for
 * stats, charts, tables, cards with buttons, quick replies, forms, confirm (a
 * `chat.ask()`-style pause mid-stream), plans, lists and more. Actions resolve
 * components via `props.__resolved__` exactly like the server.
 *
 * Extra query params for QA: `auth=1` (password gate, password "dyui"),
 * `accent=<name|hex>`, `theme=light|dark`, `history=0`, `uploads=0`,
 * `feedback=0`, `speed=<multiplier>` (0.25 = 4× faster), `fresh=1` (reset storage).
 */
import { ApiError, type FeedbackRequest, type Transport, type UploadOptions } from "./api";
import { applyMessageEvent } from "./store";
import type {
  ActionRequest,
  AppConfig,
  ChatRequest,
  FileRef,
  Message,
  Part,
  Step,
  StreamEvent,
  Thread,
  ThreadSummary,
  UINode,
} from "./types";

/* ------------------------------------------------------------------ utils */

const hex = (n: number) =>
  Array.from(crypto.getRandomValues(new Uint8Array(Math.ceil(n / 2))), (b) => b.toString(16).padStart(2, "0"))
    .join("")
    .slice(0, n);
const cid = () => `c_${hex(8)}`;
const mid = () => `msg_${hex(10)}`;
const tid = () => `thr_${hex(10)}`;
const now = () => Date.now() / 1000;
const rand = (a: number, b: number) => a + Math.random() * (b - a);

function abortError() {
  const e = new Error("The operation was aborted.");
  e.name = "AbortError";
  return e;
}

/* --------------------------------------------------------------- script DSL */

type StepSpec = {
  id?: string;
  title: string;
  type?: string;
  ms: number;
  input?: any;
  output?: any;
  logs?: string[];
  error?: string;
  parent?: string;
};

type Op =
  | { t: "reason"; text: string }
  | { t: "text"; text: string }
  | { t: "ui"; node: UINode; progressive?: "rows" | "items"; skeletonMs?: number; delay?: number }
  | { t: "step"; spec: StepSpec }
  | { t: "wait"; ms: number }
  | { t: "ask"; node: UINode; then: (req: ActionRequest | null) => Op[] };

type Emission = { delay: number; make: () => StreamEvent };

const R = (text: string): Op => ({ t: "reason", text });
const T = (text: string): Op => ({ t: "text", text });
const W = (ms: number): Op => ({ t: "wait", ms });
const S = (spec: StepSpec): Op => ({ t: "step", spec });
const N = (ui: string, props: Record<string, any>, children?: UINode[], id = cid()): UINode => ({
  id,
  ui,
  props,
  ...(children ? { children } : {}),
  status: "done",
});
const U = (node: UINode, opts: Omit<Extract<Op, { t: "ui" }>, "t" | "node"> = {}): Op => ({ t: "ui", node, ...opts });
const ASK = (node: UINode, then: (req: ActionRequest | null) => Op[]): Op => ({ t: "ask", node, then });

function tokens(text: string): string[] {
  return text.match(/\s+|\S+\s*/g) ?? [text];
}

function* expandText(text: string, messageId: string, kind: "text" | "reasoning"): Generator<Emission> {
  const toks = tokens(text);
  let i = 0;
  while (i < toks.length) {
    const n = kind === "reasoning" ? 2 + Math.floor(Math.random() * 3) : 1 + Math.floor(Math.random() * 3);
    const chunk = toks.slice(i, i + n).join("");
    i += n;
    let delay = kind === "reasoning" ? rand(14, 30) : rand(18, 44);
    if (kind === "text" && /[.!?:]\s*$/.test(chunk)) delay += rand(70, 170);
    if (/\n\n/.test(chunk)) delay += rand(60, 140);
    yield { delay, make: () => ({ event: kind, data: { message_id: messageId, delta: chunk } }) as StreamEvent };
  }
}

function* expandOp(op: Exclude<Op, { t: "ask" }>, messageId: string): Generator<Emission> {
  switch (op.t) {
    case "reason":
      yield* expandText(op.text, messageId, "reasoning");
      return;
    case "text":
      yield* expandText(op.text, messageId, "text");
      return;
    case "wait":
      yield { delay: op.ms, make: () => ({ event: "done", data: {} }) as StreamEvent };
      return;
    case "ui": {
      const node = op.node;
      const ui = (n: UINode, delay: number): Emission => ({
        delay,
        make: () => ({ event: "ui", data: { message_id: messageId, node: n } }),
      });
      const first = op.delay ?? rand(140, 260);
      if (op.progressive) {
        const key = op.progressive;
        const all: any[] = node.props[key] ?? [];
        for (let k = 1; k <= all.length; k++) {
          yield ui({ ...node, status: "streaming", props: { ...node.props, [key]: all.slice(0, k) } }, k === 1 ? first : rand(70, 120));
        }
        yield ui({ ...node, status: "done" }, 90);
      } else if (op.skeletonMs) {
        const { series: _s, rows: _r, items: _i, ...rest } = node.props;
        yield ui({ ...node, status: "streaming", props: rest }, first);
        yield ui({ ...node, status: "done" }, op.skeletonMs);
      } else {
        yield ui({ ...node, status: "done" }, first);
      }
      return;
    }
    case "step": {
      const s = op.spec;
      const id = s.id ?? `step_${hex(6)}`;
      let started = 0;
      const base = (): Step => ({
        id,
        title: s.title,
        type: s.type ?? "tool",
        status: "running",
        started_at: started,
        parent_id: s.parent ?? null,
        ...(s.input !== undefined ? { input: s.input } : {}),
      });
      yield {
        delay: rand(120, 220),
        make: () => {
          started = now();
          return { event: "step", data: { message_id: messageId, step: base() } };
        },
      };
      const logs: string[] = [];
      const per = s.logs?.length ? s.ms / (s.logs.length + 1) : 0;
      for (const line of s.logs ?? []) {
        yield {
          delay: per,
          make: () => {
            logs.push(line);
            return { event: "step", data: { message_id: messageId, step: { ...base(), logs: logs.slice() } } };
          },
        };
      }
      yield {
        delay: per || s.ms,
        make: () => ({
          event: "step",
          data: {
            message_id: messageId,
            step: {
              ...base(),
              status: s.error ? "error" : "done",
              duration_ms: Math.round((now() - started) * 1000) || s.ms,
              ...(s.output !== undefined ? { output: s.output } : {}),
              ...(s.error ? { output: { error: s.error } } : {}),
              ...(logs.length ? { logs: logs.slice() } : {}),
            },
          },
        }),
      };
      return;
    }
  }
}

/** Run a script instantly (no delays) into final parts — used for seeded history. */
function collapse(ops: Op[], messageId: string, answer?: (node: UINode) => ActionRequest | null): Part[] {
  let msgs: Message[] = [{ id: messageId, role: "assistant", created_at: now(), parts: [], status: "streaming" }];
  const run = (list: Op[]) => {
    for (const op of list) {
      if (op.t === "ask") {
        msgs = applyMessageEvent(msgs, { event: "ui", data: { message_id: messageId, node: op.node } });
        const req = answer?.(op.node) ?? null;
        if (req) {
          const resolved = { ...op.node, props: { ...op.node.props, __resolved__: { label: req.label, values: req.values ?? {} } } };
          msgs = applyMessageEvent(msgs, { event: "ui", data: { message_id: messageId, node: resolved } });
        }
        run(op.then(req));
        continue;
      }
      for (const e of expandOp(op, messageId)) {
        const ev = e.make();
        if (ev.event === "step") {
          const st = ev.data.step;
          if (st.status === "done" && !st.duration_ms) st.duration_ms = 800;
        }
        msgs = applyMessageEvent(msgs, ev);
      }
    }
  };
  run(ops);
  return msgs[0].parts;
}

/* ------------------------------------------------------------- the scripts */

type Script = { title: string; ops: Op[] };

function revenueScript(): Script {
  return {
    title: "Q3 revenue snapshot",
    ops: [
      R(
        "They want a quarter-level view. Pull invoices for Q2 and Q3, compare by region, and lead with the headline numbers before the detail. APAC looked uneven in September, so check whether that dip is real or a timing effect.",
      ),
      S({
        title: "Query revenue warehouse",
        type: "database",
        ms: 1300,
        input: {
          sql: "SELECT region, date_trunc('month', booked_at) AS month, SUM(amount)\nFROM invoices\nWHERE booked_at >= '2026-04-01'\nGROUP BY 1, 2;",
        },
        output: { rows: 1284, scanned: "2.1 GB" },
      }),
      S({ title: "Compare quarter over quarter", type: "analysis", ms: 700, output: { q2: 4322, q3: 4755, growth: "+10.0%" } }),
      T(
        "Q3 closed at **$4.76M**, up 10.0% on Q2 and the strongest quarter this year. Most of the lift came from EMEA. APAC softened through September.\n\n",
      ),
      U(
        N("stats", {
          items: [
            { label: "Revenue", value: "$4.76M", delta: "+10.0%", trend: "up" },
            { label: "New customers", value: 1284, delta: "+8.1%", trend: "up" },
            { label: "Net retention", value: "118%", delta: "+3 pts", trend: "up" },
            { label: "Gross churn", value: "2.1%", delta: "−0.4 pts", trend: "down" },
          ],
        }),
        { progressive: "items" },
      ),
      T("\nMonthly revenue by region, in thousands of dollars:\n\n"),
      U(
        N("chart", {
          kind: "line",
          title: "Monthly revenue by region",
          unit: "$k",
          labels: ["Apr", "May", "Jun", "Jul", "Aug", "Sep"],
          series: [
            { name: "EMEA", data: [520, 548, 566, 601, 640, 688] },
            { name: "Americas", data: [610, 602, 630, 655, 662, 671] },
            { name: "APAC", data: [190, 204, 212, 214, 198, 176] },
          ],
        }),
        { skeletonMs: 520 },
      ),
      U(
        N("table", {
          columns: ["Region", "Q3 revenue", "vs Q2", "Share"],
          rows: [
            ["EMEA", "$1.93M", "+18.1%", "41%"],
            ["Americas", "$1.99M", "+7.9%", "42%"],
            ["APAC", "$588k", "−3.0%", "12%"],
            ["Other", "$250k", "+4.2%", "5%"],
          ],
          caption: "Q3 2026 · recognized revenue",
        }),
        { progressive: "rows" },
      ),
      T("\nAPAC is the one to watch. Want me to dig into it, or draft a short summary for the board?"),
      U(N("quick_replies", { options: ["Why did APAC soften?", "Draft a board summary", "Break it down by product"] })),
    ],
  };
}

function apacScript(): Script {
  return {
    title: "APAC dip",
    ops: [
      R("Split APAC by country and by deal type. Look for renewals that moved quarters and for campaigns that shifted."),
      S({ title: "Segment APAC accounts", type: "database", ms: 950, output: { accounts: 212, countries: 5 } }),
      T(
        "Two things explain most of the APAC dip:\n\n1. **Japan renewals slipped.** Three enterprise renewals worth $41k moved from September into October.\n2. **Fewer new logos in Australia.** The September campaign launched two weeks late.\n\nWithout the slipped renewals, APAC would have grown 3.9% on Q2.\n\n",
      ),
      U(
        N("chart", {
          kind: "donut",
          title: "APAC revenue by country, Q3",
          unit: "$k",
          labels: ["Japan", "Australia", "Singapore", "India", "Other"],
          series: [{ name: "Q3", data: [214, 162, 98, 71, 43] }],
        }),
        { skeletonMs: 420 },
      ),
      U(
        N("callout", {
          level: "warning",
          title: "Worth watching",
          text: "If the Japan renewals don’t close by mid-October, Q4 APAC starts about $40k behind plan.",
        }),
      ),
      U(N("quick_replies", { options: ["Draft a board summary", "Who owns the Japan renewals?"] })),
    ],
  };
}

function boardScript(): Script {
  return {
    title: "Board summary",
    ops: [
      T(
        "## Q3 at a glance\n\nRevenue reached **$4.76M**, up 10.0% on Q2, with net retention at 118%. Growth was broad except in APAC, where timing pushed renewals into Q4.\n\n### Highlights\n\n- EMEA grew 18.1%, driven by three enterprise expansions.\n- Net revenue retention rose three points to 118%.\n- Gross churn fell to 2.1%, the lowest in six quarters.\n\n### Watch\n\n- APAC declined 3.0%, mostly from Japan renewals slipping into October.\n\n### Next quarter\n\n1. Close the slipped Japan renewals by mid-October.\n2. Relaunch the Australia campaign in week one.\n3. Hold EMEA expansion pricing through renewal season.\n",
      ),
      U(N("rating", { label: "Was this summary useful?", max: 5, style: "stars", action: "rating" })),
    ],
  };
}

function productScript(): Script {
  return {
    title: "Revenue by product",
    ops: [
      S({ title: "Join invoices with product catalog", type: "database", ms: 900, output: { products: 4 } }),
      T("Core still carries the business, but Analytics grew fastest this quarter:\n\n"),
      U(
        N("chart", {
          kind: "bar",
          title: "Revenue by product",
          unit: "$k",
          labels: ["Core", "Analytics", "Integrations", "Services"],
          series: [
            { name: "Q2", data: [2410, 980, 612, 320] },
            { name: "Q3", data: [2520, 1214, 688, 333] },
          ],
        }),
        { skeletonMs: 480 },
      ),
      T("\nAnalytics is up **23.9%** quarter over quarter and is now a quarter of total revenue."),
    ],
  };
}

function japanScript(): Script {
  return {
    title: "Japan renewals",
    ops: [
      T("All three renewals sit with **Akiko Mori** on the Tokyo team. Two are in legal review and one is waiting on a PO.\n\n"),
      U(
        N(
          "card",
          {
            title: "Akiko Mori",
            subtitle: "Enterprise AE · Tokyo",
            badge: "3 open renewals",
            actions: [
              { label: "Message Akiko", action: "message_owner", data: { owner: "akiko" }, style: "primary" },
              { label: "Open in CRM", action: "open_crm", data: { owner: "akiko" }, style: "ghost" },
            ],
          },
          [
            N("keyvalue", {
              items: [
                { key: "Pipeline at risk", value: "$41,200" },
                { key: "Expected close", value: "Oct 14 – Oct 22" },
                { key: "Blocker", value: "Legal review (2), PO pending (1)" },
              ],
            }),
          ],
        ),
      ),
    ],
  };
}

function lisbonScript(): Script {
  const planId = cid();
  const plan = (s: [string, string, string]) =>
    N(
      "plan",
      {
        title: "Weekend in Lisbon",
        items: [
          { title: "Find flights for Friday evening", status: s[0] },
          { title: "Pick the right neighborhood", status: s[1] },
          { title: "Draft a two-day itinerary", status: s[2] },
        ],
      },
      undefined,
      planId,
    );
  const flight = (o: {
    airline: string;
    code: string;
    times: string;
    badge?: string;
    price: string;
    bags: string;
    back: string;
  }) =>
    N(
      "card",
      {
        title: o.airline,
        subtitle: `${o.code} · ${o.times} · nonstop`,
        ...(o.badge ? { badge: o.badge } : {}),
        actions: [
          { label: "Hold seats", action: "hold_flight", data: { flight: o.code, airline: o.airline }, style: "primary" },
          { label: "Details", action: "flight_details", data: { flight: o.code }, style: "ghost" },
        ],
      },
      [
        N("keyvalue", {
          items: [
            { key: "Price", value: o.price },
            { key: "Bags", value: o.bags },
            { key: "Return", value: o.back },
          ],
        }),
      ],
    );
  return {
    title: "Weekend in Lisbon",
    ops: [
      U(plan(["active", "pending", "pending"]), { delay: 120 }),
      S({
        title: "Search flights LHR → LIS",
        type: "search",
        ms: 1200,
        input: { from: "LHR", to: "LIS", depart: "Fri evening", passengers: 2 },
        output: { options: 14, nonstop: 5 },
      }),
      U(plan(["done", "active", "pending"]), { delay: 60 }),
      T("I assumed you’re flying from London on Friday evening. These are the two best nonstop options:\n\n"),
      U(
        N("grid", { columns: 2 }, [
          flight({
            airline: "TAP Air Portugal",
            code: "TP 1351",
            times: "Fri 18:05 → 20:40",
            badge: "Best value",
            price: "€189 per person",
            bags: "Cabin + 1 checked",
            back: "Sun 19:20",
          }),
          flight({
            airline: "British Airways",
            code: "BA 500",
            times: "Fri 17:15 → 19:50",
            price: "€236 per person",
            bags: "Cabin only",
            back: "Sun 20:55",
          }),
        ]),
      ),
      S({ title: "Compare neighborhoods", type: "analysis", ms: 800, output: { pick: "Príncipe Real" } }),
      U(plan(["done", "done", "active"]), { delay: 60 }),
      T(
        "\nStay in **Príncipe Real**: quiet at night, ten minutes on foot from Chiado and Bairro Alto.\n\n**Saturday.** Coffee at the garden kiosk, then walk down through Bairro Alto to Chiado. Late lunch at Time Out Market, sunset from Miradouro da Senhora do Monte.\n\n**Sunday.** Tram 28 early, before the queues. Alfama and the castle in the morning, pastéis de nata in Belém after lunch.\n\n",
      ),
      U(plan(["done", "done", "done"]), { delay: 80 }),
      T("Should I look for a hotel next?"),
      U(N("quick_replies", { options: ["Find hotels in Príncipe Real", "Add restaurant picks", "Make it three days"] })),
    ],
  };
}

function hotelsScript(): Script {
  return {
    title: "Hotels in Lisbon",
    ops: [
      S({ title: "Search hotels", type: "search", ms: 1000, output: { results: 27 } }),
      T("Three places with good reviews and rooms free for your dates:\n\n"),
      U(
        N("list", {
          items: [
            { title: "Memmo Príncipe Real", subtitle: "Rooftop pool, city views", meta: "€240 / night", action: "choose_hotel", data: { hotel: "memmo" } },
            { title: "The Late Birds", subtitle: "Garden courtyard, adults only", meta: "€185 / night", action: "choose_hotel", data: { hotel: "late-birds" } },
            { title: "Casa Oliver", subtitle: "Boutique, breakfast included", meta: "€150 / night", action: "choose_hotel", data: { hotel: "casa-oliver" } },
          ],
        }),
      ),
      T("\nAll three offer free cancellation until 48 hours before arrival."),
    ],
  };
}

function restaurantsScript(): Script {
  return {
    title: "Lisbon restaurants",
    ops: [
      T("A short list, one per meal, all walkable from Príncipe Real:\n\n"),
      U(
        N("table", {
          columns: ["Restaurant", "For", "Area", "Price"],
          rows: [
            ["Dear Breakfast", "Saturday brunch", "Príncipe Real", "€€"],
            ["Taberna da Rua das Flores", "Saturday dinner", "Chiado", "€€"],
            ["Café de São Bento", "Steak, late", "São Bento", "€€€"],
            ["Pastéis de Belém", "Sunday treat", "Belém", "€"],
          ],
          caption: "Book Taberna ahead; it fills by 7 pm",
        }),
        { progressive: "rows" },
      ),
    ],
  };
}

function offsiteScript(): Script {
  return {
    title: "Team offsite",
    ops: [
      T("Happy to. Share a few details and I’ll shortlist venues that fit.\n\n"),
      U(
        N("form", {
          title: "Offsite details",
          fields: [
            { name: "team_size", label: "Team size", type: "number", min: 2, max: 200, default: 18, required: true },
            { name: "city", label: "City", type: "select", options: ["Lisbon", "Porto", "Barcelona", "Berlin"], default: "Lisbon" },
            { name: "start", label: "Start date", type: "date" },
            { name: "nights", label: "Nights", type: "slider", min: 1, max: 4, step: 1, default: 2 },
            { name: "needs", label: "Must-haves", type: "multiselect", options: ["Workshop room", "Catering", "Hotel rooms", "Team activity"] },
            { name: "notes", label: "Anything else?", type: "textarea", placeholder: "Accessibility needs, dietary requirements…" },
          ],
          submit_label: "Find venues",
          action: "form_submit",
        }),
      ),
    ],
  };
}

function venuesOps(values: Record<string, any> = {}): Op[] {
  const size = Number(values.team_size) || 18;
  const city = typeof values.city === "string" && values.city ? values.city : "Lisbon";
  const nights = Number(values.nights) || 2;
  return [
    S({
      title: `Search venues in ${city}`,
      type: "search",
      ms: 1300,
      input: { city, people: size, nights },
      output: { matches: 6 },
    }),
    T(`Three venues fit **${size} people** in ${city} for ${nights} night${nights === 1 ? "" : "s"}, each with a workshop room and catering:\n\n`),
    U(
      N("table", {
        columns: ["Venue", "Area", "Capacity", "Per night", "Rating"],
        rows: [
          ["Palácio Chiado", "Chiado", 40, "€4,200", 4.8],
          ["LX Factory Studio", "Alcântara", 60, "€2,900", 4.6],
          ["Quinta da Regaleira Annex", "Sintra", 24, "€3,600", 4.9],
        ],
        caption: "Availability checked for your dates",
      }),
      { progressive: "rows" },
    ),
    T("\nI can request quotes from all three at once."),
    U(
      N("buttons", {
        items: [
          { label: "Request quotes", action: "request_quotes", style: "primary" },
          { label: "Show on a map", action: "show_map", style: "secondary" },
        ],
      }),
    ),
  ];
}

function branchesScript(): Script {
  const confirm = N("confirm", {
    title: "Delete 14 stale branches?",
    text: "They’ll be removed from origin. Any of them can be restored from its last commit for 30 days.",
    confirm_label: "Delete branches",
    cancel_label: "Keep them",
    action: "confirm",
    danger: true,
  });
  return {
    title: "Stale branch cleanup",
    ops: [
      S({
        title: "Scan repository",
        type: "git",
        ms: 1100,
        input: { repo: "northwind/web", stale_after_days: 90 },
        output: { branches: 37, stale: 14, open_prs: 0 },
      }),
      T(
        "I found **14 branches** with no commits in the last 90 days. None has an open pull request, and each is either merged or abandoned.\n\n",
      ),
      U(
        N("table", {
          columns: ["Branch", "Last commit", "Author"],
          rows: [
            ["feature/legacy-export", "142 days ago", "maya"],
            ["spike/graphql-gateway", "131 days ago", "dev"],
            ["fix/tz-rounding", "118 days ago", "jonas"],
            ["chore/bump-eslint-8", "104 days ago", "renovate"],
            ["exp/new-onboarding", "97 days ago", "li"],
          ],
          caption: "5 of 14 stale branches",
        }),
        { progressive: "rows" },
      ),
      T("\n"),
      ASK(confirm, (req) =>
        req && req.values?.confirmed !== false && req.action !== "cancel"
          ? [
              S({
                title: "Delete branches",
                type: "git",
                ms: 1600,
                logs: [
                  "Deleted feature/legacy-export",
                  "Deleted spike/graphql-gateway",
                  "Deleted fix/tz-rounding",
                  "Deleted 11 more",
                ],
                output: { deleted: 14, remaining: 23 },
              }),
              T(
                "Done. I deleted 14 branches and 23 active ones remain. Their last commit SHAs are saved in `stale-branches.txt` in case you need to restore one.",
              ),
            ]
          : [T("Okay, I left all 14 branches in place. I can move them under a `stale/` prefix instead, if that helps.")],
      ),
    ],
  };
}

function defaultScript(text: string): Script {
  const words = text.trim().split(/\s+/).slice(0, 6).join(" ");
  return {
    title: words.length > 2 ? words : "New chat",
    ops: [
      R("No model is connected, so answer with the scripted demo: explain the mock transport and point at the starters."),
      T(
        "This reply comes from DyUI’s **demo transport**, so there’s no model behind it. Run `dyui run app.py` and your own handler streams here instead.\n\nA reply can mix prose, code and live components. This is all it takes on the Python side:\n\n```python\nimport dyui\nfrom dyui import ui\n\napp = dyui.App(title=\"Revenue Bot\", accent=\"indigo\")\n\n@app.on_message\nasync def reply(msg: dyui.Message, chat: dyui.Chat):\n    yield \"Here’s the quarter at a glance.\"\n    yield ui.Stat(\"Revenue\", \"$4.76M\", delta=\"+10%\", trend=\"up\")\n```\n\n",
      ),
      U(
        N("callout", {
          level: "info",
          title: "Try a scripted conversation",
          text: "Each one shows different components: charts and tables, a live plan with cards, a form, and a confirmation that pauses the reply.",
        }),
      ),
      U(
        N("quick_replies", {
          options: [
            "How did revenue do this quarter?",
            "Plan a weekend in Lisbon for two",
            "Help me book a team offsite",
            "Delete the stale branches in our repo",
          ],
        }),
      ),
    ],
  };
}

function scriptFor(text: string): Script {
  const t = text.toLowerCase();
  if (/apac|soften/.test(t)) return apacScript();
  if (/board|summary/.test(t)) return boardScript();
  if (/product/.test(t)) return productScript();
  if (/japan|renewal|owns/.test(t)) return japanScript();
  if (/hotel/.test(t)) return hotelsScript();
  if (/restaurant|food|eat/.test(t)) return restaurantsScript();
  if (/revenue|quarter|sales|\bq[1-4]\b/.test(t)) return revenueScript();
  if (/lisbon|weekend|trip|travel/.test(t)) return lisbonScript();
  if (/offsite|venue/.test(t)) return offsiteScript();
  if (/branch|stale|clean/.test(t)) return branchesScript();
  return defaultScript(text);
}

type ActionOutcome =
  /** like @app.on_action yielding a reply (no user message) */
  | { mode: "reply"; ops: Op[] }
  /** like the fallback: a user message with the action label, then on_message */
  | { mode: "message"; ops: Op[] }
  | { mode: "silent" };

function actionOutcome(req: ActionRequest): ActionOutcome {
  switch (req.action) {
    case "form_submit":
      return { mode: "message", ops: venuesOps(req.values) };
    case "hold_flight":
      return {
        mode: "message",
        ops: [
          S({ title: "Hold 2 seats", type: "booking", ms: 900, input: req.data ?? {}, output: { hold: "24h", ref: "LIS-7Q4K" } }),
          T(`Done. Two seats on **${req.data?.flight ?? "that flight"}** are held for 24 hours under reference \`LIS-7Q4K\`. Nothing is charged until you confirm.\n\n`),
          U(N("callout", { level: "success", title: "Seats held", text: "The hold expires tomorrow at 18:00 Lisbon time." })),
        ],
      };
    case "flight_details":
      return {
        mode: "reply",
        ops: [
          T(`**${req.data?.flight ?? "Flight"}** at a glance:\n\n`),
          U(
            N("timeline", {
              items: [
                { title: "Check-in closes", time: "Fri 17:20", status: "done" },
                { title: "Boarding", time: "Fri 17:35", status: "active" },
                { title: "Departs London Heathrow, T2", time: "Fri 18:05", status: "pending" },
                { title: "Arrives Lisbon, T1", time: "Fri 20:40", status: "pending" },
              ],
            }),
          ),
        ],
      };
    case "choose_hotel":
      return {
        mode: "message",
        ops: [
          T(`Good choice. I’ve noted **${req.label ?? "that hotel"}** for Friday and Saturday night. Want me to book it with the flights?`),
          U(N("quick_replies", { options: ["Book both", "Not yet"] })),
        ],
      };
    case "rating":
      return { mode: "silent" };
    case "request_quotes":
      return {
        mode: "message",
        ops: [
          S({ title: "Send quote requests", type: "email", ms: 1100, output: { sent: 3 } }),
          T("Sent. Venues usually reply within a working day; I’ll collect the quotes here."),
        ],
      };
    default:
      return { mode: "message", ops: scriptFor(req.label ?? req.action).ops };
  }
}

/* ------------------------------------------------------------------ the DB */

type DB = { threads: Thread[] };
const STORAGE_KEY = "dyui:mock:v3";

function startOfToday() {
  const d = new Date();
  return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

function seedThread(title: string, at: number, turns: { user: string; ops: Op[]; answer?: (n: UINode) => ActionRequest | null }[]): Thread {
  const t = at / 1000;
  const messages: Message[] = [];
  turns.forEach((turn, i) => {
    const uid = mid();
    const aid = mid();
    messages.push({ id: uid, role: "user", created_at: t + i * 60, parts: [{ type: "text", text: turn.user }] });
    messages.push({
      id: aid,
      role: "assistant",
      created_at: t + i * 60 + 2,
      parts: collapse(turn.ops, aid, turn.answer),
      status: "done",
    });
  });
  return { id: tid(), title, created_at: t, updated_at: t + turns.length * 60, messages };
}

function seed(): DB {
  const day = 86_400_000;
  const today = startOfToday();
  const pg: Op[] = [
    T(
      "The planner scans the whole `orders` table because no index matches both the filter and the sort. At 4.2M rows that costs about 900 ms per call.\n\nA composite index fixes it:\n\n```sql\nCREATE INDEX CONCURRENTLY orders_customer_created_idx\n  ON orders (customer_id, created_at DESC);\n```\n\n`CONCURRENTLY` keeps the table writable while the index builds. Afterwards the query uses an index scan:\n\n",
    ),
    U(
      N("table", {
        columns: ["Plan", "Rows scanned", "Time"],
        rows: [
          ["Seq scan + sort", "4,212,880", "912 ms"],
          ["Index scan", "20", "1.8 ms"],
        ],
        caption: "EXPLAIN ANALYZE, before and after",
      }),
    ),
  ];
  const email: Op[] = [
    T(
      "Here’s a short draft you can adapt:\n\n> **Subject:** Welcome to Northwind, {first_name}\n>\n> Hi {first_name}, thanks for joining. Your workspace is ready, and the first thing worth doing is connecting your data source. It takes about five minutes.\n>\n> If anything is unclear, reply to this email. A person reads every one.\n\nA few notes:\n\n- Keep the first email under 120 words. Its only job is the first action.\n- Send it from a named person, not `noreply@`.\n- Follow up on day three only if the data source still isn’t connected.\n",
    ),
  ];
  const offsite = offsiteScript();
  const threads = [
    seedThread("Q3 revenue snapshot", today - day + 16.3 * 3_600_000, [{ user: "How did revenue do this quarter?", ops: revenueScript().ops }]),
    seedThread("Weekend in Lisbon", today - 3 * day + 11.2 * 3_600_000, [{ user: "Plan a weekend in Lisbon for two", ops: lisbonScript().ops }]),
    seedThread("Postgres index tuning", today - 5 * day + 9.7 * 3_600_000, [
      { user: "Why is the orders query slow? It filters by customer and sorts by date.", ops: pg },
    ]),
    seedThread("Onboarding email draft", today - 12 * day + 14 * 3_600_000, [{ user: "Draft a welcome email for new customers", ops: email }]),
    (() => {
      const th = seedThread("Team offsite venues", today - 24 * day + 10 * 3_600_000, [{ user: "Help me book a team offsite", ops: offsite.ops }]);
      // resolve the form and append the follow-up turn
      const a = th.messages[1];
      const values = { team_size: 18, city: "Lisbon", nights: 2, needs: ["Workshop room", "Catering"] };
      a.parts = a.parts.map((p) =>
        p.type === "ui" && p.node.ui === "form"
          ? { ...p, node: { ...p.node, props: { ...p.node.props, __resolved__: { label: "Find venues", values } } } }
          : p,
      );
      const u2 = mid();
      const a2 = mid();
      th.messages.push({
        id: u2,
        role: "user",
        created_at: th.created_at + 120,
        parts: [{ type: "text", text: "Find venues" }],
        action: { name: "form_submit", label: "Find venues" },
      });
      th.messages.push({ id: a2, role: "assistant", created_at: th.created_at + 122, parts: collapse(venuesOps(values), a2), status: "done" });
      return th;
    })(),
  ];
  return { threads };
}

function findNode(parts: Part[], id: string): UINode | null {
  let found: UINode | null = null;
  const walk = (v: unknown, d = 0): void => {
    if (found || d > 12 || !v || typeof v !== "object") return;
    if (Array.isArray(v)) return v.forEach((x) => walk(x, d + 1));
    const o = v as UINode;
    if (typeof o.id === "string" && typeof o.ui === "string" && o.id === id) {
      found = o;
      return;
    }
    Object.values(v as Record<string, unknown>).forEach((x) => walk(x, d + 1));
  };
  for (const p of parts) if (p.type === "ui") walk(p.node);
  return found;
}

function humanize(action: string) {
  const s = action.replace(/[_-]+/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/* ------------------------------------------------------------ the transport */

export type MockOptions = { auth?: boolean };

class MockTransport implements Transport {
  readonly kind = "mock" as const;
  private db: DB;
  private files = new Map<string, FileRef>();
  private waiters = new Map<string, (req: ActionRequest) => void>();
  private authed = false;
  private params: URLSearchParams;
  private speed: number;
  private saveTimer: ReturnType<typeof setTimeout> | null = null;

  constructor(private opts: MockOptions = {}) {
    this.params = new URLSearchParams(typeof location !== "undefined" ? location.search : "");
    const sp = Number(this.params.get("speed"));
    this.speed = Number.isFinite(sp) && sp > 0 ? sp : 1;
    this.db = this.load() ?? seed();
    try {
      this.authed = sessionStorage.getItem("dyui:mock:auth") === "1";
    } catch {
      this.authed = false;
    }
  }

  /* -- persistence (per-browser convenience; safe to fail) -- */
  private load(): DB | null {
    try {
      if (this.params.get("fresh") === "1") {
        localStorage.removeItem(STORAGE_KEY);
        return null;
      }
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      const db = JSON.parse(raw) as DB;
      return Array.isArray(db?.threads) ? db : null;
    } catch {
      return null;
    }
  }
  private save() {
    if (this.saveTimer) return;
    this.saveTimer = setTimeout(() => {
      this.saveTimer = null;
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(this.db));
      } catch {
        /* storage full or blocked */
      }
    }, 250);
  }

  private sleep(ms: number, signal?: AbortSignal) {
    return new Promise<void>((resolve, reject) => {
      if (signal?.aborted) return reject(abortError());
      const t = setTimeout(() => {
        signal?.removeEventListener("abort", onAbort);
        resolve();
      }, ms * this.speed);
      const onAbort = () => {
        clearTimeout(t);
        reject(abortError());
      };
      signal?.addEventListener("abort", onAbort, { once: true });
    });
  }

  private guard() {
    if (this.opts.auth && !this.authed) throw new ApiError("Sign in to continue.", 401);
  }

  private thread(id: string): Thread {
    const t = this.db.threads.find((x) => x.id === id);
    if (!t) throw new ApiError("That conversation no longer exists.", 404);
    return t;
  }

  private summary(t: Thread): ThreadSummary {
    return { id: t.id, title: t.title, created_at: t.created_at, updated_at: t.updated_at };
  }

  private persist(t: Thread, ev: StreamEvent) {
    t.messages = applyMessageEvent(t.messages, ev);
    t.updated_at = now();
    this.save();
  }

  /* -- REST -- */

  async getConfig(): Promise<AppConfig> {
    await this.sleep(60);
    const p = this.params;
    const flag = (k: string) => p.get(k) !== "0" && p.get(k) !== "false";
    const theme = p.get("theme");
    return {
      title: p.get("title") || "DyUI",
      description:
        "Ask anything. Answers can include charts, tables, forms and buttons, rendered live as the reply streams.",
      welcome: p.get("welcome") || "How can I help?",
      placeholder: "Message DyUI…",
      logo: null,
      theme: theme === "light" || theme === "dark" ? theme : "system",
      accent: p.get("accent") || "indigo",
      starters: [
        { label: "Revenue snapshot", message: "How did revenue do this quarter?", icon: "chart" },
        { label: "Plan a weekend", message: "Plan a weekend in Lisbon for two", icon: "plane" },
        { label: "Book a team offsite", message: "Help me book a team offsite", icon: "calendar" },
        { label: "Clean up branches", message: "Delete the stale branches in our repo", icon: "git-branch" },
      ],
      features: { history: flag("history"), uploads: flag("uploads"), feedback: flag("feedback"), auth: !!this.opts.auth },
      authenticated: !this.opts.auth || this.authed,
      version: "0.2.0",
    };
  }

  async login(password: string): Promise<void> {
    await this.sleep(420);
    if (password !== "dyui") throw new ApiError("That password isn’t right. Try again.", 401);
    this.authed = true;
    try {
      sessionStorage.setItem("dyui:mock:auth", "1");
    } catch {
      /* ignore */
    }
  }

  async listThreads(): Promise<ThreadSummary[]> {
    this.guard();
    await this.sleep(90);
    return this.db.threads
      .filter((t) => t.messages.length > 0)
      .map((t) => this.summary(t))
      .sort((a, b) => b.updated_at - a.updated_at);
  }

  async getThread(id: string): Promise<Thread> {
    this.guard();
    await this.sleep(110);
    return structuredClone(this.thread(id));
  }

  async renameThread(id: string, title: string): Promise<ThreadSummary> {
    this.guard();
    await this.sleep(80);
    const t = this.thread(id);
    t.title = title.trim().slice(0, 120) || t.title;
    this.save();
    return this.summary(t);
  }

  async deleteThread(id: string): Promise<void> {
    this.guard();
    await this.sleep(80);
    this.thread(id);
    this.db.threads = this.db.threads.filter((t) => t.id !== id);
    this.save();
  }

  async feedback(req: FeedbackRequest): Promise<void> {
    this.guard();
    await this.sleep(60);
    const t = this.thread(req.thread_id);
    t.messages = t.messages.map((m) => (m.id === req.message_id ? { ...m, feedback: req.value } : m));
    this.save();
  }

  async upload(file: File, opts: UploadOptions = {}): Promise<FileRef> {
    this.guard();
    const total = Math.min(2200, 500 + file.size / 40_000);
    const steps = Math.max(4, Math.round(total / 70));
    for (let i = 1; i <= steps; i++) {
      await this.sleep(total / steps, opts.signal);
      opts.onProgress?.(i / steps);
    }
    const ref: FileRef = {
      id: `file_${hex(10)}`,
      name: file.name,
      type: file.type || "application/octet-stream",
      size: file.size,
      url: URL.createObjectURL(file),
    };
    this.files.set(ref.id, ref);
    return ref;
  }

  /* -- streams -- */

  async *createThread(signal?: AbortSignal): AsyncGenerator<StreamEvent> {
    this.guard();
    await this.sleep(80, signal);
    const t: Thread = { id: tid(), title: "New chat", created_at: now(), updated_at: now(), messages: [] };
    this.db.threads.unshift(t);
    yield { event: "thread", data: this.summary(t) };
    yield { event: "done", data: {} };
  }

  async *chat(req: ChatRequest, signal?: AbortSignal): AsyncGenerator<StreamEvent> {
    this.guard();
    await this.sleep(rand(90, 160), signal);
    let thread = req.thread_id ? this.thread(req.thread_id) : null;
    const fresh = !thread || thread.messages.length === 0;
    if (!thread) {
      thread = { id: tid(), title: "New chat", created_at: now(), updated_at: now(), messages: [] };
      this.db.threads.unshift(thread);
      yield { event: "thread", data: this.summary(thread) };
    }
    let text = "";
    if (req.regenerate) {
      let end = thread.messages.length;
      while (end > 0 && thread.messages[end - 1].role === "assistant") end--;
      thread.messages = thread.messages.slice(0, end);
      const last = thread.messages[end - 1];
      if (!last) throw new ApiError("There’s nothing to regenerate yet.", 400);
      text = last.parts.map((p) => (p.type === "text" ? p.text : "")).join("");
    } else if (req.edit) {
      const i = thread.messages.findIndex((m) => m.id === req.edit!.message_id);
      if (i < 0 || thread.messages[i].role !== "user") throw new ApiError("That message can’t be edited.", 400);
      const old = thread.messages[i];
      const msg: Message = { ...old, parts: [...old.parts.filter((p) => p.type === "file"), { type: "text", text: req.edit.text }] };
      thread.messages = [...thread.messages.slice(0, i), msg];
      yield { event: "user_message", data: msg };
      text = req.edit.text;
    } else if (req.message) {
      const files = (req.message.files ?? []).map((id) => this.files.get(id)).filter((f): f is FileRef => !!f);
      const msg: Message = {
        id: mid(),
        role: "user",
        created_at: now(),
        parts: [...files.map((file): Part => ({ type: "file", file })), { type: "text", text: req.message.text }],
      };
      this.persist(thread, { event: "user_message", data: msg });
      yield { event: "user_message", data: msg };
      text = req.message.text;
      if (files.length && !text.trim()) text = "file";
    } else {
      throw new ApiError("Nothing to send.", 400);
    }
    thread.updated_at = now();
    const script = scriptFor(text);
    yield* this.reply(thread, script.ops, signal);
    if (fresh && thread.title === "New chat") {
      thread.title = script.title;
      this.save();
      yield { event: "title", data: { thread_id: thread.id, title: script.title } };
    }
    yield { event: "done", data: {} };
  }

  async *action(req: ActionRequest, signal?: AbortSignal): AsyncGenerator<StreamEvent> {
    this.guard();
    await this.sleep(rand(110, 180), signal);
    const thread = this.thread(req.thread_id);
    const msg = thread.messages.find((m) => m.id === req.message_id);
    if (!msg) throw new ApiError("That message no longer exists.", 404);
    const node = findNode(msg.parts, req.component_id);
    if (!node) throw new ApiError("That component isn’t part of this message.", 400);
    const label = req.label || humanize(req.action);
    const resolvedEv: StreamEvent = {
      event: "ui",
      data: { message_id: msg.id, node: { ...node, props: { ...node.props, __resolved__: { label, values: req.values ?? {} } } } },
    };
    this.persist(thread, resolvedEv);
    yield resolvedEv;

    const waiter = this.waiters.get(req.component_id);
    if (waiter) {
      this.waiters.delete(req.component_id);
      waiter(req);
      yield { event: "done", data: {} };
      return;
    }
    const outcome = actionOutcome({ ...req, label });
    if (outcome.mode === "message") {
      const user: Message = {
        id: mid(),
        role: "user",
        created_at: now(),
        parts: [{ type: "text", text: label }],
        action: { name: req.action, label },
      };
      this.persist(thread, { event: "user_message", data: user });
      yield { event: "user_message", data: user };
    }
    if (outcome.mode !== "silent") yield* this.reply(thread, outcome.ops, signal);
    yield { event: "done", data: {} };
  }

  private waitForAction(componentId: string, signal?: AbortSignal) {
    return new Promise<ActionRequest>((resolve, reject) => {
      if (signal?.aborted) return reject(abortError());
      this.waiters.set(componentId, resolve);
      signal?.addEventListener(
        "abort",
        () => {
          this.waiters.delete(componentId);
          reject(abortError());
        },
        { once: true },
      );
    });
  }

  private async *reply(thread: Thread, ops: Op[], signal?: AbortSignal): AsyncGenerator<StreamEvent> {
    const id = mid();
    const started = Date.now();
    await this.sleep(rand(420, 760), signal); // time to first event: the shell shows its thinking indicator
    const start: StreamEvent = { event: "message_start", data: { id, role: "assistant", created_at: now() } };
    this.persist(thread, start);
    yield start;
    let ended = false;
    try {
      yield* this.play(thread, id, ops, signal);
      ended = true;
      const end: StreamEvent = { event: "message_end", data: { id, status: "done", duration_ms: Date.now() - started } };
      this.persist(thread, end);
      yield end;
    } finally {
      if (!ended) this.persist(thread, { event: "message_end", data: { id, status: "cancelled" } });
    }
  }

  private async *play(thread: Thread, messageId: string, ops: Op[], signal?: AbortSignal): AsyncGenerator<StreamEvent> {
    for (const op of ops) {
      if (op.t === "ask") {
        await this.sleep(rand(160, 240), signal);
        const ev: StreamEvent = { event: "ui", data: { message_id: messageId, node: op.node } };
        this.persist(thread, ev);
        yield ev;
        const req = await this.waitForAction(op.node.id, signal);
        await this.sleep(rand(200, 320), signal);
        yield* this.play(thread, messageId, op.then(req), signal);
        continue;
      }
      for (const e of expandOp(op, messageId)) {
        await this.sleep(e.delay, signal);
        const ev = e.make();
        if (ev.event === "done") continue; // "wait" ops emit nothing
        this.persist(thread, ev);
        yield ev;
      }
    }
  }
}

export function createMockTransport(opts: MockOptions = {}): Transport {
  return new MockTransport(opts);
}

/** Exposed for tests. */
export const __test = { scriptFor, collapse, expandOp, seed };
