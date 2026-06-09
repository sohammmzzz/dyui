"""The bundled `dyui demo` app and the served-UI feature surface."""

import pytest

from dyui import collect_events
from dyui.server import render_ui_page


def test_demo_graph_emits_a_variety_of_cards():
    from dyui.demo import build_graph

    components = {e["component"] for e in collect_events(build_graph(), {"query": "x"})}
    # The demo is the living catalogue -- it should exercise many card types.
    assert {"markdown", "table", "progress", "stat", "list", "keyvalue", "alert", "html"} <= components


def test_demo_app_serves_ui_and_streams():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from dyui.demo import build_app

    client = TestClient(build_app())
    page = client.get("/")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]

    # A bare string input must work end-to-end via the smart adapter.
    resp = client.post("/dyui/stream", json={"input": "berlin"})
    assert resp.status_code == 200
    assert "event: ui" in resp.text


def test_served_ui_has_modern_features():
    page = render_ui_page(title="X")
    # Stop button, copy buttons, scroll-to-latest pill, smart auto-scroll.
    assert 'id="toBottom"' in page
    assert "is-stop" in page
    assert "copybtn" in page
    assert "AbortController" in page
    assert "nearBottom" in page
