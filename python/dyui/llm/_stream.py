"""``dyui.llm.stream`` / ``dyui.llm.complete``."""
from __future__ import annotations

import os
from typing import Any, AsyncIterator

from dyui.parts import Reasoning

from ._errors import missing_sdk
from ._prompt import build_system, split_system, to_anthropic_messages, to_openai_messages
from ._providers import Provider, parse_model

DEFAULT_ANTHROPIC_MAX_TOKENS = 4096


# ---------------------------------------------------------------- clients
def _resolve_key(provider: Provider) -> str | None:
    for env in provider.key_envs:
        if os.environ.get(env):
            return os.environ[env]
    return None


def _make_openai_client(provider: Provider, base_url: str | None, api_key: str | None) -> Any:
    try:
        from openai import AsyncOpenAI
    except ImportError as e:
        raise missing_sdk("openai") from e
    base_url = base_url or (os.environ.get(provider.base_url_env or "") or provider.base_url)
    api_key = api_key or _resolve_key(provider)
    if api_key is None:
        if provider.key_required and provider.name != "openai":
            raise RuntimeError(
                f"No API key for '{provider.name}'. Set {' or '.join(provider.key_envs)} "
                f"or pass api_key=... to dyui.llm.stream()."
            )
        # ollama & friends ignore the key; the SDK still wants *something*.
        # For openai itself let the SDK raise its own (clear) error.
        api_key = None if provider.name == "openai" else "not-needed"
    kwargs: dict[str, Any] = {}
    if base_url:
        kwargs["base_url"] = base_url
    if api_key:
        kwargs["api_key"] = api_key
    return AsyncOpenAI(**kwargs)


def _make_anthropic_client(provider: Provider, base_url: str | None, api_key: str | None) -> Any:
    try:
        from anthropic import AsyncAnthropic
    except ImportError as e:
        raise missing_sdk("anthropic") from e
    kwargs: dict[str, Any] = {}
    base_url = base_url or os.environ.get(provider.base_url_env or "")
    if base_url:
        kwargs["base_url"] = base_url
    if api_key:
        kwargs["api_key"] = api_key
    return AsyncAnthropic(**kwargs)


# ---------------------------------------------------------------- streams
def _reasoning_of(delta: Any) -> str | None:
    for attr in ("reasoning_content", "reasoning"):
        v = getattr(delta, attr, None)
        if isinstance(v, str) and v:
            return v
    extra = getattr(delta, "model_extra", None)
    if isinstance(extra, dict):
        for attr in ("reasoning_content", "reasoning"):
            v = extra.get(attr)
            if isinstance(v, str) and v:
                return v
    return None


async def _stream_openai(client: Any, model: str, messages: list[Any], system: str | None,
                         kwargs: dict[str, Any]) -> AsyncIterator[str | Reasoning]:
    payload = to_openai_messages(messages, system)
    resp = await client.chat.completions.create(model=model, messages=payload, stream=True, **kwargs)
    try:
        async for chunk in resp:
            choices = getattr(chunk, "choices", None)
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            if delta is None:
                continue
            r = _reasoning_of(delta)
            if r:
                yield Reasoning(r)
            text = getattr(delta, "content", None)
            if isinstance(text, str) and text:
                yield text
    finally:
        close = getattr(resp, "close", None)
        if close is not None:
            try:
                res = close()
                if hasattr(res, "__await__"):
                    await res
            except Exception:  # pragma: no cover - best effort
                pass


async def _stream_anthropic(client: Any, model: str, messages: list[Any], system: str | None,
                            kwargs: dict[str, Any]) -> AsyncIterator[str | Reasoning]:
    sys_text, rest = split_system(messages, system)
    params: dict[str, Any] = dict(kwargs)
    params.setdefault("max_tokens", DEFAULT_ANTHROPIC_MAX_TOKENS)
    if sys_text:
        params["system"] = sys_text
    async with client.messages.stream(model=model, messages=to_anthropic_messages(rest), **params) as s:
        async for event in s:
            if getattr(event, "type", None) != "content_block_delta":
                continue
            delta = event.delta
            dtype = getattr(delta, "type", None)
            if dtype == "text_delta":
                if delta.text:
                    yield delta.text
            elif dtype == "thinking_delta":
                if delta.thinking:
                    yield Reasoning(delta.thinking)


async def stream(
    model: str,
    messages: list[Any],
    *,
    system: str | None = None,
    components: Any = None,
    base_url: str | None = None,
    api_key: str | None = None,
    client: Any = None,
    **kwargs: Any,
) -> AsyncIterator[str | Reasoning]:
    """Stream a completion as ``str`` text deltas and :class:`dyui.Reasoning` deltas.

    ``model`` is ``"provider/model"`` (see :data:`dyui.llm.PROVIDERS`).
    ``components`` is a catalog (anything with ``.prompt()``); its prompt is merged
    into ``system`` (at ``{dyui_components}`` if present, else appended).
    ``client`` lets you pass a pre-built async SDK client. Extra kwargs go to the SDK.
    """
    provider, model_id = parse_model(model)
    full_system = build_system(system, components)
    if client is None:
        maker = _make_openai_client if provider.sdk == "openai" else _make_anthropic_client
        client = maker(provider, base_url, api_key)
    impl = _stream_openai if provider.sdk == "openai" else _stream_anthropic
    async for part in impl(client, model_id, list(messages), full_system, kwargs):
        yield part


async def complete(model: str, messages: list[Any], **kwargs: Any) -> str:
    """Non-streaming convenience: return the full text reply (reasoning dropped)."""
    out: list[str] = []
    async for part in stream(model, messages, **kwargs):
        if isinstance(part, str):
            out.append(part)
    return "".join(out)
