"""Rate-limit handling and the 'always write prose' guidance."""
from __future__ import annotations

from types import SimpleNamespace as NS

import pytest

import dyui
from dyui import genui, llm
from dyui.llm import _stream
from dyui.llm._providers import PROVIDERS, parse_model

from test_llm_tools import AStream, AStreamCM, Cat, a_round, chunk, collect, tc


class RateLimited(Exception):
    def __init__(self, status=429, headers=None):
        super().__init__("rate limited")
        self.status_code = status
        self.response = NS(headers=headers or {})


@pytest.fixture
def sleeps(monkeypatch):
    waits: list[float] = []

    async def fake_sleep(s):
        waits.append(s)

    monkeypatch.setattr(_stream.asyncio, "sleep", fake_sleep)
    return waits


class FlakyOpenAI:
    """Raises the queued errors (one per request) before answering."""

    def __init__(self, errors, rounds):
        self.errors, self.rounds, self.calls = list(errors), list(rounds), 0
        self.chat = NS(completions=NS(create=self._create))

    async def _create(self, **kw):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return AStream(self.rounds.pop(0) if len(self.rounds) > 1 else self.rounds[0])


class FlakyAnthropic:
    def __init__(self, errors, rounds):
        self.errors, self.rounds, self.calls = list(errors), list(rounds), 0
        self.messages = NS(stream=self._stream)

    def _stream(self, **kw):
        self.calls += 1
        err = self.errors.pop(0) if self.errors else None
        items = self.rounds.pop(0) if len(self.rounds) > 1 else self.rounds[0]

        class CM(AStreamCM):
            async def __aenter__(self_inner):
                if err:
                    raise err
                return self_inner

        return CM(items)


# ------------------------------------------------------------ retries
@pytest.mark.asyncio
async def test_openai_429_waits_retry_after_then_succeeds(sleeps):
    c = FlakyOpenAI([RateLimited(headers={"retry-after": "7"})], [[chunk("hi")]])
    assert await collect(llm.stream("groq/x", [], client=c)) == ["hi"]
    assert c.calls == 2 and sleeps == [7.0]


@pytest.mark.asyncio
async def test_retry_after_ms_header_and_backoff_fallback(sleeps):
    c = FlakyOpenAI([RateLimited(headers={"retry-after-ms": "1500"}), RateLimited()], [[chunk("ok")]])
    assert await collect(llm.stream("groq/x", [], client=c)) == ["ok"]
    assert sleeps[0] == 1.5 and sleeps[1] > 0


@pytest.mark.asyncio
async def test_429_gives_up_after_rate_limit_retries(sleeps):
    c = FlakyOpenAI([RateLimited()] * 10, [[chunk("never")]])
    with pytest.raises(RateLimited):
        await collect(llm.stream("groq/x", [], client=c, rate_limit_retries=2))
    assert c.calls == 3 and len(sleeps) == 2


@pytest.mark.asyncio
async def test_long_retry_after_is_not_waited(sleeps):
    """A daily quota (retry in an hour) must fail fast, not hang the chat."""
    c = FlakyOpenAI([RateLimited(headers={"retry-after": "3600"})], [[chunk("never")]])
    with pytest.raises(RateLimited):
        await collect(llm.stream("groq/x", [], client=c))
    assert c.calls == 1 and sleeps == []


@pytest.mark.asyncio
async def test_other_errors_are_not_retried(sleeps):
    c = FlakyOpenAI([RateLimited(status=401)], [[chunk("never")]])
    with pytest.raises(RateLimited):
        await collect(llm.stream("groq/x", [], client=c))
    assert c.calls == 1 and sleeps == []


@pytest.mark.asyncio
async def test_429_between_tool_rounds_keeps_the_reply(sleeps):
    r1 = [chunk(tool_calls=[tc(0, "c1", "render_stat", '{"label":"A","value":1}')])]
    c = FlakyOpenAI([], [r1, [chunk("Summary.")]])
    c.errors = []
    orig = c._create

    async def create(**kw):  # first request fine, second rate limited once
        if c.calls == 1 and not getattr(c, "tripped", False):
            c.tripped = True
            c.calls += 1
            raise RateLimited(headers={"retry-after": "2"})
        return await orig(**kw)

    c.chat = NS(completions=NS(create=create))
    out = await collect(llm.stream("groq/x", [], components=Cat(), ui_mode="tools", client=c))
    assert out == [{"ui": "stat", "label": "A", "value": 1}, "Summary."]
    assert sleeps == [2.0]


@pytest.mark.asyncio
async def test_anthropic_429_retries(sleeps):
    c = FlakyAnthropic([RateLimited(headers={"retry-after": "3"})], [a_round("hello", [])])
    assert await collect(llm.stream("anthropic/m", [], client=c)) == ["hello"]
    assert c.calls == 2 and sleeps == [3.0]


# ------------------------------------------------------------ providers
def test_nvidia_provider():
    p, model = parse_model("nvidia/meta/llama-3.3-70b-instruct")
    assert p is PROVIDERS["nvidia"] and model == "meta/llama-3.3-70b-instruct"
    assert p.base_url == "https://integrate.api.nvidia.com/v1" and p.key_envs == ("NVIDIA_API_KEY",)


# ------------------------------------------------------------ error text
def test_public_error_message_for_rate_limits():
    from dyui.app import _public_error

    assert "rate limit" in _public_error(RateLimited()).lower()
    assert "too large" in _public_error(RateLimited(status=413)).lower()
    assert _public_error(ValueError("secret /path")) == "ValueError: something went wrong while replying."


# ------------------------------------------------------------ prose
def test_prompts_ask_for_prose_alongside_components():
    cat = genui.catalog()
    for mode in ("fence", "tools"):
        p = cat.prompt(mode=mode).lower()
        assert "never reply with components alone" in p, mode
    fence = cat.prompt()
    example = fence[fence.index("Example:"):]
    before, _, after = example.partition("```dyui")
    assert before.replace("Example:", "").strip(), "example should show prose before the block"
    assert after.rpartition("```")[2].strip(), "example should show prose after the block"


@pytest.mark.asyncio
async def test_tool_result_asks_model_to_continue_in_text():
    from test_llm_tools import ROUND1, ROUND2, FakeOpenAI

    c = FakeOpenAI([ROUND1, ROUND2])
    await collect(llm.stream("openai/x", [], components=Cat(), ui_mode="tools", client=c))
    result = c.calls[1]["messages"][-1]["content"]
    assert result == _stream.TOOL_RESULT and "text" in result.lower()
    assert dyui.llm.stream is llm.stream
