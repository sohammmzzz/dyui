# {{title}}

A DyUI chatbot where an OpenAI model renders the interface.

```bash
pip install -r requirements.txt
cp .env.example .env     # Windows: copy .env.example .env  - then add your OPENAI_API_KEY
dyui run                 # loads .env automatically
```

`dyui run` reads `.env` next to `app.py` and never overrides a variable you already set in
your shell. Keep `.env` out of git.

Switch models with `DYUI_MODEL=anthropic/claude-sonnet-5-5` or `ollama/llama3.2`
(any OpenAI-compatible provider works). API keys for every provider:
https://sohammmzzz.github.io/dyui/get-started/api-keys/
