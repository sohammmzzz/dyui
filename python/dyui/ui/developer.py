"""Developer-only components (never offered to the LLM): html, invalid."""
from __future__ import annotations

from pathlib import PurePath
from typing import Annotated, Any, Optional

from pydantic import field_validator, model_validator

from .base import Component
from .types import PyOnly

__all__ = ["Html", "Invalid"]


class Html(Component):
    """Developer-authored HTML rendered in a sandboxed iframe.

    The browser renders it in ``<iframe sandbox="allow-scripts" srcdoc=...>``
    without same-origin access. Pass inline ``html`` source, or a ``template``
    file plus ``props``. Template files are looked up in ``templates/`` and then
    the folder itself, first in ``template_root`` if given, else in your app's
    directory and the current directory; only ``.html`` files inside those
    folders can be read (see :func:`dyui.html.load_template`). In the template,
    ``{{ key }}`` is HTML-escaped and ``{{{ key }}}`` is inserted raw. Never
    produced by the LLM.

    Example:
        ``ui.Html(template="cards/flight.html", props={"airline": "TAP"}, height=180)``
        reads ``<app dir>/templates/cards/flight.html`` (or ``<app dir>/cards/flight.html``).
    """

    group = "developer"
    llm = False
    positional = ("html",)

    html: str = ""
    height: Optional[int] = None
    template: Annotated[Optional[str], PyOnly()] = None
    props: Annotated[Optional[dict[str, Any]], PyOnly()] = None
    template_root: Annotated[Optional[str], PyOnly()] = None

    @field_validator("template", "template_root", mode="before")
    @classmethod
    def _pathlike(cls, value: Any) -> Any:
        return str(value) if isinstance(value, PurePath) else value

    @model_validator(mode="after")
    def _needs_source(self) -> "Html":
        if not self.html and not self.template:
            raise ValueError("Html needs `html` or `template`")
        return self

    def _finish_node(self, node: dict[str, Any]) -> dict[str, Any]:
        props = node["props"]
        if self.template:
            from ..html import load_template, render_template

            source = load_template(self.template, root=self.template_root)
            props["html"] = render_template(source, self.props or {})
        props.pop("template", None)
        props.pop("props", None)
        props.pop("template_root", None)
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
