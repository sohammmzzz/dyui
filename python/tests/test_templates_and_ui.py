"""HTML-template cards + the built-in served UI (the zero-frontend path)."""

import json
from pathlib import Path

import pytest

from dyui import HtmlTemplates, collect_events, render_template
from dyui.server import render_ui_page
from examples.html_agent import build_graph

CARDS_DIR = Path(__file__).parent.parent / "examples" / "cards"


def test_render_template_escapes_by_default():
    out = render_template("<b>{{ name }}</b>", {"name": "<script>"})
    assert "&lt;script&gt;" in out
    assert "<script>" not in out


def test_render_template_raw_with_triple_or_amp():
    assert render_template("{{{ x }}}", {"x": "<i>hi</i>"}) == "<i>hi</i>"
    assert render_template("{{& x }}", {"x": "<i>hi</i>"}) == "<i>hi</i>"


def test_html_templates_loader():
    cards = HtmlTemplates(CARDS_DIR)
    assert {"weather", "invoice"} <= set(cards.available())
    html = cards.render("invoice", number=7, total="$10", customer="Acme",
                         date="2026", items=3, status="Paid")
    assert "Invoice #7" in html
    assert "Acme" in html


def test_html_templates_missing_raises():
    with pytest.raises(FileNotFoundError):
        HtmlTemplates(CARDS_DIR).render("nope")


def test_agent_emits_html_cards():
    events = collect_events(build_graph(), {"city": "Berlin"})
    html_cards = [e for e in events if e["component"] == "html"]
    assert len(html_cards) == 2
    assert any("Berlin" in e["props"]["html"] for e in html_cards)
    # template name is recorded in meta
    assert {e["meta"]["template"] for e in html_cards} == {"weather", "invoice"}


def test_render_ui_page_fills_placeholders():
    page = render_ui_page(stream_path="/dyui/stream", title="My App", auto_input="hi")
    assert "__DYUI_STREAM_PATH__" not in page
    assert "/dyui/stream" in page
    assert "My App" in page
    assert json.dumps("hi") in page  # auto_input injected as JSON


def test_served_ui_and_stream_end_to_end():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from examples.html_agent import _input_adapter
    from dyui.server import create_dyui_app

    app = create_dyui_app(
        build_graph(), input_adapter=_input_adapter, stream_tokens=False, serve_ui=True
    )
    client = TestClient(app)

    # The UI page is served at GET / with no frontend build.
    page = client.get("/")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]

    # And the same server streams the html cards.
    resp = client.post("/dyui/stream", json={"input": "Berlin"})
    frames = resp.text
    assert "event: ui" in frames
    assert "Invoice #1042" in frames  # rendered template content on the wire
