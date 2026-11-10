---
title: Groq, OpenRouter & others
description: Every provider prefix dyui.llm.stream understands, with its endpoint and API-key variable.
sidebar:
  order: 4
---

`dyui.llm.stream` takes a `"provider/model"` string. Everything except `anthropic/` uses the `openai` SDK (`pip install "dyui[openai]"`) against the provider's OpenAI-compatible endpoint.

| Prefix | Default endpoint | API key variable | Base-URL override |
|---|---|---|---|
| `openai/` | SDK default | `OPENAI_API_KEY` | `OPENAI_BASE_URL` |
| `anthropic/` | SDK default (Anthropic SDK) | `ANTHROPIC_API_KEY` | `ANTHROPIC_BASE_URL` |
| `ollama/` | `http://localhost:11434/v1` | not required (`OLLAMA_API_KEY` if set) | `OLLAMA_BASE_URL` |
| `groq/` | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` | `GROQ_BASE_URL` |
| `openrouter/` | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` | `OPENROUTER_BASE_URL` |
| `together/` | `https://api.together.ai/v1` | `TOGETHER_API_KEY` | `TOGETHER_BASE_URL` |
| `deepseek/` | `https://api.deepseek.com` | `DEEPSEEK_API_KEY` | `DEEPSEEK_BASE_URL` |
| `gemini/` | `https://generativelanguage.googleapis.com/v1beta/openai/` | `GEMINI_API_KEY` or `GOOGLE_API_KEY` | `GEMINI_BASE_URL` |
| `mistral/` | `https://api.mistral.ai/v1` | `MISTRAL_API_KEY` | `MISTRAL_BASE_URL` |
| `xai/` | `https://api.x.ai/v1` | `XAI_API_KEY` | `XAI_BASE_URL` |
| `nvidia/` | `https://integrate.api.nvidia.com/v1` (NVIDIA NIM) | `NVIDIA_API_KEY` | `NVIDIA_BASE_URL` |

The model id may itself contain slashes:

```python
dyui.llm.stream("openrouter/anthropic/claude-sonnet-5-5", chat.history, components=app.catalog)
dyui.llm.stream("together/meta-llama/Llama-3.3-70B-Instruct-Turbo", chat.history, components=app.catalog)
dyui.llm.stream("groq/llama-3.3-70b-versatile", chat.history, components=app.catalog)
dyui.llm.stream("nvidia/meta/llama-3.3-70b-instruct", chat.history, components=app.catalog)
```

`base_url=` and `api_key=` arguments override the environment. The table is available in code as `dyui.llm.PROVIDERS`.

A provider DyUI doesn't list still works if it speaks the OpenAI API: use `openai/<model>` with `base_url=`, or [bring your own SDK](../bring-your-own-sdk/).

## Rate limits and free tiers

Free tiers (Groq, NVIDIA NIM, Gemini) limit requests and tokens per minute. `dyui.llm.stream` handles the short limits for you: on an HTTP 429 it waits for the provider's `Retry-After` (or 2s, 4s, 8s) and retries, up to `rate_limit_retries=3` times. A wait longer than a minute means a daily quota, so it fails straight away and the chat shows a rate-limit message instead of hanging.

Retries can't help when one request is bigger than the per-minute token budget. Keep requests small:

- **Stay on `ui_mode="fence"`** (the default). `ui_mode="tools"` sends a JSON schema for every component, about 6,000 tokens for the full catalog, and sends it again on every tool round.
- **Trim the catalog** to what the app needs: `components=app.catalog.only("stats", "chart", "table")`. The full fence prompt is about 1,250 tokens; `app.catalog.token_estimate()` tells you the size.
- **Lower `max_tool_rounds`** if you do use tools mode. Each round is one more request.
- **Cap the history** you send, for example `chat.history[-12:]`. Every component the model showed earlier is sent back as context.
