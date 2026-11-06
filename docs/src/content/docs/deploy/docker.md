---
title: Docker
description: A small production image for a DyUI app.
sidebar:
  order: 2
---

```dockerfile title="Dockerfile"
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN useradd --create-home bot && mkdir -p /app/.dyui && chown -R bot /app/.dyui
USER bot

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
```

```text title="requirements.txt"
dyui[openai]
```

```text title=".dockerignore"
.dyui/
.venv/
__pycache__/
.env
```

Build and run it with a volume for conversations and uploads:

```bash
docker build -t my-bot .
docker run -p 8000:8000 \
  -e OPENAI_API_KEY \
  -e DYUI_SECRET \
  -v my-bot-data:/app/.dyui \
  my-bot
```

## Compose

```yaml title="compose.yaml"
services:
  bot:
    build: .
    ports: ["8000:8000"]
    environment:
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      DYUI_SECRET: ${DYUI_SECRET}
    volumes:
      - bot-data:/app/.dyui
    restart: unless-stopped
volumes:
  bot-data:
```

Keep a single container per app, or use sticky sessions; see [Run one process per app](../production/#run-one-process-per-app).
