"""Use your own SDK client. DyUI only needs raw text: it parses ```dyui fences itself."""
import os
from functools import lru_cache

import dyui
from openai import AsyncOpenAI


@lru_cache(maxsize=1)
def client() -> AsyncOpenAI:
    # Any OpenAI-compatible endpoint. Created on first use, so the app starts without a key.
    return AsyncOpenAI(base_url=os.getenv("DYUI_BASE_URL", "https://integrate.api.nvidia.com/v1"),
                       api_key=os.environ["NVIDIA_API_KEY"])


MODEL = os.getenv("DYUI_MODEL", "moonshotai/kimi-k2.6")  # the endpoint model id, no dyui provider prefix

app = dyui.App(title="BYO SDK", description="Raw OpenAI client, DyUI rendering.")


@app.on_message
async def reply(msg: dyui.Message, chat: dyui.Chat):
    system = "You are a helpful assistant.\n\n" + app.catalog.prompt()
    stream = await client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system}, *chat.history],
        stream=True,
    )
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content  # raw text deltas; fences become components
