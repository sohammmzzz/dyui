# {{title}}

A DyUI chatbot where a Claude model renders the interface.

```bash
pip install -r requirements.txt
cp .env.example .env     # Windows: copy .env.example .env  - then add your ANTHROPIC_API_KEY
dyui run                 # loads .env automatically
```

`dyui run` reads `.env` next to `app.py` and never overrides a variable you already set in
your shell. Keep `.env` out of git.

Uncomment the `thinking=` line in `app.py` to stream Claude's reasoning.
API keys for every provider: https://sohammmzzz.github.io/dyui/get-started/api-keys/
