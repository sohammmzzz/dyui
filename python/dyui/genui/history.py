"""Serialize stored messages into LLM history (SPEC §5.2).

Assistant messages become text where every ``ui`` part is re-serialized as a
compact ```dyui block (props only — no ids/status), so the model keeps the
context of the UI it showed. Steps and reasoning are omitted. User messages
created from actions use the ``[action:name] {...}`` form.
"""
from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Optional

__all__ = ["serialize_history", "action_text", "node_source", "message_llm_text"]

_SKIP_UI = frozenset({"html", "invalid"})


def _compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def action_text(name: str, data: Optional[Mapping[str, Any]] = None, values: Optional[Mapping[str, Any]] = None) -> str:
    """Return the LLM-friendly form of an action: ``[action:name] {data+values}``."""
    payload = {**(data or {}), **(values or {})}
    return f"[action:{name}] {_compact(payload)}"


def _is_node(value: Any) -> bool:
    return isinstance(value, Mapping) and "ui" in value and "props" in value and "id" in value


def _convert(value: Any) -> Any:
    if _is_node(value):
        return node_source(value)
    if isinstance(value, list):
        out = [_convert(v) for v in value]
        return [v for v in out if v is not None]
    if isinstance(value, Mapping):
        return {k: _convert(v) for k, v in value.items() if not str(k).startswith("__")}
    return value


def node_source(node: Mapping[str, Any]) -> Optional[dict[str, Any]]:
    """Convert a ``UINode`` back to its compact LLM form ``{"ui", ...props}``.

    Returns ``None`` for nodes the model shouldn't see (``html``, ``invalid``,
    errored nodes).
    """
    ui = node.get("ui")
    if not isinstance(ui, str) or ui in _SKIP_UI or node.get("status") == "error":
        return None
    props = node.get("props") or {}
    out: dict[str, Any] = {"ui": ui}
    for key, value in props.items():
        if str(key).startswith("__"):
            continue
        out[key] = _convert(value)
    children = node.get("children")
    if children:
        out["children"] = [c for c in (_convert(ch) for ch in children) if c is not None]
    return out


def _user_text(msg: Mapping[str, Any]) -> str:
    meta = msg.get("meta") or {}
    if isinstance(meta, Mapping) and meta.get("llm_text"):
        return str(meta["llm_text"])
    texts: list[str] = []
    files: list[str] = []
    for part in msg.get("parts") or []:
        if part.get("type") == "text":
            texts.append(str(part.get("text", "")))
        elif part.get("type") == "file":
            f = part.get("file") or {}
            files.append(f"[Attached file: {f.get('name', 'file')} ({f.get('type') or 'unknown type'})]")
    text = "".join(texts)
    if files:
        text = (text + "\n\n" if text else "") + "\n".join(files)
    return text


def _assistant_text(msg: Mapping[str, Any]) -> str:
    out = ""
    block: list[str] = []

    def flush() -> None:
        nonlocal out, block
        if not block:
            return
        if out and not out.endswith("\n"):
            out += "\n"
        out += "```dyui\n" + "\n".join(block) + "\n```\n"
        block = []

    for part in msg.get("parts") or []:
        kind = part.get("type")
        if kind == "text":
            text = str(part.get("text", ""))
            if text:
                flush()
                out += text
        elif kind == "ui":
            source = part.get("source")
            if not isinstance(source, Mapping):
                source = node_source(part.get("node") or {})
            if source:
                block.append(_compact(source))
    flush()
    return out.strip("\n")


def message_llm_text(msg: Mapping[str, Any]) -> str:
    """Return the LLM-facing text for one stored message dict."""
    if msg.get("role") == "user":
        return _user_text(msg)
    return _assistant_text(msg)


def serialize_history(messages: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Convert stored messages to OpenAI-style ``[{"role", "content"}]``.

    Empty messages (e.g. an assistant turn that only ran steps) are skipped.
    """
    out: list[dict[str, str]] = []
    for msg in messages:
        role = msg.get("role")
        if role not in ("user", "assistant"):
            continue
        content = message_llm_text(msg)
        if not content.strip():
            continue
        out.append({"role": str(role), "content": content})
    return out
