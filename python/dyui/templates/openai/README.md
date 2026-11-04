# {{title}}

A DyUI chatbot where an OpenAI model renders the interface.

```bash
pip install -r requirements.txt
cp .env.example .env     # add your OPENAI_API_KEY
export $(grep -v '^#' .env | xargs)
dyui run
```

Switch models with `DYUI_MODEL=anthropic/claude-sonnet-5-5` or `ollama/llama3.2`
(any OpenAI-compatible provider works; see the DyUI docs).
