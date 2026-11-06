---
title: Installation
description: Install DyUI from PyPI, with the extras for the model provider you use.
sidebar:
  order: 1
---

DyUI is one Python package. It contains the server, the CLI and the compiled chat app, so there is no Node.js or frontend build step.

```bash
pip install dyui
```

DyUI needs **Python 3.10 or newer**. Its core dependencies are FastAPI, Uvicorn, pydantic, watchfiles and python-multipart.

## Extras

Model SDKs are optional and imported only when you use them. Install the extra for your provider:

| Extra | Installs | Use it for |
|---|---|---|
| `dyui[openai]` | `openai` | OpenAI, plus every OpenAI-compatible provider: Ollama, Groq, OpenRouter, Together, DeepSeek, Gemini, Mistral, xAI |
| `dyui[anthropic]` | `anthropic` | Claude models through the Anthropic SDK |
| `dyui[langgraph]` | `langgraph>=1.0` | Streaming LangGraph agents |
| `dyui[all]` | all of the above | Trying everything |

```bash
pip install "dyui[openai]"
```

If you call a provider whose SDK isn't installed, `dyui.llm.stream` raises a `MissingDependencyError` that names the extra to install.

## Check the install

```bash
dyui version
dyui demo          # a guided tour at http://localhost:8000, no API key needed
```

## Upgrading from 0.1

DyUI 1.0 is a rewrite with a different API. The `server` extra no longer exists because the server is part of the core package. See [Upgrading from 0.1](../../changelog/#upgrading-from-01) in the changelog.
