"""Data analyst: the model reasons over a small in-file dataset and answers with stats, charts and tables."""
import csv
import io
import os

import dyui

MODEL = os.getenv("DYUI_MODEL", "openai/gpt-5")
# "fence" (default, works everywhere) or "tools": strict structured outputs via render_* tools.
UI_MODE = os.getenv("DYUI_UI_MODE", "fence")

DATA = """month,region,revenue,orders
Jan,EU,41200,310
Jan,US,58800,402
Feb,EU,43900,331
Feb,US,61400,415
Mar,EU,47800,352
Mar,US,66100,447
Apr,EU,52100,380
Apr,US,64900,431
"""
ROWS = list(csv.DictReader(io.StringIO(DATA)))

SYSTEM = f"""You are a data analyst. Answer only from this dataset (CSV):

{DATA}
Prefer a `stats` row for headline numbers, a `chart` for trends or comparisons, and a
`table` for lists. Always explain in words too: open with a sentence that answers the
question, show the components, then close with the insight a reader should take away.
Compute numbers carefully.

{{dyui_components}}"""

app = dyui.App(
    title="Data Analyst",
    description=f"Ask questions about {len(ROWS)} rows of monthly sales.",
    starters=["Revenue trend by region", "Which month had the most orders?", "Show the raw data"],
)


# Only the components an analyst needs. A smaller catalog means a smaller prompt, which
# matters on rate-limited free tiers (Groq, NVIDIA NIM), most of all with UI_MODE=tools.
CATALOG = app.catalog.only("stat", "stats", "chart", "table", "keyvalue", "callout", "quick_replies")


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    # "{dyui_components}" in SYSTEM is replaced with the live component catalog.
    async for part in dyui.llm.stream(MODEL, chat.history, system=SYSTEM, components=CATALOG,
                                      ui_mode=UI_MODE):
        yield part
