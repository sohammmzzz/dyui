"""Interactive components: buttons, quick_replies, choice, form, confirm, rating.

Interactive components send an *action* back to the server when used (SPEC
§3.4); ``quick_replies`` instead send the option text as a user message.
"""
from __future__ import annotations

from typing import Any, Mapping, Optional, Union

from pydantic import model_validator

from .base import Component, Model
from .types import JsonObject, lax_enum

__all__ = ["Button", "Buttons", "QuickReplies", "Choice", "Field", "Form", "Confirm", "Rating"]

ButtonStyle = lax_enum(
    "primary", "secondary", "ghost", "danger", aliases={"default": "secondary", "outline": "secondary", "link": "ghost"}
)
FieldType = lax_enum(
    "text",
    "textarea",
    "number",
    "email",
    "select",
    "multiselect",
    "date",
    "time",
    "checkbox",
    "radio",
    "slider",
    aliases={"string": "text", "integer": "number", "int": "number", "float": "number", "bool": "checkbox",
             "boolean": "checkbox", "dropdown": "select", "range": "slider", "long_text": "textarea"},
)
RatingStyle = lax_enum("stars", "thumbs", aliases={"star": "stars", "thumb": "thumbs"})


def _single(action: Any, default: str, data: Any = None) -> list[tuple[str, Optional[dict[str, Any]]]]:
    name = action if isinstance(action, str) and action else default
    return [(name, data if isinstance(data, dict) else None)]


class Button(Model):
    """One button: ``label``, ``action`` name, optional static ``data`` and ``style``.

    Example:
        ``ui.Button("Book", action="book_flight", data={"id": "TP123"})``
    """

    __positional__ = ("label", "action")

    label: str
    action: str
    data: JsonObject = None
    style: Optional[ButtonStyle] = None


class Buttons(Component):
    """Action buttons; the click is sent back to you.

    Example:
        ``ui.Buttons(ui.Button("Approve", action="approve", style="primary"), ui.Button("Reject", action="reject"))``
    """

    group = "interactive"
    varargs = "items"
    examples = [{"items": [{"label": "Approve", "action": "approve", "style": "primary"},
                           {"label": "Reject", "action": "reject"}]}]

    items: list[Button]

    @classmethod
    def declared_actions(cls, props: Mapping[str, Any]) -> list[tuple[str, Optional[dict[str, Any]]]]:
        return [(b["action"], b.get("data")) for b in props.get("items") or [] if isinstance(b, dict) and b.get("action")]


class QuickReplies(Component):
    """Suggested follow-up replies the user can tap.

    Tapping sends the option text as a normal user message.

    Example:
        ``ui.QuickReplies("Show hotels", "Book the cheaper one")``
    """

    group = "interactive"
    varargs = "options"
    examples = [{"options": ["Show hotels too", "Book the cheaper one"]}]

    options: list[str]


class Choice(Component):
    """A single- or multiple-choice question.

    Values sent back: ``{"selected": [...], "other": "..."}``.

    Example:
        ``ui.Choice("Which seat?", ["Window", "Aisle"])``
    """

    group = "interactive"
    positional = ("question", "options")
    examples = [{"question": "Which seat do you prefer?", "options": ["Window", "Aisle"]}]

    question: str
    options: list[str]
    multiple: Optional[bool] = None
    allow_other: Optional[bool] = None
    action: str = "choice"
    submit_label: Optional[str] = None

    @classmethod
    def declared_actions(cls, props: Mapping[str, Any]) -> list[tuple[str, Optional[dict[str, Any]]]]:
        return _single(props.get("action"), "choice")


FieldDefault = Union[str, float, bool, list[str], None]


class Field(Model):
    """One form field.

    ``type`` is one of text, textarea, number, email, select, multiselect, date,
    time, checkbox, radio, slider. ``label`` defaults to a humanized ``name``.

    Example:
        ``ui.Field("email", "Work email", "email", required=True)``
    """

    __positional__ = ("name", "label", "type")
    __str_field__ = "name"

    name: str
    label: Optional[str] = None
    type: FieldType = "text"
    options: Optional[list[str]] = None
    required: Optional[bool] = None
    placeholder: Optional[str] = None
    default: FieldDefault = None
    min: Optional[float] = None
    max: Optional[float] = None
    step: Optional[float] = None

    @model_validator(mode="after")
    def _label(self) -> "Field":
        if not self.label:
            self.label = self.name.replace("_", " ").strip().capitalize() or self.name
        return self


class Form(Component):
    """A form to collect structured input.

    Values sent back: ``{<field name>: value}``.

    Example:
        ``ui.Form(ui.Field("name"), ui.Field("email", type="email"), title="Contact", action="contact")``
    """

    group = "interactive"
    positional = ("title",)
    varargs = "fields"
    examples = [{"title": "Contact details", "fields": [{"name": "email", "label": "Email", "type": "email",
                                                          "required": True}], "submit_label": "Send"}]

    title: Optional[str] = None
    fields: list[Field]
    submit_label: str = "Submit"
    action: str = "form_submit"

    @classmethod
    def declared_actions(cls, props: Mapping[str, Any]) -> list[tuple[str, Optional[dict[str, Any]]]]:
        return _single(props.get("action"), "form_submit")


class Confirm(Component):
    """Ask the user to confirm or cancel an action.

    Values sent back: ``{"confirmed": true|false}``.

    Example:
        ``ui.Confirm("Book TAP 18:05 for $189?", confirm_label="Book", data={"flight": "TP123"})``
    """

    group = "interactive"
    positional = ("title",)
    examples = [{"title": "Cancel the subscription?", "text": "You keep access until May 31.", "danger": True}]

    title: str
    text: Optional[str] = None
    confirm_label: str = "Confirm"
    cancel_label: str = "Cancel"
    action: str = "confirm"
    data: JsonObject = None
    danger: Optional[bool] = None

    @classmethod
    def declared_actions(cls, props: Mapping[str, Any]) -> list[tuple[str, Optional[dict[str, Any]]]]:
        return _single(props.get("action"), "confirm", props.get("data"))


class Rating(Component):
    """Ask the user for a rating.

    Values sent back: ``{"rating": n}`` (``1``/``-1`` for thumbs).

    Example:
        ``ui.Rating("How was this answer?")``
    """

    group = "interactive"
    positional = ("label",)

    label: Optional[str] = None
    max: int = 5
    style: Optional[RatingStyle] = None
    action: str = "rating"

    @classmethod
    def declared_actions(cls, props: Mapping[str, Any]) -> list[tuple[str, Optional[dict[str, Any]]]]:
        return _single(props.get("action"), "rating")
