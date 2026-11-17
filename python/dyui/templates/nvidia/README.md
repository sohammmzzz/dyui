# {{title}}

A DyUI chatbot where the model renders the interface.

```bash
pip install -r requirements.txt
cp .env.example .env     # Windows: copy .env.example .env  - then add your NVIDIA_API_KEY
dyui run                 # loads .env automatically
```

Open http://127.0.0.1:8000. `dyui run` reads `.env` next to `app.py` and never overrides a
variable you already set in your shell. Keep `.env` out of git.

Switch models with `DYUI_MODEL`: any model from https://build.nvidia.com as `nvidia/<model id>`,
or another provider such as `openai/...`, `anthropic/...` or `ollama/...`. API keys for every
provider: https://sohammmzzz.github.io/dyui/get-started/api-keys/

Want help building it out? `pip install "dyui[mcp]"` then `dyui mcp install` gives your coding agent the DyUI docs, component schemas and validators.
