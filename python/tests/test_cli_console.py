"""The CLI must not crash on consoles that can't encode its glyphs (Windows cp1252)."""
from __future__ import annotations

import io
import sys

import pytest

from dyui import cli


def cp1252_stream() -> io.TextIOWrapper:
    return io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict", write_through=True)


def text_of(stream: io.TextIOWrapper) -> str:
    stream.flush()
    return stream.buffer.getvalue().decode("cp1252")


def test_banner_falls_back_to_ascii_on_cp1252(monkeypatch):
    out = cp1252_stream()
    monkeypatch.setattr(sys, "stdout", out)
    cli._banner("Travel Bot", "http://127.0.0.1:8000")  # used to raise UnicodeEncodeError
    text = text_of(out)
    assert "* " in text and "Travel Bot" in text and "- DyUI" in text


def test_banner_keeps_glyphs_on_utf8(monkeypatch):
    out = io.TextIOWrapper(io.BytesIO(), encoding="utf-8", write_through=True)
    monkeypatch.setattr(sys, "stdout", out)
    cli._banner("T", "http://x")
    out.flush()
    assert cli._GLYPHS[0] in out.buffer.getvalue().decode("utf-8")


def test_main_never_crashes_on_unencodable_output(monkeypatch, tmp_path):
    out, err = cp1252_stream(), cp1252_stream()
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", err)
    app_py = tmp_path / "app.py"
    app_py.write_text('import dyui\napp = dyui.App(title="日本 ◉ Bot", persist=False)\n', encoding="utf-8")
    # `catalog` prints em dashes, middots and the approx sign; the title has CJK + a glyph
    assert cli.main(["catalog", str(app_py)]) == 0
    assert out.errors == "replace"
    assert "components" in text_of(out)
    monkeypatch.setattr(sys, "stdout", cp1252_stream())
    cli.main([])  # help text too
    cli._banner("日本 Bot", "http://x")


def test_safe_console_tolerates_streams_without_reconfigure(monkeypatch):
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    cli._safe_console()  # StringIO has no reconfigure(): must be a no-op


@pytest.mark.parametrize("enc,ok", [("utf-8", True), ("cp1252", False), ("ascii", False), ("bogus-enc", False)])
def test_can_encode(enc, ok):
    class S:
        encoding = enc

    assert cli._can_encode(cli._GLYPHS, S()) is ok
