---
title: Render, Fly & Railway
description: Deploy a DyUI app to common Python hosting platforms.
sidebar:
  order: 3
---

Every platform needs the same three things:

- **Start command:** `uvicorn app:app --host 0.0.0.0 --port $PORT --proxy-headers`
- **Persistent disk** mounted at your app's `.dyui` directory, or set `App(data_dir=...)` to the mount path
- **Environment variables:** your model API key, plus `DYUI_SECRET` if you use `password=`

Run a single instance (or enable sticky sessions); see [Production server](../production/#run-one-process-per-app).

## Render

Create a **Web Service** from your repository.

| Setting | Value |
|---|---|
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn app:app --host 0.0.0.0 --port $PORT --proxy-headers` |
| Disk | Mount path `/opt/render/project/src/.dyui` |
| Instances | 1 |

## Fly.io

Use the [Docker image](../docker/), then:

```bash
fly launch --no-deploy
fly volumes create dyui_data --size 1
fly secrets set OPENAI_API_KEY=... DYUI_SECRET=...
```

```toml title="fly.toml (excerpt)"
[mounts]
  source = "dyui_data"
  destination = "/app/.dyui"

[http_service]
  internal_port = 8000
  force_https = true
  min_machines_running = 1
```

## Railway

Deploy the repository (or the Dockerfile), then:

- set the start command to `uvicorn app:app --host 0.0.0.0 --port $PORT --proxy-headers`;
- add a **Volume** mounted at `/app/.dyui`;
- add your API keys under **Variables**.

## Serverless platforms

DyUI streams long-lived responses and keeps conversation state on disk, which suits containers and VMs. Serverless functions with short timeouts and ephemeral filesystems are a poor fit unless you add your own `Store` and keep replies short.
