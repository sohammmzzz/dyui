# DyUI examples

Run any of them with `dyui run examples/<file>.py` (install `dyui[all]` for the LLM ones).
Pick a model with `DYUI_MODEL`, e.g. `DYUI_MODEL=anthropic/claude-sonnet-5-5`.

| file | shows |
|---|---|
| `no_llm.py` | Pure Python: scripted components, actions, steps, `chat.ask`. No API key. |
| `travel_bot.py` | LLM + custom `Flight` / `Hotel` components, `@app.on_action`, human-in-the-loop `chat.ask(ui.Confirm(...))`. |
| `data_analyst.py` | The model answers with stats, charts and tables computed from an in-file dataset. |
| `support_bot.py` | Support flow: form, plan, sources and live steps. |
| `langgraph_agent.py` | LangGraph agent streaming text and `emit()`ed components. |
| `bring_your_own_sdk.py` | Raw `openai` client + `app.catalog.prompt()`; yield raw text and DyUI parses the fences. |
| `local_ollama.py` | A fully local bot via Ollama. |

## Structured mode

By default the model writes ```` ```dyui ```` fences, which works with every provider. For OpenAI and
Anthropic you can opt into schema-guaranteed components: `dyui.llm.stream(..., ui_mode="tools")`
registers a strict `render_<name>` tool per component and runs the tool loop for you. Try it with
`DYUI_UI_MODE=tools dyui run examples/data_analyst.py`.
