# {{title}}

A DyUI chatbot where a Claude model renders the interface.

```bash
pip install -r requirements.txt
cp .env.example .env     # add your ANTHROPIC_API_KEY
export $(grep -v '^#' .env | xargs)
dyui run
```

Uncomment the `thinking=` line in `app.py` to stream Claude's reasoning.
