"""Regression tests for the security + functional fixes.

Each test pins a specific vulnerability or footgun that was fixed, so a future
change that reintroduces it fails loudly.
"""

import json
import warnings

import pytest

from dyui import Card, HtmlTemplates, collect_events, emit, render_template
from dyui.server import _sanitize_client_config, render_ui_page

CARDS_DIR = __import__("pathlib").Path(__file__).parent.parent / "examples" / "cards"


# --------------------------------------------------------------------------- #
# Path traversal in HtmlTemplates._load
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "bad_name",
    [
        "../../dyui/static/index",
        "../secrets",
        "foo/bar",
        "foo\\bar",
        "..",
        "",
    ],
)
def test_template_loader_rejects_traversal(bad_name):
    cards = HtmlTemplates(CARDS_DIR)
    with pytest.raises(ValueError):
        cards.render(bad_name)


def test_template_loader_still_loads_valid_name():
    cards = HtmlTemplates(CARDS_DIR)
    html = cards.render("weather", emoji="x", city="Berlin", temp=21, summary="ok")
    assert "Berlin" in html


# --------------------------------------------------------------------------- #
# render_template: missing keys no longer silently blank
# --------------------------------------------------------------------------- #
def test_render_template_warns_on_missing_key():
    with pytest.warns(UserWarning):
        out = render_template("<b>{{ name }}</b>", {})
    assert out == "<b></b>"


def test_render_template_strict_raises_on_missing_key():
    with pytest.raises(KeyError):
        render_template("<b>{{ name }}</b>", {}, strict=True)


def test_render_template_no_warning_when_all_keys_present():
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert render_template("<b>{{ name }}</b>", {"name": "x"}) == "<b>x</b>"


# --------------------------------------------------------------------------- #
# render_ui_page: title escaped, stream_path JSON-encoded
# --------------------------------------------------------------------------- #
def test_render_ui_page_escapes_title():
    page = render_ui_page(title='</title><script>alert(1)</script>')
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_render_ui_page_json_encodes_stream_path():
    page = render_ui_page(stream_path='/x";evil()//')
    # The path is injected as a JS string literal, so the quote is escaped and
    # can't break out of the assignment.
    assert 'const STREAM_PATH = ' + json.dumps('/x";evil()//') in page
    # The unescaped break-out sequence must not appear (it's `\";` not `";`).
    assert '"/x";evil' not in page


# --------------------------------------------------------------------------- #
# Client config sanitization
# --------------------------------------------------------------------------- #
def test_sanitize_client_config_strips_thread_and_checkpoint():
    cfg = {
        "configurable": {
            "thread_id": "victim-thread",
            "checkpoint_id": "c1",
            "checkpoint_ns": "n",
            "__internal": "x",
            "my_setting": "ok",
        },
        "recursion_limit": 9999,
    }
    out = _sanitize_client_config(cfg)
    assert out == {"configurable": {"my_setting": "ok"}}
    assert "recursion_limit" not in out


def test_sanitize_client_config_handles_non_dicts():
    assert _sanitize_client_config(None) == {}
    assert _sanitize_client_config("nope") == {}
    assert _sanitize_client_config({"configurable": {"thread_id": "x"}}) == {}


# --------------------------------------------------------------------------- #
# Card lifecycle: active cards finalize on clean exit
# --------------------------------------------------------------------------- #
def test_card_active_is_finalized_on_clean_exit():
    with Card("progress", title="Indexing") as card:
        card.progress({"value": 1, "max": 3})
        assert card._event.status == "active"
    # Clean exit without done() must not leave the card spinning forever.
    assert card._event.status == "done"


def test_card_error_on_exception():
    try:
        with Card("progress") as card:
            card.progress({"value": 1})
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert card._event.status == "error"
