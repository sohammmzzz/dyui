"""End-to-end: the example agent over the FastAPI SSE endpoint."""

import json

import pytest

from examples.agent import graph
from dyui.server import create_dyui_app


def _parse_sse(raw: str):
    """Parse an SSE stream body into a list of (event, data) tuples."""
    frames = []
    event = None
    for block in raw.strip().split("\n\n"):
        if not block.strip():
            continue
        ev_type, data = None, None
        for line in block.splitlines():
            if line.startswith("event:"):
                ev_type = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data = line[len("data:"):].strip()
        if ev_type is not None:
            frames.append((ev_type, json.loads(data) if data else {}))
    return frames


def test_sse_endpoint_streams_cards():
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    app = create_dyui_app(graph, stream_tokens=False)
    client = TestClient(app)

    resp = client.post("/dyui/stream", json={"input": {"query": "berlin"}})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    frames = _parse_sse(resp.text)
    kinds = [k for k, _ in frames]
    assert "ui" in kinds
    assert kinds[-1] == "done"

    ui_events = [d for k, d in frames if k == "ui"]
    components = {e["component"] for e in ui_events}
    # The example graph emits these card types.
    assert {"markdown", "table", "progress", "stat", "html"} <= components

    # The search table progresses pending -> done under one id.
    table_events = [e for e in ui_events if e["component"] == "table"]
    assert [e["status"] for e in table_events] == ["pending", "done"]
    assert len({e["id"] for e in table_events}) == 1


def test_healthz():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    client = TestClient(create_dyui_app(graph))
    assert client.get("/healthz").json() == {"status": "ok"}
