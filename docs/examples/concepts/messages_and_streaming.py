"""Handlers, yields, files, a component updated in place, and a greeting.

Save as app.py, then run:  dyui run app.py
"""
import asyncio

import dyui
from dyui import ui

app = dyui.App(title="Indexer", description="Attach a file, or send any message.", starters=["Index my notes"])


@app.on_chat_start
async def start(chat: dyui.Chat):
    # runs when a conversation is created: post a first assistant message
    await chat.send("Hi! Attach files and I'll index them.", ui.QuickReplies("Index my notes", "What can you do?"))


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    if not chat.session.get("titled"):  # name the conversation once (turns off auto-titling)
        await chat.set_title(f"Indexing: {msg.text[:40]}")
        chat.session["titled"] = True
    for f in msg.files:
        yield f"Got **{f.name}** ({f.size} bytes).\n\n"
    # the same id replaces the component where it stands
    for done in range(0, 101, 25):
        yield ui.Progress(done, label="Indexing", id="indexing")
        await asyncio.sleep(0.2)
    yield "Done. "
    yield [ui.Callout("Index is up to date.", level="success"), ui.QuickReplies("Index again")]
