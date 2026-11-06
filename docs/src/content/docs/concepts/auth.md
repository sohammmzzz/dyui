---
title: Authentication
description: Protect an app with a shared password, and how anonymous identity works.
sidebar:
  order: 9
---

## Shared password

```python
import os
app = dyui.App(title="Internal Analyst", password=os.environ["APP_PASSWORD"])
```

With `password` set:

- the app shows a password screen first;
- `POST /api/login` checks the password with a constant-time comparison and sets a signed, `HttpOnly`, `SameSite=Lax` `dyui_auth` cookie that lasts 30 days (marked `Secure` when the request arrived over HTTPS);
- after **10 failed attempts within 5 minutes** from one client address, login answers `429 Too many attempts` until the window passes, and a successful login resets the count;
- every other `/api/*` route (except `/api/config` and `/api/logo`) returns `401` without that cookie.

The throttle is kept in memory per process and keys on the client address the server sees. Behind a reverse proxy, run Uvicorn with `--proxy-headers` (and `--forwarded-allow-ips` set to your proxy). Otherwise every user shares the proxy's address, and HTTPS isn't detected for the `Secure` flag.

The cookie is an HMAC of the password, signed with a secret. The secret comes from the `DYUI_SECRET` environment variable, or, when that isn't set, from a random key generated once in `<data_dir>/secret`. **Changing the password signs everyone out.** Set `DYUI_SECRET` explicitly when you run several instances, so they all accept the same cookie.

:::caution
A shared password is a gate, not user management. Everyone with the password shares the same app, and each browser still sees only its own conversations. Serve it over HTTPS (see [Behind a reverse proxy](../../deploy/reverse-proxy/)).
:::

## Anonymous identity

Each browser gets a random `dyui_uid` cookie, and threads, messages, uploaded files and actions are scoped to it. One browser can't read or act on another browser's conversations, even with the ids. Clearing cookies starts a fresh, empty history.

## Your own auth

DyUI's `app` is a standard ASGI application, so you can put it behind any gateway that authenticates users: an SSO proxy, your platform's access control, or ASGI middleware you wrap around it. OAuth providers are on the roadmap.
