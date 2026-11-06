---
title: Production server
description: Serve a DyUI app with Uvicorn — process model, storage, secrets and a checklist.
sidebar:
  order: 1
---

`dyui run` is for development: it reloads on every save. In production, serve the ASGI app with Uvicorn:

```bash
pip install dyui
uvicorn app:app --host 0.0.0.0 --port 8000 --proxy-headers
```

The compiled chat app ships inside the wheel, so there's nothing to build. The same process serves the web app (`/`), its assets and the API (`/api/*`).

## Run one process per app

`chat.ask()` waits **in memory** for the user's answer, and in-flight streams belong to the process that started them. Run **one worker** (Uvicorn's default) and scale by giving each instance its own data. If you must run several workers or replicas, use sticky sessions so that a browser always reaches the same process, and share the store.

A single async worker handles many concurrent chats, because handlers spend most of their time awaiting the model.

## Storage

- Conversations go to SQLite at `./.dyui/dyui.db`, and uploads to `./.dyui/uploads/`. Mount `.dyui` on a **persistent volume**, or set `App(data_dir="/var/lib/my-bot")`.
- For a managed database, implement a [`Store`](../../concepts/sessions-and-persistence/#your-own-store) and pass it as `persist=`.
- `persist=False` keeps everything in memory, which suits demos and stateless bots.

## Secrets

- Keep model API keys in environment variables (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`…). DyUI never sends them to the browser.
- With `password=`, set **`DYUI_SECRET`** to a long random value so the auth cookie survives redeploys and works on every instance:

```bash
export DYUI_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
```

## Checklist

- [ ] Serve over **HTTPS**, terminated at your proxy or platform; see [Behind a reverse proxy](../reverse-proxy/).
- [ ] Disable response buffering for `/api/` so replies stream. DyUI sends `X-Accel-Buffering: no` and a 15-second heartbeat, but some proxies need explicit configuration.
- [ ] Put `.dyui/` (or your `data_dir`) on persistent storage, and back it up.
- [ ] Set `DYUI_SECRET` if you use `password=`.
- [ ] Set `max_upload_mb`, or `uploads=False` if you don't need attachments. Oversized uploads, and JSON bodies over 1 MB, are refused with `413` before they're buffered.
- [ ] Behind a proxy, pass `--proxy-headers --forwarded-allow-ips <proxy ip>`, so HTTPS is detected (`Secure` cookies) and the login throttle sees real client addresses.
- [ ] Log at `INFO`: DyUI logs handler exceptions on the `dyui` logger, and users only see a generic error.

## Health check

`GET /api/config` returns the app's public configuration with a `200`, which makes a cheap readiness probe.
