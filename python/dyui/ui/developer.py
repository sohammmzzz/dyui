"""Developer-only components (never offered to the LLM): html, invalid."""
from __future__ import annotations

from typing import Annotated, Any, Optional

from pydantic import model_validator

from .base import Component
from .types import PyOnly

__all__ = ["Html", "Invalid"]


class Html(Component):
    """Developer-authored HTML rendered in a sandboxed iframe.

    The browser renders it in ``<iframe sandbox="allow-scripts" srcdoc=...>``
    without same-origin access. Pass raw ``html``, or a ``template`` path
    (relative to your app's directory) plus ``props``; ``{{ key }}`` is escaped
    and ``{{{ key }}}`` inserted raw (see :mod:`dyui.html`). Never produced by
    the LLM.

    Example:
        ``ui.Html(template="cards/flight.html", props={"airline": "TAP"}, height=180)``
    """

    group = "developer"
    llm = False
    positional = ("html",)

    html: str = ""
    height: Optional[int] = None
    template: Annotated[Optional[str], PyOnly()] = None
    props: Annotated[Optional[dict[str, Any]], PyOnly()] = None

    @model_validator(mode="after")
    def _needs_source(self) -> "Html":
        if not self.html and not self.template:
            raise ValueError("Html needs `html` or `template`")
        return self

    def _finish_node(self, node: dict[str, Any]) -> dict[str, Any]:
        props = node["props"]
        if self.template:
            from ..html import render_template

            props["html"] = render_template(self.template, self.props or {})
        props.pop("template", None)
        props.pop("props", None)
        return node


class Invalid(Component):
    """A component that failed validation.

    Rendered as a quiet "Couldn't display this component" chip with the raw
    payload and error available on expand.
    """

    group = "developer"
    llm = False

    raw: str = ""
    error: str = ""

    def _finish_node(self, node: dict[str, Any]) -> dict[str, Any]:
        node["props"] = {"raw": self.raw[:4000], "error": self.error}
        node["status"] = "error"
        node["error"] = self.error
        return node
