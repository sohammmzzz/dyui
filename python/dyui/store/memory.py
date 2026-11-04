"""In-memory store (``App(persist=False)``): fast, process-local, not persisted."""
from __future__ import annotations

import copy
import secrets
from typing import Any, Optional

from .base import DEFAULT_TITLE, now_ms

__all__ = ["MemoryStore"]


class MemoryStore:
    """A :class:`~dyui.store.Store` that keeps everything in process memory.

    Records are deep-copied on the way in and out, so callers can't mutate
    stored state by accident.
    """

    def __init__(self) -> None:
        self._threads: dict[str, dict[str, Any]] = {}
        self._messages: dict[str, list[dict[str, Any]]] = {}
        self._files: dict[str, dict[str, Any]] = {}

    async def create_thread(self, user_id: str, *, title: str = DEFAULT_TITLE) -> dict[str, Any]:
        ts = now_ms()
        thread = {
            "id": f"t_{secrets.token_hex(8)}",
            "user_id": user_id,
            "title": title,
            "title_locked": False,
            "session": {},
            "created_at": ts,
            "updated_at": ts,
        }
        self._threads[thread["id"]] = thread
        self._messages[thread["id"]] = []
        return copy.deepcopy(thread)

    async def get_thread(self, thread_id: str) -> Optional[dict[str, Any]]:
        thread = self._threads.get(thread_id)
        return copy.deepcopy(thread) if thread else None

    async def list_threads(self, user_id: str, *, limit: int = 200) -> list[dict[str, Any]]:
        rows = [t for t in self._threads.values() if t["user_id"] == user_id]
        rows.sort(key=lambda t: (t["updated_at"], t["created_at"]), reverse=True)
        return copy.deepcopy(rows[:limit])

    async def update_thread(self, thread_id: str, **fields: Any) -> Optional[dict[str, Any]]:
        thread = self._threads.get(thread_id)
        if thread is None:
            return None
        for key in ("title", "title_locked", "session", "updated_at"):
            if key in fields and fields[key] is not None:
                thread[key] = copy.deepcopy(fields[key])
        return copy.deepcopy(thread)

    async def delete_thread(self, thread_id: str) -> bool:
        self._messages.pop(thread_id, None)
        return self._threads.pop(thread_id, None) is not None

    async def get_messages(self, thread_id: str) -> list[dict[str, Any]]:
        return copy.deepcopy(self._messages.get(thread_id, []))

    async def get_message(self, thread_id: str, message_id: str) -> Optional[dict[str, Any]]:
        for msg in self._messages.get(thread_id, []):
            if msg["id"] == message_id:
                return copy.deepcopy(msg)
        return None

    async def put_message(self, thread_id: str, message: dict[str, Any]) -> None:
        msgs = self._messages.setdefault(thread_id, [])
        record = copy.deepcopy(message)
        for i, msg in enumerate(msgs):
            if msg["id"] == record["id"]:
                msgs[i] = record
                return
        msgs.append(record)

    async def delete_messages_after(self, thread_id: str, message_id: str, *, inclusive: bool = False) -> int:
        msgs = self._messages.get(thread_id, [])
        for i, msg in enumerate(msgs):
            if msg["id"] == message_id:
                cut = i if inclusive else i + 1
                removed = len(msgs) - cut
                del msgs[cut:]
                return removed
        return 0

    async def put_file(self, record: dict[str, Any]) -> None:
        self._files[record["id"]] = copy.deepcopy(record)

    async def get_file(self, file_id: str) -> Optional[dict[str, Any]]:
        rec = self._files.get(file_id)
        return copy.deepcopy(rec) if rec else None

    async def close(self) -> None:
        return None
