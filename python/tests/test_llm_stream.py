from __future__ import annotations

import builtins
import sys
from types import SimpleNamespace as NS

import pytest

from dyui import llm
from dyui.llm import _stream
from dyui.llm._prompt import build_system
from dyui.llm._providers import PROVIDERS, parse_model
from dyui.parts import Reasoning


class Catalog:
    def prompt(self) -> str:
        return "## UI components\nCATALOG"


async def collect(agen):
    return [p async for p in agen]


# ------------------------------------------------------------ openai-like
class FakeOpenAIStream:
    def __init__(self, deltas):
        self.deltas = deltas

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        yield NS(choices=[])  # keepalive-style empty chunk
        for d in self.deltas:
            yield NS(choices=[NS(delta=NS(**d))])


class FakeOpenAI:
    def __init__(self, deltas):
        self.calls = []
        self.chat = NS(completions=NS(create=self._create))
        self.deltas = deltas

    async def _create(self, **kw):
        self.calls.append(kw)
        return FakeOpenAIStream(self.deltas)


@pytest.mark.asyncio
async def test_openai_text_and_reasoning():
    c = FakeOpenAI([
        {"content": None, "reasoning_content": "hmm "},
        {"content": "Hel", "reasoning_content": None},
        {"content": "lo"},
        {"content": None, "reasoning": "alt"},
    ])
    out = await collect(llm.stream("openai/gpt-5", [{"role": "user", "content": "hi"}], client=c, temperature=0.2))
    assert out == [Reasoning("hmm "), "Hel", "lo", Reasoning("alt")]
    call = c.calls[0]
    assert call["model"] == "gpt-5" and call["stream"] is True and call["temperature"] == 0.2
    assert call["messages"] == [{"role": "user", "content": "hi"}]


@pytest.mark.asyncio
async def test_system_and_catalog_appended():
    c = FakeOpenAI([{"content": "x"}])
    await collect(llm.stream("groq/llama", [{"role": "user", "content": "q"}], system="Be nice.", components=Catalog(), client=c))
    msgs = c.calls[0]["messages"]
    assert msgs[0] == {"role": "system", "content": "Be nice.\n\n## UI components\nCATALOG"}


def test_build_system_variants():
    cat = Catalog()
    assert build_system(None, cat) == cat.prompt()
    assert build_system("A {dyui_components} B", cat) == "A ## UI components\nCATALOG B"
    assert build_system("A", None) == "A"
    assert build_system(None, None) is None


@pytest.mark.asyncio
async def test_content_list_passthrough_openai():
    c = FakeOpenAI([{"content": "ok"}])
    parts = [{"type": "text", "text": "hello"}]
    await collect(llm.stream("openai/x", [{"role": "user", "content": parts}], client=c))
    assert c.calls[0]["messages"][0]["content"] == parts


@pytest.mark.asyncio
async def test_complete():
    c = FakeOpenAI([{"reasoning_content": "t"}, {"content": "a"}, {"content": "b"}])
    assert await llm.complete("ollama/llama3", [{"role": "user", "content": "x"}], client=c) == "ab"


def test_parse_model():
    p, m = parse_model("openrouter/anthropic/claude-sonnet-5-5")
    assert p.name == "openrouter" and m == "anthropic/claude-sonnet-5-5"
    with pytest.raises(ValueError):
        parse_model("gpt-5")
    with pytest.raises(ValueError):
        parse_model("nope/x")
    assert {"openai", "anthropic", "ollama", "groq", "openrouter", "together", "deepseek",
            "gemini", "mistral", "xai"} <= set(PROVIDERS)


def test_make_openai_client_urls_and_keys(monkeypatch):
    captured = {}

    class FakeAsyncOpenAI:
        def __init__(self, **kw):
            captured.update(kw)

    import openai
    monkeypatch.setattr(openai, "AsyncOpenAI", FakeAsyncOpenAI)
    for k in ("OLLAMA_BASE_URL", "GROQ_API_KEY", "OPENAI_BASE_URL"):
        monkeypatch.delenv(k, raising=False)
    _stream._make_openai_client(PROVIDERS["ollama"], None, None)
    assert captured["base_url"] == "http://localhost:11434/v1" and captured["api_key"]
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://box:1/v1")
    _stream._make_openai_client(PROVIDERS["ollama"], None, None)
    assert captured["base_url"] == "http://box:1/v1"
    with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
        _stream._make_openai_client(PROVIDERS["groq"], None, None)
    monkeypatch.setenv("GROQ_API_KEY", "k")
    captured.clear()
    _stream._make_openai_client(PROVIDERS["groq"], "http://override", None)
    assert captured == {"base_url": "http://override", "api_key": "k"}


@pytest.mark.asyncio
async def test_client_factory_used(monkeypatch):
    fake = FakeOpenAI([{"content": "z"}])
    monkeypatch.setattr(_stream, "_make_openai_client", lambda p, b, k: fake)
    assert await collect(llm.stream("deepseek/deepseek-chat", [])) == ["z"]


# ------------------------------------------------------------ anthropic
class FakeAnthropicStream:
    def __init__(self, events):
        self.events = events

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        for e in self.events:
            yield e


class FakeAnthropic:
    def __init__(self, events):
        self.calls = []
        self.events = events
        self.messages = NS(stream=self._stream)

    def _stream(self, **kw):
        self.calls.append(kw)
        return FakeAnthropicStream(self.events)


def cbd(delta):
    return NS(type="content_block_delta", delta=delta)


@pytest.mark.asyncio
async def test_anthropic_thinking_and_system():
    events = [
        NS(type="message_start"),
        cbd(NS(type="thinking_delta", thinking="pondering")),
        cbd(NS(type="signature_delta", signature="s")),
        cbd(NS(type="text_delta", text="Hi ")),
        NS(type="text", text="Hi "),  # SDK helper event must not duplicate
        cbd(NS(type="text_delta", text="there")),
    ]
    c = FakeAnthropic(events)
    msgs = [
        {"role": "system", "content": "from history"},
        {"role": "user", "content": [{"type": "text", "text": "hello"}]},
        {"role": "assistant", "content": "yo"},
        {"role": "user", "content": ""},
    ]
    out = await collect(llm.stream("anthropic/claude-sonnet-5-5", msgs, system="SYS", components=Catalog(), client=c,
                                   thinking={"type": "adaptive"}))
    assert out == [Reasoning("pondering"), "Hi ", "there"]
    call = c.calls[0]
    assert call["model"] == "claude-sonnet-5-5"
    assert call["max_tokens"] == 4096
    assert call["thinking"] == {"type": "adaptive"}
    assert call["system"] == "SYS\n\n## UI components\nCATALOG\n\nfrom history"
    assert call["messages"] == [
        {"role": "user", "content": [{"type": "text", "text": "hello"}]},
        {"role": "assistant", "content": "yo"},
    ]


@pytest.mark.asyncio
async def test_anthropic_max_tokens_override_and_no_system():
    c = FakeAnthropic([cbd(NS(type="text_delta", text="a"))])
    await collect(llm.stream("anthropic/m", [{"role": "user", "content": "x"}], max_tokens=10, client=c))
    assert c.calls[0]["max_tokens"] == 10 and "system" not in c.calls[0]


# ------------------------------------------------------------ missing SDK
@pytest.mark.parametrize("model,extra", [("openai/gpt-5", "openai"), ("anthropic/x", "anthropic")])
@pytest.mark.asyncio
async def test_missing_sdk_message(monkeypatch, model, extra):
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == extra or name.startswith(extra + "."):
            raise ImportError("no " + name)
        return real_import(name, *a, **k)

    for m in [m for m in sys.modules if m == extra or m.startswith(extra + ".")]:
        monkeypatch.delitem(sys.modules, m)
    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(llm.MissingDependencyError, match=rf'pip install "dyui\[{extra}\]"'):
        await collect(llm.stream(model, [{"role": "user", "content": "x"}]))
