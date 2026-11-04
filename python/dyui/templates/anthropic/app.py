"""{{title}} - a DyUI bot powered by Claude. Run it with:  dyui run"""
import os

import dyui

MODEL = os.getenv("DYUI_MODEL", "anthropic/claude-sonnet-5-5")

app = dyui.App(
    title="{{title}}",
    description="Ask me anything - I answer with tables, charts and cards when they help.",
    starters=["Compare three programming languages in a table", "Show a bar chart of planet sizes"],
)


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    async for part in dyui.llm.stream(
        MODEL,
        chat.history,
        system="You are a concise, friendly assistant.",
        components=app.catalog,
        max_tokens=4096,
        # Optional: show Claude's reasoning in a collapsible block.
        # thinking={"type": "adaptive", "display": "summarized"},
    ):
        yield part  # str deltas and dyui.Reasoning deltas
