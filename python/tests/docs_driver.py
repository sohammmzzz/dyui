"""Run one documentation example end to end, offline. Used by test_docs_examples.py.

    echo '[{"id": "x", "path": "app.py"}, {"id": "y", "source": "import dyui..."}]' | python docs_driver.py

The model SDKs are replaced by fakes *before* the example is imported, so nothing
touches the network and no API key is needed:

* ``dyui.llm.stream`` / ``dyui.llm.complete`` check their arguments against the real
  signatures (a docs example with an invented parameter fails here), validate the model
  string and the catalog prompt, then stream a short reply with one ```dyui fence;
* ``openai.AsyncOpenAI`` (and Azure) stream the same reply as chat-completion chunks;
* ``langgraph.prebuilt.create_react_agent`` and ``dyui.integrations.langgraph.stream``
  are stubbed, so LangGraph examples run without langchain model packages.

The driver then starts a conversation, sends the first starter (or "hello"), answers
every ``chat.ask()`` it meets, and clicks the first interactive component of each reply
for a few rounds. It prints one JSON line and exits 1 if any step failed.
"""
from __future__ import annotations

import asyncio
import importlib.util
import inspect
import json
import logging
import os
import sys
import tempfile
import types
from pathlib import Path
from typing import Any

FAKE_REPLY = [
    "Here is a quick summary.\n",
    "```dyui\n",
    '{"ui":"stat","label":"Total","value":"42"}\n',
    "```\n",
    "That's the headline number.",
]


# ------------------------------------------------------------------ fakes
def install_fakes(calls: list[str]) -> None:
    import dyui
    import dyui.llm as llm
    from dyui.llm._providers import parse_model

    real_stream, real_complete = llm.stream, llm.complete
    stream_sig = inspect.signature(real_stream)
    complete_sig = inspect.signature(real_complete)

    async def fake_stream(*args: Any, **kwargs: Any):
        bound = stream_sig.bind(*args, **kwargs)  # TypeError on an invented positional/keyword misuse
        parse_model(bound.arguments["model"])  # ValueError on a malformed "provider/model"
        msgs = bound.arguments["messages"]
        assert isinstance(msgs, list), "messages must be a list (usually chat.history)"
        comps = bound.arguments.get("components")
        reply = list(FAKE_REPLY)
        if comps is not None:
            from dyui.ui.registry import BUILTINS

            mode = bound.arguments.get("ui_mode", "fence")
            assert comps.prompt(mode=mode).startswith("## UI components")
            # like a real model, use the app's own components (their first example)
            for cls in comps:
                info = cls.__dyui__
                if cls not in BUILTINS and info.examples:
                    reply.insert(3, json.dumps({"ui": info.name, **dict(info.examples[0])}) + "\n")
        calls.append("llm.stream")
        for chunk in reply:
            await asyncio.sleep(0)
            yield chunk

    async def fake_complete(*args: Any, **kwargs: Any) -> str:
        complete_sig.bind(*args, **kwargs)
        calls.append("llm.complete")
        return "A short answer."

    llm.stream = fake_stream  # type: ignore[assignment]
    llm.complete = fake_complete  # type: ignore[assignment]
    dyui.llm = llm

    try:
        import openai
    except ImportError:
        openai = None
    if openai is not None:
        class _Chunk:
            def __init__(self, text: str) -> None:
                delta = types.SimpleNamespace(content=text)
                self.choices = [types.SimpleNamespace(delta=delta)]

        class _Stream:
            def __init__(self) -> None:
                self._it = iter(FAKE_REPLY)

            def __aiter__(self):
                return self

            async def __anext__(self):
                try:
                    return _Chunk(next(self._it))
                except StopIteration:
                    raise StopAsyncIteration from None

        class _Completions:
            async def create(self, **kwargs: Any):
                assert kwargs.get("model") and isinstance(kwargs.get("messages"), list)
                calls.append("openai.create")
                if kwargs.get("stream"):
                    return _Stream()
                msg = types.SimpleNamespace(content="".join(FAKE_REPLY))
                return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])

        class FakeOpenAI:
            def __init__(self, **kwargs: Any) -> None:
                self.chat = types.SimpleNamespace(completions=_Completions())

        openai.AsyncOpenAI = FakeOpenAI  # type: ignore[misc]
        openai.AsyncAzureOpenAI = FakeOpenAI  # type: ignore[misc]

    try:
        import langgraph.prebuilt as prebuilt
    except ImportError:
        prebuilt = None
    if prebuilt is not None:
        def fake_agent(model: Any, tools: Any = None, **kwargs: Any) -> Any:
            calls.append("create_react_agent")
            return types.SimpleNamespace(model=model, tools=tools, kwargs=kwargs)

        prebuilt.create_react_agent = fake_agent  # type: ignore[assignment]
        import dyui.integrations.langgraph as lg

        async def fake_lg_stream(graph: Any, input: Any, config: Any = None, **kwargs: Any):
            assert isinstance(input, dict) and "messages" in input
            calls.append("langgraph.stream")
            for chunk in FAKE_REPLY:
                yield chunk

        lg.stream = fake_lg_stream  # type: ignore[assignment]


# ------------------------------------------------------------------ helpers
def parse_sse(text: str) -> list[tuple[str, dict]]:
    events = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        name, data = None, []
        for line in block.split("\n"):
            if line.startswith("event:"):
                name = line[6:].strip()
            elif line.startswith("data:"):
                data.append(line[5:].strip())
        if name:
            events.append((name, json.loads("\n".join(data) or "{}")))
    return events


def sample_values(node: dict[str, Any]) -> dict[str, Any]:
    """What a user would send back for this top-level component."""
    kind, props = node.get("ui"), node.get("props") or {}
    if kind == "confirm":
        return {"confirmed": True}
    if kind == "rating":
        return {"rating": 5}
    if kind == "choice":
        opts = props.get("options") or ["x"]
        first = opts[0]
        return {"selected": [first.get("label", first.get("value")) if isinstance(first, dict) else first]}
    if kind == "form":
        out: dict[str, Any] = {}
        for f in props.get("fields") or []:
            t = f.get("type", "text")
            if t == "number":
                out[f["name"]] = 2
            elif t in ("checkbox", "switch"):
                out[f["name"]] = True
            elif t in ("select", "radio") and f.get("options"):
                o = f["options"][0]
                out[f["name"]] = o.get("value", o.get("label")) if isinstance(o, dict) else o
            elif t == "email":
                out[f["name"]] = "alex@example.com"
            elif t == "date":
                out[f["name"]] = "2026-05-01"
            else:
                out[f["name"]] = "test value"
        return out
    return {}


def interactive(events: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    """``(message_id, node)`` for the top-level ui nodes in this stream that declare an action."""
    from dyui.chat import declared_action_entries

    latest: dict[str, tuple[str, dict]] = {}
    for name, data in events:
        if name == "ui":
            node = data["node"]
            latest[node["id"]] = (data["message_id"], node)
    out = []
    for mid, node in latest.values():
        if node.get("status") != "done" or (node.get("props") or {}).get("__resolved__"):
            continue
        if declared_action_entries(node):
            out.append((mid, node))
    return out


# ------------------------------------------------------------------ drive
async def drive(app: Any, report: dict[str, Any]) -> None:
    import httpx

    from dyui.chat import declared_action_entries, find_node

    answered: set[tuple[str, str]] = set()

    async def post(c: httpx.AsyncClient, url: str, body: dict[str, Any]) -> list[tuple[str, dict]]:
        task = asyncio.create_task(c.post(url, json=body))
        deadline = asyncio.get_running_loop().time() + 20
        while not task.done():
            await asyncio.sleep(0.02)
            if asyncio.get_running_loop().time() > deadline:
                task.cancel()
                raise TimeoutError(f"{url} did not finish in 20s")
            for key, (_fut, turn) in list(app._pending.items()):
                if key in answered or not turn.message:
                    continue
                answered.add(key)
                tid, cid = key
                node = find_node(turn.message.get("parts") or [], cid) or {}
                name, data = (declared_action_entries(node) or [("confirm", None)])[0]
                r = await c.post("/api/action", json={
                    "thread_id": tid, "message_id": turn.message["id"], "component_id": cid,
                    "action": name, "label": "OK", "data": data or {}, "values": sample_values(node)})
                report["asks"].append({"ui": node.get("ui"), "action": name, "status": r.status_code})
                if r.status_code != 200:
                    report["errors"].append(f"answering chat.ask({node.get('ui')}) -> HTTP {r.status_code}")
        r = task.result()
        if r.status_code != 200:
            report["errors"].append(f"{url} -> HTTP {r.status_code}: {r.text[:200]}")
            return []
        events = parse_sse(r.text)
        for name, data in events:
            if name == "error":
                report["errors"].append(f"{url}: error event: {data.get('message')}")
        report["events"] += len(events)
        return events

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://docs.test") as c:
        if app.password:
            r = await c.post("/api/login", json={"password": app.password})
            if r.status_code != 200:
                report["errors"].append(f"login -> HTTP {r.status_code}")
                return
        r = await c.get("/api/config")
        if r.status_code != 200:
            report["errors"].append(f"/api/config -> HTTP {r.status_code}")
            return
        start = await post(c, "/api/threads", {})
        thread = next((d for e, d in start if e == "thread"), None)
        if thread is None:
            report["errors"].append("/api/threads emitted no thread")
            return
        text = app.starters[0].message if app.starters else "hello"
        events = await post(c, "/api/chat", {"thread_id": thread["id"], "message": {"text": text}})
        report["texts"] += sum(1 for e, _ in events if e in ("text", "ui"))
        if not any(e == "message_end" for e, _ in events):
            report["errors"].append("the reply never finished (no message_end)")
        # click through: the first interactive component of each reply, a few rounds deep
        for _ in range(4):
            targets = interactive(events)
            if not targets:
                break
            mid, node = targets[0]
            name, data = declared_action_entries(node)[0]
            events = await post(c, "/api/action", {
                "thread_id": thread["id"], "message_id": mid, "component_id": node["id"],
                "action": name, "label": "Clicked", "data": data or {}, "values": sample_values(node)})
            report["actions"].append({"ui": node.get("ui"), "action": name})


def find_app(module: Any) -> Any:
    import dyui

    for name in ("app", "application", "bot"):
        obj = getattr(module, name, None)
        if isinstance(obj, dyui.App):
            return obj
    return None


class _Capture(logging.Handler):
    """Collects what the app logs at ERROR (handler tracebacks) into the report."""

    def __init__(self) -> None:
        super().__init__(logging.ERROR)
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(self.format(record))


def run_one(item_id: str, path: Path, calls: list[str]) -> dict[str, Any]:
    report: dict[str, Any] = {"id": item_id, "errors": [], "asks": [], "actions": [], "events": 0, "texts": 0}
    start = len(calls)
    capture = _Capture()
    capture.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger("dyui").addHandler(capture)
    mod_name = f"docs_example_{abs(hash(item_id))}"
    sys.path.insert(0, str(path.parent))
    try:
        spec = importlib.util.spec_from_file_location(mod_name, path)
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        sys.modules[mod_name] = module
        try:
            spec.loader.exec_module(module)  # type: ignore[union-attr]
        except Exception as exc:
            report["errors"].append(f"import failed: {type(exc).__name__}: {exc}")
            return report
        app = find_app(module)
        if app is None:
            report["errors"].append("no dyui.App named app/application/bot")
        elif app._on_message is None:
            report["errors"].append("the app has no @app.on_message handler")
        else:
            app._persist = False
            app.data_dir = Path(os.getcwd()) / ".dyui"
            try:
                asyncio.run(drive(app, report))
            except Exception as exc:
                report["errors"].append(f"driving the app failed: {type(exc).__name__}: {exc}")
        if capture.records:
            report["errors"].extend(f"logged: {r}" for r in capture.records)
        return report
    finally:
        report["calls"] = calls[start:]
        logging.getLogger("dyui").removeHandler(capture)
        sys.path.remove(str(path.parent))
        sys.modules.pop(mod_name, None)


def main() -> int:
    """``docs_driver.py`` reads ``[{"id", "path" | "source"}, ...]`` as JSON on stdin and
    prints one JSON report per item. One process for all items keeps the SDK imports
    (openai, langgraph) to a single cold start."""
    items = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    calls: list[str] = []
    install_fakes(calls)
    scratch = Path(tempfile.mkdtemp(prefix="dyui-docs-"))
    failed = 0
    for n, item in enumerate(items):
        if "source" in item:
            folder = scratch / f"src{n}"
            folder.mkdir()
            path = folder / "app.py"
            path.write_text(item["source"], encoding="utf-8")
        else:
            path = Path(item["path"]).resolve()
        report = run_one(item["id"], path, calls)
        failed += bool(report["errors"])
        print(json.dumps(report), flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
