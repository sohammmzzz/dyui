"""``dyui.App`` — declare a chatbot in one Python file.

Example:
    >>> import dyui
    >>> app = dyui.App(title="Travel Bot", starters=["Plan a weekend in Lisbon"])
    >>> @app.on_message
    ... async def reply(msg, chat):
    ...     yield f"You said: {msg.text}"
"""
from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any, Callable, Literal, Optional, Sequence, Union

from .chat import Action, Chat, Feedback, File, Message, Starter, Turn, iterate
from .genui import Catalog, action_text
from .store import make_store, now_ms
from .store.base import DEFAULT_TITLE
from .ui.base import Component
from .ui.registry import BUILTINS, LLM_BUILTINS
from .__version__ import __version__

log = logging.getLogger("dyui")

__all__ = ["App"]

Handler = Callable[..., Any]

NAMED_ACCENTS = {"indigo", "teal", "rose", "amber", "emerald", "slate"}
_CLAIM_TTL_S = 120.0
_ORIGIN = re.compile(r"https?://(\*\.)?[A-Za-z0-9.-]+(:\d{1,5})?")


class App:
    """A DyUI chat application (and an ASGI app: ``uvicorn app:app`` works).

    Args:
        title: App name, shown in the header and browser tab.
        description: Shown under the welcome heading.
        welcome: Welcome heading (default "How can I help?").
        placeholder: Composer placeholder; ``{title}`` is substituted.
        logo: URL or local image path for your logo.
        theme: ``"system"``, ``"light"`` or ``"dark"``.
        accent: ``indigo`` (default), ``teal``, ``rose``, ``amber``, ``emerald``, ``slate`` or a hex color.
        starters: Suggested first messages (strings or :class:`dyui.Starter`).
        components: Which built-in components the LLM may use: ``"all"``, a list of names /
            component classes, or ``None`` for none. Custom components are always included.
        persist: ``True`` → SQLite at ``./.dyui/dyui.db``; a path → SQLite there;
            ``False`` → in memory; or a ``Store`` instance.
        password: Require this shared password to use the app.
        uploads: Allow file uploads.
        feedback: Show thumbs up/down on replies.
        history: Show the conversation sidebar.
        max_upload_mb: Upload size limit.
        data_dir: Where DyUI keeps its database and uploads (default ``./.dyui``).
        embed_origins: Sites allowed to show this app in an ``<iframe>``
            (e.g. ``["https://example.com"]``). By default only the app itself may frame it.
        csp: The Content-Security-Policy sent with the app's HTML: ``True`` (DyUI's
            strict default), a policy string of your own, or ``False`` to send none.
    """

    def __init__(
        self,
        title: str = "DyUI",
        *,
        description: Optional[str] = None,
        welcome: Optional[str] = None,
        placeholder: str = "Message {title}…",
        logo: Optional[str] = None,
        theme: Literal["system", "light", "dark"] = "system",
        accent: str = "indigo",
        starters: Sequence[Union[str, Starter]] = (),
        components: Union[Literal["all"], Sequence[Union[str, type[Component]]], None] = "all",
        persist: Any = True,
        password: Optional[str] = None,
        uploads: bool = True,
        feedback: bool = True,
        history: bool = True,
        max_upload_mb: int = 20,
        data_dir: Union[str, Path, None] = None,
        embed_origins: Sequence[str] = (),
        csp: Union[bool, str] = True,
    ) -> None:
        self.title = title
        self.description = description
        self.welcome = welcome or "How can I help?"
        self.placeholder = placeholder
        self.logo = logo
        self.theme = theme
        self.accent = accent
        self.starters = [s if isinstance(s, Starter) else Starter(str(s)) for s in starters]
        self.components = components
        self.password = password
        self.uploads = uploads
        self.feedback = feedback
        self.history = history
        self.max_upload_mb = max_upload_mb
        self.data_dir = Path(data_dir) if data_dir else Path.cwd() / ".dyui"
        for origin in embed_origins:
            if not _ORIGIN.fullmatch(str(origin)):
                raise ValueError(f"embed_origins: {origin!r} is not an origin like 'https://example.com'")
        self.embed_origins = tuple(str(o) for o in embed_origins)
        if not isinstance(csp, (bool, str)) or (isinstance(csp, str) and ("\r" in csp or "\n" in csp)):
            raise ValueError("csp must be True, False or a policy string")
        self.csp = csp
        _register_caller_dir()
        self._persist = persist
        self._store: Any = None
        self._custom: list[type[Component]] = []
        self._on_message: Optional[Handler] = None
        self._on_chat_start: Optional[Handler] = None
        self._on_feedback: Optional[Handler] = None
        self._actions: dict[str, Handler] = {}
        self._pending: dict[tuple[str, str], tuple[asyncio.Future, Turn]] = {}
        self._claims: dict[tuple[str, str], float] = {}
        self._live_messages: set[str] = set()   # assistant messages a turn is still streaming
        self._asgi: Any = None

    # ------------------------------------------------------------ decorators
    def on_message(self, fn: Handler) -> Handler:
        """Register the reply handler: ``(msg: Message, chat: Chat)``. Required."""
        self._on_message = fn
        return fn

    def on_chat_start(self, fn: Handler) -> Handler:
        """Register a handler run when a conversation starts: ``(chat: Chat)``."""
        self._on_chat_start = fn
        return fn

    def on_feedback(self, fn: Handler) -> Handler:
        """Register a thumbs up/down handler: ``(feedback: Feedback, chat: Chat)``."""
        self._on_feedback = fn
        return fn

    def on_action(self, name: str) -> Callable[[Handler], Handler]:
        """Register a handler for a component action: ``(action: Action, chat: Chat)``.

        It may yield a reply like ``on_message``. Unhandled actions are sent to
        ``on_message`` as an LLM-friendly ``"[action:name] {...}"`` message.
        """

        def deco(fn: Handler) -> Handler:
            self._actions[name] = fn
            return fn

        return deco

    def component(self, cls: type[Component]) -> type[Component]:
        """Register a custom component; the LLM learns it on the next turn."""
        if not (isinstance(cls, type) and issubclass(cls, Component)):
            raise TypeError("@app.component expects a dyui.Component subclass")
        if cls not in self._custom:
            self._custom.append(cls)
        return cls

    # ------------------------------------------------------------ catalog
    @property
    def catalog(self) -> Catalog:
        """The components this app's LLM may use (enabled built-ins + your custom ones).

        Rebuilt on every access, so the prompt always reflects the live registry.
        """
        if self.components == "all":
            builtins = list(LLM_BUILTINS)
        elif not self.components:
            builtins = []
        else:
            wanted = {c if isinstance(c, str) else c.__dyui__.name for c in self.components}
            builtins = [c for c in LLM_BUILTINS if c.__dyui__.name in wanted]
            builtins += [c for c in self.components if isinstance(c, type) and c not in builtins and c not in LLM_BUILTINS]
        return Catalog([*builtins, *self._custom])

    @property
    def render_catalog(self) -> Catalog:
        """Everything this app can render (all built-ins + custom)."""
        return Catalog([*BUILTINS, *self._custom])

    @property
    def untrusted_catalog(self) -> Catalog:
        """What *model-written* UI may use: every LLM built-in + custom components.

        Used for fenced ``dyui`` blocks in text and ``{"ui": ...}`` dicts (which is
        what tools-mode LLM calls produce). Developer-only components (``html``,
        ``invalid``) are excluded — the LLM can never produce HTML. Developers
        render ``ui.Html`` by yielding the component instance.
        """
        return Catalog([*LLM_BUILTINS, *self._custom])

    # ------------------------------------------------------------ store
    @property
    def store(self) -> Any:
        if self._store is None:
            self._store = make_store(self._persist, self.data_dir)
        return self._store

    # ------------------------------------------------------------ config
    def config(self, authenticated: bool = True) -> dict[str, Any]:
        """The ``AppConfig`` the web app loads (SPEC §4)."""
        logo = self.logo
        if logo and not logo.startswith(("http://", "https://", "/", "data:")):
            logo = "api/logo"
        return {
            "title": self.title,
            "description": self.description,
            "welcome": self.welcome,
            "placeholder": self.placeholder.replace("{title}", self.title),
            "logo": logo,
            "theme": self.theme,
            "accent": self.accent,
            "starters": [s.to_dict() for s in self.starters],
            "features": {"history": self.history, "uploads": self.uploads,
                         "feedback": self.feedback, "auth": bool(self.password)},
            "authenticated": authenticated,
            "version": __version__,
            "max_upload_mb": self.max_upload_mb if self.uploads else None,
        }

    # ------------------------------------------------------------ turns
    async def _messages(self, thread_id: str) -> list[dict[str, Any]]:
        return await self.store.get_messages(thread_id)

    async def _run_handler(self, turn: Turn, fn: Handler, *args: Any) -> None:
        chat: Chat = args[-1]
        try:
            async for item in iterate(fn, *args):
                turn.add(item)
            await turn.end_message("done")
        except asyncio.CancelledError:
            await asyncio.shield(turn.end_message("cancelled"))
            raise
        except Exception as exc:  # never leak tracebacks to the client
            log.exception("dyui: handler %s failed", getattr(fn, "__name__", fn))
            turn.emit("error", {"message": f"{type(exc).__name__}: something went wrong while replying.",
                                "message_id": turn.message["id"] if turn.message else None})
            await turn.end_message("error")
        finally:
            await chat._save_session()

    def _chat(self, turn: Turn, thread: dict[str, Any], messages: list[dict[str, Any]]) -> Chat:
        return Chat(self, thread, turn, messages)

    async def start_thread(self, turn: Turn, user_id: str) -> dict[str, Any]:
        """Create a thread, emit ``thread``, and run ``on_chat_start``."""
        thread = await self.store.create_thread(user_id)
        turn.thread = thread
        turn.emit("thread", _summary(thread))
        if self._on_chat_start is not None:
            chat = self._chat(turn, thread, [])
            await self._run_handler(turn, self._on_chat_start, chat)
        return thread

    async def handle_chat(self, turn: Turn, user_id: str, req: dict[str, Any]) -> None:
        """Run one ``POST /api/chat`` request (new message, regenerate or edit)."""
        thread_id = req.get("thread_id")
        if thread_id:
            thread = await self.store.get_thread(thread_id)
            if thread is None or thread.get("user_id") != user_id:
                turn.emit("error", {"message": "Conversation not found."})
                return
            turn.thread = thread
        else:
            thread = await self.start_thread(turn, user_id)

        messages = await self._messages(thread["id"])
        user_msg: Optional[dict[str, Any]] = None
        if req.get("regenerate"):
            users = [m for m in messages if m["role"] == "user"]
            if not users:
                turn.emit("error", {"message": "Nothing to regenerate."})
                return
            user_msg = users[-1]
            await self.store.delete_messages_after(thread["id"], user_msg["id"])
        elif req.get("edit"):
            edit = req["edit"]
            user_msg = await self.store.get_message(thread["id"], edit.get("message_id", ""))
            if user_msg is None or user_msg["role"] != "user":
                turn.emit("error", {"message": "Message not found."})
                return
            user_msg["parts"] = [p for p in user_msg["parts"] if p["type"] == "file"] + [{"type": "text", "text": str(edit.get("text", ""))}]
            user_msg.pop("meta", None)
            await self.store.delete_messages_after(thread["id"], user_msg["id"])
            await self.store.put_message(thread["id"], user_msg)
            turn.emit("user_message", user_msg)
        elif req.get("message") is not None:
            m = req["message"] or {}
            files = []
            for fid in m.get("files") or []:
                rec = await self.store.get_file(fid)
                if rec and rec.get("user_id") == user_id:
                    files.append(File.from_record(rec))
            parts: list[dict[str, Any]] = [{"type": "file", "file": f.ref()} for f in files]
            parts.append({"type": "text", "text": str(m.get("text", ""))})
            user_msg = {"id": _mid(), "role": "user", "created_at": now_ms(), "parts": parts, "status": "done"}
            await self.store.put_message(thread["id"], user_msg)
            turn.emit("user_message", user_msg)
        else:
            return  # e.g. a bare "create thread" request
        await self._reply_to(turn, thread, user_msg)

    async def _reply_to(self, turn: Turn, thread: dict[str, Any], user_msg: dict[str, Any]) -> None:
        if self._on_message is None:
            turn.emit("error", {"message": "This app has no @app.on_message handler yet."})
            return
        messages = await self._messages(thread["id"])
        text = "".join(p.get("text", "") for p in user_msg["parts"] if p["type"] == "text")
        files = []
        for p in user_msg["parts"]:
            if p["type"] == "file":
                rec = await self.store.get_file(p["file"]["id"])
                if rec:
                    files.append(File.from_record(rec))
        action = None
        meta = user_msg.get("meta") or {}
        if meta.get("action"):
            a = meta["action"]
            action = Action(name=a.get("name", ""), data=a.get("data") or {}, values=a.get("values") or {},
                            label=a.get("label", ""), message_id=a.get("message_id", ""),
                            component_id=a.get("component_id", ""))
            text = meta.get("llm_text", text)
        msg = Message(id=user_msg["id"], text=text, files=files, action=action)
        chat = self._chat(turn, thread, messages)
        await self._run_handler(turn, self._on_message, msg, chat)
        await self._auto_title(turn, thread, text if not action else action.label or text)

    async def _auto_title(self, turn: Turn, thread: dict[str, Any], text: str) -> None:
        fresh = await self.store.get_thread(thread["id"])
        if fresh is None:
            return
        if fresh.get("title_locked") or (fresh.get("title") and fresh["title"] != DEFAULT_TITLE):
            await self.store.update_thread(thread["id"], updated_at=now_ms())
            return
        words = " ".join(text.split()[:6]).strip(" .,:;!?")
        title = (words[:60] or "New chat")
        if len(text.split()) > 6:
            title += "…"
        await self.store.update_thread(thread["id"], title=title, updated_at=now_ms())
        turn.emit("title", {"thread_id": thread["id"], "title": title})

    async def check_action(self, user_id: str, req: dict[str, Any]) -> tuple[int, str, Any]:
        """Verify an action request without side effects.

        Returns ``(status, error, data)``: ``status`` is 0 when the action is valid
        (``data`` is then the server-side static data to use), else an HTTP status.
        """
        from .chat import find_node, is_forged, trusted_action_data

        thread = await self.store.get_thread(str(req.get("thread_id") or ""))
        if thread is None or thread.get("user_id") != user_id:
            return 404, "Conversation not found.", None
        component_id = str(req.get("component_id") or "")
        name = str(req.get("action") or "")
        pending = self._pending.get((thread["id"], component_id))
        if pending is not None:
            live = pending[1].message
            node = find_node(live["parts"], component_id) if live else None
        else:
            stored = await self.store.get_message(thread["id"], str(req.get("message_id") or ""))
            node = find_node(stored["parts"], component_id) if stored and stored.get("role") == "assistant" else None
        if node is None:
            return 400, "Unknown action.", None
        data = trusted_action_data(node, name, req.get("data"))
        if is_forged(data):
            return 400, "Unknown action.", None
        if (node.get("props") or {}).get("__resolved__") is not None:
            return 409, "This has already been answered.", None
        return 0, "", data

    def claim_action(self, req: dict[str, Any]) -> Optional[tuple[str, str]]:
        """Claim a component for one action request (synchronous: call right after
        :meth:`check_action`, with no ``await`` in between).

        Returns the claim key, or ``None`` if another request already holds it (a
        concurrent double-click). Released by :meth:`handle_action` once the
        resolution is recorded; stale claims expire after ``_CLAIM_TTL_S``.
        """
        import time

        key = (str(req.get("thread_id") or ""), str(req.get("component_id") or ""))
        now = time.monotonic()
        held = self._claims.get(key)
        if held is not None and now - held < _CLAIM_TTL_S:
            return None
        if len(self._claims) > 10_000:  # bound memory; drop expired claims
            self._claims = {k: t for k, t in self._claims.items() if now - t < _CLAIM_TTL_S}
        self._claims[key] = now
        return key

    def _release_claim(self, claim: Optional[tuple[str, str]]) -> None:
        if claim is not None:
            self._claims.pop(claim, None)

    async def handle_action(self, turn: Turn, user_id: str, req: dict[str, Any], *,
                            claim: Optional[tuple[str, str]] = None) -> Optional[str]:
        """Run one ``POST /api/action`` request. Returns an error string for 4xx."""
        try:
            problem = await self._handle_action(turn, user_id, req, claim)
        finally:
            self._release_claim(claim)
        if problem:
            turn.emit("error", {"message": problem})
        return problem

    async def _handle_action(self, turn: Turn, user_id: str, req: dict[str, Any],
                             claim: Optional[tuple[str, str]]) -> Optional[str]:
        from .chat import find_node, top_level_node

        status, problem, data = await self.check_action(user_id, req)
        if status:
            return problem
        thread = await self.store.get_thread(str(req.get("thread_id") or ""))
        turn.thread = thread
        message_id, component_id = str(req.get("message_id") or ""), str(req.get("component_id") or "")
        name = str(req.get("action") or "")
        label = str(req.get("label") or name)[:200]
        values = req.get("values") if isinstance(req.get("values"), dict) else {}
        resolved = {"label": label, "values": values}
        action = Action(name=name, data=data, values=values, label=label,
                        message_id=message_id, component_id=component_id)

        pending = self._pending.get((thread["id"], component_id))
        if pending is not None:
            fut, live_turn = pending
            if fut.done():  # lost a race with another request for the same ask()
                return "This has already been answered."
            live_turn.resolve(component_id, resolved)
            fut.set_result(action)
            return None

        stored = await self.store.get_message(thread["id"], message_id)
        node = find_node(stored["parts"], component_id)
        if (node.get("props") or {}).get("__resolved__") is not None:
            return "This has already been answered."
        node.setdefault("props", {})["__resolved__"] = resolved
        await self.store.put_message(thread["id"], stored)
        self._release_claim(claim)  # resolution is persisted: the 409 check now covers it
        turn.emit("ui", {"message_id": message_id, "node": top_level_node(stored["parts"], component_id)})

        messages = await self._messages(thread["id"])
        handler = self._actions.get(name)
        if handler is not None:
            chat = self._chat(turn, thread, messages)
            await self._run_handler(turn, handler, action, chat)
            return None
        # fallback: becomes a user turn for on_message
        user_msg = {
            "id": _mid(), "role": "user", "created_at": now_ms(), "status": "done",
            "parts": [{"type": "text", "text": label}],
            "action": {"name": name, "label": label},
            "meta": {"llm_text": action_text(name, data, values),
                     "action": {"name": name, "label": label, "data": data, "values": values,
                                "message_id": message_id, "component_id": component_id}},
        }
        await self.store.put_message(thread["id"], user_msg)
        turn.emit("user_message", _public_message(user_msg))
        await self._reply_to(turn, thread, user_msg)
        return None

    async def handle_feedback(self, user_id: str, req: dict[str, Any]) -> Optional[str]:
        thread = await self.store.get_thread(req.get("thread_id", ""))
        if thread is None or thread.get("user_id") != user_id:
            return "Conversation not found."
        msg = await self.store.get_message(thread["id"], str(req.get("message_id") or ""))
        if msg is None or msg.get("role") != "assistant":
            return "Message not found."
        try:
            value = int(req.get("value") or 0)
        except (TypeError, ValueError):
            value = 0
        msg["feedback"] = value if value in (-1, 0, 1) else 0
        comment = req.get("comment")
        comment = str(comment)[:2000] if comment is not None else None
        await self.store.put_message(thread["id"], msg)
        if self._on_feedback is not None:
            q: asyncio.Queue = asyncio.Queue()
            turn = Turn(self, thread, q)
            chat = self._chat(turn, thread, await self._messages(thread["id"]))
            fb = Feedback(message_id=msg["id"], value=msg["feedback"], comment=comment)
            sent = False
            try:
                async for item in iterate(self._on_feedback, fb, chat):
                    sent = sent or item is not None
            except Exception:  # a buggy feedback handler must not turn the click into a 500
                log.exception("dyui: on_feedback handler failed")
            finally:
                await chat._save_session()
            if sent or turn.message is not None:
                turn.forget()
                log.warning("dyui: @app.on_feedback can't send messages (there is no reply stream); "
                            "yielded items / chat.send() calls were ignored.")
        return None

    # ------------------------------------------------------------ ASGI
    def asgi(self) -> Any:
        """The underlying FastAPI application (built lazily)."""
        if self._asgi is None:
            from .server import create_server

            self._asgi = create_server(self)
        return self._asgi

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        await self.asgi()(scope, receive, send)


def _register_caller_dir() -> None:
    """Let ``ui.Html(template=...)`` find templates next to the app's own file."""
    import sys

    from .html import register_template_root

    try:
        caller = sys._getframe(2).f_globals.get("__file__")
    except (AttributeError, ValueError):  # pragma: no cover - exotic interpreters
        return
    if caller:
        register_template_root(Path(caller).resolve().parent)


def _mid() -> str:
    from .ui.base import new_id

    return new_id("m")


def _summary(thread: dict[str, Any]) -> dict[str, Any]:
    return {k: thread[k] for k in ("id", "title", "created_at", "updated_at")}


def _public_message(msg: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in msg.items() if k != "meta"}
