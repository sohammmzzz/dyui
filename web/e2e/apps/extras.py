"""E2E fixture app: flows the demo doesn't cover (choice, thumbs rating, slow
streams for Stop, uploads, handler errors, long content for scrolling)."""
from __future__ import annotations

import asyncio
import json

import dyui

app = dyui.App(title="Extras", description="E2E fixture app.", persist=False)


def block(*components: dict) -> str:
    return "\n```dyui\n" + "\n".join(json.dumps(c) for c in components) + "\n```\n"


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    text = msg.text.lower()
    if msg.action is not None:
        yield f"Got action **{msg.action.name}** with values `{json.dumps(msg.action.values, sort_keys=True)}`."
        return
    if "choice" in text:
        yield "Pick some:" + block({"ui": "choice", "question": "Which cities?", "options": ["Lisbon", "Porto", "Faro"],
                                    "multiple": True, "allow_other": True, "submit_label": "Choose"})
    elif "thumbs" in text:
        yield "Quick check:" + block({"ui": "rating", "label": "Was this useful?", "style": "thumbs"})
    elif "slow" in text:
        for i in range(400):
            yield f"word{i} "
            await asyncio.sleep(0.05)
    elif "files" in text:
        names = ", ".join(f"{f.name} ({f.size} B)" for f in msg.files) or "none"
        yield f"Files received: {names}"
    elif "boom" in text:
        yield "Starting…"
        raise RuntimeError("fixture failure")
    elif "long" in text:
        for i in range(60):
            yield f"Paragraph {i}: lorem ipsum dolor sit amet, consectetur adipiscing elit.\n\n"
            await asyncio.sleep(0.005)
    else:
        yield f"Echo: {msg.text}"
