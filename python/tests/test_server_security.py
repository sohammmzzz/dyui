"""Server-level security tests: auth, CORS default, body limit, config, errors."""

import json

import pytest

from examples.agent import graph
from dyui.server import create_dyui_app

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402


def _client(**kwargs):
    return TestClient(create_dyui_app(graph, stream_tokens=False, **kwargs))


# --------------------------------------------------------------------------- #
# CORS no longer wildcard by default
# --------------------------------------------------------------------------- #
def test_cors_default_blocks_arbitrary_origin():
    client = _client()
    resp = client.post(
        "/dyui/stream",
        json={"input": {"query": "berlin"}},
        headers={"Origin": "https://evil.example"},
    )
    # The request still runs (CORS is browser-enforced) but the server must not
    # bless a foreign origin with an ACAO header.
    assert resp.headers.get("access-control-allow-origin") != "*"
    assert resp.headers.get("access-control-allow-origin") != "https://evil.example"


def test_cors_allows_localhost_origin():
    client = _client()
    resp = client.post(
        "/dyui/stream",
        json={"input": {"query": "berlin"}},
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


# --------------------------------------------------------------------------- #
# Optional API token
# --------------------------------------------------------------------------- #
def test_api_token_required_when_set():
    client = _client(api_token="s3cret")
    # Missing token -> 401.
    resp = client.post("/dyui/stream", json={"input": {"query": "x"}})
    assert resp.status_code == 401
    # Wrong token -> 401.
    resp = client.post(
        "/dyui/stream",
        json={"input": {"query": "x"}},
        headers={"Authorization": "Bearer nope"},
    )
    assert resp.status_code == 401
    # Correct token -> 200.
    resp = client.post(
        "/dyui/stream",
        json={"input": {"query": "x"}},
        headers={"Authorization": "Bearer s3cret"},
    )
    assert resp.status_code == 200
    # X-DyUI-Token header also accepted.
    resp = client.post(
        "/dyui/stream",
        json={"input": {"query": "x"}},
        headers={"X-DyUI-Token": "s3cret"},
    )
    assert resp.status_code == 200


# --------------------------------------------------------------------------- #
# Body-size guard + malformed body
# --------------------------------------------------------------------------- #
def test_oversized_body_rejected():
    client = _client()
    big = {"input": {"query": "x" * (2 * 1024 * 1024 + 10)}}
    resp = client.post("/dyui/stream", json=big)
    assert resp.status_code == 413


def test_malformed_json_rejected():
    client = _client()
    resp = client.post(
        "/dyui/stream",
        content=b"not json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400


# --------------------------------------------------------------------------- #
# Client config ignored by default
# --------------------------------------------------------------------------- #
def test_client_config_ignored_by_default():
    # A client trying to hijack another thread must not have its config forwarded.
    seen = {}

    class SpyGraph:
        async def astream(self, input, *, config, stream_mode):
            seen["config"] = config
            if False:  # pragma: no cover - make this an async generator
                yield

    app = create_dyui_app(SpyGraph(), stream_tokens=False)
    client = TestClient(app)
    client.post(
        "/dyui/stream",
        json={"input": {}, "config": {"configurable": {"thread_id": "victim"}}},
    )
    assert seen["config"] == {}


def test_client_config_sanitized_when_allowed():
    seen = {}

    class SpyGraph:
        async def astream(self, input, *, config, stream_mode):
            seen["config"] = config
            if False:  # pragma: no cover
                yield

    app = create_dyui_app(SpyGraph(), stream_tokens=False, allow_client_config=True)
    client = TestClient(app)
    client.post(
        "/dyui/stream",
        json={
            "input": {},
            "config": {"configurable": {"thread_id": "victim", "ok": 1}},
        },
    )
    assert seen["config"] == {"configurable": {"ok": 1}}


# --------------------------------------------------------------------------- #
# Errors masked by default
# --------------------------------------------------------------------------- #
def test_error_message_masked_by_default():
    class BoomGraph:
        async def astream(self, input, *, config, stream_mode):
            raise RuntimeError("super secret internal detail")
            if False:  # pragma: no cover
                yield

    app = create_dyui_app(BoomGraph(), stream_tokens=False)
    client = TestClient(app)
    resp = client.post("/dyui/stream", json={"input": {}})
    assert "super secret internal detail" not in resp.text
    assert "The agent run failed." in resp.text


def test_error_message_shown_with_debug_errors():
    class BoomGraph:
        async def astream(self, input, *, config, stream_mode):
            raise RuntimeError("super secret internal detail")
            if False:  # pragma: no cover
                yield

    app = create_dyui_app(BoomGraph(), stream_tokens=False, debug_errors=True)
    client = TestClient(app)
    resp = client.post("/dyui/stream", json={"input": {}})
    assert "super secret internal detail" in resp.text
