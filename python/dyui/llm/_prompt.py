"""System-prompt assembly and message normalisation."""
from __future__ import annotations

from typing import Any

PLACEHOLDER = "{dyui_components}"


def build_system(system: str | None, components: Any = None) -> str | None:
    """Merge ``system`` with ``components.prompt()``.

    * ``{dyui_components}`` in ``system`` is replaced by the catalog prompt;
    * otherwise the catalog prompt is appended after a blank line;
    * with ``system=None`` the system prompt is just the catalog prompt.
    """
    if components is None:
        return system
    prompt = components.prompt() if hasattr(components, "prompt") else str(components)
    if system is None or not system.strip():
        return prompt
    if PLACEHOLDER in system:
        return system.replace(PLACEHOLDER, prompt)
    return f"{system.rstrip()}\n\n{prompt}"


def content_text(content: Any) -> str:
    """Flatten OpenAI-style ``content`` (str | list of parts | None) to text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out: list[str] = []
        for part in content:
            if isinstance(part, str):
                out.append(part)
            elif isinstance(part, dict):
                if isinstance(part.get("text"), str):
                    out.append(part["text"])
                elif part.get("type") == "text" and isinstance(part.get("content"), str):
                    out.append(part["content"])
        return "".join(out)
    return str(content)


def _get(msg: Any, key: str) -> Any:
    if isinstance(msg, dict):
        return msg.get(key)
    return getattr(msg, key, None)


def split_system(messages: list[Any], system: str | None) -> tuple[str | None, list[dict[str, Any]]]:
    """Pull ``system`` role messages out of ``messages`` (Anthropic style).
    Returns ``(system_text, remaining_messages)``."""
    sys_parts: list[str] = [system] if system else []
    rest: list[dict[str, Any]] = []
    for m in messages:
        role = _get(m, "role")
        if role in ("system", "developer"):
            text = content_text(_get(m, "content"))
            if text:
                sys_parts.append(text)
        else:
            rest.append({"role": role, "content": _get(m, "content")})
    return ("\n\n".join(sys_parts) or None), rest


def _anthropic_blocks(content: Any) -> str | list[dict[str, Any]]:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)
    blocks: list[dict[str, Any]] = []
    for part in content:
        if isinstance(part, str):
            blocks.append({"type": "text", "text": part})
        elif isinstance(part, dict):
            t = part.get("type")
            if t in (None, "text") and isinstance(part.get("text"), str):
                blocks.append({"type": "text", "text": part["text"]})
            elif t == "image_url":
                url = part.get("image_url")
                url = url.get("url") if isinstance(url, dict) else url
                if isinstance(url, str) and url.startswith("data:") and ";base64," in url:
                    head, data = url.split(",", 1)
                    media = head[5:].split(";")[0]
                    blocks.append({"type": "image", "source": {"type": "base64", "media_type": media, "data": data}})
                elif isinstance(url, str):
                    blocks.append({"type": "image", "source": {"type": "url", "url": url}})
            else:
                blocks.append(part)  # already Anthropic-shaped (image, document, ...)
    return blocks


def to_anthropic_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        role = "assistant" if m["role"] == "assistant" else "user"
        content = _anthropic_blocks(m["content"])
        if content in ("", []):
            continue
        out.append({"role": role, "content": content})
    return out


def to_openai_messages(messages: list[Any], system: str | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if system:
        out.append({"role": "system", "content": system})
    for m in messages:
        if isinstance(m, dict):
            out.append(m)
        else:  # tolerate objects with role/content
            out.append({"role": _get(m, "role"), "content": _get(m, "content")})
    return out


