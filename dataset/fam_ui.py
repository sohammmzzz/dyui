"""Piece builders, part 2: media, interactive, agent, layout components."""
from __future__ import annotations

import re
from typing import Any

from fam_data import (Has, _fix, _s, code_piece, markdown_piece, stat_piece, keyvalue_piece, SNIPS, table_piece,
                      progress_piece, chart_trend_piece, callout_piece, badges_piece, quote_piece, divider_piece, json_piece,
                      sources_piece, timeline_piece, plan_piece, stats_piece, chart_shares_piece, chart_compare_piece,
                      chart_scatter_piece)
from kit import Ctx, Piece, cell_text, fnum, gen_url, num

# ----------------------------------------------------------------------------------------------
# media
# ----------------------------------------------------------------------------------------------

_SCENES = ["the old tram climbing Rua da Bica", "the rooftop terrace at sunset", "the new front entrance", "a team offsite on the beach",
           "the product on a white background", "the warehouse after the reorganisation", "the harvest at dawn", "the stage before doors opened",
           "the updated storefront", "the trail marker at the summit", "the finished kitchen", "the pilot batch on the line"]


def _scene(c: Ctx) -> str:
    return c.pick(_SCENES)


def image_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    has = Has(c, mode)
    url = gen_url(c, "image")
    scene = _scene(c)
    obj: dict[str, Any] = {"ui": "image", "src": url}
    if has("alt"):
        obj["alt"] = _fix(scene)
    cap = c.pick(["Photo by the site team", "Taken last week", "Draft version", "Approved by marketing"])
    if has("caption"):
        obj["caption"] = cap
    facts = _s(c, [f"Here's the photo of {scene}: {url}", f"Image URL: {url} – it shows {scene}.", f"This is {scene}: {url}"])
    if "caption" in obj:
        facts += f" Caption it \"{cap}\"."
    ask = _s(c, ["Show it in the chat.", "Can you display it?", "Put it inline."])
    intro = _s(c, ["Here is the image you shared.", "This is the photo, displayed inline."])
    outro = _s(c, ["It is shown exactly as linked, with no edits.", "The image comes straight from the URL you gave."])
    return Piece(facts, ask, [obj], intro, outro, "media", [url], lang="en")


def gallery_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    has = Has(c, mode)
    n = c.rng.randint(3, 6)
    imgs, lines = [], []
    use_alt, use_cap = has("alt"), has("caption")
    for i in range(n):
        url = gen_url(c, "image") + f"?v={i + 1}"
        scene = _scene(c)
        it: dict[str, Any] = {"src": url}
        if use_alt:
            it["alt"] = _fix(scene)
        if use_cap:
            it["caption"] = c.pick(["Day one", "Before", "After", "Detail", "Wide shot", "Close-up", "Final"])
        lines.append(f"{url} ({scene}" + (f", caption {it['caption']}" if "caption" in it else "") + ")")
        imgs.append(it)
    facts = _s(c, ["Photos from the shoot:\n", "I have these images:\n", "Gallery links:\n"]) + "\n".join("- " + l for l in lines)
    ask = _s(c, ["Show them as a gallery.", "Lay them out together.", "Display all of them in a grid."])
    intro = _s(c, [f"Here are the {c.d(n)} images as a gallery.", "This is the set of photos together."])
    outro = _s(c, ["They appear in the order you listed them.", "Open any image to see it at full size."])
    return Piece(facts, ask, [{"ui": "gallery", "images": imgs}], intro, outro, "media", [i["src"] for i in imgs], lang="en")


def video_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    has = Has(c, mode)
    url = gen_url(c, "video")
    topic = c.pick(["the product demo", "the onboarding walkthrough", "last week's town hall", "the safety briefing", "the launch teaser", "the tutorial"])
    obj: dict[str, Any] = {"ui": "video", "src": url}
    facts = f"Here's {topic}: {url}"
    if has("poster"):
        p = gen_url(c, "image")
        obj["poster"] = p
        facts += f" (cover image: {p})"
    if has("caption"):
        obj["caption"] = _fix(topic)
        facts += f". Caption it \"{_fix(topic)}\""
    facts += "."
    ask = _s(c, ["Embed it so I can watch.", "Can you play it here?", "Show the video."])
    intro = _s(c, [f"Here is {topic}, ready to play.", "The video is embedded below."])
    outro = _s(c, ["YouTube and Vimeo links embed directly; other links play from the file.", "Press play to watch it without leaving the chat."]) if "youtube" in url else \
        _s(c, ["It plays straight from the file you linked.", "Press play to watch it without leaving the chat."])
    return Piece(facts, ask, [obj], intro, outro, "media", [url], lang="en")


def audio_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    has = Has(c, mode)
    url = gen_url(c, "audio")
    title = c.pick(["Episode recap", "Voicemail from the supplier", "Standup recording", "Interview with the founder", "Demo track", "Customer call"])
    obj: dict[str, Any] = {"ui": "audio", "src": url}
    facts = f"The recording is at {url}"
    if has("title"):
        obj["title"] = title
        facts += f" – it's the {title.lower()}"
    facts += "."
    ask = _s(c, ["Give me a player for it.", "Let me listen here.", "Can you embed the audio?"])
    intro = _s(c, ["Here is an audio player for the recording.", "The recording is ready to play."])
    outro = _s(c, ["Playback starts when you press play.", "The audio streams from the link you shared."])
    return Piece(facts, ask, [obj], intro, outro, "media", [url], lang="en")


_MIME = {"pdf": "application/pdf", "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "csv": "text/csv", "zip": "application/zip"}


def file_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    has = Has(c, mode)
    url = gen_url(c, "file")
    ext = url.rsplit(".", 1)[1]
    base = c.pick(["q3-summary", "price-list", "customer-export", "audit-report", "roadmap", "invoice-batch"])
    name = f"{base}.{ext}"
    url = url.rsplit("/", 1)[0] + "/" + name
    obj: dict[str, Any] = {"ui": "file", "name": name, "url": url}
    facts = f"The file {name} is at {url}"
    if has("size"):
        if c.rng.random() < 0.5:
            sz = c.rng.randint(12000, 4800000)
            obj["size"] = sz
            facts += f", {fnum(sz, 0, c.sep)} bytes"
        else:
            sz_s = f"{round(c.rng.uniform(0.2, 48), 1)} MB"
            obj["size"] = sz_s
            facts += f", {sz_s}"
    if has("type"):
        obj["type"] = _MIME[ext]
        facts += f" ({_MIME[ext]})"
    facts += "."
    ask = _s(c, ["Let me download it.", "Attach it so I can grab it.", "Share it as a file."])
    intro = _s(c, ["Here is the file, ready to download.", "The download is attached below."])
    outro = _s(c, ["Downloading opens the exact link you provided.", "It is the same file you linked, unchanged."])
    return Piece(facts, ask, [obj], intro, outro, "media", [url], lang="en")


def link_preview_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    has = Has(c, mode)
    url = gen_url(c, "page")
    host = url.split("/")[2]
    title = c.pick(["Pricing that scales with your team", "Release notes: what's new this month", "How we cut deploy time in half", "Security overview", "2026 industry benchmark report"])
    desc = c.pick(["A plain-language walkthrough of plans and limits.", "Everything that shipped, grouped by area.", "A look at the changes behind the speedup.", "Controls, audits and data handling in one place."])
    obj: dict[str, Any] = {"ui": "link_preview", "url": url}
    facts = f"The link is {url}"
    extras = []
    if has("title"):
        obj["title"] = title
        extras.append(f"title \"{title}\"")
    if has("description"):
        obj["description"] = desc
        extras.append(f"description \"{desc}\"")
    if has("image"):
        im = gen_url(c, "image")
        obj["image"] = im
        extras.append(f"preview image {im}")
    if has("site"):
        obj["site"] = host
        extras.append(f"site {host}")
    if extras:
        facts += " with " + ", ".join(extras)
    facts += "."
    ask = _s(c, ["Show it as a preview card.", "Give me a rich preview of the link.", "Make that link look nice."])
    intro = _s(c, ["Here is a preview card for the link.", "This is the link as a rich preview."])
    outro = _s(c, ["The card opens the original page.", "Only the details you supplied are shown on the card."])
    return Piece(facts, ask, [obj], intro, outro, "media", [url], lang="en")


# ----------------------------------------------------------------------------------------------
# interactive
# ----------------------------------------------------------------------------------------------

_BTN = {
    "primary": ["Approve", "Book now", "Open dashboard", "Start review", "Continue", "Confirm details"],
    "secondary": ["Edit details", "View history", "Compare options", "Download summary", "Assign owner", "Add note"],
    "ghost": ["Remind me later", "Skip for now", "Learn more", "Not now", "See full report"],
    "danger": ["Reject request", "Decline offer", "Flag as fraud", "Mark as spam", "Dismiss alert"],
}


def _snake(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def _ident(c: Ctx) -> str:
    pfx = c.pick(["ORD", "TCK", "INV", "REQ", "CLM", "BK"])
    return f"{pfx}-{c.rng.randint(100, 9999)}"


def buttons_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    force = force or {}
    has = Has(c, mode)
    styles = list(force.get("styles") or [])
    n = max(len(styles), c.rng.randint(2, 4))
    while len(styles) < n:
        styles.append(c.pick(list(_BTN)))
    ident = _ident(c)
    used_labels: set[str] = set()
    items = []
    use_style, use_data = has("style") or bool(force.get("styles")), has("data")
    for st in styles:
        for _ in range(10):
            lab = c.pick(_BTN[st])
            if lab not in used_labels:
                break
        used_labels.add(lab)
        it: dict[str, Any] = {"label": lab, "action": _snake(lab)}
        if use_data:
            it["data"] = {"id": ident}
        if use_style:
            it["style"] = st
        items.append(it)
    facts = _s(c, [f"Request {ident} is waiting on a decision.", f"{ident} just came in and needs attention.", f"I'm looking at {ident} now."])
    ask = _s(c, ["What can I do with it?", "Give me the next actions.", "What are my options?", "Let me act on it from here."])
    intro = _s(c, [f"Here are the actions available for {ident}.", f"These are the next steps you can take on {ident}."])
    outro = _s(c, ["Each button sends its action back to me when you press it.", "Pick one and I will carry it out."])
    return Piece(facts, ask, [{"ui": "buttons", "items": items}], intro, outro, "next_actions", [ident] if use_data else [], lang="en")


_FOLLOWUPS = ["Break it down by {dim}", "Compare with last month", "Show the top 3", "What changed the most?", "Which {dim} is weakest?",
              "Set an alert for this", "Explain the biggest drop", "Show it as a table", "How does this compare to target?", "Forecast next month"]


def quick_replies_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    force = force or {}
    n = force.get("n") or c.rng.randint(2, 4)
    dim = c.pick(list(c.dom.sets))
    opts = c.sample(_FOLLOWUPS, n)
    opts = [o.format(dim=dim) for o in opts]
    m = c.metric()
    v = m.show(m.gen(c.rng), c.sep)
    facts = _s(c, [f"{m.label} is {v} this month.", f"Our {m.label.lower()} just landed at {v}.", f"{m.label}: {v}."])
    ask = _s(c, ["Suggest what I could ask next.", "What should I look at next?", "Give me some follow-up questions to tap.", "Offer me a few next questions."])
    intro = _s(c, [f"With {m.label.lower()} at {v}, these follow-ups are the most useful.", f"Here are a few natural questions to ask about {m.label.lower()}."])
    outro = _s(c, ["Tap one and I will pull it up.", "Each one sends itself as your next message."])
    return Piece(facts, ask, [{"ui": "quick_replies", "options": opts}], intro, outro, "next_questions", [], lang="en")


_CHOICES = [
    ("I want to book a table for tonight.", "What time works for you?", ["6:00 pm", "7:30 pm", "9:00 pm"], False, "pick_time", "Reserve"),
    ("Help me pick a support plan.", "Which plan fits your team?", ["Starter", "Pro", "Team", "Enterprise"], False, "choose_plan", "Continue"),
    ("Which integrations should I turn on?", "Which integrations do you want to enable?", ["Slack", "Google Sheets", "Zapier", "Webhooks"], True, "enable_integrations", "Enable"),
    ("I need to export my data.", "Which format do you prefer?", ["CSV", "JSON", "Excel"], False, "export_format", "Export"),
    ("Set up my notifications.", "How should we notify you?", ["Email", "Push", "SMS"], True, "notify_channels", "Save"),
    ("Let's schedule the review.", "Which day suits you best?", ["Monday", "Wednesday", "Friday"], False, "pick_day", "Schedule"),
    ("What should the report cover?", "Which sections should the report include?", ["Summary", "Charts", "Raw tables", "Recommendations"], True, "report_sections", "Build report"),
    ("Pick a delivery speed for me.", "How fast do you need it?", ["Standard", "Express", "Same day"], False, "delivery_speed", "Choose"),
    ("I'm not sure what to learn next.", "Which topic interests you most?", ["Statistics", "Biology", "History", "Chemistry"], False, "pick_topic", "Start"),
]


def choice_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    force = force or {}
    has = Has(c, mode)
    ask, q, opts, mult_default, action, sub = force.get("scenario") or c.pick(_CHOICES)
    obj: dict[str, Any] = {"ui": "choice", "question": q, "options": list(opts)}
    if has("multiple") and (mult_default or c.rng.random() < 0.3):
        obj["multiple"] = True
    elif mult_default and mode == "all":
        obj["multiple"] = True
    if has("allow_other"):
        obj["allow_other"] = True
    if has("action"):
        obj["action"] = action
    if has("submit_label"):
        obj["submit_label"] = sub
    intro = _s(c, ["I need one detail from you first.", "One quick question before I continue."])
    outro = _s(c, ["Your answer comes back to me as soon as you submit.", "Once you answer I will pick it up from there."])
    return Piece("", ask, [obj], intro, outro, "single_choice", [], lang="en")


_FIELD_BANK: dict[str, list[dict]] = {
    "text": [{"name": "full_name", "label": "Full name", "placeholder": "Ana Silva"}, {"name": "company", "label": "Company"},
             {"name": "order_id", "label": "Order number", "placeholder": "ORD-1042"}],
    "textarea": [{"name": "notes", "label": "Anything we should know?", "placeholder": "Allergies, access instructions..."},
                 {"name": "description", "label": "What happened?"}],
    "number": [{"name": "guests", "label": "Number of guests", "min": 1, "max": 12, "default": 2}, {"name": "quantity", "label": "Quantity", "min": 1, "max": 50}],
    "email": [{"name": "email", "label": "Email", "placeholder": "you@company.com"}],
    "select": [{"name": "priority", "label": "Priority", "options": ["Low", "Normal", "High", "Urgent"]},
               {"name": "department", "label": "Department", "options": ["Sales", "Support", "Billing", "Engineering"]}],
    "multiselect": [{"name": "topics", "label": "Topics", "options": ["Pricing", "Security", "Integrations", "Onboarding"]},
                    {"name": "days", "label": "Available days", "options": ["Mon", "Tue", "Wed", "Thu", "Fri"]}],
    "date": [{"name": "date", "label": "Preferred date"}, {"name": "start_date", "label": "Start date"}],
    "time": [{"name": "time", "label": "Preferred time"}, {"name": "arrival", "label": "Arrival time", "default": "09:00"}],
    "checkbox": [{"name": "newsletter", "label": "Send me updates", "default": False}, {"name": "terms", "label": "I accept the terms", "default": False}],
    "radio": [{"name": "contact_method", "label": "How should we contact you?", "options": ["Email", "Phone", "Chat"]},
              {"name": "seating", "label": "Seating", "options": ["Indoor", "Terrace", "Bar"]}],
    "slider": [{"name": "budget", "label": "Budget ($)", "min": 100, "max": 5000, "step": 100, "default": 1000},
               {"name": "satisfaction", "label": "How satisfied are you?", "min": 0, "max": 10, "step": 1, "default": 5}],
}
_FORM_SCENARIOS = [
    ("I want to book an appointment.", "Book an appointment", "Book", "book_appointment", ["full_name", "date", "time", "select", "notes"]),
    ("Help me file a support request.", "Support request", "Send request", "support_request", ["email", "select", "description", "multiselect", "checkbox"]),
    ("Can you set me up for the event?", "Event registration", "Register", "event_registration", ["full_name", "email", "number", "radio", "newsletter"]),
    ("I'd like a quote for the project.", "Project quote", "Get quote", "request_quote", ["company", "email", "slider", "date", "textarea"]),
    ("I need to report an incident.", "Incident report", "Submit report", "report_incident", ["time", "select", "textarea", "date", "checkbox"]),
    ("Let me reserve a table.", "Reserve a table", "Reserve", "reserve_table", ["full_name", "number", "time", "radio", "textarea"]),
    ("Start my onboarding.", "Onboarding", "Continue", "start_onboarding", ["full_name", "company", "multiselect", "slider", "checkbox"]),
]


def _pick_field(c: Ctx, token: str) -> dict:
    if token in _FIELD_BANK:
        pool = _FIELD_BANK[token]
        return dict(c.pick(pool), type=token)
    for t, pool in _FIELD_BANK.items():
        for f in pool:
            if f["name"] == token:
                return dict(f, type=t)
    raise KeyError(token)


def form_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    force = force or {}
    has = Has(c, mode)
    ask, title, sub, action, tokens = c.pick(_FORM_SCENARIOS)
    want = list(force.get("field_types") or [])
    fields = []
    have_types: set[str] = set()
    for tok in tokens:
        f = _pick_field(c, tok)
        fields.append(f)
        have_types.add(f["type"])
    for t in want:
        if t not in have_types:
            # replace a field to include the wanted type
            f = _pick_field(c, t)
            if all(x["name"] != f["name"] for x in fields):
                idx = c.rng.randrange(len(fields))
                have_types.discard(fields[idx]["type"])
                fields[idx] = f
                have_types.add(t)
    k = c.rng.randint(3, min(5, len(fields)))
    keep = fields[:k] if not want else fields
    seen: set[str] = set()
    out_fields = []
    for f in keep:
        if f["name"] in seen:
            continue
        seen.add(f["name"])
        o: dict[str, Any] = {"name": f["name"]}
        if has("label") or mode != "min":
            o["label"] = f["label"]
        if f["type"] != "text" or mode == "all" or "text" in want:
            o["type"] = f["type"]
        if "options" in f:
            o["options"] = f["options"]
        if c.rng.random() < (0 if mode == "min" else 1 if mode == "all" else 0.5):
            o["required"] = True
        for opt in ("placeholder", "default", "min", "max", "step"):
            if opt in f and (mode == "all" or (mode == "typ" and c.rng.random() < 0.6) or (opt in ("min", "max") and f["type"] in ("slider",))):
                o[opt] = f[opt]
        out_fields.append(o)
    obj: dict[str, Any] = {"ui": "form"}
    if has("title"):
        obj["title"] = title
    obj["fields"] = out_fields
    if has("submit_label"):
        obj["submit_label"] = sub
    if has("action"):
        obj["action"] = action
    intro = _s(c, ["I'll need a few details to do that.", "Here is a short form to collect what I need."])
    outro = _s(c, ["Submit it and I will take it from there.", "Your answers come straight back to me when you submit."])
    return Piece("", ask, [obj], intro, outro, "structured_input", [], lang="en")


_CONFIRMS = [
    # (ask, title, text, confirm_label, cancel_label, action, data-factory, danger)
    ("Cancel my {plan} subscription.", "Cancel your {plan} subscription?", "You keep access until the end of the billing period.", "Cancel subscription", "Keep {plan}", "cancel_subscription", lambda s: {"plan": s["plan"].lower()}, True),
    ("Delete the project {proj}.", "Delete project {proj}?", "All files and history in {proj} will be removed permanently.", "Delete project", "Keep it", "delete_project", lambda s: {"project": s["proj"]}, True),
    ("Send invoice {inv} to {client}.", "Send invoice {inv} to {client}?", "The client will receive it by email right away.", "Send invoice", "Not yet", "send_invoice", lambda s: {"invoice": s["inv"]}, False),
    ("Book the {time} flight for {amt}.", "Book the {time} flight for {amt}?", "Your card will be charged when you confirm.", "Book flight", "Go back", "book_flight", lambda s: {"flight": s["flight"]}, False),
    ("Refund order {ord} ({amt}).", "Refund order {ord}?", "{amt} goes back to the original payment method.", "Issue refund", "Cancel", "issue_refund", lambda s: {"order": s["ord"]}, False),
    ("Publish release {ver} to production.", "Publish release {ver}?", "This deploys {ver} to all production regions.", "Publish", "Not now", "publish_release", lambda s: {"version": s["ver"]}, False),
    ("Remove {person} from the workspace.", "Remove {person}?", "They will lose access to every shared board immediately.", "Remove member", "Keep member", "remove_member", lambda s: {"member": s["person"]}, True),
    ("Pay the {bill} bill ({amt}).", "Pay the {bill} bill?", "{amt} will be debited from your checking account today.", "Pay now", "Later", "pay_bill", lambda s: {"bill": s["bill"].lower()}, False),
]


def confirm_slots(c: Ctx) -> dict:
    return {"plan": c.pick(["Pro", "Team", "Starter"]), "proj": c.pick(["atlas-demo", "q3-campaign", "staging-eu", "orion-docs"]),
            "inv": f"INV-{c.rng.randint(100, 999)}", "client": c.pick(["Acme", "Northwind", "Globex"]), "time": f"{c.rng.randint(6, 21)}:{c.pick(['05', '30', '45'])}",
            "amt": f"${c.rng.randint(40, 980)}", "flight": f"TP{c.rng.randint(100, 999)}", "ord": f"ORD-{c.rng.randint(100, 9999)}",
            "ver": f"v{c.rng.randint(1, 4)}.{c.rng.randint(0, 9)}.{c.rng.randint(0, 9)}", "person": c.person(),
            "bill": c.pick(["electricity", "internet", "water", "phone"])}


def confirm_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    force = force or {}
    has = Has(c, mode)
    sc = force.get("scenario") or c.pick(_CONFIRMS)
    slots = force.get("slots") or confirm_slots(c)
    ask, title, text, yes, no, action, dfn, danger = sc
    ask = ask.format(**slots)
    obj: dict[str, Any] = {"ui": "confirm", "title": title.format(**slots)}
    if has("text"):
        obj["text"] = text.format(**slots)
    if has("confirm_label"):
        obj["confirm_label"] = yes
    if has("cancel_label"):
        obj["cancel_label"] = no.format(**slots)
    # action must be present for the E flows; always include it for destructive/outward ones
    obj["action"] = action
    data = dfn(slots)
    obj["data"] = data
    if danger:
        obj["danger"] = True
    elif has("danger") and False:
        obj["danger"] = False
    intro = _s(c, ["That one can't be undone, so I need your confirmation first.", "Before I go ahead, please confirm."]) if danger else \
        _s(c, ["Please confirm before I go ahead.", "I'll wait for your confirmation first."])
    outro = _s(c, ["Nothing happens until you choose.", "I will only proceed if you confirm."])
    ground = [str(v) for v in data.values()]
    return Piece("", ask, [obj], intro, outro, "irreversible_action", ground, lang="en")


def rating_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    force = force or {}
    has = Has(c, mode, ("style",) if force.get("style") else ())
    style = force.get("style") or c.pick(["stars", "thumbs"])
    obj: dict[str, Any] = {"ui": "rating"}
    ask = _s(c, ["I'd like to give feedback on this answer.", "Can I rate today's support chat?", "Let me rate the onboarding session.",
                 "I want to leave a rating for that tutorial.", "Thumbs up or down for this reply?" if style == "thumbs" else "How do I score this conversation?"])
    if has("label"):
        obj["label"] = c.pick(["How was this answer?", "Rate this session", "How helpful was this?", "Your feedback"])
    if style == "stars" and has("max") and c.rng.random() < 0.7:
        obj["max"] = c.pick([3, 10]) if c.rng.random() < 0.6 else 5
    if has("style") or force.get("style"):
        obj["style"] = style
    if has("action"):
        obj["action"] = c.pick(["rate_answer", "session_feedback", "rate_tutorial"])
    intro = _s(c, ["Here is a quick rating you can use.", "You can rate it right here."])
    outro = _s(c, ["Your score comes back to me as soon as you tap.", "One tap is enough; I will log it."])
    return Piece("", ask, [obj], intro, outro, "structured_input", [], lang="en")


# ----------------------------------------------------------------------------------------------
# agent: step, reasoning
# ----------------------------------------------------------------------------------------------

_STEPS = [("Search flights", "search", {"from": "LIS", "to": "MAD"}, "12 results"), ("Fetch invoice", "tool", {"invoice": "INV-0412"}, "paid"),
          ("Query orders", "sql", {"table": "orders", "window": "7d"}, "318 rows"), ("Check inventory", "tool", {"sku": "SKU-2210"}, "42 in stock"),
          ("Summarise thread", "llm", {"messages": 24}, "3 action items"), ("Geocode address", "tool", {"city": "Porto"}, "41.15, -8.61")]


def step_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    force = force or {}
    has = Has(c, mode)
    title, typ, inp, out = c.pick(_STEPS)
    status = force.get("status") or c.pick(["pending", "running", "done", "error"])
    dur = c.rng.randint(120, 4800)
    obj: dict[str, Any] = {"ui": "step", "title": title}
    if has("status") or force.get("status") or True:
        obj["status"] = status
    facts = f"The agent's '{title}' step is {status}"
    if has("type"):
        obj["type"] = typ
        facts += f", type {typ}"
    if has("input"):
        obj["input"] = inp
        facts += f", input {_jc(inp)}"
    if status in ("done", "error") and has("output"):
        o: Any = out if status == "done" else {"error": "timeout"}
        obj["output"] = o if not isinstance(o, str) else {"result": o}
        facts += f", output {_jc(obj['output'])}"
    if status in ("done", "error") and has("duration_ms"):
        obj["duration_ms"] = dur
        facts += f", took {dur} ms"
    facts += "."
    ask = _s(c, ["Show the step so I can follow along.", "Render that tool step.", "Display it in the trace."])
    intro = _s(c, [f"Here is the '{title}' step as it stands.", f"The '{title}' step is shown below with its current state."])
    outro = {"pending": "It has not started yet, so there is nothing to inspect.", "running": "It is still running; the status will update when it finishes.",
             "done": "It finished, and the output is attached to the step.", "error": "It failed, so the error is recorded on the step."}[status]
    return Piece(facts, ask, [obj], intro, outro, "work_sequence", [], lang="en")


def _jc(o: Any) -> str:
    from kit import compact
    return compact(o)


def reasoning_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    has = Has(c, mode)
    a, b = c.pick(["TAP", "Iberia"]), c.pick(["Vueling", "easyJet"])
    pa, pb = c.rng.randint(120, 420), c.rng.randint(120, 420)
    if pa == pb:
        pb += 17
    cheap, dear, pc, pd = (a, b, pa, pb) if pa < pb else (b, a, pb, pa)
    diff = c.d(pd - pc)
    text = f"Comparing the two fares: {cheap} at ${pc} is ${diff} cheaper than {dear} at ${pd}. Price is the deciding factor, so {cheap} is the better pick."
    obj: dict[str, Any] = {"ui": "reasoning", "text": text}
    facts = f"{a} costs ${pa} and {b} costs ${pb}."
    if has("duration_ms"):
        d = c.rng.randint(300, 3200)
        obj["duration_ms"] = d
        facts += f" It took {d} ms to decide."
    ask = _s(c, ["Show how you picked the cheaper one.", "Explain your reasoning for the choice.", "Walk me through why."])
    intro = "Here is the reasoning behind the choice."
    outro = f"The recommendation follows directly from the fare difference."
    return Piece(facts, ask, [obj], intro, outro, "no_component" if False else "compare", [], lang="en")


# ----------------------------------------------------------------------------------------------
# layouts (A-level builders; D composes more elaborate ones)
# ----------------------------------------------------------------------------------------------

def _leaf(c: Ctx, name: str, mode: str = "typ") -> Piece:
    return PIECES[name](c, mode, None)


def card_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    force = force or {}
    has = Has(c, mode)
    ttl, items = None, None
    title_t, ents = __import__("kit").gen_entity(c)
    name = c.pick(["Lisbon · 3 nights", "Hotel Avenida", "Riverside Studio", "Pro plan", "Spring Festival", "Orion Dashboard"])
    child_kind = c.pick(["stat", "keyvalue", "markdown"])
    child = _leaf(c, child_kind, "min")
    facts = f"{name}. " + child.facts
    obj: dict[str, Any] = {"ui": "card"}
    obj["title"] = name
    if has("subtitle"):
        sub = c.pick(["Fri – Mon", "Best value this season", "Free cancellation", "Limited seats"])
        obj["subtitle"] = sub
        facts += f" Subtitle: {sub}."
    if has("image"):
        im = gen_url(c, "image")
        obj["image"] = im
        facts += f" Cover image: {im}."
    if has("badge"):
        bd = c.pick(["New", "Popular", "Last seats", "Sale"])
        obj["badge"] = bd
        facts += f" Badge: {bd}."
    if has("children") or mode == "min":
        obj["children"] = child.objs
    else:
        obj["children"] = child.objs
    if has("actions") or force.get("action_style"):
        act = c.pick([("Book", "book_item", "primary"), ("Save", "save_item", "secondary"), ("Details", "view_details", "ghost")])
        a: dict[str, Any] = {"label": act[0], "action": act[1]}
        if force.get("action_style"):
            st = force["action_style"]
            a = {"label": {"primary": "Book", "secondary": "Save", "ghost": "Details", "danger": "Decline"}[st],
                 "action": {"primary": "book_item", "secondary": "save_item", "ghost": "view_details", "danger": "decline_item"}[st], "style": st}
            facts_btn = a["label"]
        elif c.rng.random() < 0.6:
            a["style"] = act[2]
        obj["actions"] = [a]
        facts += f" Add a {a['label']} button."
    ask = _s(c, ["Show it as a card.", "Make a card for it.", "Put it in a card."])
    intro = _s(c, [f"Here is {name} as a card.", f"This is the card for {name}."])
    outro = _s(c, ["The card keeps the details together in one place.", "Everything you listed sits on the card."])
    return Piece(facts, ask, [obj], intro, outro, "comparable_items", child.ground, lang="en")


def grid_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    force = force or {}
    has = Has(c, mode)
    k = c.rng.randint(2, 4)
    ps = [_leaf(c, "stat", "min") for _ in range(k)]
    seen = set()
    uniq = []
    for p in ps:
        if p.objs[0]["label"] not in seen:
            seen.add(p.objs[0]["label"])
            uniq.append(p)
    ps = uniq
    k = len(ps)
    cols = force.get("columns") or c.rng.randint(1, 4)
    obj: dict[str, Any] = {"ui": "grid"}
    if has("columns") or force.get("columns") or cols != 2:
        obj["columns"] = cols
    obj["children"] = [p.objs[0] for p in ps]
    facts = " ".join(p.facts for p in ps)
    facts += f" Use {cols} column{'s' if cols != 1 else ''}."
    ask = _s(c, ["Lay them out side by side.", "Arrange these as tiles in a grid.", "Show them in a grid."])
    intro = _s(c, [f"Here are the {c.d(k)} numbers in a grid.", "These are laid out as tiles."])
    outro = _s(c, ["Each tile stands on its own, so you can scan them quickly.", "The grid keeps related numbers visible together."])
    return Piece(facts, ask, [obj], intro, outro, "headline_numbers", [], lang="en")


_ENV_VARIANTS = [("Python", "python", 'import os\n\nkey = os.environ["API_KEY"]'), ("Go", "go", 'key := os.Getenv("API_KEY")'),
                 ("Node.js", "javascript", "const key = process.env.API_KEY;"), ("Ruby", "ruby", 'key = ENV.fetch("API_KEY")'),
                 ("Java", "java", 'String key = System.getenv("API_KEY");'), ("Rust", "rust", 'let key = std::env::var("API_KEY")?;'),
                 ("C#", "csharp", 'var key = Environment.GetEnvironmentVariable("API_KEY");'), ("Bash", "bash", 'echo "$API_KEY"')]
_INSTALL_VARIANTS = [("macOS", "bash", "brew install postgresql@16"), ("Ubuntu", "bash", "sudo apt install postgresql"),
                     ("Windows", "powershell", "winget install PostgreSQL.PostgreSQL"), ("Docker", "bash", "docker run -d -p 5432:5432 postgres:16")]


def tabs_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    force = force or {}
    if c.rng.random() < 0.5:
        vs = c.sample(_ENV_VARIANTS, c.rng.randint(2, 4))
        langs = ", ".join(v[0] for v in vs)
        ask = _s(c, [f"How do I read an env var in {langs.replace(', ', ' and ', 1) if len(vs) == 2 else langs}?", f"Show an env var read in {langs}."])
        topic = "reading an environment variable"
    else:
        vs = c.sample(_INSTALL_VARIANTS, c.rng.randint(2, 4))
        langs = ", ".join(v[0] for v in vs)
        ask = _s(c, [f"How do I install PostgreSQL on {langs}?", f"Give me the PostgreSQL install command for {langs}."])
        topic = "installing PostgreSQL"
    tabs = [{"label": v[0], "children": [{"ui": "code", "code": v[2], "language": v[1]}]} for v in vs]
    intro = f"Here is {topic} for each option, one tab per choice."
    outro = _s(c, ["Pick the tab that matches your setup.", "The tabs differ only in syntax, not in behaviour."])
    return Piece("", ask, [{"ui": "tabs", "tabs": tabs}], intro, outro, "variants", [], lang="en")


_FAQ = [("How do refunds work?", "Refunds go back to the original payment method within **5–10 business days**."),
        ("Can I change my plan later?", "Yes. Upgrades apply immediately; downgrades start at the next billing date."),
        ("Where is my data stored?", "Data lives in the region you pick at signup and is encrypted at rest."),
        ("Do you offer student discounts?", "Students get a discount with a valid school email."),
        ("How do I reset my password?", "Use **Forgot password** on the sign-in page and follow the emailed link."),
        ("Is there an API?", "Yes. Every plan includes API access with per-key rate limits.")]


def accordion_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    k = c.rng.randint(2, 4)
    qa = c.sample(_FAQ, k)
    items = [{"title": q, "children": [{"ui": "markdown", "text": a}]} for q, a in qa]
    ask = _s(c, ["Draft an FAQ for the pricing page.", "I need a short FAQ section.", "Put the common questions in expandable sections."])
    intro = _s(c, [f"Here are {c.d(k)} common questions, each in its own collapsible section.", "This FAQ keeps every answer one click away."])
    outro = _s(c, ["Each answer stays hidden until someone opens it.", "Add more questions the same way as they come in."])
    return Piece("", ask, [{"ui": "accordion", "items": items}], intro, outro, "faq", [], lang="en")


_PRODUCTS = [("Casa Alfama", "Lisbon", 142), ("Hotel Avenida", "Porto", 118), ("Mar & Sol", "Valencia", 96), ("Quinta Verde", "Sintra", 164), ("Praça Suites", "Lisbon", 187)]


def _hotel_cards(c: Ctx, n: int, with_actions: bool) -> tuple[list[dict], str, list[str]]:
    hs = c.sample(_PRODUCTS, n)
    cards, lines, ground = [], [], []
    for name, city, price in hs:
        card: dict[str, Any] = {"ui": "card", "title": name, "subtitle": city,
                                "children": [{"ui": "stat", "label": "Per night", "value": f"${price}"}]}
        if with_actions:
            card["actions"] = [{"label": "Book", "action": "book_hotel", "data": {"hotel": name}}]
        cards.append(card)
        lines.append(f"{name} in {city}, ${price} per night")
        ground += [name, f"${price}"]
    return cards, "; ".join(lines) + ".", ground


def carousel_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    n = c.rng.randint(3, 5)
    cards, facts, ground = _hotel_cards(c, n, c.rng.random() < 0.5)
    facts = "Hotels to compare: " + facts
    ask = _s(c, ["Show them as a swipeable row.", "Let me scroll through the options.", "Give me a carousel of them."])
    intro = _s(c, [f"Here are the {c.d(n)} hotels in a scrollable row.", "Swipe through the options below."])
    outro = _s(c, ["Each card shows the price per night for quick comparison.", "Scroll sideways to compare them one by one."])
    return Piece(facts, ask, [{"ui": "carousel", "children": cards}], intro, outro, "comparable_items", ground, lang="en")


def list_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    has = Has(c, mode)
    n = c.rng.randint(3, 5)
    hs = c.sample(_PRODUCTS, n)
    items, lines, ground = [], [], []
    use_sub, use_meta, use_act, use_img = has("subtitle"), has("meta"), has("action"), has("image")
    for name, city, price in hs:
        it: dict[str, Any] = {"title": name}
        ln = name
        if use_sub:
            it["subtitle"] = city
            ln += f", {city}"
        if use_meta:
            it["meta"] = f"${price}/night"
            ln += f", ${price}/night"
        if use_img:
            im = gen_url(c, "image")
            it["image"] = im
            ln += f", photo {im}"
        if use_act:
            it["action"] = "pick_hotel"
            it["data"] = {"hotel": name}
        items.append(it)
        lines.append(ln)
        ground.append(name)
    facts = "Hotels: " + "; ".join(lines) + "." + (" Each row should be clickable." if use_act else "")
    ask = _s(c, ["Show a compact list.", "Give me a tidy list I can scan.", "List them briefly."])
    intro = _s(c, [f"Here are the {c.d(n)} hotels as a compact list.", "This is a quick list of the options."])
    outro = _s(c, ["Tap a row to choose it." if use_act else "The rows keep the order you gave.", "Each row carries the essentials only."])
    return Piece(facts, ask, [{"ui": "list", "items": items}], intro, outro, "comparable_items", ground, lang="en")


PIECES = {
    "markdown": markdown_piece, "callout": callout_piece, "code": code_piece, "quote": quote_piece, "sources": sources_piece,
    "badges": badges_piece, "divider": divider_piece, "table": table_piece, "stat": stat_piece, "stats": stats_piece,
    "keyvalue": keyvalue_piece, "chart": None, "progress": progress_piece, "timeline": timeline_piece, "json": json_piece,
    "image": image_piece, "gallery": gallery_piece, "video": video_piece, "audio": audio_piece, "file": file_piece,
    "link_preview": link_preview_piece, "buttons": buttons_piece, "quick_replies": quick_replies_piece, "choice": choice_piece,
    "form": form_piece, "confirm": confirm_piece, "rating": rating_piece, "card": card_piece, "grid": grid_piece,
    "tabs": tabs_piece, "accordion": accordion_piece, "carousel": carousel_piece, "list": list_piece, "step": step_piece,
    "reasoning": reasoning_piece, "plan": plan_piece,
}


def chart_piece(c: Ctx, mode: str = "typ", force: dict | None = None) -> Piece:
    force = force or {}
    kind = force.get("kind") or c.pick(["line", "area", "bar", "donut", "pie", "scatter"])
    force = dict(force, kind=kind)
    if kind in ("line", "area"):
        return chart_trend_piece(c, mode, force)
    if kind == "bar":
        return chart_compare_piece(c, mode, force)
    if kind == "scatter":
        return chart_scatter_piece(c, mode, force)
    return chart_shares_piece(c, mode, force)


PIECES["chart"] = chart_piece
