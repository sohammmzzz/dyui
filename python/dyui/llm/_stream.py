"""``dyui.llm.stream`` / ``dyui.llm.complete``."""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, AsyncIterator

from dyui.parts import Reasoning

from ._errors import missing_sdk
from ._prompt import build_system, split_system, to_anthropic_messages, to_openai_messages
from ._providers import Provider, parse_model

DEFAULT_ANTHROPIC_MAX_TOKENS = 4096
DEFAULT_RATE_LIMIT_RETRIES = 3
MAX_RATE_LIMIT_WAIT = 60.0  # seconds; a longer Retry-After (daily quota) fails fast
# Sent back to the model after each render_* call. It nudges the model to keep
# talking: without it many models stop after the tool call and the reply has no prose.
TOOL_RESULT = (
    "Rendered and shown to the user. Do not render it again. Continue your reply in plain text: "
    "say what it shows and the key takeaway (don't repeat the raw data), or render another component."
)


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
RENDER_PREFIX = "render_"
log = logging.getLogger("dyui")


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


def _tool_schemas(components: Any, provider: str) -> list[dict[str, Any]]:
    try:
        return list(components.tool_schemas(provider))
    except TypeError:
        return list(components.tool_schemas())


def _render_node(name: str, args_json: str) -> dict[str, Any] | None:
    """``render_<ui>`` + JSON args -> ``{"ui": ui, **args}`` (null values dropped)."""
    try:
        args = json.loads(args_json) if args_json.strip() else {}
    except ValueError:
        log.warning("dyui.llm: invalid JSON arguments for tool %s; skipped.", name)
        return None
    if not isinstance(args, dict):
        return None
    node: dict[str, Any] = {"ui": name[len(RENDER_PREFIX):]}
    node.update({k: v for k, v in args.items() if v is not None})
    return node


def _warn_foreign(names: list[str]) -> None:
    log.warning(
        "dyui.llm: the model called tool(s) %s which dyui does not run; stopping the tool loop. "
        "Custom tools need their own loop.", ", ".join(names))


def _rate_limit_wait(exc: BaseException, attempt: int, retries: int) -> float | None:
    """Seconds to wait before retrying ``exc``, or ``None`` if it shouldn't be retried.

    Only HTTP 429 is retried. The provider's ``retry-after-ms`` / ``retry-after`` header
    wins; otherwise back off 2s, 4s, 8s... A wait above ``MAX_RATE_LIMIT_WAIT`` means a
    long-window quota (per day), so give up instead of hanging the chat.
    """
    if getattr(exc, "status_code", None) != 429 or attempt >= retries:
        return None
    headers = getattr(getattr(exc, "response", None), "headers", None)
    wait: float | None = None
    if headers is not None:
        for name, scale in (("retry-after-ms", 0.001), ("retry-after", 1.0)):
            try:
                raw = headers.get(name)
                if raw is not None:
                    wait = max(0.0, float(raw) * scale)
                    break
            except (TypeError, ValueError):  # e.g. an HTTP-date; fall back to backoff
                continue
    if wait is None:
        wait = float(min(2 ** (attempt + 1), 30))
    if wait > MAX_RATE_LIMIT_WAIT:
        return None
    return wait


async def _wait_rate_limit(wait: float, attempt: int, retries: int) -> None:
    log.warning("dyui.llm: provider rate limit hit (HTTP 429); retrying in %.1fs (retry %d of %d).",
                wait, attempt + 1, retries)
    await asyncio.sleep(wait)


async def _create_openai(client: Any, retries: int, **request: Any) -> Any:
    attempt = 0
    while True:
        try:
            return await client.chat.completions.create(**request)
        except Exception as exc:
            wait = _rate_limit_wait(exc, attempt, retries)
            if wait is None:
                raise
            await _wait_rate_limit(wait, attempt, retries)
            attempt += 1


async def _anthropic_events(client: Any, retries: int, **request: Any) -> AsyncIterator[Any]:
    """Events of one ``messages.stream`` request; a 429 before the first event is retried."""
    attempt = 0
    while True:
        started = False
        try:
            async with client.messages.stream(**request) as s:
                async for event in s:
                    started = True
                    yield event
            return
        except Exception as exc:
            wait = None if started else _rate_limit_wait(exc, attempt, retries)
            if wait is None:
                raise
            await _wait_rate_limit(wait, attempt, retries)
            attempt += 1


async def _aclose(resp: Any) -> None:
    close = getattr(resp, "close", None)
    if close is not None:
        try:
            res = close()
            if hasattr(res, "__await__"):
                await res
        except Exception:  # pragma: no cover - best effort
            pass


async def _stream_openai(client: Any, model: str, messages: list[Any], system: str | None,
                         kwargs: dict[str, Any], tools: list[dict[str, Any]] | None = None,
                         max_rounds: int = 1,
                         retries: int = DEFAULT_RATE_LIMIT_RETRIES) -> AsyncIterator[Any]:
    payload = to_openai_messages(messages, system)
    params = dict(kwargs)
    if tools:
        params["tools"] = tools
    for _ in range(max(1, max_rounds)):
        resp = await _create_openai(client, retries, model=model, messages=payload, stream=True, **params)
        text_parts: list[str] = []
        calls: dict[int, dict[str, Any]] = {}
        done: set[int] = set()
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
                    text_parts.append(text)
                    yield text
                for tc in getattr(delta, "tool_calls", None) or []:
                    idx = getattr(tc, "index", None)
                    idx = len(calls) if idx is None else idx
                    # a new index means every earlier call is complete: render it now
                    for prev in sorted(i for i in calls if i < idx and i not in done):
                        done.add(prev)
                        node = _finish_openai_call(calls[prev])
                        if node:
                            yield node
                    c = calls.setdefault(idx, {"id": None, "name": "", "args": ""})
                    if getattr(tc, "id", None):
                        c["id"] = tc.id
                    fn = getattr(tc, "function", None)
                    if fn is not None:
                        if getattr(fn, "name", None):
                            c["name"] += fn.name
                        if getattr(fn, "arguments", None):
                            c["args"] += fn.arguments
        finally:
            await _aclose(resp)
        for idx in sorted(calls):
            if idx not in done:
                node = _finish_openai_call(calls[idx])
                if node:
                    yield node
        if not calls:
            return
        ordered = [calls[i] for i in sorted(calls)]
        for n, c in enumerate(ordered):
            c["id"] = c["id"] or f"call_{n}"
        foreign = [c["name"] for c in ordered if not c["name"].startswith(RENDER_PREFIX)]
        if foreign:
            _warn_foreign(foreign)
            return
        payload.append({
            "role": "assistant",
            "content": "".join(text_parts) or None,
            "tool_calls": [{"id": c["id"], "type": "function",
                            "function": {"name": c["name"], "arguments": c["args"] or "{}"}} for c in ordered],
        })
        for c in ordered:
            payload.append({"role": "tool", "tool_call_id": c["id"], "content": TOOL_RESULT})


def _finish_openai_call(c: dict[str, Any]) -> dict[str, Any] | None:
    if not c["name"].startswith(RENDER_PREFIX):
        return None
    return _render_node(c["name"], c["args"])


async def _stream_anthropic(client: Any, model: str, messages: list[Any], system: str | None,
                            kwargs: dict[str, Any], tools: list[dict[str, Any]] | None = None,
                            max_rounds: int = 1,
                            retries: int = DEFAULT_RATE_LIMIT_RETRIES) -> AsyncIterator[Any]:
    sys_text, rest = split_system(messages, system)
    params: dict[str, Any] = dict(kwargs)
    params.setdefault("max_tokens", DEFAULT_ANTHROPIC_MAX_TOKENS)
    if sys_text:
        params["system"] = sys_text
    if tools:
        params["tools"] = tools
    payload = to_anthropic_messages(rest)
    for _ in range(max(1, max_rounds)):
        blocks: dict[int, dict[str, Any]] = {}
        order: list[int] = []
        events = _anthropic_events(client, retries, model=model, messages=payload, **params)
        try:
            async for event in events:
                etype = getattr(event, "type", None)
                idx = getattr(event, "index", None)
                if etype == "content_block_start":
                    cb = event.content_block
                    kind = getattr(cb, "type", None)
                    b: dict[str, Any] = {"kind": kind, "text": "", "thinking": "", "sig": "", "json": ""}
                    if kind == "tool_use":
                        b["id"], b["name"] = cb.id, cb.name
                    blocks[idx] = b
                    order.append(idx)
                elif etype == "content_block_delta":
                    delta = event.delta
                    dtype = getattr(delta, "type", None)
                    b = blocks.setdefault(idx, {"kind": None, "text": "", "thinking": "", "sig": "", "json": ""})
                    if dtype == "text_delta":
                        if delta.text:
                            b["text"] += delta.text
                            yield delta.text
                    elif dtype == "thinking_delta":
                        if delta.thinking:
                            b["thinking"] += delta.thinking
                            yield Reasoning(delta.thinking)
                    elif dtype == "signature_delta":
                        b["sig"] += delta.signature
                    elif dtype == "input_json_delta":
                        b["json"] += delta.partial_json
                elif etype == "content_block_stop":
                    b = blocks.get(idx)
                    if b and b["kind"] == "tool_use" and b["name"].startswith(RENDER_PREFIX):
                        node = _render_node(b["name"], b["json"])
                        if node:
                            yield node
        finally:
            await events.aclose()
        tool_blocks = [blocks[i] for i in order if blocks[i]["kind"] == "tool_use"]
        if not tool_blocks:
            return
        foreign = [b["name"] for b in tool_blocks if not b["name"].startswith(RENDER_PREFIX)]
        if foreign:
            _warn_foreign(foreign)
            return
        content: list[dict[str, Any]] = []
        for i in order:
            b = blocks[i]
            if b["kind"] == "thinking" and b["sig"]:
                content.append({"type": "thinking", "thinking": b["thinking"], "signature": b["sig"]})
            elif b["kind"] == "text" and b["text"]:
                content.append({"type": "text", "text": b["text"]})
            elif b["kind"] == "tool_use":
                try:
                    inp = json.loads(b["json"]) if b["json"].strip() else {}
                except ValueError:
                    inp = {}
                content.append({"type": "tool_use", "id": b["id"], "name": b["name"], "input": inp})
        payload.append({"role": "assistant", "content": content})
        payload.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": b["id"], "content": TOOL_RESULT} for b in tool_blocks]})


async def stream(
    model: str,
    messages: list[Any],
    *,
    system: str | None = None,
    components: Any = None,
    ui_mode: str = "fence",
    max_tool_rounds: int = 8,
    rate_limit_retries: int = DEFAULT_RATE_LIMIT_RETRIES,
    base_url: str | None = None,
    api_key: str | None = None,
    client: Any = None,
    **kwargs: Any,
) -> AsyncIterator[Any]:
    """Stream a completion as ``str`` text deltas and :class:`dyui.Reasoning` deltas.

    ``model`` is ``"provider/model"`` (see :data:`dyui.llm.PROVIDERS`).
    ``components`` is a catalog (anything with ``.prompt()``); its prompt is merged
    into ``system`` (at ``{dyui_components}`` if present, else appended).

    ``ui_mode="fence"`` (default): the model writes ```dyui fences inside its text.
    ``ui_mode="tools"``: one ``render_<name>`` tool per component (strict schemas via
    ``components.tool_schemas``); dyui runs the tool loop (at most ``max_tool_rounds``
    requests) and yields each completed call as a ``{"ui": name, ...props}`` dict.
    A caller-supplied ``tools=`` list is merged; if the model calls one of those tools
    the loop stops (custom tools need their own loop).

    Rate limits: an HTTP 429 from the provider is retried up to ``rate_limit_retries``
    times, waiting for the provider's ``Retry-After`` (or 2s, 4s, 8s...). Waits over a
    minute (daily quotas) are not retried. Set ``rate_limit_retries=0`` to disable.

    ``client`` lets you pass a pre-built async SDK client. Extra kwargs go to the SDK.
    """
    if ui_mode not in ("fence", "tools"):
        raise ValueError(f"ui_mode must be 'fence' or 'tools', got {ui_mode!r}")
    provider, model_id = parse_model(model)
    tools: list[dict[str, Any]] | None = None
    rounds = 1
    if ui_mode == "tools":
        if components is None:
            raise ValueError("ui_mode='tools' needs components=<catalog>.")
        kind = "anthropic" if provider.sdk == "anthropic" else "openai"
        tools = _tool_schemas(components, kind) + list(kwargs.pop("tools", None) or [])
        rounds = max_tool_rounds
    full_system = build_system(system, components, ui_mode)
    if client is None:
        maker = _make_openai_client if provider.sdk == "openai" else _make_anthropic_client
        client = maker(provider, base_url, api_key)
    impl = _stream_openai if provider.sdk == "openai" else _stream_anthropic
    async for part in impl(client, model_id, list(messages), full_system, kwargs, tools, rounds,
                           max(0, rate_limit_retries)):
        yield part


async def complete(model: str, messages: list[Any], **kwargs: Any) -> str:
    """Non-streaming convenience: return the full text reply (reasoning dropped)."""
    out: list[str] = []
    async for part in stream(model, messages, **kwargs):
        if isinstance(part, str):
            out.append(part)
    return "".join(out)
