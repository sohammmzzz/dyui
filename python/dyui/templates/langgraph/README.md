# {{title}}

A DyUI chatbot backed by a LangGraph agent. Text streams as the model writes it,
and components passed to `emit()` appear inline.

```bash
pip install -r requirements.txt
cp .env.example .env     # add your OPENAI_API_KEY
export $(grep -v '^#' .env | xargs)
dyui run
```
