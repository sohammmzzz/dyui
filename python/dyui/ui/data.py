"""Data components: table, stat, stats, keyvalue, chart, progress, timeline, json."""
from __future__ import annotations

import json
from typing import Annotated, Any, Optional, Union

from pydantic import BeforeValidator, field_validator, model_validator

from .base import Component, Model
from .types import TS, Scalar, lax_enum

__all__ = [
    "Table",
    "Stat",
    "StatItem",
    "Stats",
    "KeyValue",
    "KeyValueItem",
    "Chart",
    "Series",
    "Progress",
    "Timeline",
    "TimelineItem",
    "Json",
]


def _scalarize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        return str(value)


Cell = Annotated[Union[str, int, float, bool, None], BeforeValidator(_scalarize)]
Trend = lax_enum("up", "down", "flat", aliases={"neutral": "flat", "same": "flat", "increase": "up", "decrease": "down"})
ChartKind = lax_enum(
    "bar", "line", "area", "pie", "donut", "scatter", aliases={"column": "bar", "doughnut": "donut", "ring": "donut"}
)
TimelineStatus = lax_enum(
    "done",
    "active",
    "pending",
    aliases={"complete": "done", "completed": "done", "current": "active", "in_progress": "active", "todo": "pending"},
)


class Table(Component):
    """Tabular data; use for 3+ rows.

    Rows may also be given as a list of dicts (columns are taken from the keys).

    Example:
        ``ui.Table(["City", "Temp"], [["Lisbon", 24], ["Porto", 21]])``
    """

    group = "data"
    positional = ("columns", "rows")
    examples = [{"columns": ["Plan", "Price"], "rows": [["Starter", "$9"], ["Pro", "$29"]]}]

    columns: list[str]
    rows: Annotated[list[list[Cell]], TS("(string|number)[][]")]
    caption: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def _rows_from_dicts(cls, data: Any) -> Any:
        if isinstance(data, dict):
            rows = data.get("rows")
            if isinstance(rows, list) and rows and all(isinstance(r, dict) for r in rows):
                cols = data.get("columns") or list(dict.fromkeys(k for r in rows for k in r))
                data = {**data, "columns": cols, "rows": [[r.get(c) for c in cols] for r in rows]}
            elif "columns" not in data and isinstance(data.get("headers"), list):
                data = {**data, "columns": data["headers"]}
        return data


def _infer_trend(delta: Optional[str]) -> Optional[str]:
    if not delta:
        return None
    s = delta.strip()
    if s.startswith("+") or s.startswith("▲"):
        return "up"
    if s.startswith(("-", "−", "▼")):
        return "down"
    return None


class Stat(Component):
    """One headline number.

    ``trend`` is inferred from a signed ``delta`` (``+12%`` → up) when omitted.

    Example:
        ``ui.Stat("Revenue", "$48.2k", delta="+12%")``
    """

    group = "data"
    positional = ("label", "value")
    examples = [{"label": "Revenue", "value": "$48.2k", "delta": "+12%", "trend": "up"}]

    label: str
    value: Union[str, int, float]
    unit: Optional[str] = None
    delta: Optional[str] = None
    trend: Optional[Trend] = None
    help: Optional[str] = None

    @model_validator(mode="after")
    def _trend(self) -> "Stat":
        if self.trend is None:
            self.trend = _infer_trend(self.delta)  # type: ignore[assignment]
        return self


class StatItem(Model):
    """One stat inside ``stats`` (same props as ``stat``)."""

    __positional__ = ("label", "value")
    __ts__ = "stat"

    label: str
    value: Union[str, int, float]
    unit: Optional[str] = None
    delta: Optional[str] = None
    trend: Optional[Trend] = None
    help: Optional[str] = None

    @model_validator(mode="after")
    def _trend(self) -> "StatItem":
        if self.trend is None:
            self.trend = _infer_trend(self.delta)  # type: ignore[assignment]
        return self


class Stats(Component):
    """A responsive row of headline numbers.

    Example:
        ``ui.Stats(ui.Stat("Orders", 1284), ui.Stat("AOV", "$37.50"))``
    """

    group = "data"
    varargs = "items"
    examples = [{"items": [{"label": "Orders", "value": 1284}, {"label": "Churn", "value": "2.1%", "delta": "-0.4pt"}]}]

    items: Annotated[list[StatItem], TS("stat[]")]

    @field_validator("items", mode="before")
    @classmethod
    def _from_stats(cls, value: Any) -> Any:
        if isinstance(value, (list, tuple)):
            return [v.model_dump(exclude_none=True) if isinstance(v, Stat) else v for v in value]
        return value


class KeyValueItem(Model):
    """One ``key``/``value`` pair."""

    __positional__ = ("key", "value")

    key: str
    value: Annotated[Scalar, BeforeValidator(_scalarize)] = None


class KeyValue(Component):
    """Labeled facts as key/value pairs.

    Accepts ``items=[{key, value}]``, a plain dict, or ``data={k: v}``.

    Example:
        ``ui.KeyValue({"Status": "Open", "Priority": "High"})``
    """

    name = "keyvalue"
    group = "data"
    positional = ("items",)
    examples = [{"items": [{"key": "Status", "value": "Open"}, {"key": "Owner", "value": "Ana"}]}]

    items: list[KeyValueItem]

    @model_validator(mode="before")
    @classmethod
    def _from_mapping(cls, data: Any) -> Any:
        if isinstance(data, dict):
            items = data.get("items")
            if items is None and isinstance(data.get("data"), dict):
                items = data["data"]
            if isinstance(items, dict):
                items = [{"key": str(k), "value": v} for k, v in items.items()]
            if items is not None:
                data = {**data, "items": items}
        return data


SeriesData = Annotated[
    Union[list[Optional[float]], list[tuple[float, float]]], TS("number[]|[number,number][]")
]


class Series(Model):
    """One chart series: ``name`` and ``data`` (numbers, or ``[x, y]`` pairs)."""

    __positional__ = ("name", "data")

    name: str = ""
    data: SeriesData

    @model_validator(mode="before")
    @classmethod
    def _aliases(cls, data: Any) -> Any:
        if isinstance(data, dict) and "data" not in data:
            for alt in ("values", "points", "y"):
                if alt in data:
                    return {**data, "data": data[alt]}
        if isinstance(data, list):
            return {"data": data}
        return data


class Chart(Component):
    """A chart: bar/line/area for trends and comparisons, pie/donut for shares, scatter for x/y.

    Example:
        ``ui.Chart("bar", [ui.Series("Revenue", [12, 18, 24])], labels=["Jul", "Aug", "Sep"])``
    """

    group = "data"
    positional = ("kind", "series")
    examples = [
        {
            "kind": "bar",
            "labels": ["Jul", "Aug", "Sep"],
            "series": [{"name": "Revenue", "data": [42, 51, 58]}],
            "unit": "$k",
        }
    ]

    kind: ChartKind
    labels: Optional[list[str]] = None
    series: list[Series]
    title: Optional[str] = None
    unit: Optional[str] = None
    stacked: Optional[bool] = None

    @model_validator(mode="before")
    @classmethod
    def _shorthand(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        if "kind" not in data:
            for alt in ("type", "chart"):
                if isinstance(data.get(alt), str):
                    data["kind"] = data[alt]
                    break
        series = data.get("series")
        if series is None and isinstance(data.get("data"), list):
            series = data["data"]
        if isinstance(series, dict):
            series = [series]
        if isinstance(series, list) and series and all(
            isinstance(v, (int, float, str)) or v is None for v in series
        ):
            series = [{"name": data.get("title") or "", "data": series}]
        if series is not None:
            data["series"] = series
        return data

    @model_validator(mode="after")
    def _names(self) -> "Chart":
        for i, s in enumerate(self.series):
            if not s.name:
                s.name = f"Series {i + 1}"
        return self


def _percent(value: Any) -> Any:
    if isinstance(value, str) and value.strip().endswith("%"):
        return value.strip().rstrip("%").strip()
    return value


class Progress(Component):
    """Progress toward a goal.

    Example:
        ``ui.Progress(64, label="Upload")``
    """

    group = "data"
    positional = ("value",)
    examples = [{"value": 64, "label": "Profile complete"}]

    value: Annotated[float, BeforeValidator(_percent)]
    max: float = 100
    label: Optional[str] = None


class TimelineItem(Model):
    """One timeline entry."""

    __positional__ = ("title", "time", "text")
    __str_field__ = "title"

    title: str
    time: Optional[str] = None
    text: Optional[str] = None
    status: Optional[TimelineStatus] = None


class Timeline(Component):
    """Events or steps in time order.

    Example:
        ``ui.Timeline(ui.TimelineItem("Ordered", "Mon"), ui.TimelineItem("Shipped", "Tue"))``
    """

    group = "data"
    varargs = "items"
    examples = [
        {
            "items": [
                {"title": "Order placed", "time": "Mon 09:12", "status": "done"},
                {"title": "Out for delivery", "time": "Today", "status": "active"},
            ]
        }
    ]

    items: list[TimelineItem]


class Json(Component):
    """Raw structured data as a collapsible tree.

    Example:
        ``ui.Json({"id": 42, "tags": ["a", "b"]}, title="Response")``
    """

    group = "data"
    positional = ("data",)

    data: Any
    title: Optional[str] = None
