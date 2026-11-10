from __future__ import annotations

import logging
from types import SimpleNamespace as NS

import pytest

from dyui import llm
from dyui.llm._stream import TOOL_RESULT
from dyui.parts import Reasoning


class Cat:
    def __init__(self):
        self.providers = []

    def tool_schemas(self, provider="openai"):
        self.providers.append(provider)
        if provider == "anthropic":
            return [{"name": "render_stat", "description": "d", "input_schema": {"type": "object"}, "strict": True}]
        return [{"type": "function", "function": {"name": "render_stat", "strict": True, "parameters": {}}}]

    def prompt(self, mode="fence"):
        return f"PROMPT[{mode}]"


class OldCat:  # prompt() without mode
    def tool_schemas(self):
        return []

    def prompt(self):
        return "OLD"


async def collect(agen):
    return [p async for p in agen]


# ----------------------------------------------------------- openai
def tc(index, id=None, name=None, args=None):
    return NS(index=index, id=id, function=NS(name=name, arguments=args))


def chunk(content=None, tool_calls=None, reasoning=None):
    return NS(choices=[NS(delta=NS(content=content, tool_calls=tool_calls, reasoning_content=reasoning))])


class AStream:
    def __init__(self, items):
        self.items = items

    def __aiter__(self):
        return self._g()

    async def _g(self):
        for i in self.items:
            yield i


class FakeOpenAI:
    def __init__(self, rounds):
        self.rounds = list(rounds)
        self.calls = []
        self.chat = NS(completions=NS(create=self._create))

    async def _create(self, **kw):
        self.calls.append({**kw, "messages": list(kw["messages"])})
        return AStream(self.rounds.pop(0) if len(self.rounds) > 1 else self.rounds[0])


ROUND1 = [
    chunk(reasoning="think"),
    chunk("Here: "),
    chunk(tool_calls=[tc(0, "c1", "render_stat", '{"label":"Rev",')]),
    chunk(tool_calls=[tc(0, None, None, '"value":"$4k","unit":null}')]),
    chunk(tool_calls=[tc(1, "c2", "render_stat", '{"label":"B","value":2}')]),
]
ROUND2 = [chunk("All done.")]


@pytest.mark.asyncio
async def test_openai_tools_loop():
    c = FakeOpenAI([ROUND1, ROUND2])
    cat = Cat()
    out = await collect(llm.stream("openai/gpt-5", [{"role": "user", "content": "go"}], system="S",
                                   components=cat, ui_mode="tools", client=c, parallel_tool_calls=False))
    assert out == [Reasoning("think"), "Here: ",
                   {"ui": "stat", "label": "Rev", "value": "$4k"},
                   {"ui": "stat", "label": "B", "value": 2},
                   "All done."]
    assert cat.providers == ["openai"]
    first, second = c.calls
    assert first["tools"][0]["function"]["name"] == "render_stat"
    assert first["parallel_tool_calls"] is False
    assert first["messages"][0] == {"role": "system", "content": "S\n\nPROMPT[tools]"}
    m = second["messages"]
    assert m[-3]["role"] == "assistant" and m[-3]["content"] == "Here: "
    assert [t["id"] for t in m[-3]["tool_calls"]] == ["c1", "c2"]
    assert m[-3]["tool_calls"][0]["function"]["arguments"] == '{"label":"Rev","value":"$4k","unit":null}'
    assert m[-2:] == [{"role": "tool", "tool_call_id": "c1", "content": TOOL_RESULT},
                      {"role": "tool", "tool_call_id": "c2", "content": TOOL_RESULT}]
    assert "parallel_tool_calls" in second


@pytest.mark.asyncio
async def test_openai_max_rounds():
    c = FakeOpenAI([ROUND1])  # always asks for tools again
    out = await collect(llm.stream("groq/x", [], components=Cat(), ui_mode="tools", client=c, max_tool_rounds=2))
    assert len(c.calls) == 2
    assert sum(isinstance(p, dict) for p in out) == 4


@pytest.mark.asyncio
async def test_openai_no_parallel_flag_unless_set():
    c = FakeOpenAI([[chunk("hi")]])
    await collect(llm.stream("openai/x", [], components=Cat(), ui_mode="tools", client=c))
    assert "parallel_tool_calls" not in c.calls[0]


@pytest.mark.asyncio
async def test_openai_foreign_tool_stops(caplog):
    r = [chunk("x"), chunk(tool_calls=[tc(0, "k", "get_weather", "{}")])]
    c = FakeOpenAI([r, ROUND2])
    mine = {"type": "function", "function": {"name": "get_weather"}}
    with caplog.at_level(logging.WARNING, logger="dyui"):
        out = await collect(llm.stream("openai/x", [], components=Cat(), ui_mode="tools", client=c, tools=[mine]))
    assert out == ["x"] and len(c.calls) == 1
    assert mine in c.calls[0]["tools"] and len(c.calls[0]["tools"]) == 2
    assert any("own loop" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_prompt_fallback_and_validation():
    c = FakeOpenAI([[chunk("a")]])
    await collect(llm.stream("openai/x", [], components=OldCat(), ui_mode="tools", client=c))
    assert c.calls[0]["messages"][0]["content"] == "OLD"
    with pytest.raises(ValueError):
        await collect(llm.stream("openai/x", [], ui_mode="tools", client=c))
    with pytest.raises(ValueError):
        await collect(llm.stream("openai/x", [], ui_mode="nope", client=c))


# ----------------------------------------------------------- anthropic
def ev(type, **kw):
    return NS(type=type, **kw)


def a_round(text, calls, thinking=False):
    out = []
    i = 0
    if thinking:
        out += [ev("content_block_start", index=i, content_block=NS(type="thinking")),
                ev("content_block_delta", index=i, delta=NS(type="thinking_delta", thinking="hm")),
                ev("content_block_delta", index=i, delta=NS(type="signature_delta", signature="SIG")),
                ev("content_block_stop", index=i)]
        i += 1
    if text:
        out += [ev("content_block_start", index=i, content_block=NS(type="text")),
                ev("content_block_delta", index=i, delta=NS(type="text_delta", text=text)),
                ev("content_block_stop", index=i)]
        i += 1
    for id, name, parts in calls:
        out.append(ev("content_block_start", index=i, content_block=NS(type="tool_use", id=id, name=name)))
        out += [ev("content_block_delta", index=i, delta=NS(type="input_json_delta", partial_json=p)) for p in parts]
        out.append(ev("content_block_stop", index=i))
        i += 1
    return out


class AStreamCM:
    def __init__(self, items):
        self.items = items

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def __aiter__(self):
        return self._g()

    async def _g(self):
        for i in self.items:
            yield i


class FakeAnthropic:
    def __init__(self, rounds):
        self.rounds = list(rounds)
        self.calls = []
        self.messages = NS(stream=self._stream)

    def _stream(self, **kw):
        self.calls.append({**kw, "messages": list(kw["messages"])})
        return AStreamCM(self.rounds.pop(0) if len(self.rounds) > 1 else self.rounds[0])


@pytest.mark.asyncio
async def test_anthropic_tools_loop():
    r1 = a_round("Look: ", [("tu1", "render_stat", ['{"label":"R",', '"value":5,"help":null}'])], thinking=True)
    r2 = a_round("Done.", [])
    c = FakeAnthropic([r1, r2])
    cat = Cat()
    out = await collect(llm.stream("anthropic/claude-sonnet-5-5", [{"role": "user", "content": "go"}],
                                   components=cat, ui_mode="tools", client=c))
    assert out == [Reasoning("hm"), "Look: ", {"ui": "stat", "label": "R", "value": 5}, "Done."]
    assert cat.providers == ["anthropic"]
    first, second = c.calls
    assert first["tools"][0]["name"] == "render_stat" and first["system"] == "PROMPT[tools]"
    m = second["messages"]
    assert m[-2] == {"role": "assistant", "content": [
        {"type": "thinking", "thinking": "hm", "signature": "SIG"},
        {"type": "text", "text": "Look: "},
        {"type": "tool_use", "id": "tu1", "name": "render_stat", "input": {"label": "R", "value": 5, "help": None}},
    ]}
    assert m[-1] == {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tu1", "content": TOOL_RESULT}]}


@pytest.mark.asyncio
async def test_anthropic_max_rounds_and_foreign(caplog):
    c = FakeAnthropic([a_round("", [("t", "render_stat", ['{"label":"a","value":1}'])])])
    out = await collect(llm.stream("anthropic/m", [], components=Cat(), ui_mode="tools", client=c, max_tool_rounds=3))
    assert len(c.calls) == 3 and len(out) == 3
    c2 = FakeAnthropic([a_round("", [("t", "search", ["{}"])])])
    with caplog.at_level(logging.WARNING, logger="dyui"):
        out = await collect(llm.stream("anthropic/m", [], components=Cat(), ui_mode="tools", client=c2))
    assert out == [] and len(c2.calls) == 1
