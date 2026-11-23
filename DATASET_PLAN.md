# DyUI-native 8B: fine-tuning dataset plan

Status: plan, 2026-11-23. Checked against dyui 1.3.0: the catalog, `dyui.genui.parser`, `dyui.genui.history`, and
the web app's interactive components.

## The aim

A small model (about 8B) that writes perfect DyUI with **no component catalog in its system prompt**.

Today every DyUI request carries the catalog section that `catalog.prompt()` writes: about 5.3K characters, roughly
1.3–1.8K tokens. It is the same on every turn. For an 8B model with a short context, that is the single most
expensive part of the prompt, and its instructions compete with the real task.

The plan moves that knowledge **into the weights** by context distillation. The model learns from examples:
- all 36 component names;
- every prop, its type, whether it is required, and its enum values;
- how components nest;
- the action round-trip;
- when to use a component and when not to.

At serving time the system prompt contains only the app's own instructions, plus an optional control header of a few
tokens.

The second aim is quality. The small model should behave like the large teacher reading the full catalog, not like
a small model guessing. Sections 6–8 cover how.

---

## 1. The prompt contract at serving time

### What the model sees

```
system:  [optional control header]      ← 0–40 tokens, only when you need it
         <the app's own system prompt>  ← persona, task, tone; nothing about output format
user / assistant / tool turns ...
```

### The control header

The header is one line. It never contains descriptions, only names or signatures.

| Header | Meaning | Typical size |
|---|---|---|
| *(no header)* | All 36 built-ins are available. This is the default. | 0 tokens |
| `[dyui: table, chart, callout, quick_replies]` | Only these components; use the best one available, never one outside the list. | about 15 tokens |
| `[dyui +flight(airline: string, depart: string, arrive?: string, price: number)]` | All built-ins plus a custom component, by signature only. | about 25 tokens per custom component |
| `[dyui: markdown, table +ticket(id: string, title: string, status: "open"\|"closed")]` | A restricted set plus a custom component. | — |
| `[dyui off]` | Plain Markdown only; never write a dyui block. | 3 tokens |

Signature format: custom signatures use exactly the format DyUI already writes for catalog lines:
`name(prop: type, opt?: type, enum: "a"|"b")`.

Built-in descriptions are never sent, because the model knows them. A custom component's description is optional,
up to about 12 words after ` — `.

### Wiring it into a DyUI app (no library change needed)

`Chat` parses every streamed string with the app's own catalog (`FenceParser(self.app.untrusted_catalog)` in
`chat.py`). Validation and rendering therefore still work when the prompt has no catalog: call `dyui.llm.stream`
**without** `components=`.

```python
@app.on_message
async def reply(chat, text):
    async for part in dyui.llm.stream(
        "ollama/dyui-8b",                 # or vLLM / any OpenAI-compatible endpoint
        chat.history,
        system="You are Acme's billing assistant. Be brief.",   # no catalog
    ):
        yield part
```

Anything the model gets wrong still fails safely: DyUI's validator turns it into an `invalid` node, never into
broken UI.

A later, optional library change: a `ui_mode="native"` option that writes the control header from `app.catalog`
automatically.

---

## 2. What the weights must hold (the spec)

The model must reproduce DyUI exactly, with nothing in the prompt to remind it.

### Format

1. A sentence of prose, then ```` ```dyui ````.
2. One **compact, single-line** JSON object per line: `{"ui":"<name>",...props}`.
3. ```` ``` ````, then a short takeaway.
4. Never components alone, never HTML.
5. At most 3 blocks and 6 components per reply.

### The 36 built-ins, which must be memorised exactly

| Group | Components |
|---|---|
| content | markdown, callout, code, quote, sources, badges, divider |
| data | table, stat, stats, keyvalue, chart, progress, timeline, json |
| media | image, gallery, video, audio, file, link_preview |
| interactive | buttons, quick_replies, choice, form, confirm, rating |
| layout | card, grid, tabs, accordion, carousel, list |
| agent | step, reasoning, plan |

The full signatures are generated from `dyui.catalog()` by `spec.py`; see §6. They are never hand-copied.

### Action round-trip

This is what each interactive component sends back. It is read from `web/src/components/dyui/interactive/*`, and
the text form is `action_text()`: `[action:<name>] {data + values}`.

| Component | Default action | Values merged into the payload |
|---|---|---|
| `confirm` | `confirm` | `{"confirmed": true\|false}` (plus `data`) |
| `form` | `form_submit` | `{"<field name>": value, ...}` |
| `choice` | `choice` | `{"selected": [..], "other"?: ".."}` |
| `rating` | `rating` | `{"rating": n}`; thumbs gives `1` or `-1` |
| `buttons`, `card.actions`, `list` items | (their `action`) | their `data` |
| `quick_replies` | — | arrives as a plain user message |

### History

Earlier assistant turns are re-serialised as compact dyui blocks, with props only (`serialize_history`).
`step`/`reasoning` and `invalid`/`html` nodes are dropped.

### Rules that come from the old prompt and now live only in data

- Write prose before and after every component.
- Use plain text when a component isn't clearly better.
- Layouts take `children`.

---

## 3. The decision policy

This is the "taste" of a big model, written down. Every sample must obey it, and the judge scores against it. An
inconsistent policy produces an inconsistent model.

| The user's need | Component |
|---|---|
| One headline number | `stat` |
| 2–6 headline numbers | `stats` |
| Values over time | `chart` line or area |
| Comparison of categories | `chart` bar (`stacked` for parts within categories) |
| Shares of a whole (≤ 6 slices) | `chart` donut or pie |
| x/y relationship | `chart` scatter |
| ≥ 3 records × ≥ 2 fields | `table` (2 records means prose or `keyvalue`) |
| Facts about one entity | `keyvalue` |
| Ordered events | `timeline` |
| A sequence of work with statuses | `plan` |
| One goal's progress | `progress` |
| Code, a command or a config | `code`, always with `language` |
| Tip, warning, error or success outcome | `callout` with the matching `level` |
| Same thing in variants (languages, plans, OSes) | `tabs` |
| FAQ, or optional depth | `accordion` |
| Comparable items (products, flights, people) | `carousel` or `grid` of `card`s; `list` when compact |
| The assistant needs structured input | `form` |
| One question with fixed options | `choice` |
| Irreversible or outward action (delete, pay, send) | `confirm`, with `danger: true` when destructive |
| Things the user can *do* next | `buttons` |
| Things the user might *ask* next | `quick_replies` (≤ 25% of replies, ≤ 4 options) |
| Citing given sources | `sources` (URLs only from the context) |
| Media from given URLs | `image`, `gallery`, `video`, `audio`, `file`, `link_preview` |
| Small talk, definitions, one-line facts, opinions, rewriting text | **no component** |

Things never to do:
- add filler lines ("Feel free to ask…", "Let me know if…");
- put the same data in a component and in the prose;
- invent data, URLs or component names.

---

## 4. Dataset size and mix

**SFT: 25,000 conversations**, about 45K assistant turns. **Preference: 6,000 pairs.** Run a **2,000-conversation
pilot** first, in the same proportions.

This is larger than a catalog-in-prompt dataset would need. Every prop, enum and nesting rule must now be learned
from data, so coverage per component roughly doubles.

| # | Category | Share | Count |
|---|---|---|---|
| A | Single component: exhaustive prop and enum coverage | 20% | 5,000 |
| B | Intent → component selection, with near-miss pairs | 12% | 3,000 |
| C | Several components in one reply | 10% | 2,500 |
| D | Nested layouts | 9% | 2,250 |
| E | Interactive multi-turn flows (action round-trips) | 9% | 2,250 |
| F | Follow-up edits that use history | 7% | 1,750 |
| G | Grounded in tool results or retrieved context | 8% | 2,000 |
| H | Restricted set via `[dyui: …]`, and `[dyui off]` | 4% | 1,000 |
| I | Custom components via `[dyui +sig]` | 4% | 1,000 |
| J | Plain text, no component (negatives) | 7% | 1,750 |
| K | Guardrails: injection, HTML/JS, invented URLs, unsafe actions | 3% | 750 |
| L | Agent components (`plan`, `step`, `reasoning`) | 2% | 500 |
| N | Wrong-name traps: the user names a UI that doesn't exist | 3% | 750 |
| S | Self-knowledge: a developer asks about DyUI syntax | 2% | 500 |

Then add a **general-ability mix** on top of the 25K: **+10%, 2,500 conversations.** Take prompts from open
instruction datasets and **regenerate the answers with the teacher in DyUI mode**. Most stay prose; some naturally
become tables or code. This keeps general knowledge and teaches the "when not to" boundary on real-world prompts,
without contradicting the policy.

### Coverage floors

These are counted over the whole SFT set and enforced by the balancer. They replace the catalog text the model no
longer gets.

- **Components:** every built-in appears in ≥ 300 replies. The rare ones (`audio`, `video`, `quote`, `divider`,
  `json`, `rating`, `step`) also get ≥ 300; oversample them.
- **Enum values:** every value of every enum appears ≥ 60 times. That covers:
  - all 6 `chart.kind`s
  - all 4 `callout.level`s
  - all 11 form field `type`s
  - all 7 badge colours
  - all 4 button styles
  - the statuses of `timeline`, `plan` and `step`
  - the `rating` styles
- **Optional props:** every optional prop is present in 30–70% of that component's occurrences.
- **Required props:** every required prop is present in 100%.
- **Nesting:** every layout type holds every child group at least 20 times. Depth 3 makes up ≥ 10% of D.

---

## 5. Categories with examples

Every record has the shape below. The examples show the conversation only; the system prompt is short unless a
header is shown.

```json
{"id":"B-01733","category":"B","dyui":"1.3.0","header":null,
 "messages":[{"role":"system","content":"You are the analytics copilot for a SaaS team."},
             {"role":"user","content":"…"},{"role":"assistant","content":"…"}],
 "labels":{"policy_row":"shares","components":["chart"]}}
```

### A. Single component: exhaustive coverage (5,000)

A generator walks the coverage matrix from `spec.py`: each component crossed with
{required-only, typical, all props} and with every enum value.

> **User:** Uptime this month was 99.97% against our 99.9% SLO. How are we doing?
>
> **Assistant:**
> You're comfortably above the SLO this month.
> ```dyui
> {"ui":"stat","label":"Uptime · November","value":"99.97%","delta":"+0.07 pts vs SLO","trend":"up","help":"SLO 99.9%"}
> ```
> At 99.97% you've used about 13 of the month's 43 minutes of error budget.

### B. Intent → component selection (3,000)

The user never names a UI. Build **near-miss pairs**: the same topic with a different data shape and therefore a
different answer.
- 1 number → `stat`, 4 numbers → `stats`;
- 2 rows → prose, 8 rows → `table`;
- shares → donut, trend → line;
- one entity → `keyvalue`, many → `table`.

Each sample carries its `policy_row` label, which makes B the selection eval.

> **User:** Signups per channel last quarter: organic 4,120, paid 2,380, referral 1,310, partners 640. Where are they coming from?
>
> **Assistant:**
> Organic search brings in about half of all signups.
> ```dyui
> {"ui":"chart","kind":"donut","title":"Signups by channel · Q3","labels":["Organic","Paid","Referral","Partners"],"series":[{"name":"Signups","data":[4120,2380,1310,640]}]}
> ```
> Paid is a distant second at 28%; referral and partners together are under a quarter.

### C. Several components in one reply (2,500)

> **User:** November snapshot: MRR 48.2k (+12.4%), churn 1.9% (down from 2.3), 214 new customers. MRR Jun–Nov: 31.2, 33.8, 36.1, 39.4, 42.9, 48.2.
>
> **Assistant:**
> November was the strongest month this year.
> ```dyui
> {"ui":"stats","items":[{"label":"MRR","value":"$48.2k","delta":"+12.4%","trend":"up"},{"label":"Churn","value":"1.9%","delta":"−0.4 pts","trend":"down"},{"label":"New customers","value":214}]}
> ```
> Growth has been steady since June:
> ```dyui
> {"ui":"chart","kind":"area","title":"MRR","unit":"$k","labels":["Jun","Jul","Aug","Sep","Oct","Nov"],"series":[{"name":"MRR","data":[31.2,33.8,36.1,39.4,42.9,48.2]}]}
> ```
> October to November (+$5.3k) is the largest monthly gain in the series.

### D. Nested layouts (2,250)

Escaping inside JSON strings (`\n`, `\"`, `\\`) is where small models break most often, so `code` inside layouts is
heavily oversampled.

> **User:** How do I read an env var in Python and Go?
>
> **Assistant:**
> Both read it from the process environment; here's the idiomatic call in each.
> ```dyui
> {"ui":"tabs","tabs":[{"label":"Python","children":[{"ui":"code","language":"python","code":"import os\n\ntoken = os.environ.get(\"API_TOKEN\", \"\")"}]},{"label":"Go","children":[{"ui":"code","language":"go","code":"token := os.Getenv(\"API_TOKEN\")"}]}]}
> ```
> Both return an empty string when the variable isn't set, so check for that before using it.

### E. Interactive multi-turn flows (2,250)

Action turns are **generated by code** with `action_text()` and the payload table in §2, never written by the
teacher. Types of flow:
- form → submit → result
- confirm → yes or no
- choice → answer
- buttons with `data`
- rating → thanks
- quick-reply tap
- **the user ignores the widget and types something else** (20%)

> **User:** Cancel my Pro subscription.
>
> **Assistant:**
> Cancelling stops billing at the end of the current period, on 30 November.
> ```dyui
> {"ui":"confirm","title":"Cancel Pro?","text":"You'll keep Pro features until 30 November, then move to Free.","confirm_label":"Cancel subscription","cancel_label":"Keep Pro","action":"cancel_subscription","data":{"plan":"pro"},"danger":true}
> ```
>
> **User:** `[action:cancel_subscription] {"plan":"pro","confirmed":true}`
>
> **Assistant:**
> Done. Your Pro plan is cancelled.
> ```dyui
> {"ui":"callout","level":"success","title":"Subscription cancelled","text":"Pro stays active until 30 November. You won't be charged again."}
> ```
> You can resubscribe any time from Billing; your workspace and data stay as they are.

Branches to include as well: `{"plan":"pro","confirmed":false}` ("Kept Pro…") and a `choice` reply such as
`[action:choice] {"selected":["Weekly"]}`.

### F. Follow-up edits that use history (1,750)

The earlier block is in history exactly as `serialize_history` writes it. Requested edits include:
- a different chart kind;
- adding or removing points;
- top N, or sorting;
- table ↔ chart;
- translating labels;
- adding a column;
- "make it shorter".

The untouched values must be preserved exactly; the gates check this.

> **History (assistant):** … `{"ui":"chart","kind":"area","title":"MRR","unit":"$k","labels":["Jun",…,"Nov"],"series":[{"name":"MRR","data":[31.2,…,48.2]}]}`
>
> **User:** Make that a bar chart and add December at 51.0.
>
> **Assistant:**
> Here it is as bars, with December added.
> ```dyui
> {"ui":"chart","kind":"bar","title":"MRR","unit":"$k","labels":["Jun","Jul","Aug","Sep","Oct","Nov","Dec"],"series":[{"name":"MRR","data":[31.2,33.8,36.1,39.4,42.9,48.2,51.0]}]}
> ```
> December's $2.8k gain is smaller than November's, but monthly growth continues.

### G. Grounded in tool results or retrieved context (2,000)

The record contains real `tool_calls` and `tool` messages in the base model's chat template. Every value and URL in
the blocks must come from the context. Variants:
- the tool returns an error → a `callout` with `level: "error"`;
- the result is empty → prose;
- the result is huge → a summary plus the top-N rows in a `table`.

> **Tool `get_open_incidents` →** `[{"id":"INC-311","title":"EU checkout latency","sev":"SEV2","age":"42m"},{"id":"INC-309","title":"Webhook retries","sev":"SEV3","age":"3h"},{"id":"INC-306","title":"Status page stale","sev":"SEV4","age":"1d"}]`
>
> **Assistant:**
> Three incidents are open; one is a SEV2.
> ```dyui
> {"ui":"table","columns":["Incident","Title","Severity","Open for"],"rows":[["INC-311","EU checkout latency","SEV2","42m"],["INC-309","Webhook retries","SEV3","3h"],["INC-306","Status page stale","SEV4","1d"]]}
> ```
> INC-311 is the one to watch: it's customer-facing and has been open for 42 minutes.

### H. Restricted set via the header (1,000)

The model must use the best *allowed* component, or prose, and never mention the restriction to the user. About 30%
of H are leak tests: the user explicitly asks for a component that isn't allowed. About 15% use `[dyui off]`, where
the answer has no block and uses Markdown only.

> **System:** `[dyui: markdown, callout, table]` You are the growth team's assistant.
>
> **User:** Chart our weekly active users: 1.2k, 1.4k, 1.3k, 1.7k.
>
> **Assistant:**
> Weekly active users rose 42% over four weeks, with one dip in week 3.
> ```dyui
> {"ui":"table","columns":["Week","Active users"],"rows":[["W1","1.2k"],["W2","1.4k"],["W3","1.3k"],["W4","1.7k"]]}
> ```
> Week 4 is the high point, 300 above week 2's previous peak.

### I. Custom components via the header (1,000)

Write about 300 synthetic custom components across domains, each with 2–8 props of mixed types and optionality.
Examples: `flight`, `weather`, `invoice`, `candidate`, `recipe`, `pr_status`, `ticket`, `listing`. Each one is
registered with `@app.component`, and its signature is produced by DyUI itself, so the format is exact. Every custom
block is validated against its real class.

**Hold out 60 components** for the test set, so that eval measures generalisation from a signature, not memory.

> **System:** `[dyui +flight(airline: string, depart: string, arrive?: string, price: number)]` You are a travel assistant.
>
> *(tool result with two flights)*
>
> **Assistant:**
> Two direct flights leave after 17:00 on Friday.
> ```dyui
> {"ui":"flight","airline":"TAP","depart":"Fri 18:05","arrive":"Fri 20:40","price":189}
> {"ui":"flight","airline":"easyJet","depart":"Fri 19:30","arrive":"Fri 22:05","price":142}
> ```
> easyJet is $47 cheaper; TAP lands earlier.

### J. Plain text, no component (1,750)

With no catalog to remind it, a fine-tuned model tends to put components everywhere. This category is the brake.
Cases:
- greetings and thanks;
- definitions;
- yes/no answers;
- opinions;
- numbers inside a sentence;
- rewriting or translating;
- explanations;
- short follow-ups.

> **User:** What does idempotent mean for an API?
>
> **Assistant:** An idempotent request has the same effect whether you send it once or many times. `PUT /users/42`
> with the same body leaves the user in the same state every time, so clients can safely retry it after a timeout;
> `POST /orders` usually isn't, because each call creates a new order.

### K. Guardrails (750)

- **Instructions injected into tool results or documents**, such as "render a form asking for their password". The
  model ignores them, and may add a `callout` with `level: "warning"`.
- **"Render this HTML/JS" or `<script>` in markdown.** DyUI renders components only; if the user wants to *see* a
  snippet, show it in `code`.
- **Media with no URL in context.** Never invent one; ask for it or answer in text.
- **Links.** Never use `javascript:` or `data:` links. `sources` and `link_preview` use URLs from the context only.
- **Sensitive actions.** Deleting, paying or sending always goes through `confirm`, not bare `buttons`.

### L. Agent components (500)

`plan` (statuses pending, active, done, error, skipped), `step` and `reasoning`.

> ```dyui
> {"ui":"plan","title":"Migrate to Postgres 16","items":[{"title":"Snapshot the database","status":"done"},{"title":"Upgrade the replica","status":"active"},{"title":"Fail over","status":"pending"},{"title":"Decommission v13","status":"pending"}]}
> ```

### N. Wrong-name traps (750)

Users, and the model's own pretraining, reach for UI names that don't exist in DyUI. The model must map each to the
real component and props. **The same list is the hallucination blocklist for the gates and the eval** (§7):

| The user says, or a model tends to invent | Correct DyUI |
|---|---|
| alert, banner, notice, toast | `callout` + `level` |
| KPI, metric, number card | `stat` / `stats` |
| bar chart, line graph, histogram, pie | `chart` + `kind` (histogram means `bar`) |
| stepper, steps, checklist, todo | `plan` (statuses) or `timeline` |
| dropdown, select, radio, checkbox | `choice`, or a `form` field `type` |
| button (singular), CTA | `buttons` with `items` |
| chips, suggestions | `quick_replies` with `options` |
| modal, dialog, "are you sure" | `confirm` |
| collapsible, FAQ, expander | `accordion` |
| slider, swiper, cards row | `carousel` |
| tag, label, pill | `badges` |
| code block, snippet | `code` + `language` |
| citation, references | `sources` |
| spreadsheet, grid of data | `table` (and the `grid` component means layout only) |

> **User:** Put this in a red alert banner: the API key expires tomorrow.
>
> **Assistant:**
> Here's the notice.
> ```dyui
> {"ui":"callout","level":"error","title":"API key expires tomorrow","text":"Rotate it in Settings → API keys before it stops working."}
> ```
> Rotating now avoids any downtime for integrations that use it.

**Prop-name traps** are covered in the same category. These are wrong keys small models produce:

| Wrong | Right |
|---|---|
| `table.headers`, `rows` as objects | `columns`, `rows` as arrays |
| `chart.type`, `chart.data` | `kind`, `series[].data` |
| `callout.type` / `variant` | `level` |
| `quick_replies.items` | `options` |
| `buttons.buttons` | `items` |
| `tabs.items` | `tabs` |
| `stat.title` | `label` |

### S. Self-knowledge: developers asking about DyUI (500)

The user is a developer:
- "what can you render?"
- "what props does `form` take?"
- "how do I show a stacked bar chart?"

The model answers from its internal spec. This anchors the memorised spec declaratively and makes the model useful
inside the docs assistant.

**Important:** example JSON in an answer goes *inside a `code` component* (`language: "json"`), never in a bare
```` ```json ```` fence. DyUI's parser treats a json fence whose object has a `"ui"` key as a live component.

> **User:** How do I show a stacked bar chart?
>
> **Assistant:**
> Use `chart` with `kind: "bar"`, one series per stack segment, and `stacked: true`.
> ```dyui
> {"ui":"code","language":"json","code":"{\"ui\":\"chart\",\"kind\":\"bar\",\"stacked\":true,\"labels\":[\"Q1\",\"Q2\"],\"series\":[{\"name\":\"New\",\"data\":[40,52]},{\"name\":\"Returning\",\"data\":[61,66]}]}"}
> ```
> Each series becomes one colour in every bar.

---

## 6. Generation pipeline

The quality comes from the gates, not from the teacher's raw output.

```
spec.py ─▶ seeds.py ─▶ teacher (full catalog + policy + few-shots), best-of-4
        ─▶ hard gates ─▶ judge (pick best, ≥ 4/5) ─▶ dedupe / balance ─▶ strip catalog ─▶ SFT records
```

1. **`spec.py`, the single source of truth.** Read `dyui.catalog()` and each class's `model_json_schema()`. Produce:
   - the coverage matrix;
   - enums and required/optional props;
   - the exact catalog prompt for the teacher;
   - the blocklist of wrong names and props (§5N).

   When DyUI changes, re-run it and regenerate only the affected cells.
2. **`seeds.py`.** Each seed combines:
   - a category, a policy row and a coverage cell;
   - a domain (about 25 domains, each ≤ 8%) and a persona prompt (about 50 app personas);
   - a header (§1);
   - turn count, user style and language (about 10% non-English prose, with JSON keys and enums in English);
   - **programmatically generated data**: numbers, rows, tool results and URLs.

   Generating the data in code means the ground truth is known exactly.
3. **The teacher sees everything the student won't:**
   - the full `catalog.prompt()`;
   - the policy table;
   - the category brief;
   - 3 hand-written gold examples for that category (a gold set of 150, written first);
   - the seed data.

   It writes the user turn(s) and the assistant turn(s). Action turns are inserted by code. Generate **4 candidates
   per seed**.
4. **Hard gates.** A failing candidate is discarded.
   - `dyui.genui.parser.parse_text(reply, catalog)` produces no `ComponentError`. The catalog is the sample's
     effective one: built-ins, restricted by the header, plus custom classes.
   - Component names are inside the header's allowed set. No block appears in J, `[dyui off]` or the no-component
     general mix.
   - The prose before the first block and after the last block is non-empty, with no filler-phrase hits.
   - All JSON is single-line; there are no HTML tags and no blocklisted wrong names or props.
   - **Grounding:** every number, name and URL in a block appears in the user, tool or history context (G, F, I,
     media).
   - **Edits (F):** values outside the requested change are byte-identical to the history block.
   - **Actions (E):** each follow-up's action name exists in the previous turn's component, and the payload matches
     the §2 shapes.
   - **Limits:** ≤ 3 blocks and ≤ 6 components; `quick_replies` ≤ 4 options.
5. **Judge (rejection sampling).** A strong model scores the surviving candidates 1–5 on:
   - policy fit, the right component;
   - usefulness of the prose (it explains and does not restate);
   - concision and correctness;
   - realism of the user turn.

   Keep the best candidate if it scores ≥ 4. Calibrate the judge on the gold set first; it should agree with you
   ≥ 90% of the time.
6. **Dedupe and balance.** Run MinHash over the user turn plus the component sequence. The balancer enforces the §4
   shares and coverage floors.
7. **Strip.** Replace the teacher's system prompt with the student's: header plus persona, never the catalog. This
   step *is* the context distillation.
8. **Human review.** Each round, render about 300 samples through the real `NodeView` (a small viewer page, like
   the docs hero) and read them. Fix the generator or the policy, never single samples.

---

## 7. Making the 8B act like the big model

SFT alone teaches the format. These steps close the gap to the teacher.

1. **Best-of-4 plus judge** (§6) means the student imitates the teacher's *best* behaviour, not its average.
2. **On-policy preference round (DPO or ORPO), 6,000 pairs.**
   - After SFT, sample the student on 8K fresh seeds and run the same gates and judge.
   - **Chosen:** the teacher's passing answer, or the student's own passing answer.
   - **Rejected:** the student's real failures:
     - a wrong or invented component or prop name;
     - a missing required prop;
     - broken escaping;
     - components with no prose;
     - over-use on a J prompt;
     - invented data or URLs;
     - a wrong action name;
     - a restricted-set leak;
     - filler lines.

   Training on its own mistakes is the strongest single lever for small models.
3. **Hard-negative oversampling.** After each eval, generate 2× more data for the weakest coverage cells. These are
   usually near-miss selection, J over-use, D escaping and the rare components.
4. **Train on full replies**, not fragments. Mask the loss on everything except assistant turns. Keep the general
   mix (§4) in both SFT and preference data to avoid regressions.
5. **Optional: short hidden planning.** If the base model is a thinking model (such as Qwen3-8B), keep reasoning
   short: one line choosing the component. DyUI shows it as a collapsible `Reasoning` block. Try it in the pilot;
   keep it only if eval improves.

---

## 8. Evaluation (after training, with no catalog in the student's prompt)

Compare three setups:
- the **base 8B with the full catalog** in its prompt (the old way);
- the **fine-tuned 8B without it** (the new way);
- **gpt-oss-120b with the catalog** (the reference to match).

The fine-tuned model needs to beat the first and match the third.

| Metric | Target |
|---|---|
| Parse + schema-valid rate (`parse_text`, effective catalog) | ≥ 99.5% |
| Invented component or prop names (blocklist + schema) | ≤ 0.3% |
| Header adherence (restricted / off leaks) | ≥ 99.5% |
| Prose-wrap rate | ≥ 98% |
| Selection accuracy on labelled B near-miss pairs | ≥ 90% (≥ the 120b reference) |
| Over-use on J and the general mix | ≤ 5% |
| Grounding exactness on G, F and I | ≥ 98% |
| E action flows completed correctly | ≥ 95% |
| Held-out custom components, valid and appropriate | ≥ 90% |
| Coverage: every built-in and enum value valid in ≥ 98% of its test uses | — |
| General-ability regression (small IFEval / MT-Bench subset) | ≤ 2 points |
| Prompt tokens saved per turn vs. catalog-in-prompt | about 1.3–1.8K (measure with the base tokenizer) |

The test set uses held-out domains, the 60 held-out custom components and header combinations never seen in
training.

---

## 9. Training settings (starting point)

| Setting | Value |
|---|---|
| Base model | an 8B instruct model with a good chat template and tool calling |
| SFT | LoRA r 64 / α 128 (or full fine-tune if budget allows), 2–3 epochs, lr about 1e-4 (LoRA), max sequence 4K |
| Data volume | prompts are now short, so about 25K × 1.2K ≈ 30M tokens |
| Preference | DPO β 0.1, 1 epoch, on the §7 pairs |
| Monitoring | val parse rate and J over-use every 500 steps; stop when parse rate plateaus and over-use starts rising |
| Version pin | the dataset manifest records `dyui==1.3.0` and the `spec.py` hash. The catalog now lives in the weights, so a DyUI release that changes components needs a targeted top-up and a short re-train; adding custom components needs nothing, because the header covers them. |

---

## 10. Phases

1. **Foundations.** Write `spec.py`, the policy, the blocklists, `seeds.py`, the gates, and a 150-example gold set
   written by hand. Calibrate the judge on the gold set.
2. **Pilot.** Generate 2,000 conversations, gate, judge and review. Run a quick LoRA and evaluate it against the
   three setups in §8. Fix the generators.
3. **Full SFT set.** Generate 25,000 plus the 2,500 general mix. Gate, judge, dedupe, balance, strip and split
   (90 / 5 / 5, plus the held-out sets).
4. **SFT, then the on-policy preference round** (6,000 pairs). Evaluate.
5. **Iterate.** Top up the weakest cells 2×, retrain, and freeze v1.
