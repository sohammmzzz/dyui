# {{title}}

A DyUI chatbot where the model renders the interface.

```bash
pip install -r requirements.txt
cp .env.example .env     # add your NVIDIA_API_KEY
export $(grep -v '^#' .env | xargs)
dyui run
```

Switch models with `DYUI_MODEL`: any model from https://build.nvidia.com as `nvidia/<model id>`,
or another provider such as `openai/...`, `anthropic/...` or `ollama/...` (see the DyUI docs).

Want help building it out? `dyui agent` opens your coding agent with the DyUI skill loaded.
