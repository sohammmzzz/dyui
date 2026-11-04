/** Example nodes for every built-in component — used by the gallery and docs demos. */
import type { UINode } from "../lib/types";

let n = 0;
const node = (ui: string, props: Record<string, any>, children?: UINode[]): UINode => ({ id: `fx_${ui}_${++n}`, ui, props, children, status: "done" });
const img = (id: string, w = 1200) => `https://images.unsplash.com/${id}?auto=format&fit=crop&w=${w}&q=70`;
const LISBON = img("photo-1555881400-74d7acaacd8b");
const PORTO = img("photo-1555881400-69a2384edcd4");

export const FIXTURES: Record<string, UINode[]> = {
  markdown: [node("markdown", { text: "## Your Lisbon weekend\nTwo nights in **Alfama**, a sunset tram ride on the *28*, and dinner at a tasca the locals actually use.\n\n- Fri — arrive 18:05, check in\n- Sat — Belém, pastéis, LX Factory\n- Sun — Sintra day trip\n\nTotal estimate: `€640` per person." })],
  callout: [
    node("callout", { level: "info", title: "Prices refresh every 15 minutes", text: "Fares shown are live from the airline and may change before you book." }),
    node("callout", { level: "success", text: "Your refund of **€189.00** was approved and will arrive in 3–5 business days." }),
    node("callout", { level: "warning", title: "Passport validity", text: "Your passport expires within 6 months of travel. Some countries may refuse entry." }),
  ],
  code: [node("code", { language: "python", filename: "app.py", code: 'import dyui\nfrom dyui import ui\n\napp = dyui.App(title="Travel Bot", accent="indigo")\n\n@app.on_message\nasync def reply(msg: dyui.Message, chat: dyui.Chat):\n    yield "Here are two options:"\n    yield ui.Stat("Cheapest", "$189", delta="-12%", trend="down")\n' })],
  quote: [node("quote", { text: "The best interface is the one that appears exactly when you need it, and gets out of the way after.", author: "Maya Lin", source: "Design notes, 2026" })],
  sources: [node("sources", { items: [
    { title: "Lisbon travel guide — neighbourhoods, transport and tips", url: "https://www.visitlisboa.com/en", snippet: "Official tourism portal with itineraries and the Lisboa Card." },
    { title: "Tram 28: the complete route", url: "https://en.wikipedia.org/wiki/Lisbon_tramway_network", snippet: "History and stops of Lisbon’s most famous tram line." },
    { title: "TAP Air Portugal — flight status", url: "https://www.flytap.com/en-us/" },
  ] })],
  badges: [node("badges", { items: [{ label: "Direct flight", color: "green" }, { label: "Free cancellation", color: "accent" }, { label: "2 seats left", color: "amber" }, { label: "Economy", color: "gray" }, { label: "Wi‑Fi", color: "blue" }] })],
  divider: [node("divider", { label: "Return journey" })],
  table: [node("table", { caption: "Flights to Lisbon · Fri 14 Nov", columns: ["Airline", "Depart", "Arrive", "Stops", "Price"], rows: [
    ["TAP Air Portugal", "18:05", "20:40", 0, "$189"], ["easyJet", "06:50", "09:30", 0, "$142"], ["Lufthansa", "11:15", "16:05", 1, "$264"], ["Iberia", "13:40", "18:55", 1, "$231"], ["Ryanair", "21:10", "23:45", 0, "$118"],
  ] })],
  stat: [node("stat", { label: "Monthly recurring revenue", value: "$48.2k", delta: "+12.4%", trend: "up", help: "vs. October" })],
  stats: [node("stats", { items: [
    { label: "Revenue", value: "$48.2k", delta: "+12%", trend: "up" },
    { label: "Active users", value: "12,840", delta: "+4.1%", trend: "up" },
    { label: "Churn", value: "2.3%", delta: "−0.4%", trend: "down" },
    { label: "NPS", value: 61, delta: "0", trend: "flat" },
  ] })],
  keyvalue: [node("keyvalue", { items: [
    { key: "Booking reference", value: "TP-7Q4XK2" }, { key: "Passenger", value: "Alex Morgan" }, { key: "Route", value: "London LHR → Lisbon LIS" },
    { key: "Departure", value: "Fri 14 Nov, 18:05" }, { key: "Seat", value: "14A · window" }, { key: "Checked bag", value: true },
  ] })],
  chart: [
    node("chart", { kind: "area", title: "Revenue", unit: "$", labels: ["Jun", "Jul", "Aug", "Sep", "Oct", "Nov"], series: [{ name: "Revenue", data: [31200, 33800, 36100, 39400, 42900, 48200] }] }),
    node("chart", { kind: "bar", title: "Tickets by channel", labels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], series: [{ name: "Chat", data: [42, 51, 47, 60, 55, 28, 22] }, { name: "Email", data: [30, 28, 35, 31, 26, 12, 9] }] }),
    node("chart", { kind: "donut", title: "Trip budget", unit: "€", labels: ["Flights", "Hotel", "Food", "Activities", "Transport"], series: [{ name: "Budget", data: [378, 420, 210, 140, 60] }] }),
    node("chart", { kind: "line", title: "Response time", unit: "ms", labels: ["W1", "W2", "W3", "W4", "W5", "W6", "W7", "W8"], series: [{ name: "p50", data: [220, 210, 205, 190, 185, 180, 176, 170] }, { name: "p95", data: [610, 590, 640, 560, 520, 500, 470, 455] }] }),
  ],
  progress: [node("progress", { label: "Onboarding", value: 68 }), node("progress", { label: "Documents uploaded", value: 3, max: 4 })],
  timeline: [node("timeline", { items: [
    { title: "Order placed", time: "Mon 09:12", text: "Payment confirmed — Visa ending 4242.", status: "done" },
    { title: "Packed at warehouse", time: "Mon 16:40", status: "done" },
    { title: "Out for delivery", time: "Today", text: "Courier is 4 stops away.", status: "active" },
    { title: "Delivered", status: "pending" },
  ] })],
  json: [node("json", { title: "Webhook payload", data: { id: "evt_1Q8x", type: "invoice.paid", created: 1730716800, data: { amount: 4900, currency: "usd", customer: { id: "cus_92", email: "alex@example.com" }, lines: [{ sku: "pro-monthly", qty: 1 }] }, livemode: false } })],
  image: [node("image", { src: LISBON, alt: "Lisbon rooftops at golden hour", caption: "Alfama at golden hour — your hotel is two streets from here." })],
  gallery: [node("gallery", { images: [
    { src: img("photo-1555881400-74d7acaacd8b", 800), alt: "Lisbon rooftops", caption: "Alfama" },
    { src: img("photo-1513735492246-483525079686", 800), alt: "Tram in Lisbon", caption: "Tram 28" },
    { src: img("photo-1588614959060-4d144f28b207", 800), alt: "Belém tower", caption: "Belém" },
    { src: img("photo-1536663815808-535e2280d2c2", 800), alt: "Sintra palace", caption: "Sintra" },
  ] })],
  video: [node("video", { src: "https://www.youtube.com/watch?v=aqz-KE-bpKQ", caption: "Big Buck Bunny — sample video (loads on click)" })],
  audio: [node("audio", { src: "https://interactive-examples.mdn.mozilla.net/media/cc0-audio/t-rex-roar.mp3", title: "Voice memo — itinerary summary" })],
  file: [node("file", { name: "Lisbon-itinerary.pdf", url: "https://example.com/files/lisbon-itinerary.pdf", size: 248000, type: "application/pdf" }), node("file", { name: "q3-revenue.csv", url: "https://example.com/files/q3.csv", size: 18200 })],
  link_preview: [node("link_preview", { url: "https://www.visitlisboa.com/en/places/alfama", title: "Alfama — the oldest district in Lisbon", description: "Narrow streets, fado houses and the best viewpoints over the Tagus river.", image: img("photo-1513735492246-483525079686", 600), site: "Visit Lisboa" })],
  buttons: [node("buttons", { items: [{ label: "Book TAP · $189", action: "book_flight", data: { flight: "TP1351" }, style: "primary" }, { label: "Hold seat 24h", action: "hold", style: "secondary" }, { label: "See more options", action: "more", style: "ghost" }] })],
  quick_replies: [node("quick_replies", { options: ["Check hotels too", "Book the cheaper one", "What about Porto?"] })],
  choice: [node("choice", { question: "Which part of Lisbon suits you best?", options: ["Alfama — historic, hilly, fado", "Chiado — central, shopping, cafés", "Príncipe Real — quiet, leafy, boutique"], allow_other: true })],
  form: [node("form", { title: "Request a quote", submit_label: "Get quote", fields: [
    { name: "name", label: "Full name", type: "text", required: true, placeholder: "Alex Morgan" },
    { name: "email", label: "Email", type: "email", required: true, placeholder: "alex@example.com" },
    { name: "date", label: "Departure", type: "date" },
    { name: "cabin", label: "Cabin", type: "select", options: ["Economy", "Premium", "Business"] },
    { name: "travellers", label: "Travellers", type: "slider", min: 1, max: 8, default: 2 },
    { name: "extras", label: "Extras", type: "multiselect", options: ["Checked bag", "Seat choice", "Lounge", "Insurance"] },
    { name: "flex", label: "Flexibility", type: "radio", options: ["Exact", "±1 day", "±3 days"], default: "Exact" },
    { name: "notes", label: "Anything else?", type: "textarea", placeholder: "Dietary needs, accessibility…" },
    { name: "terms", label: "I agree to the booking terms", type: "checkbox", required: true },
  ] })],
  confirm: [node("confirm", { title: "Book TAP 18:05 for $189?", text: "Your card ending 4242 will be charged now. Free cancellation for 24 hours.", confirm_label: "Book flight", cancel_label: "Not yet", action: "confirm_booking", data: { flight: "TP1351" } }), node("confirm", { title: "Delete this workspace?", text: "All 14 conversations and uploaded files will be permanently removed.", confirm_label: "Delete", danger: true })],
  rating: [node("rating", { label: "How helpful was this itinerary?" }), node("rating", { label: "Did this answer your question?", style: "thumbs" })],
  card: [
    node("card", { title: "TAP Air Portugal", subtitle: "LHR → LIS · Fri 14 Nov · Direct", badge: "Best value", actions: [{ label: "Book · $189", action: "book_flight", style: "primary" }, { label: "Details", action: "details", style: "ghost" }] }, [
      node("keyvalue", { items: [{ key: "Departs", value: "18:05" }, { key: "Arrives", value: "20:40" }, { key: "Duration", value: "2h 35m" }] }),
    ]),
    node("card", { title: "Memmo Alfama", subtitle: "Boutique hotel · rooftop pool", image: PORTO, badge: { label: "9.2 · Superb", color: "green" } }, [node("markdown", { text: "Quiet, design-led rooms above the river. **€182 / night**, breakfast included." })]),
  ],
  grid: [node("grid", { columns: 2 }, [node("stat", { label: "Flights", value: "$189" }), node("stat", { label: "Hotel · 2 nights", value: "€364" })])],
  tabs: [node("tabs", { tabs: [
    { label: "Overview", children: [{ ui: "markdown", text: "A relaxed long weekend: history in **Alfama**, food in **Cais do Sodré**, and a day in Sintra." }] },
    { label: "Budget", children: [{ ui: "stats", items: [{ label: "Total", value: "€1,208" }, { label: "Per day", value: "€403" }] }] },
    { label: "Checklist", children: [{ ui: "plan", title: "Before you go", items: [{ title: "Book flights", status: "done" }, { title: "Reserve hotel", status: "active" }, { title: "Buy Lisboa Card", status: "pending" }] }] },
  ] })],
  accordion: [node("accordion", { items: [
    { title: "Can I change my flight?", children: [{ ui: "markdown", text: "Yes — changes are free up to **24 hours** before departure. After that a €45 fee applies." }] },
    { title: "What is included in the fare?", children: [{ ui: "badges", items: [{ label: "Cabin bag", color: "green" }, { label: "Seat selection", color: "gray" }] }] },
    { title: "How do refunds work?", text: "Refunds go back to the original payment method within 3–5 business days." },
  ] })],
  carousel: [node("carousel", { title: "Hotels in Alfama" }, [
    node("card", { title: "Memmo Alfama", subtitle: "€182 / night · 9.2", image: img("photo-1566073771259-6a8506099945", 700) }),
    node("card", { title: "Santiago de Alfama", subtitle: "€214 / night · 9.4", image: img("photo-1582719478250-c89cae4dc85b", 700) }),
    node("card", { title: "Palácio Belmonte", subtitle: "€390 / night · 9.6", image: img("photo-1551882547-ff40c63fe5fa", 700) }),
  ])],
  list: [node("list", { items: [
    { title: "Pastéis de Belém", subtitle: "Bakery since 1837 — the original custard tart", meta: "€1.40", action: "add_stop", image: img("photo-1588614959060-4d144f28b207", 200) },
    { title: "Time Out Market", subtitle: "Food hall with 24 kitchens", meta: "€€", action: "add_stop", image: img("photo-1513735492246-483525079686", 200) },
    { title: "Miradouro da Graça", subtitle: "Sunset viewpoint, free", meta: "Free", action: "add_stop", image: img("photo-1555881400-74d7acaacd8b", 200) },
  ] })],
  step: [node("step", { title: "Search flights LHR → LIS", type: "search", status: "done", duration_ms: 1240, input: { from: "LHR", to: "LIS", date: "2026-11-14" }, output: "5 results" }), node("step", { title: "Checking hotel availability", type: "tool", status: "running" })],
  reasoning: [node("reasoning", { text: "The user wants a weekend trip. Friday evening departures keep Saturday free, so I'll prioritise flights after 17:00 and compare total cost including bags.", duration_ms: 4200 })],
  plan: [node("plan", { title: "Planning your trip", items: [{ title: "Find flights", status: "done" }, { title: "Shortlist hotels", status: "done" }, { title: "Build day-by-day itinerary", status: "active" }, { title: "Estimate budget", status: "pending" }, { title: "Car rental", status: "skipped" }] })],
  html: [node("html", { html: '<div style="padding:16px;border:1px solid var(--dy-border);border-radius:14px;background:var(--dy-surface)"><b>Boarding pass</b><div style="font-size:28px;margin-top:6px">LHR → LIS</div><div style="color:var(--dy-text-muted)">Seat 14A · Gate B32 · Boards 17:35</div></div>' })],
  invalid: [{ id: "fx_invalid", ui: "invalid", status: "error", props: { raw: '{"ui":"chart","kind":"radar","series":[...]}', error: 'Unknown chart kind "radar"' } }],
};
