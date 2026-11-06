---
title: Ollama & local models
description: Run a fully local DyUI bot with Ollama or any OpenAI-compatible local server.
sidebar:
  order: 3
---

Ollama exposes an OpenAI-compatible API, so DyUI talks to it through the `openai` SDK. No API key is needed.

```bash
pip install "dyui[openai]"
ollama pull llama3.2
```

```python
MODEL = "ollama/llama3.2"

@app.on_message
async def reply(msg, chat):
    async for part in dyui.llm.stream(MODEL, chat.history, components=app.catalog):
        yield part
```

DyUI connects to `http://localhost:11434/v1`. Set `OLLAMA_BASE_URL` (or pass `base_url=`) for another host.

## Tips for small models

- **Keep the catalog short.** A smaller catalog is easier to follow: `components=app.catalog.only("table", "stat", "callout", "quick_replies")`.
- **Use fence mode.** Most local models handle the `dyui` fence well. Tool calling varies by model.
- **Invalid output is safe.** A malformed component becomes a quiet "couldn't display" chip, and the rest of the answer is kept.

## Other local servers

Anything that speaks the OpenAI chat completions API works (LM Studio, vLLM, llama.cpp server). Use the `openai/` prefix with your server's URL:

```python
dyui.llm.stream("openai/local-model", chat.history, components=app.catalog,
                base_url="http://localhost:1234/v1", api_key="not-needed")
```

See the runnable [`examples/local_ollama.py`](https://github.com/sohammmzzz/dyui/blob/main/examples/local_ollama.py).
