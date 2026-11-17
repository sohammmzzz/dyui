# {{title}}

A DyUI chatbot backed by a LangGraph agent. Text streams as the model writes it,
and components passed to `emit()` appear inline.

```bash
pip install -r requirements.txt
cp .env.example .env     # Windows: copy .env.example .env  - then add your OPENAI_API_KEY
dyui run                 # loads .env automatically
```

`dyui run` reads `.env` next to `app.py` and never overrides a variable you already set in
your shell. Keep `.env` out of git.
API keys for every provider: https://sohammmzzz.github.io/dyui/get-started/api-keys/
