---
title: Behind a reverse proxy
description: Nginx and Caddy configuration for streaming replies, HTTPS and subpaths.
sidebar:
  order: 4
---

Replies are streamed with Server-Sent Events, so the proxy must **not buffer** responses, and must allow long reads. DyUI sends `X-Accel-Buffering: no` and a heartbeat comment every 15 seconds.

## Nginx

```nginx
server {
    listen 443 ssl;
    server_name bot.example.com;
    # ssl_certificate ...; ssl_certificate_key ...;

    client_max_body_size 25m;          # ≥ App(max_upload_mb=...)

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_buffering off;           # stream replies as they're generated
        proxy_cache off;
        proxy_read_timeout 1h;         # long agent runs and chat.ask() waits
    }
}
```

## Caddy

Caddy streams SSE without extra configuration:

```text
bot.example.com {
    reverse_proxy 127.0.0.1:8000
}
```

## Serving under a subpath

The web app loads its assets with relative URLs and calls the API relative to the page, so it can live under a prefix such as `https://example.com/assistant/`. Strip the prefix at the proxy:

```nginx
location /assistant/ {
    proxy_pass http://127.0.0.1:8000/;   # trailing slash strips /assistant/
    proxy_buffering off;
    proxy_read_timeout 1h;
    proxy_set_header Host $host;
}
```

## HTTPS

Terminate TLS at the proxy and run Uvicorn so that it trusts the proxy's `X-Forwarded-*` headers:

```bash
uvicorn app:app --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips 127.0.0.1
```

This matters for two security features:

- **`Secure` cookies.** The `dyui_uid` and `dyui_auth` cookies are always `HttpOnly` and `SameSite=Lax`, and are marked `Secure` when DyUI sees the request as HTTPS. Behind a TLS-terminating proxy, it only sees that through `X-Forwarded-Proto`.
- **The login throttle** (10 failed passwords per 5 minutes) is keyed on the client address. Without forwarded headers, every user shares the proxy's address.

Serve the app **only** over HTTPS in production.
