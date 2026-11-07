---
title: Theming & branding
description: Title, welcome copy, starters, logo, accent colour and theme — all from App(...).
sidebar:
  order: 8
---

Everything users see is configured on `dyui.App`:

```python
app = dyui.App(
    title="Acme Support",                         # header + browser tab
    description="Answers about orders, returns and billing.",   # under the welcome heading
    welcome="How can we help today?",            # welcome heading (default "How can I help?")
    placeholder="Message {title}…",              # {title} is substituted
    logo="static/acme.svg",                      # local path (served by the app) or URL
    theme="system",                              # "system" | "light" | "dark"
    accent="emerald",                            # named accent or any hex
    starters=[
        "Where is my order?",
        dyui.Starter("Start a return", "I'd like to return an item", icon="shop"),
    ],
)
```

## Accent

Named accents: `indigo` (default), `teal`, `rose`, `amber`, `emerald` and `slate`, or any hex such as `"#0F766E"`. The app derives the soft and strong shades from it, in both themes.

## Theme

`theme` sets the default. Users can still switch between light, dark and system in the header, and their choice is remembered in the browser. The palettes are "dawn" (warm paper) and "midnight" (deep blue-ink).

## Logo

`logo` accepts a URL or a local file path. A local file is served from `/api/logo`. The logo is used in the sidebar, on the welcome screen, as the assistant's avatar and as the favicon.

## Starters

Starters are suggestion cards on the welcome screen. A plain string is both the label and the message sent. `dyui.Starter(label, message, icon=)` separates them and adds an icon. Icon names include:

`plane` · `map` · `search` · `chart` · `code` · `mail` · `calendar` · `shop` · `idea` · `write` · `tasks` · `user` · `food` · `music` · `news` · `rocket` · `settings` · `terminal` · `trend` · `zap`

Most [lucide](https://lucide.dev/icons/) icon names work too (kebab-case, e.g. `life-buoy`); unknown names fall back to a chat bubble.

## Features

| Option | Default | Effect |
|---|---|---|
| `history` | `True` | Show the conversation sidebar |
| `uploads` | `True` | Allow file attachments (`max_upload_mb=20`) |
| `feedback` | `True` | Thumbs up and down on replies (see `@app.on_feedback`) |
| `password` | `None` | Require a shared password; see [Authentication](../auth/) |
| `embed_origins` | `()` | Sites allowed to show the app in an `<iframe>`; see [Security headers](../../deploy/production/#security-headers) |
| `csp` | `True` | DyUI's strict Content-Security-Policy; a string replaces it, `False` sends none |

```python
@app.on_feedback
async def feedback(fb: dyui.Feedback, chat: dyui.Chat):
    print(fb.message_id, fb.value, fb.comment)    # value: 1, -1 or 0 (cleared)
```
